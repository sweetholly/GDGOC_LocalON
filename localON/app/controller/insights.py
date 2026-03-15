from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import (
    Area,
    AreaHourlyTimeseries,
    AreaLiveMetric,
    CitydataCulturalEvent,
    CitydataSnapshot,
    CitydataWeatherForecast,
    ReviewReliabilitySnapshot,
    ReviewSnapshot,
)
from app.schema.insights import (
    EventSignalOut,
    PopulationForecastOut,
    ReviewReliabilityIn,
    ReviewReliabilityOut,
    SuspiciousReviewOut,
    VisitInsightOut,
    VisitTimeSlotOut,
)

logger = logging.getLogger(__name__)

_DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_HOT_LEVEL_HINTS = (
    "busy",
    "crowded",
    "congested",
    "\ubd90\ube54",
    "\ud63c\uc7a1",
)
_AD_PATTERNS = tuple(
    re.compile(p, flags=re.IGNORECASE)
    for p in (
        r"\uad11\uace0",
        r"\ud611\ucc2c",
        r"\uccb4\ud5d8\ub2e8",
        r"\uc6d0\uace0\ub8cc",
        r"\uc81c\uacf5\ubc1b\uc544",
        r"\ud30c\ud2b8\ub108\uc2a4",
        r"sponsored",
        r"paid partnership",
        r"ad\b",
    )
)
_AI_STYLE_PATTERNS = tuple(
    re.compile(p, flags=re.IGNORECASE)
    for p in (
        r"\uc804\ubc18\uc801\uc73c\ub85c",
        r"\uc885\ud569\uc801\uc73c\ub85c",
        r"\uc694\uc57d\ud558\uc790\uba74",
        r"\uacb0\ub860\uc801\uc73c\ub85c",
        r"\ud55c\ud3b8",
        r"overall",
        r"in conclusion",
    )
)


def build_place_key(place_id: str | None, place_name: str, source: str | None = None) -> str:
    if place_id:
        normalized_id = place_id.strip()
        if source and ":" not in normalized_id:
            return f"{source}:{normalized_id}"
        return normalized_id
    return re.sub(r"\s+", "_", place_name.strip().lower())


