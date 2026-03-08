"""GET /main 엔드포인트 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.mainpage import AreaSummaryOut, HotPlaceOut, MainOut, RisingOut, TrendsOut

AREA_1 = AreaSummaryOut(
    area_id=1,
    area_cd="POI001",
    name="강남 MICE 관광특구",
    category="관광특구",
    lat=37.5130,
    lng=127.0597,
    congestion_level="보통",
    congestion_score=50.0,
    population_min=32000,
    population_max=35000,
    weather_temp=12.5,
    air_idx="보통",
    distance_m=None,
    updated_at=datetime(2026, 3, 8, 14, 30, 0),
)

AREA_2 = AreaSummaryOut(
    area_id=2,
    area_cd="POI002",
    name="광화문·덕수궁",
    category="역사공간",
    lat=37.5701,
    lng=126.9769,
    congestion_level="여유",
    congestion_score=20.0,
    population_min=5000,
    population_max=8000,
    weather_temp=11.0,
    air_idx="좋음",
    distance_m=None,
    updated_at=datetime(2026, 3, 8, 14, 30, 0),
)

MOCK_MAIN_OUT = MainOut(
    areas=[AREA_1, AREA_2],
    trends=TrendsOut(
        hot_places=[
            HotPlaceOut(
                rank=1,
                area_id=1,
                name="강남 MICE 관광특구",
                congestion_level="붐빔",
                congestion_score=88.5,
                rank_change=2,
            )
        ],
        rising=[
            RisingOut(
                area_id=68,
                name="성수카페거리",
                change_pct=22.3,
                change_label="급상승",
            )
        ],
    ),
)


@pytest.mark.asyncio
async def test_main_returns_200(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_main_response_structure(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    body = resp.json()
    assert "areas" in body
    assert "trends" in body
    assert "hot_places" in body["trends"]
    assert "rising" in body["trends"]


@pytest.mark.asyncio
async def test_main_area_fields(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    area = resp.json()["areas"][0]
    assert area["area_id"] == 1
    assert area["area_cd"] == "POI001"
    assert area["name"] == "강남 MICE 관광특구"
    assert area["congestion_level"] == "보통"
    assert area["congestion_score"] == 50.0


@pytest.mark.asyncio
async def test_main_without_location_no_distance(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    area = resp.json()["areas"][0]
    assert area["distance_m"] is None


@pytest.mark.asyncio
async def test_main_with_location_passes_lat_lng(client: AsyncClient):
    mock_get_main = AsyncMock(return_value=MOCK_MAIN_OUT)
    with patch("app.router.mainpage.get_main", new=mock_get_main):
        resp = await client.get("/main?lat=37.4979&lng=127.0276")

    assert resp.status_code == 200
    _, kwargs = mock_get_main.call_args
    assert kwargs["lat"] == pytest.approx(37.4979)
    assert kwargs["lng"] == pytest.approx(127.0276)


@pytest.mark.asyncio
async def test_main_hot_places(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    hot = resp.json()["trends"]["hot_places"][0]
    assert hot["rank"] == 1
    assert hot["rank_change"] == 2
    assert hot["congestion_score"] == 88.5


@pytest.mark.asyncio
async def test_main_rising(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    rising = resp.json()["trends"]["rising"][0]
    assert rising["area_id"] == 68
    assert rising["change_label"] == "급상승"
    assert rising["change_pct"] == pytest.approx(22.3)
