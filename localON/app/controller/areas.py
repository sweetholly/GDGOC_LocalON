from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    Area,
    AreaHourlySample,
    AreaHourlyTimeseries,
    AreaLiveMetric,
    AreaPopulationBaseline5m,
    CitydataLiveCommercialSummary,
    CitydataLivePopulation,
    CitydataSnapshot,
    CitydataWeatherCurrent,
)
from app.schema.areas import (
    AreaDetailOut,
    CommercialOut,
    CongestionOut,
    DemandOut,
    DemographicsOut,
    HourlyOut,
    RecommendationOut,
    WeatherOut,
)


def _demand_type(resident_rate: float | None, non_resident_rate: float | None) -> str:
    if resident_rate is not None and resident_rate > 60:
        return "거주 수요 중심"
    if non_resident_rate is not None and non_resident_rate > 60:
        return "관광/방문 수요 중심"
    return "혼합 수요"


async def get_area_detail(
    session: AsyncSession,
    area_id: int,
    stat_date: Optional[date] = None,
) -> AreaDetailOut | None:
    # ── 기본 정보 ──
    area_row = (
        await session.execute(select(Area).where(Area.area_id == area_id))
    ).scalar_one_or_none()
    if area_row is None:
        return None

    # ── live metrics ──
    metric = (
        await session.execute(
            select(AreaLiveMetric).where(AreaLiveMetric.area_id == area_id)
        )
    ).scalar_one_or_none()

    # ── 최신 snapshot_id ──
    latest_snap_id = (
        await session.execute(
            select(CitydataSnapshot.snapshot_id)
            .where(CitydataSnapshot.area_id == area_id)
            .order_by(CitydataSnapshot.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # ── 인구 / 상권 / 날씨 (최신 snapshot 기준) ──
    pop = commercial_snap = weather_snap = None
    if latest_snap_id is not None:
        pop = (
            await session.execute(
                select(CitydataLivePopulation).where(
                    CitydataLivePopulation.snapshot_id == latest_snap_id
                )
            )
        ).scalar_one_or_none()
        commercial_snap = (
            await session.execute(
                select(CitydataLiveCommercialSummary).where(
                    CitydataLiveCommercialSummary.snapshot_id == latest_snap_id
                )
            )
        ).scalar_one_or_none()
        weather_snap = (
            await session.execute(
                select(CitydataWeatherCurrent).where(
                    CitydataWeatherCurrent.snapshot_id == latest_snap_id
                )
            )
        ).scalar_one_or_none()

    # ── 시간대별 그래프 ──
    target_date = stat_date or date.today()
    hourly_rows = (
        await session.execute(
            select(AreaHourlyTimeseries)
            .where(
                AreaHourlyTimeseries.area_id == area_id,
                AreaHourlyTimeseries.stat_date == target_date,
            )
            .order_by(AreaHourlyTimeseries.hour)
        )
    ).scalars().all()
    hourly_latest_by_hour = {int(row.hour): row for row in hourly_rows}

    sample_rows = (
        await session.execute(
            select(AreaHourlySample)
            .where(
                AreaHourlySample.area_id == area_id,
                AreaHourlySample.stat_date == target_date,
            )
            .order_by(
                AreaHourlySample.hour,
                AreaHourlySample.sample_time,
                AreaHourlySample.sample_id,
            )
        )
    ).scalars().all()

    sample_latest_by_hour: dict[int, AreaHourlySample] = {}
    sample_stats_by_hour: dict[int, dict[str, float | int]] = {}
    for row in sample_rows:
        hour = int(row.hour)
        sample_latest_by_hour[hour] = row
        if row.actual_count is None:
            continue

        bucket = sample_stats_by_hour.get(hour)
        if bucket is None:
            sample_stats_by_hour[hour] = {
                "sum": float(row.actual_count),
                "count": 1,
                "min": int(row.actual_count),
                "max": int(row.actual_count),
            }
            continue

        bucket["sum"] = float(bucket["sum"]) + float(row.actual_count)
        bucket["count"] = int(bucket["count"]) + 1
        bucket["min"] = min(int(bucket["min"]), int(row.actual_count))
        bucket["max"] = max(int(bucket["max"]), int(row.actual_count))

    hourly: list[HourlyOut] = []
    for hour in range(24):
        sample_latest = sample_latest_by_hour.get(hour)
        ts_latest = hourly_latest_by_hour.get(hour)

        actual = (
            sample_latest.actual_count
            if sample_latest
            else (ts_latest.actual_count if ts_latest else None)
        )
        baseline = (
            sample_latest.baseline_count
            if sample_latest
            else (ts_latest.baseline_count if ts_latest else None)
        )
        level = (
            sample_latest.congestion_level
            if sample_latest
            else (ts_latest.congestion_level if ts_latest else None)
        )

        stats = sample_stats_by_hour.get(hour)
        if stats is not None and int(stats["count"]) > 0:
            actual_avg = round(float(stats["sum"]) / int(stats["count"]), 2)
            actual_min = int(stats["min"])
            actual_max = int(stats["max"])
        else:
            actual_avg = float(actual) if actual is not None else None
            actual_min = actual
            actual_max = actual

        hourly.append(
            HourlyOut(
                hour=hour,
                actual=actual,
                baseline=baseline,
                level=level,
                actual_avg=actual_avg,
                actual_min=actual_min,
                actual_max=actual_max,
            )
        )

    # ── 추천 방문 시간 (baseline_5m 기반, 오늘 요일 기준 최저 3개 시간대) ──
    today = date.today()
    day_type = "weekend" if today.weekday() >= 5 else "weekday"
    hour_col = func.floor(AreaPopulationBaseline5m.slot_5m / 12).label("hour")
    avg_col = func.avg(AreaPopulationBaseline5m.avg_ppltn_min).label("avg_min")
    rec_rows = (
        await session.execute(
            select(hour_col, avg_col)
            .where(
                AreaPopulationBaseline5m.area_id == area_id,
                AreaPopulationBaseline5m.day_type == day_type,
            )
            .group_by(hour_col)
            .order_by(avg_col)
            .limit(3)
        )
    ).all()
    recommendations = [
        RecommendationOut(
            time_range=f"{int(row.hour):02d}:00~{int(row.hour) + 1:02d}:00",
            expected_level="여유",
            avg_population=int(row.avg_min) if row.avg_min is not None else 0,
        )
        for row in rec_rows
    ]

    # ── 수요 분석 ──
    resident_rate = float(metric.resident_rate) if metric and metric.resident_rate is not None else None
    non_resident_rate = float(metric.non_resident_rate) if metric and metric.non_resident_rate is not None else None

    return AreaDetailOut(
        area_id=area_row.area_id,
        area_cd=area_row.area_cd,
        name=area_row.area_nm,
        eng_name=area_row.eng_nm,
        category=area_row.ui_category,
        lat=float(area_row.lat) if area_row.lat is not None else None,
        lng=float(area_row.lng) if area_row.lng is not None else None,
        congestion=CongestionOut(
            level=metric.congestion_level if metric else None,
            citydata_score=float(metric.citydata_score) if metric and metric.citydata_score is not None else None,
            sdot_score=float(metric.sdot_score) if metric and metric.sdot_score is not None else None,
            msg=metric.congestion_msg if metric else None,
            population_min=metric.population_min if metric else None,
            population_max=metric.population_max if metric else None,
            sdot_current=metric.sdot_current_count if metric else None,
            sdot_baseline=metric.sdot_baseline_count if metric else None,
            is_estimated=metric.is_estimated if metric else False,
            updated_at=metric.updated_at if metric else None,
        ),
        hourly=hourly,
        recommendations=recommendations,
        demand=DemandOut(
            type=_demand_type(resident_rate, non_resident_rate),
            resident_rate=resident_rate,
            non_resident_rate=non_resident_rate,
            demographics=DemographicsOut(
                male_rate=float(pop.male_ppltn_rate) if pop and pop.male_ppltn_rate is not None else None,
                female_rate=float(pop.female_ppltn_rate) if pop and pop.female_ppltn_rate is not None else None,
                age_0=float(pop.ppltn_rate_0) if pop and pop.ppltn_rate_0 is not None else None,
                age_10=float(pop.ppltn_rate_10) if pop and pop.ppltn_rate_10 is not None else None,
                age_20=float(pop.ppltn_rate_20) if pop and pop.ppltn_rate_20 is not None else None,
                age_30=float(pop.ppltn_rate_30) if pop and pop.ppltn_rate_30 is not None else None,
                age_40=float(pop.ppltn_rate_40) if pop and pop.ppltn_rate_40 is not None else None,
                age_50=float(pop.ppltn_rate_50) if pop and pop.ppltn_rate_50 is not None else None,
                age_60=float(pop.ppltn_rate_60) if pop and pop.ppltn_rate_60 is not None else None,
                age_70=float(pop.ppltn_rate_70) if pop and pop.ppltn_rate_70 is not None else None,
            ),
        ),
        commercial=CommercialOut(
            level=commercial_snap.area_cmrcl_lvl if commercial_snap else (metric.commercial_level if metric else None),
            payment_cnt=commercial_snap.area_sh_payment_cnt if commercial_snap else (metric.payment_cnt if metric else None),
            payment_amt_min=commercial_snap.area_sh_payment_amt_min if commercial_snap else (metric.payment_amt_min if metric else None),
            payment_amt_max=commercial_snap.area_sh_payment_amt_max if commercial_snap else (metric.payment_amt_max if metric else None),
        ),
        weather=WeatherOut(
            temp=float(weather_snap.temp) if weather_snap and weather_snap.temp is not None else None,
            sensible_temp=float(weather_snap.sensible_temp) if weather_snap and weather_snap.sensible_temp is not None else None,
            humidity=weather_snap.humidity if weather_snap else None,
            wind_spd=float(weather_snap.wind_spd) if weather_snap and weather_snap.wind_spd is not None else None,
            pm25=float(weather_snap.pm25) if weather_snap and weather_snap.pm25 is not None else None,
            pm25_index=weather_snap.pm25_index if weather_snap else None,
            pm10=float(weather_snap.pm10) if weather_snap and weather_snap.pm10 is not None else None,
            pm10_index=weather_snap.pm10_index if weather_snap else None,
        ),
    )