def _normalize(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.5
    return (value - min_value) / (max_value - min_value)


def _is_hot_level(level: str | None) -> bool:
    if not level:
        return False
    lowered = level.lower()
    return any(token in lowered for token in _HOT_LEVEL_HINTS)


def _safe_population(row: AreaHourlyTimeseries) -> int | None:
    if row.actual_count is not None:
        return int(row.actual_count)
    if row.citydata_ppltn_min is not None and row.citydata_ppltn_max is not None:
        return int((int(row.citydata_ppltn_min) + int(row.citydata_ppltn_max)) / 2)
    if row.baseline_count is not None:
        return int(row.baseline_count)
    return None


def _truncate_preview(text: str, size: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= size:
        return compact
    return f"{compact[:size].rstrip()}..."


def _rating_extreme(item_rating: float | None) -> bool:
    if item_rating is None:
        return False
    return item_rating >= 4.8 or item_rating <= 1.2


def _review_ai_suspect(text: str, normalized: str) -> bool:
    tokens = [token for token in re.split(r"\W+", normalized) if token]
    if not tokens:
        return False

    unique_ratio = len(set(tokens)) / max(len(tokens), 1)
    repeated_ratio = Counter(tokens).most_common(1)[0][1] / max(len(tokens), 1)
    style_hit = any(pattern.search(text) for pattern in _AI_STYLE_PATTERNS)
    too_uniform = unique_ratio < 0.45 and len(tokens) >= 25
    too_repetitive = repeated_ratio > 0.20 and len(tokens) >= 20
    too_long = len(text) >= 260 and text.count(",") >= 4
    return style_hit or too_uniform or too_repetitive or too_long


def _weather_factor(row: CitydataWeatherForecast) -> tuple[float, str | None]:
    rain_chance = int(row.rain_chance) if row.rain_chance is not None else None
    precipitation = float(row.precipitation) if row.precipitation is not None else 0.0
    sky = (row.sky_stts or "").lower()

    if rain_chance is not None and rain_chance >= 60:
        return -0.18, "high_rain_chance"
    if precipitation >= 5.0:
        return -0.15, "heavy_precipitation"
    if rain_chance is not None and rain_chance <= 20 and ("\ub9d1" in sky or "clear" in sky):
        return 0.08, "clear_weather"
    return 0.0, None


def _grade_from_trust(trust: float) -> str:
    if trust >= 80.0:
        return "high"
    if trust >= 60.0:
        return "medium"
    return "low"


async def get_visit_insights(
    session: AsyncSession,
    area_id: int,
    lookback_days: int = 28,
) -> VisitInsightOut | None:
    area = (await session.execute(select(Area).where(Area.area_id == area_id))).scalar_one_or_none()
    if area is None:
        return None

    today = date.today()
    start_date = today - timedelta(days=max(lookback_days - 1, 1))
    timeseries = (
        await session.execute(
            select(AreaHourlyTimeseries)
            .where(
                AreaHourlyTimeseries.area_id == area_id,
                AreaHourlyTimeseries.stat_date >= start_date,
                AreaHourlyTimeseries.stat_date <= today,
            )
            .order_by(AreaHourlyTimeseries.stat_date, AreaHourlyTimeseries.hour)
        )
    ).scalars().all()

    grouped: dict[tuple[int, int], dict[str, object]] = defaultdict(
        lambda: {"population": [], "ratio": [], "hot_hits": 0}
    )
    for row in timeseries:
        key = (row.stat_date.weekday(), int(row.hour))
        bucket = grouped[key]
        population = _safe_population(row)

        if population is not None:
            bucket["population"].append(population)
            if row.baseline_count and row.baseline_count > 0:
                bucket["ratio"].append(population / float(row.baseline_count))
        if _is_hot_level(row.congestion_level):
            bucket["hot_hits"] = int(bucket["hot_hits"]) + 1

    event_rows = (
        await session.execute(
            select(
                CitydataCulturalEvent.event_nm,
                CitydataCulturalEvent.event_period,
                CitydataCulturalEvent.event_place,
                func.count(CitydataCulturalEvent.id).label("mentions"),
            )
            .join(CitydataSnapshot, CitydataSnapshot.snapshot_id == CitydataCulturalEvent.snapshot_id)
            .where(
                CitydataSnapshot.area_id == area_id,
                CitydataSnapshot.fetched_at >= datetime.combine(start_date, datetime.min.time()),
            )
            .group_by(
                CitydataCulturalEvent.event_nm,
                CitydataCulturalEvent.event_period,
                CitydataCulturalEvent.event_place,
            )
            .order_by(func.count(CitydataCulturalEvent.id).desc())
            .limit(5)
        )
    ).all()
    event_signals = [
        EventSignalOut(
            name=row.event_nm or "Unknown Event",
            mention_count=int(row.mentions or 0),
            period=row.event_period,
            place=row.event_place,
        )
        for row in event_rows
    ]
    event_boost = min(0.20, len(event_signals) * 0.03)

    latest_snapshot_id = (
        await session.execute(
            select(CitydataSnapshot.snapshot_id)
            .where(CitydataSnapshot.area_id == area_id)
            .order_by(CitydataSnapshot.fetched_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    weather_map: dict[tuple[int, int], tuple[float, str | None]] = {}
    if latest_snapshot_id is not None:
        weather_rows = (
            await session.execute(
                select(CitydataWeatherForecast)
                .where(CitydataWeatherForecast.snapshot_id == latest_snapshot_id)
                .order_by(CitydataWeatherForecast.fcst_dt)
            )
        ).scalars().all()
        for row in weather_rows:
            if row.fcst_dt is not None:
                weather_map[(row.fcst_dt.weekday(), row.fcst_dt.hour)] = _weather_factor(row)

    slot_rows: list[dict[str, float | int | str | None]] = []
    population_values: list[float] = []
    ratio_values: list[float] = []

    for (dow, hour), bucket in grouped.items():
        populations = [int(v) for v in bucket["population"]]
        ratios = [float(v) for v in bucket["ratio"]]
        sample_count = len(populations)
        if sample_count == 0:
            continue

        avg_population = sum(populations) / sample_count
        population_values.append(avg_population)

        congestion_ratio = (sum(ratios) / len(ratios)) if ratios else 1.0
        if ratios:
            ratio_values.append(congestion_ratio)

        if sample_count > 1:
            variance = sum((value - avg_population) ** 2 for value in populations) / sample_count
            std_dev = math.sqrt(variance)
            cv = std_dev / max(avg_population, 1.0)
        else:
            cv = 0.0
        stability = max(0.0, 1.0 - min(cv / 1.5, 1.0))

        hot_rate = int(bucket["hot_hits"]) / sample_count
        weather_bonus = weather_map.get((dow, hour), (0.0, None))[0]

        slot_rows.append(
            {
                "day_of_week": dow,
                "hour": hour,
                "avg_population": avg_population,
                "congestion_ratio": congestion_ratio,
                "sample_count": sample_count,
                "hot_rate": hot_rate,
                "stability": stability,
                "weather_bonus": weather_bonus,
            }
        )

    if not slot_rows:
        return VisitInsightOut(
            area_id=area.area_id,
            area_name=area.area_nm,
            lookback_days=lookback_days,
            generated_at=datetime.now(),
            hottest_slots=[],
            recommended_slots=[],
            next_hours_forecast=[],
            event_signals=event_signals,
        )

    pop_min = min(population_values) if population_values else 0.0
    pop_max = max(population_values) if population_values else 1.0
    ratio_min = min(ratio_values) if ratio_values else 0.5
    ratio_max = max(ratio_values) if ratio_values else 1.5

    for slot in slot_rows:
        pop_norm = _normalize(float(slot["avg_population"]), pop_min, pop_max)
        ratio_norm = _normalize(float(slot["congestion_ratio"]), ratio_min, ratio_max)
        hot_rate = float(slot["hot_rate"])
        stability = float(slot["stability"])
        weather_bonus = float(slot["weather_bonus"])

        hot_score = (
            0.55 * pop_norm
            + 0.25 * ratio_norm
            + 0.15 * hot_rate
            + 0.05 * event_boost
            + 0.05 * max(weather_bonus, 0.0)
        )
        visit_score = (
            0.35 * (1.0 - pop_norm)
            + 0.20 * (1.0 - min(abs(ratio_norm - 0.4), 1.0))
            + 0.25 * stability
            + 0.15 * (1.0 - hot_rate)
            + 0.05 * max(weather_bonus, 0.0)
        )
        confidence = min(0.95, 0.35 + min(int(slot["sample_count"]), 40) / 80.0)

        if hot_rate >= 0.6:
            primary_cause = "historical_congestion_pattern"
        elif event_boost >= 0.1:
            primary_cause = "event_driven_demand"
        else:
            primary_cause = "regular_time_pattern"

        slot["hot_score"] = max(0.0, min(1.0, hot_score))
        slot["visit_score"] = max(0.0, min(1.0, visit_score))
        slot["confidence"] = confidence
        slot["primary_cause"] = primary_cause

    def _to_out(slot: dict[str, float | int | str | None]) -> VisitTimeSlotOut:
        hour = int(slot["hour"])
        day_of_week = int(slot["day_of_week"])
        return VisitTimeSlotOut(
            day_of_week=day_of_week,
            day_label=_DAY_LABELS[day_of_week],
            hour=hour,
            time_range=f"{hour:02d}:00~{(hour + 1) % 24:02d}:00",
            avg_population=int(float(slot["avg_population"])),
            congestion_ratio=round(float(slot["congestion_ratio"]), 3),
            hot_score=round(float(slot["hot_score"]), 4),
            visit_score=round(float(slot["visit_score"]), 4),
            confidence=round(float(slot["confidence"]), 4),
            primary_cause=str(slot["primary_cause"]) if slot["primary_cause"] else None,
        )

    hottest_slots = [
        _to_out(row)
        for row in sorted(slot_rows, key=lambda row: float(row["hot_score"]), reverse=True)[:5]
    ]
    recommended_slots = [
        _to_out(row)
        for row in sorted(slot_rows, key=lambda row: float(row["visit_score"]), reverse=True)[:5]
    ]

    slot_map = {(int(row["day_of_week"]), int(row["hour"])): row for row in slot_rows}
    live_metric = (
        await session.execute(select(AreaLiveMetric).where(AreaLiveMetric.area_id == area_id))
    ).scalar_one_or_none()
    live_mid = None
    if live_metric and live_metric.population_min is not None and live_metric.population_max is not None:
        live_mid = int((int(live_metric.population_min) + int(live_metric.population_max)) / 2)

    now = datetime.now()
    forecasts: list[PopulationForecastOut] = []
    for offset in range(6):
        target = now + timedelta(hours=offset)
        key = (target.weekday(), target.hour)
        slot = slot_map.get(key)
        weather_adj, weather_reason = weather_map.get(key, (0.0, None))
        cause_factors: list[str] = []

        if slot is not None:
            base_population = float(slot["avg_population"])
            confidence = min(0.95, float(slot["confidence"]) * 0.92)
            if float(slot["hot_score"]) >= 0.75:
                cause_factors.append("historical_peak_hour")
        else:
            base_population = float(live_mid) if live_mid is not None else 0.0
            confidence = 0.42 if base_population > 0 else 0.30
            cause_factors.append("limited_history")

        if event_boost > 0.0:
            cause_factors.append("event_signal")
        if weather_reason:
            cause_factors.append(weather_reason)

        if base_population <= 0:
            expected_population = None
        else:
            adjusted = base_population * (1.0 + weather_adj + (event_boost * 0.5))
            expected_population = max(0, int(round(adjusted)))

        forecasts.append(
            PopulationForecastOut(
                at=target.replace(minute=0, second=0, microsecond=0),
                expected_population=expected_population,
                confidence=round(confidence, 4),
                cause_factors=cause_factors,
            )
        )

    return VisitInsightOut(
        area_id=area.area_id,
        area_name=area.area_nm,
        lookback_days=lookback_days,
        generated_at=datetime.now(),
        hottest_slots=hottest_slots,
        recommended_slots=recommended_slots,
        next_hours_forecast=forecasts,
        event_signals=event_signals,
    )


async def analyze_review_reliability(
    session: AsyncSession,
    payload: ReviewReliabilityIn,
) -> ReviewReliabilityOut:
    place_key = build_place_key(payload.place_id, payload.place_name, payload.source)
    suspicious_reviews: list[SuspiciousReviewOut] = []

    total_reviews = len(payload.reviews)
    ad_hits = 0
    ai_hits = 0
    duplicate_ratio = 0.0
    ad_ratio = 0.0
    ai_ratio = 0.0
    extreme_ratio = 0.0

    if total_reviews > 0:
        normalized_texts: list[str] = []
        extreme_hits = 0

        for review in payload.reviews:
            text = review.text.strip()
            normalized = re.sub(r"\s+", " ", text).lower()
            normalized_texts.append(normalized)

            ad_suspected = any(pattern.search(text) for pattern in _AD_PATTERNS)
            ai_suspected = _review_ai_suspect(text, normalized)

            if ad_suspected:
                ad_hits += 1
                suspicious_reviews.append(
                    SuspiciousReviewOut(reason="ad_suspected", preview=_truncate_preview(text))
                )
            if ai_suspected:
                ai_hits += 1
                suspicious_reviews.append(
                    SuspiciousReviewOut(reason="ai_generated_suspected", preview=_truncate_preview(text))
                )

            if _rating_extreme(review.rating) and len(text) <= 24:
                extreme_hits += 1

        text_counts = Counter(normalized_texts)
        duplicate_count = sum(count - 1 for count in text_counts.values() if count > 1)

        duplicate_ratio = duplicate_count / total_reviews
        ad_ratio = ad_hits / total_reviews
        ai_ratio = ai_hits / total_reviews
        extreme_ratio = extreme_hits / total_reviews
    elif payload.area_id is not None:
        latest = (
            await session.execute(
                select(ReviewSnapshot)
                .where(ReviewSnapshot.area_id == payload.area_id)
                .order_by(ReviewSnapshot.crawled_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest and latest.review_count:
            confidence_bonus = min(0.15, int(latest.review_count) / 500.0)
            ad_ratio = max(0.0, 0.15 - confidence_bonus)
            ai_ratio = max(0.0, 0.10 - confidence_bonus)

    penalty = (
        0.45 * ad_ratio
        + 0.30 * ai_ratio
        + 0.15 * duplicate_ratio
        + 0.10 * extreme_ratio
    )
    trust_score = max(0.0, min(100.0, round((1.0 - penalty) * 100.0, 2)))
    grade = _grade_from_trust(trust_score)

    out = ReviewReliabilityOut(
        place_key=place_key,
        place_name=payload.place_name,
        total_reviews=total_reviews,
        ad_suspect_ratio=round(ad_ratio, 4),
        ai_suspect_ratio=round(ai_ratio, 4),
        duplicate_ratio=round(duplicate_ratio, 4),
        trust_score=trust_score,
        grade=grade,
        suspicious_reviews=suspicious_reviews[:8],
        analyzed_at=datetime.now(),
        model_version="heuristic-v1",
    )

    snapshot = ReviewReliabilitySnapshot(
        place_key=place_key,
        place_name=payload.place_name,
        area_id=payload.area_id,
        source=payload.source,
        total_reviews=out.total_reviews,
        ad_suspect_ratio=out.ad_suspect_ratio,
        ai_suspect_ratio=out.ai_suspect_ratio,
        duplicate_ratio=out.duplicate_ratio,
        trust_score=out.trust_score,
        model_version=out.model_version,
        signal_summary_json={
            "grade": out.grade,
            "suspicious_count": len(out.suspicious_reviews),
        },
    )
    session.add(snapshot)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.warning("Failed to persist review reliability snapshot: %s", exc)

    return out
