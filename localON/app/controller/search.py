from __future__ import annotations

import logging
import os

from sqlalchemy import case, func, or_, select
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
from app.schema.search import SearchOut, SearchResultOut

logger = logging.getLogger(__name__)


def _trust_grade(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80.0:
        return "high"
    if score >= 60.0:
        return "medium"
    return "low"


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
            text=item.text,
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
    google_client = GooglePlacesClient(
        api_key=os.getenv("GOOGLE_PLACES_API_KEY", ""),
        timeout_seconds=float(os.getenv("GOOGLE_PLACES_TIMEOUT_SECONDS", "8")),
    )
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

        auto_analyzed: SearchResultOut | None = None
        if (
            snapshot is None
            and google_client.enabled
            and _google_review_enrich_enabled()
            and place_name
        ):
            auto_analyzed = await _analyze_external_place_reviews_with_google(
                session=session,
                google_client=google_client,
                kakao_place_id=place_id,
                place_name=place_name,
                address=address,
            )

        if auto_analyzed is not None:
            auto_analyzed.category = doc.get("category_name") or auto_analyzed.category
            auto_analyzed.lat = float(doc.get("y")) if doc.get("y") else None
            auto_analyzed.lng = float(doc.get("x")) if doc.get("x") else None
            results.append(auto_analyzed)
            continue

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
                review_total_reviews=snapshot.total_reviews if snapshot else None,
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
