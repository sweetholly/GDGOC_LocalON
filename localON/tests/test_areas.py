"""GET /areas/{area_id} 엔드포인트 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.areas import (
    AreaDetailOut,
    CommercialOut,
    CongestionOut,
    DemandOut,
    DemographicsOut,
    HourlyOut,
    RecommendationOut,
    WeatherOut,
)

MOCK_AREA_DETAIL = AreaDetailOut(
    area_id=1,
    area_cd="POI001",
    name="강남 MICE 관광특구",
    eng_name="Gangnam MICE Special Tourist Zone",
    category="관광특구",
    lat=37.5130,
    lng=127.0597,
    congestion=CongestionOut(
        level="보통",
        score=50.0,
        msg="사람이 몰리는 시간대는 조금 혼잡할 수 있어요",
        population_min=32000,
        population_max=35000,
        sdot_current=245,
        sdot_baseline=200,
        is_estimated=False,
        updated_at=datetime(2026, 3, 8, 14, 30, 0),
    ),
    hourly=[
        HourlyOut(hour=h, actual=5000 + h * 100, baseline=4800 + h * 90, level="여유")
        for h in range(24)
    ],
    recommendations=[
        RecommendationOut(time_range="10:00~11:00", expected_level="여유", avg_population=18000),
        RecommendationOut(time_range="14:00~15:00", expected_level="여유", avg_population=20000),
        RecommendationOut(time_range="06:00~07:00", expected_level="여유", avg_population=12000),
    ],
    demand=DemandOut(
        type="관광/방문 수요 중심",
        resident_rate=35.2,
        non_resident_rate=64.8,
        demographics=DemographicsOut(
            male_rate=48.5,
            female_rate=51.5,
            age_0=2.1,
            age_10=8.3,
            age_20=28.3,
            age_30=25.1,
            age_40=18.5,
            age_50=10.2,
            age_60=5.4,
            age_70=2.1,
        ),
    ),
    commercial=CommercialOut(
        level="보통",
        payment_cnt=1523,
        payment_amt_min=45000000,
        payment_amt_max=52000000,
    ),
    weather=WeatherOut(
        temp=12.5,
        sensible_temp=10.2,
        humidity=45,
        wind_spd=3.2,
        pm25=15.0,
        pm25_index="좋음",
        pm10=28.0,
        pm10_index="보통",
    ),
)


@pytest.mark.asyncio
async def test_area_detail_returns_200(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_area_detail_basic_fields(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    body = resp.json()
    assert body["area_id"] == 1
    assert body["area_cd"] == "POI001"
    assert body["name"] == "강남 MICE 관광특구"
    assert body["eng_name"] == "Gangnam MICE Special Tourist Zone"
    assert body["category"] == "관광특구"


@pytest.mark.asyncio
async def test_area_detail_congestion(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    c = resp.json()["congestion"]
    assert c["level"] == "보통"
    assert c["score"] == 50.0
    assert c["population_min"] == 32000
    assert c["population_max"] == 35000
    assert c["sdot_current"] == 245
    assert c["is_estimated"] is False


@pytest.mark.asyncio
async def test_area_detail_hourly_has_24_slots(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    hourly = resp.json()["hourly"]
    assert len(hourly) == 24
    assert hourly[0]["hour"] == 0
    assert hourly[23]["hour"] == 23


@pytest.mark.asyncio
async def test_area_detail_recommendations(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    recs = resp.json()["recommendations"]
    assert len(recs) == 3
    assert recs[0]["time_range"] == "10:00~11:00"
    assert recs[0]["expected_level"] == "여유"


@pytest.mark.asyncio
async def test_area_detail_demand(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    demand = resp.json()["demand"]
    assert demand["type"] == "관광/방문 수요 중심"
    assert demand["resident_rate"] == pytest.approx(35.2)
    assert demand["non_resident_rate"] == pytest.approx(64.8)
    assert demand["demographics"]["male_rate"] == pytest.approx(48.5)
    assert demand["demographics"]["age_20"] == pytest.approx(28.3)


@pytest.mark.asyncio
async def test_area_detail_commercial(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    com = resp.json()["commercial"]
    assert com["level"] == "보통"
    assert com["payment_cnt"] == 1523
    assert com["payment_amt_min"] == 45000000


@pytest.mark.asyncio
async def test_area_detail_weather(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=MOCK_AREA_DETAIL)):
        resp = await client.get("/areas/1")

    w = resp.json()["weather"]
    assert w["temp"] == pytest.approx(12.5)
    assert w["pm25_index"] == "좋음"
    assert w["pm10_index"] == "보통"


@pytest.mark.asyncio
async def test_area_detail_with_date_param(client: AsyncClient):
    mock = AsyncMock(return_value=MOCK_AREA_DETAIL)
    with patch("app.router.areas.get_area_detail", new=mock):
        resp = await client.get("/areas/1?date=2026-03-08")

    assert resp.status_code == 200
    _, kwargs = mock.call_args
    from datetime import date
    assert kwargs["stat_date"] == date(2026, 3, 8)


@pytest.mark.asyncio
async def test_area_detail_not_found(client: AsyncClient):
    with patch("app.router.areas.get_area_detail", new=AsyncMock(return_value=None)):
        resp = await client.get("/areas/999")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_area_detail_invalid_id_zero(client: AsyncClient):
    resp = await client.get("/areas/0")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_area_detail_invalid_id_string(client: AsyncClient):
    resp = await client.get("/areas/abc")
    assert resp.status_code == 422
