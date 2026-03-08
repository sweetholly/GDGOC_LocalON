from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    Area,
    AreaLiveMetric,
    TrendHotPlace,
    TrendRisingRegion,
)
from app.schema.mainpage import AreaSummaryOut, HotPlaceOut, MainOut, RisingOut, TrendsOut


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return int(2 * R * math.asin(math.sqrt(a)))


async def get_main(
    session: AsyncSession,
    lat: Optional[float],
    lng: Optional[float],
) -> MainOut:
    # ── Areas + live metrics ──
    stmt = (
        select(Area, AreaLiveMetric)
        .outerjoin(AreaLiveMetric, Area.area_id == AreaLiveMetric.area_id)
        .where(Area.is_active == True)
    )
    rows = (await session.execute(stmt)).all()

    use_distance = lat is not None and lng is not None
    area_list: list[AreaSummaryOut] = []
    for area, metric in rows:
        distance = None
        if use_distance and area.lat is not None and area.lng is not None:
            distance = _haversine_m(lat, lng, float(area.lat), float(area.lng))
        area_list.append(
            AreaSummaryOut(
                area_id=area.area_id,
                area_cd=area.area_cd,
                name=area.area_nm,
                category=area.ui_category,
                lat=float(area.lat) if area.lat is not None else None,
                lng=float(area.lng) if area.lng is not None else None,
                congestion_level=metric.congestion_level if metric else None,
                congestion_score=float(metric.congestion_score) if metric and metric.congestion_score is not None else None,
                population_min=metric.population_min if metric else None,
                population_max=metric.population_max if metric else None,
                weather_temp=float(metric.weather_temp) if metric and metric.weather_temp is not None else None,
                air_idx=metric.air_idx if metric else None,
                distance_m=distance,
                updated_at=metric.updated_at if metric else None,
            )
        )

    if use_distance:
        area_list.sort(key=lambda a: (a.distance_m is None, a.distance_m or 0))
    else:
        area_list.sort(key=lambda a: a.area_cd)

    # ── Trend hot places (최신 snapshot_time 기준 top 10) ──
    latest_hp_time = select(func.max(TrendHotPlace.snapshot_time)).scalar_subquery()
    hp_stmt = (
        select(TrendHotPlace, Area)
        .join(Area, TrendHotPlace.area_id == Area.area_id)
        .where(TrendHotPlace.snapshot_time == latest_hp_time)
        .order_by(TrendHotPlace.rank)
        .limit(10)
    )
    hp_rows = (await session.execute(hp_stmt)).all()
    hot_places = [
        HotPlaceOut(
            rank=hp.rank,
            area_id=hp.area_id,
            name=area.area_nm,
            congestion_level=hp.congestion_level,
            congestion_score=float(hp.congestion_score) if hp.congestion_score is not None else None,
            rank_change=hp.rank_change,
        )
        for hp, area in hp_rows
    ]

    # ── Trend rising regions (최신 snapshot_time 기준 top 5) ──
    latest_rr_time = select(func.max(TrendRisingRegion.snapshot_time)).scalar_subquery()
    rr_stmt = (
        select(TrendRisingRegion, Area)
        .outerjoin(Area, TrendRisingRegion.mapped_area_id == Area.area_id)
        .where(TrendRisingRegion.snapshot_time == latest_rr_time)
        .order_by(TrendRisingRegion.change_pct.desc())
        .limit(5)
    )
    rr_rows = (await session.execute(rr_stmt)).all()
    rising = [
        RisingOut(
            area_id=rr.mapped_area_id,
            name=area.area_nm if area else rr.label,
            change_pct=float(rr.change_pct) if rr.change_pct is not None else None,
            change_label=rr.change_label,
        )
        for rr, area in rr_rows
    ]

    return MainOut(
        areas=area_list,
        trends=TrendsOut(hot_places=hot_places, rising=rising),
    )
