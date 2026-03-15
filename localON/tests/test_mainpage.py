"""GET /main contract tests."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.mainpage import AreaSummaryOut, HotPlaceOut, MainOut, RisingOut, TrendsOut

AREA_1 = AreaSummaryOut(
    area_id=1,
    area_cd="POI001",
    name="Gangnam MICE Tourism Zone",
    category="tourism_zone",
    lat=37.5130,
    lng=127.0597,
    congestion_level="normal",
    citydata_score=50.0,
    sdot_score=61.25,
    population_min=32000,
    population_max=35000,
    weather_temp=12.5,
    air_idx="normal",
    distance_m=None,
    updated_at=datetime(2026, 3, 8, 14, 30, 0),
)

AREA_2 = AreaSummaryOut(
    area_id=2,
    area_cd="POI002",
    name="Gwanghwamun Square",
    category="public_space",
    lat=37.5701,
    lng=126.9769,
    congestion_level="free",
    citydata_score=25.0,
    sdot_score=None,
    population_min=5000,
    population_max=8000,
    weather_temp=11.0,
    air_idx="good",
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
                name="Gangnam MICE Tourism Zone",
                congestion_level="crowded",
                citydata_score=90.0,
                sdot_score=87.0,
                rank_change=2,
            )
        ],
        rising=[
            RisingOut(
                area_id=68,
                name="Seongsu Cafe Street",
                change_pct=22.3,
                change_label="rising",
            )
        ],
        popular_searches=["seongsu", "hongdae", "gangnam"],
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
    assert "popular_searches" in body["trends"]


@pytest.mark.asyncio
async def test_main_area_fields(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    area = resp.json()["areas"][0]
    assert area["area_id"] == 1
    assert area["area_cd"] == "POI001"
    assert area["name"] == "Gangnam MICE Tourism Zone"
    assert area["congestion_level"] == "normal"
    assert area["citydata_score"] == 50.0
    assert area["sdot_score"] == 61.25


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
    assert hot["citydata_score"] == 90.0
    assert hot["sdot_score"] == 87.0


@pytest.mark.asyncio
async def test_main_rising_and_popular_searches(client: AsyncClient):
    with patch("app.router.mainpage.get_main", new=AsyncMock(return_value=MOCK_MAIN_OUT)):
        resp = await client.get("/main")

    rising = resp.json()["trends"]["rising"][0]
    assert rising["area_id"] == 68
    assert rising["change_label"] == "rising"
    assert rising["change_pct"] == pytest.approx(22.3)

    ps = resp.json()["trends"]["popular_searches"]
    assert len(ps) == 3
    assert ps[0] == "seongsu"
