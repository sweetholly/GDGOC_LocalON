"""GET /areas/{area_id}/visit-insights and POST /reviews/reliability contract tests."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.insights import (
    EventSignalOut,
    PopulationForecastOut,
    ReviewReliabilityOut,
    SuspiciousReviewOut,
    VisitInsightOut,
    VisitTimeSlotOut,
)

MOCK_VISIT_INSIGHT = VisitInsightOut(
    area_id=1,
    area_name="Gangnam MICE Tourism Zone",
    lookback_days=28,
    generated_at=datetime(2026, 3, 16, 12, 0, 0),
    hottest_slots=[
        VisitTimeSlotOut(
            day_of_week=5,
            day_label="SAT",
            hour=20,
            time_range="20:00~21:00",
            avg_population=35000,
            congestion_ratio=1.52,
            hot_score=0.91,
            visit_score=0.20,
            confidence=0.88,
            primary_cause="event_driven_demand",
        )
    ],
    recommended_slots=[
        VisitTimeSlotOut(
            day_of_week=1,
            day_label="TUE",
            hour=10,
            time_range="10:00~11:00",
            avg_population=15000,
            congestion_ratio=0.92,
            hot_score=0.44,
            visit_score=0.83,
            confidence=0.81,
            primary_cause="regular_time_pattern",
        )
    ],
    next_hours_forecast=[
        PopulationForecastOut(
            at=datetime(2026, 3, 16, 13, 0, 0),
            expected_population=24500,
            confidence=0.77,
            cause_factors=["historical_peak_hour"],
        )
    ],
    event_signals=[
        EventSignalOut(
            name="Seoul Night Festival",
            mention_count=3,
            period="2026-03-14~2026-03-20",
            place="Gangnam",
        )
    ],
)

MOCK_REVIEW_OUT = ReviewReliabilityOut(
    place_key="kakao_123",
    place_name="Some Cafe",
    total_reviews=42,
    ad_suspect_ratio=0.1429,
    ai_suspect_ratio=0.0952,
    duplicate_ratio=0.0476,
    trust_score=82.5,
    grade="high",
    suspicious_reviews=[
        SuspiciousReviewOut(reason="ad_suspected", preview="협찬으로 방문한 카페 후기입니다...")
    ],
    analyzed_at=datetime(2026, 3, 16, 12, 30, 0),
    model_version="heuristic-v1",
)


@pytest.mark.asyncio
async def test_visit_insights_returns_200(client: AsyncClient):
    with patch("app.router.insights.get_visit_insights", new=AsyncMock(return_value=MOCK_VISIT_INSIGHT)):
        resp = await client.get("/areas/1/visit-insights")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_visit_insights_passes_lookback(client: AsyncClient):
    mock = AsyncMock(return_value=MOCK_VISIT_INSIGHT)
    with patch("app.router.insights.get_visit_insights", new=mock):
        resp = await client.get("/areas/1/visit-insights?lookback_days=35")

    assert resp.status_code == 200
    _, kwargs = mock.call_args
    assert kwargs["area_id"] == 1
    assert kwargs["lookback_days"] == 35


@pytest.mark.asyncio
async def test_visit_insights_not_found(client: AsyncClient):
    with patch("app.router.insights.get_visit_insights", new=AsyncMock(return_value=None)):
        resp = await client.get("/areas/999/visit-insights")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_visit_insights_validation(client: AsyncClient):
    resp = await client.get("/areas/1/visit-insights?lookback_days=2")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_review_reliability_returns_200(client: AsyncClient):
    with patch(
        "app.router.insights.analyze_review_reliability",
        new=AsyncMock(return_value=MOCK_REVIEW_OUT),
    ):
        resp = await client.post(
            "/reviews/reliability",
            json={
                "place_name": "Some Cafe",
                "place_id": "kakao_123",
                "reviews": [{"text": "분위기 좋았어요", "rating": 5}],
            },
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_review_reliability_structure(client: AsyncClient):
    with patch(
        "app.router.insights.analyze_review_reliability",
        new=AsyncMock(return_value=MOCK_REVIEW_OUT),
    ):
        resp = await client.post(
            "/reviews/reliability",
            json={"place_name": "Some Cafe", "reviews": [{"text": "좋아요"}]},
        )

    body = resp.json()
    assert body["place_key"] == "kakao_123"
    assert body["place_name"] == "Some Cafe"
    assert body["trust_score"] == pytest.approx(82.5)
    assert body["grade"] == "high"
    assert "suspicious_reviews" in body


@pytest.mark.asyncio
async def test_review_reliability_validation(client: AsyncClient):
    resp = await client.post("/reviews/reliability", json={"reviews": [{"text": "x"}]})
    assert resp.status_code == 422
