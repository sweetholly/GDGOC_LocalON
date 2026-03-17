"""Live E2E tests (disabled by default).

How to run:
1) Set RUN_LIVE_E2E=1
2) Configure .env (DATABASE_URL, KAKAO_REST_API_KEY, optional GOOGLE_PLACES_API_KEY)
3) Run: uv run pytest -q tests/test_live_e2e.py
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.app import create_app
from app.domain import dispose_engine


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


pytestmark = pytest.mark.skipif(
    not _truthy(os.getenv("RUN_LIVE_E2E")),
    reason="Live E2E is disabled. Set RUN_LIVE_E2E=1 to run these tests.",
)


@pytest.fixture
async def live_client():
    app = create_app()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        # Avoid stale aiomysql pooled connections across async test event loops.
        await dispose_engine()


@pytest.mark.asyncio
async def test_live_main_endpoint(live_client: AsyncClient):
    resp = await live_client.get("/main")
    assert resp.status_code == 200

    body = resp.json()
    assert "areas" in body
    assert "trends" in body


@pytest.mark.asyncio
async def test_live_search_endpoint(live_client: AsyncClient):
    query = os.getenv("LIVE_SEARCH_QUERY", "강남")
    resp = await live_client.get("/search", params={"q": query})
    assert resp.status_code == 200

    body = resp.json()
    assert body["query"] == query
    assert isinstance(body["results"], list)


@pytest.mark.asyncio
async def test_live_area_detail_endpoint(live_client: AsyncClient):
    main_resp = await live_client.get("/main")
    assert main_resp.status_code == 200
    areas = main_resp.json().get("areas", [])
    if not areas:
        pytest.skip("No areas found in DB. Skip /areas/{area_id} live check.")

    area_id = areas[0]["area_id"]
    resp = await live_client.get(f"/areas/{area_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["area_id"] == area_id
    assert "hourly" in body
    assert "recommendations" in body


@pytest.mark.asyncio
async def test_live_visit_insights_endpoint(live_client: AsyncClient):
    main_resp = await live_client.get("/main")
    assert main_resp.status_code == 200
    areas = main_resp.json().get("areas", [])
    if not areas:
        pytest.skip("No areas found in DB. Skip /areas/{area_id}/visit-insights live check.")

    area_id = areas[0]["area_id"]
    resp = await live_client.get(f"/areas/{area_id}/visit-insights", params={"lookback_days": 28})
    assert resp.status_code == 200
    body = resp.json()
    assert body["area_id"] == area_id
    assert "hottest_slots" in body
    assert "recommended_slots" in body


@pytest.mark.asyncio
async def test_live_review_reliability_endpoint(live_client: AsyncClient):
    payload = {
        "place_name": "Live Test Cafe",
        "source": "manual_live_test",
        "reviews": [
            {"text": "분위기 좋고 서비스가 빨랐어요", "rating": 4.6},
            {"text": "광고 없이 솔직한 후기입니다. 커피 맛이 깔끔해요", "rating": 4.5},
            {"text": "좌석이 넓고 공부하기 좋았어요", "rating": 4.4},
        ],
    }
    resp = await live_client.post("/reviews/reliability", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["place_name"] == "Live Test Cafe"
    assert body["total_reviews"] == 3
    assert 0.0 <= body["trust_score"] <= 100.0
    assert body["grade"] in {"high", "medium", "low"}
