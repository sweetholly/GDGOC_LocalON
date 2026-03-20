from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
from typing import Literal
from urllib.parse import quote

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.clients.google_places import GooglePlacesClient
from app.collector.clients.kakao_local import KakaoLocalClient
from app.controller.insights import analyze_review_reliability, build_place_key
from app.domain import (
    Area,
    AreaAlias,
    AreaLiveMetric,
    ReviewReliabilitySnapshot,
    SearchQueryLog,
)
from app.schema.insights import ReviewItemIn, ReviewReliabilityIn
from app.schema.search import (
    ExternalPlaceReviewReliabilityIn,
    ExternalPlaceReviewReliabilityOut,
    SearchOut,
    SearchResultOut,
)

logger = logging.getLogger(__name__)


def _trust_grade(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80.0:
        return "high"
    if score >= 60.0:
        return "medium"
    return "low"


def _normalize_place_id(place_id: str | None) -> str | None:
    if place_id is None:
        return None
    normalized = str(place_id).strip()
    return normalized or None


def _extract_kakao_place_id(place_id: str | None) -> str | None:
    normalized = _normalize_place_id(place_id)
    if not normalized:
        return None
    if normalized.startswith("kakao:"):
        suffix = normalized.split(":", 1)[1].strip()
        return suffix or None
    if normalized.startswith("external:"):
        return None
    return normalized


def _build_kakao_place_url(*, place_id: str | None, place_name: str, address: str | None) -> str | None:
    kakao_place_id = _extract_kakao_place_id(place_id)
    if kakao_place_id:
        return f"https://place.map.kakao.com/{kakao_place_id}"

    query = " ".join(part.strip() for part in [place_name, address or ""] if part and part.strip())
    if not query:
        return None
    return f"https://map.kakao.com/?q={quote(query)}"


def _extract_external_review_count(doc: dict) -> int | None:
    # Some providers include coarse review-count signals in search payloads.
    for key in (
        "review_count",
        "reviews_count",
        "comment_count",
        "rating_count",
        "user_rating_count",
    ):
        raw = doc.get(key)
        if raw is None:
            continue
        try:
            value = int(str(raw).strip())
        except ValueError:
            continue
        if value >= 0:
            return value
    return None


def _snapshot_to_external_reliability_out(
    *,
    snapshot: ReviewReliabilitySnapshot,
    place_id: str | None,
    place_name: str,
    address: str | None,
    status: Literal["analyzed", "cached", "insufficient_data"],
) -> ExternalPlaceReviewReliabilityOut:
    trust_score = float(snapshot.trust_score) if snapshot.trust_score is not None else None
    return ExternalPlaceReviewReliabilityOut(
        place_id=place_id,
        place_key=snapshot.place_key,
        place_name=place_name,
        review_data_status=status,
        review_trust_score=trust_score,
        review_trust_grade=_trust_grade(trust_score),
        review_total_reviews=snapshot.total_reviews,
        review_model_version=snapshot.model_version,
        review_analyzed_at=snapshot.analyzed_at,
        kakao_place_url=_build_kakao_place_url(
            place_id=place_id,
            place_name=place_name,
            address=address,
        ),
    )


async def _load_latest_external_review_snapshot(
    session: AsyncSession,
    *,
    place_id: str | None,
    place_name: str,
    source: str,
) -> ReviewReliabilitySnapshot | None:
    candidate_keys: set[str] = set()
    normalized_place_id = _normalize_place_id(place_id)
    if normalized_place_id:
        candidate_keys.add(normalized_place_id)
        candidate_keys.add(f"{source}:{normalized_place_id}" if ":" not in normalized_place_id else normalized_place_id)
    candidate_keys.add(build_place_key(normalized_place_id, place_name, source=source))

    rows = (
        await session.execute(
            select(ReviewReliabilitySnapshot)
            .where(ReviewReliabilitySnapshot.place_key.in_(candidate_keys))
            .order_by(desc(ReviewReliabilitySnapshot.analyzed_at), desc(ReviewReliabilitySnapshot.id))
        )
    ).scalars().all()
    return rows[0] if rows else None


async def _load_external_review_snapshots(
    session: AsyncSession,
    external_docs: list[dict],
) -> dict[str, ReviewReliabilitySnapshot]:
    candidate_keys: set[str] = set()

    for doc in external_docs:
        place_name = str(doc.get("place_name") or "").strip()
        raw_place_id = doc.get("id")
        place_id = str(raw_place_id).strip() if raw_place_id is not None else None

        if place_id:
            candidate_keys.add(place_id)  # Backward-compatibility for old stored keys.
        if place_name:
            candidate_keys.add(build_place_key(place_id, place_name, source="kakao"))

    if not candidate_keys:
        return {}

    rows = (
        await session.execute(
            select(ReviewReliabilitySnapshot)
            .where(ReviewReliabilitySnapshot.place_key.in_(candidate_keys))
            .order_by(ReviewReliabilitySnapshot.analyzed_at.desc())
        )
    ).scalars().all()

    latest_by_key: dict[str, ReviewReliabilitySnapshot] = {}
    for row in rows:
        if row.place_key not in latest_by_key:
            latest_by_key[row.place_key] = row
    return latest_by_key


def _google_review_enrich_enabled() -> bool:
    raw = os.getenv("ENABLE_GOOGLE_REVIEW_ENRICH", "true").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _review_snapshot_max_age_hours() -> int:
    raw = os.getenv("REVIEW_SNAPSHOT_MAX_AGE_HOURS", "24").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 24


def _is_review_snapshot_stale(snapshot: ReviewReliabilitySnapshot) -> bool:
    analyzed_at = snapshot.analyzed_at
    if analyzed_at is None:
        return True

    max_age_hours = _review_snapshot_max_age_hours()
    if max_age_hours == 0:
        return True

    return analyzed_at <= (datetime.now() - timedelta(hours=max_age_hours))


async def analyze_external_place_review_reliability(
    session: AsyncSession,
    payload: ExternalPlaceReviewReliabilityIn,
) -> ExternalPlaceReviewReliabilityOut:
    place_name = payload.place_name.strip()
    normalized_place_id = _normalize_place_id(payload.place_id)
    source = (payload.source or "kakao").strip() or "kakao"

    snapshot = await _load_latest_external_review_snapshot(
        session,
        place_id=normalized_place_id,
        place_name=place_name,
        source=source,
    )
    if snapshot and not payload.force_refresh and not _is_review_snapshot_stale(snapshot):
        return _snapshot_to_external_reliability_out(
            snapshot=snapshot,
            place_id=normalized_place_id,
            place_name=place_name,
            address=payload.address,
            status="cached",
        )

    google_client = GooglePlacesClient(
        api_key=os.getenv("GOOGLE_PLACES_API_KEY", ""),
        timeout_seconds=float(os.getenv("GOOGLE_PLACES_TIMEOUT_SECONDS", "8")),
    )
    if not google_client.enabled:
        if snapshot:
            return _snapshot_to_external_reliability_out(
                snapshot=snapshot,
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
                status="cached",
            )
        return ExternalPlaceReviewReliabilityOut(
            place_id=normalized_place_id,
            place_key=build_place_key(normalized_place_id, place_name, source=source),
            place_name=place_name,
            review_data_status="insufficient_data",
            kakao_place_url=_build_kakao_place_url(
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
            ),
        )

    bundle = await google_client.fetch_reviews_for_place(
        place_name=place_name,
        address=payload.address,
        language_code="ko",
        region_code="KR",
    )
    if bundle is None:
        if snapshot:
            return _snapshot_to_external_reliability_out(
                snapshot=snapshot,
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
                status="cached",
            )
        return ExternalPlaceReviewReliabilityOut(
            place_id=normalized_place_id,
            place_key=build_place_key(normalized_place_id, place_name, source=source),
            place_name=place_name,
            review_data_status="insufficient_data",
            kakao_place_url=_build_kakao_place_url(
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
            ),
        )
    if not bundle.reviews:
        if snapshot:
            return _snapshot_to_external_reliability_out(
                snapshot=snapshot,
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
                status="cached",
            )
        return ExternalPlaceReviewReliabilityOut(
            place_id=normalized_place_id,
            place_key=build_place_key(normalized_place_id, place_name, source=source),
            place_name=place_name,
            review_data_status="insufficient_data",
            review_total_reviews=bundle.user_rating_count,
            kakao_place_url=_build_kakao_place_url(
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
            ),
        )

    review_items = [
        ReviewItemIn(
            text=item.text[:3000] if item.text else item.text,
            rating=item.rating,
            created_at=item.published_at,
            source="google_places",
        )
        for item in bundle.reviews
        if item.text and item.text.strip()
    ]
    if not review_items:
        if snapshot:
            return _snapshot_to_external_reliability_out(
                snapshot=snapshot,
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
                status="cached",
            )
        return ExternalPlaceReviewReliabilityOut(
            place_id=normalized_place_id,
            place_key=build_place_key(normalized_place_id, place_name, source=source),
            place_name=place_name,
            review_data_status="insufficient_data",
            review_total_reviews=bundle.user_rating_count,
            kakao_place_url=_build_kakao_place_url(
                place_id=normalized_place_id,
                place_name=place_name,
                address=payload.address,
            ),
        )

    analysis = await analyze_review_reliability(
        session=session,
        payload=ReviewReliabilityIn(
            place_name=place_name,
            place_id=f"{source}:{normalized_place_id}" if normalized_place_id else None,
            source="google_places",
            total_reviews_hint=bundle.user_rating_count,
            reviews=review_items,
        ),
    )
    return ExternalPlaceReviewReliabilityOut(
        place_id=normalized_place_id,
        place_key=analysis.place_key,
        place_name=analysis.place_name,
        review_data_status="analyzed",
        review_trust_score=analysis.trust_score,
        review_trust_grade=analysis.grade if analysis.grade in {"high", "medium", "low"} else "unknown",
        review_total_reviews=analysis.total_reviews,
        review_model_version=analysis.model_version,
        review_analyzed_at=analysis.analyzed_at,
        kakao_place_url=_build_kakao_place_url(
            place_id=normalized_place_id,
            place_name=place_name,
            address=payload.address,
        ),
    )


async def _analyze_external_place_reviews_with_google(
    session: AsyncSession,
    google_client: GooglePlacesClient,
    *,
    kakao_place_id: str | None,
    place_name: str,
    address: str | None,
) -> SearchResultOut | None:
    bundle = await google_client.fetch_reviews_for_place(
        place_name=place_name,
        address=address,
        language_code="ko",
        region_code="KR",
    )
    if bundle is None or not bundle.reviews:
        return None

    review_items = [
        ReviewItemIn(
            text=item.text[:3000] if item.text else item.text,
            rating=item.rating,
            created_at=item.published_at,
            source="google_places",
        )
        for item in bundle.reviews
    ]
    if not review_items:
        return None

    # Keep search-time key aligned to Kakao external_place key for future cache hit.
    normalized_id = f"kakao:{kakao_place_id}" if kakao_place_id else None
    analysis = await analyze_review_reliability(
        session=session,
        payload=ReviewReliabilityIn(
            place_name=place_name,
            place_id=normalized_id,
            source="google_places",
            total_reviews_hint=bundle.user_rating_count,
            reviews=review_items,
        ),
    )

    return SearchResultOut(
        result_type="external_place",
        area_id=kakao_place_id or f"external:{place_name or 'unknown'}",
        name=place_name or (bundle.place_name or "Unknown place"),
        address=address,
        category="external_place",
        lat=None,
        lng=None,
        review_trust_score=analysis.trust_score,
        review_trust_grade=analysis.grade if analysis.grade in {"high", "medium", "low"} else "unknown",
        review_total_reviews=analysis.total_reviews,
        review_model_version=analysis.model_version,
        review_analyzed_at=analysis.analyzed_at,
        review_data_status="analyzed",
    )


async def search_areas(session: AsyncSession, q: str) -> SearchOut:
    keyword = f"%{q}%"

    # Search keyword log for trends.
    session.add(SearchQueryLog(query=q))

    alias_subq = (
        select(AreaAlias.area_id)
        .where(AreaAlias.alias_value.like(keyword))
        .scalar_subquery()
    )

    exact_name = func.lower(Area.area_nm) == q.lower()
    has_alias = Area.area_id.in_(alias_subq)
    partial_name = Area.area_nm.like(keyword)
    partial_eng = Area.eng_nm.like(keyword)

    priority_expr = case(
        (exact_name, 1),
        (has_alias, 2),
        (partial_name, 3),
        (partial_eng, 4),
        else_=5,
    )

    local_stmt = (
        select(Area, AreaLiveMetric, priority_expr.label("priority"))
        .outerjoin(AreaLiveMetric, Area.area_id == AreaLiveMetric.area_id)
        .where(
            Area.is_active == True,  # noqa: E712
            or_(exact_name, has_alias, partial_name, partial_eng),
        )
        .order_by(priority_expr)
    )

    local_rows = (await session.execute(local_stmt)).all()

    kakao_client = KakaoLocalClient(os.getenv("KAKAO_REST_API_KEY", ""))
    try:
        external_docs = await kakao_client.search_keyword(session, q)
    except Exception as exc:
        external_docs = []
        logger.warning("Kakao search error: %s", exc)

    external_review_map = await _load_external_review_snapshots(session, external_docs)

    results: list[SearchResultOut] = []

    for area, metric, _ in local_rows:
        results.append(
            SearchResultOut(
                result_type="localon_area",
                area_id=area.area_id,
                area_cd=area.area_cd,
                name=area.area_nm,
                category=area.ui_category,
                lat=float(area.lat) if area.lat is not None else None,
                lng=float(area.lng) if area.lng is not None else None,
                congestion_level=metric.congestion_level if metric else None,
                citydata_score=(
                    float(metric.citydata_score)
                    if metric and metric.citydata_score is not None
                    else None
                ),
                sdot_score=(
                    float(metric.sdot_score)
                    if metric and metric.sdot_score is not None
                    else None
                ),
            )
        )

    for doc in external_docs:
        raw_place_id = doc.get("id")
        place_id = str(raw_place_id).strip() if raw_place_id is not None else None
        place_name = str(doc.get("place_name") or "").strip()
        address = doc.get("road_address_name") or doc.get("address_name")
        place_key = build_place_key(place_id, place_name, source="kakao")
        snapshot = external_review_map.get(place_key) or (
            external_review_map.get(place_id) if place_id else None
        )

        trust_score = (
            float(snapshot.trust_score)
            if snapshot and snapshot.trust_score is not None
            else None
        )

        results.append(
            SearchResultOut(
                result_type="external_place",
                area_id=place_id or f"external:{place_name or 'unknown'}",
                name=place_name or "Unknown place",
                address=address,
                category=doc.get("category_name") or "external_place",
                lat=float(doc.get("y")) if doc.get("y") else None,
                lng=float(doc.get("x")) if doc.get("x") else None,
                review_trust_score=trust_score,
                review_trust_grade=_trust_grade(trust_score),
                review_total_reviews=(
                    snapshot.total_reviews
                    if snapshot
                    else _extract_external_review_count(doc)
                ),
                review_model_version=snapshot.model_version if snapshot else None,
                review_analyzed_at=snapshot.analyzed_at if snapshot else None,
                review_data_status="analyzed" if snapshot else "insufficient_data",
            )
        )

    # Persist side effects (query logs + external cache rows) without failing response.
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.warning("Failed to persist search side effects: %s", exc)

    return SearchOut(query=q, results=results)
