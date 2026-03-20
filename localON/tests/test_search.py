"""Contract tests for /search and /external-places/review-reliability."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schema.search import (
    ExternalPlaceReviewReliabilityOut,
    SearchOut,
    SearchResultOut,
)

MOCK_SEARCH_OUT = SearchOut(
    query="seongsu",
    results=[
        SearchResultOut(
            result_type="localon_area",
            area_id=68,
            area_cd="POI068",
            name="Seongsu Cafe Street",
            category="food",
            lat=37.5446,
            lng=127.0586,
            congestion_level="MEDIUM",
            citydata_score=70.0,
            sdot_score=60.0,
        )
    ],
)

MOCK_EMPTY_SEARCH = SearchOut(query="no-match-keyword", results=[])

MOCK_EXTERNAL_RELIABILITY_OUT = ExternalPlaceReviewReliabilityOut(
    place_id="123456",
    place_key="kakao:123456",
    place_name="Test Cafe",
    review_data_status="analyzed",
    review_trust_score=81.5,
    review_trust_grade="high",
    review_total_reviews=53,
    review_model_version="heuristic-v1+gemini-rejudge-v1",
    review_analyzed_at=datetime(2026, 3, 20, 12, 0, 0),
    kakao_place_url="https://place.map.kakao.com/123456",
)


@pytest.mark.asyncio
async def test_search_returns_200(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=seongsu")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_response_structure(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=seongsu")

    body = resp.json()
    assert "query" in body
    assert "results" in body
    assert body["query"] == "seongsu"


@pytest.mark.asyncio
async def test_search_result_fields(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_SEARCH_OUT)):
        resp = await client.get("/search?q=seongsu")

    result = resp.json()["results"][0]
    assert result["result_type"] == "localon_area"
    assert result["area_id"] == 68
    assert result["area_cd"] == "POI068"
    assert result["name"] == "Seongsu Cafe Street"
    assert result["category"] == "food"
    assert result["congestion_level"] == "MEDIUM"
    assert result["citydata_score"] == pytest.approx(70.0)
    assert result["sdot_score"] == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_search_passes_query_to_controller(client: AsyncClient):
    mock = AsyncMock(return_value=MOCK_SEARCH_OUT)
    with patch("app.router.search.search_areas", new=mock):
        await client.get("/search?q=hongdae")

    _, kwargs = mock.call_args
    assert kwargs["q"] == "hongdae"


@pytest.mark.asyncio
async def test_search_empty_results(client: AsyncClient):
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=MOCK_EMPTY_SEARCH)):
        resp = await client.get("/search?q=no-match-keyword")

    body = resp.json()
    assert resp.status_code == 200
    assert body["results"] == []
    assert body["query"] == "no-match-keyword"


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
        query="gangnam",
        results=[
            SearchResultOut(
                result_type="localon_area",
                area_id=1,
                area_cd="POI001",
                name="Gangnam MICE",
                category="tourism",
                lat=37.5130,
                lng=127.0597,
                congestion_level="MEDIUM",
                citydata_score=50.0,
                sdot_score=None,
            ),
            SearchResultOut(
                result_type="localon_area",
                area_id=5,
                area_cd="POI005",
                name="Gangnam Station",
                category="food",
                lat=37.4979,
                lng=127.0276,
                congestion_level="HIGH",
                citydata_score=90.0,
                sdot_score=80.0,
            ),
        ],
    )
    with patch("app.router.search.search_areas", new=AsyncMock(return_value=multi)):
        resp = await client.get("/search?q=gangnam")

    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["name"] == "Gangnam MICE"
    assert body["results"][1]["name"] == "Gangnam Station"


@pytest.mark.asyncio
async def test_search_external_place_review_trust_fields(client: AsyncClient):
    with_review = SearchOut(
        query="cafe",
        results=[
            SearchResultOut(
                result_type="external_place",
                area_id="123456",
                name="Test Cafe",
                address="Seoul Gangnam-gu",
                category="cafe",
                lat=37.5,
                lng=127.0,
                review_trust_score=74.5,
                review_trust_grade="medium",
                review_total_reviews=41,
                review_model_version="heuristic-v1",
                review_data_status="analyzed",
            )
        ],
    )

    with patch("app.router.search.search_areas", new=AsyncMock(return_value=with_review)):
        resp = await client.get("/search?q=cafe")

    body = resp.json()
    result = body["results"][0]
    assert result["result_type"] == "external_place"
    assert result["review_trust_score"] == pytest.approx(74.5)
    assert result["review_trust_grade"] == "medium"
    assert result["review_total_reviews"] == 41
    assert result["review_data_status"] == "analyzed"


@pytest.mark.asyncio
async def test_external_place_review_reliability_returns_200(client: AsyncClient):
    with patch(
        "app.router.search.analyze_external_place_review_reliability",
        new=AsyncMock(return_value=MOCK_EXTERNAL_RELIABILITY_OUT),
    ):
        resp = await client.post(
            "/external-places/review-reliability",
            json={
                "place_id": "123456",
                "place_name": "Test Cafe",
                "address": "Seoul Gangnam-gu",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["place_key"] == "kakao:123456"
    assert body["review_data_status"] == "analyzed"
    assert body["review_trust_score"] == pytest.approx(81.5)


@pytest.mark.asyncio
async def test_external_place_review_reliability_validation(client: AsyncClient):
    resp = await client.post(
        "/external-places/review-reliability",
        json={"place_id": "123456"},
    )
    assert resp.status_code == 422
