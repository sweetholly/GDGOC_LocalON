from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.insights import analyze_review_reliability, get_visit_insights
from app.domain import get_db
from app.schema.insights import ReviewReliabilityIn, ReviewReliabilityOut, VisitInsightOut

router = APIRouter()


@router.get("/areas/{area_id}/visit-insights", response_model=VisitInsightOut)
async def area_visit_insights_endpoint(
    area_id: Annotated[int, Path(gt=0, description="Area ID")],
    lookback_days: Annotated[int, Query(ge=7, le=90, description="Historical lookback window")] = 28,
    db: AsyncSession = Depends(get_db),
) -> VisitInsightOut:
    result = await get_visit_insights(session=db, area_id=area_id, lookback_days=lookback_days)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "Area not found"},
        )
    return result


@router.post("/reviews/reliability", response_model=ReviewReliabilityOut)
async def review_reliability_endpoint(
    payload: ReviewReliabilityIn,
    db: AsyncSession = Depends(get_db),
) -> ReviewReliabilityOut:
    return await analyze_review_reliability(session=db, payload=payload)
