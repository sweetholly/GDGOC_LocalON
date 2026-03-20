from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.search import (
    analyze_external_place_review_reliability,
    search_areas,
)
from app.domain import get_db
from app.schema.search import (
    ExternalPlaceReviewReliabilityIn,
    ExternalPlaceReviewReliabilityOut,
    SearchOut,
)

router = APIRouter()


@router.get('/search', response_model=SearchOut)
async def search_endpoint(
    q: Annotated[str, Query(min_length=1, description='Search keyword')],
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    return await search_areas(session=db, q=q)


@router.post(
    "/external-places/review-reliability",
    response_model=ExternalPlaceReviewReliabilityOut,
)
async def external_place_review_reliability_endpoint(
    payload: ExternalPlaceReviewReliabilityIn,
    db: AsyncSession = Depends(get_db),
) -> ExternalPlaceReviewReliabilityOut:
    return await analyze_external_place_review_reliability(session=db, payload=payload)
