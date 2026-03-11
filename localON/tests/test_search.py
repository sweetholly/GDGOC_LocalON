"""GET /search 엔드포인트 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.search import SearchOut, SearchResultOut

MOCK_SEARCH_OUT = SearchOut(
    query="성수",
    results=[
        SearchResultOut(
            result_type="localon_area",
            area_id=68,
            area_cd="POI068",
            name="성수카페거리",
            category="발달상권",
            lat=37.5446,
            lng=127.0586,
            congestion_level="약간 붐빔",
            citydata_score=70.0,
            sdot_score=60.0,
        )
    ],
)

MOCK_EMPTY_SEARCH = SearchOut(query="없는지역xyz", results=[])


@pytest.mark.asyncio
async def test_search_returns_200(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=성수")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_response_structure(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=성수")

    body = resp.json()
    assert "query" in body
    assert "results" in body
    assert body["query"] == "성수"


@pytest.mark.asyncio
async def test_search_result_fields(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=성수")

    result = resp.json()["results"][0]
    assert result["result_type"] == "localon_area"
    assert result["area_id"] == 68
    assert result["area_cd"] == "POI068"
    assert result["name"] == "성수카페거리"
    assert result["category"] == "발달상권"
    assert result["congestion_level"] == "약간 붐빔"
    assert result["citydata_score"] == pytest.approx(70.0)
    assert result["sdot_score"] == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_search_passes_query_to_controller(client: AsyncClient):
    mock = AsyncMock(return_value=MOCK_SEARCH_OUT)
    with patch("app.router.search.search_areas", new=mock):
        await client.get("/search?q=홍대")

    _, kwargs = mock.call_args
    assert kwargs["q"] == "홍대"


@pytest.mark.asyncio
async def test_search_empty_results(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_EMPTY_SEARCH)):
        resp = await client.get("/search?q=없는지역xyz")

    body = resp.json()
    assert resp.status_code == 200
    assert body["results"] == []
    assert body["query"] == "없는지역xyz"


@pytest.mark.asyncio
async def test_search_missing_query_param(client: AsyncClient):
    resp = await client.get("/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_empty_query_param(client: AsyncClient):
    resp = await client.get("/search?q=")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_multiple_results(client: AsyncClient):
    multi = SearchOut(
        query="강남",
        results=[
            SearchResultOut(
                result_type="localon_area",
                area_id=1,
                area_cd="POI001",
                name="강남 MICE 관광특구",
                category="관광특구",
                lat=37.5130,
                lng=127.0597,
                congestion_level="보통",
                citydata_score=50.0,
                sdot_score=None,
            ),
            SearchResultOut(
                result_type="localon_area",
                area_id=5,
                area_cd="POI005",
                name="강남역",
                category="발달상권",
                lat=37.4979,
                lng=127.0276,
                congestion_level="붐빔",
                citydata_score=90.0,
                sdot_score=80.0,
            ),
        ],
    )
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=multi)):
        resp = await client.get("/search?q=강남")

    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["name"] == "강남 MICE 관광특구"
    assert body["results"][1]["name"] == "강남역"
