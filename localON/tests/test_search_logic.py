from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.collector.clients.google_places import GooglePlaceReview, GooglePlaceReviewBundle
from app.controller.search import search_areas


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, *, rows=None, scalars=None):
        self._rows = rows or []
        self._scalars = scalars or []

    def all(self):
        return self._rows

    def scalars(self):
        return _ScalarsResult(self._scalars)


class _FakeSession:
    def __init__(self, execute_results):
        self._execute_results = list(execute_results)
        self.execute_calls = []
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, stmt):
        self.execute_calls.append(stmt)
        if not self._execute_results:
            raise AssertionError("Unexpected execute call")
        return self._execute_results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


def _doc(place_id: str = "123", place_name: str = "Test Cafe") -> dict:
    return {
        "id": place_id,
        "place_name": place_name,
        "road_address_name": "Seoul Gangnam",
        "category_name": "cafe",
        "x": "127.01",
        "y": "37.50",
    }


def _bundle() -> GooglePlaceReviewBundle:
    return GooglePlaceReviewBundle(
        google_place_id="g-123",
        place_name="Test Cafe",
        rating=4.5,
        user_rating_count=321,
        reviews=[
            GooglePlaceReview(
                text="Great coffee and kind staff",
                rating=4.6,
                published_at=datetime(2026, 3, 20, 9, 0, 0),
                author_name="alice",
            )
        ],
    )


@pytest.mark.asyncio
async def test_search_areas_auto_analyzes_when_snapshot_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    monkeypatch.setenv("ENABLE_GOOGLE_REVIEW_ENRICH", "true")
    session = _FakeSession(
        [
            _ExecuteResult(rows=[]),  # local rows
            _ExecuteResult(scalars=[]),  # no existing review snapshot
        ]
    )

    call_counter = {"analyze": 0}

    async def _fake_kakao(self, session, query):
        return [_doc()]

    async def _fake_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        return _bundle()

    async def _fake_analyze(*, session, payload):
        call_counter["analyze"] += 1
        return SimpleNamespace(
            trust_score=88.4,
            grade="high",
            total_reviews=1,
            model_version="heuristic-v1",
            analyzed_at=datetime(2026, 3, 20, 10, 0, 0),
        )

    monkeypatch.setattr(
        "app.collector.clients.kakao_local.KakaoLocalClient.search_keyword",
        _fake_kakao,
    )
    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _fake_google,
    )
    monkeypatch.setattr("app.controller.search.analyze_review_reliability", _fake_analyze)

    out = await search_areas(session, "test cafe")

    assert len(out.results) == 1
    result = out.results[0]
    assert result.result_type == "external_place"
    assert result.review_data_status == "analyzed"
    assert result.review_trust_score == pytest.approx(88.4)
    assert result.review_model_version == "heuristic-v1"
    assert call_counter["analyze"] == 1
    assert session.commit_count == 1
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_search_areas_reanalyzes_when_snapshot_is_stale(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    monkeypatch.setenv("ENABLE_GOOGLE_REVIEW_ENRICH", "true")
    monkeypatch.setenv("REVIEW_SNAPSHOT_MAX_AGE_HOURS", "24")

    stale_snapshot = SimpleNamespace(
        place_key="kakao:123",
        trust_score=55.0,
        total_reviews=9,
        model_version="heuristic-v1",
        analyzed_at=datetime.now() - timedelta(hours=49),
    )
    session = _FakeSession(
        [
            _ExecuteResult(rows=[]),  # local rows
            _ExecuteResult(scalars=[stale_snapshot]),
        ]
    )

    call_counter = {"analyze": 0}

    async def _fake_kakao(self, session, query):
        return [_doc()]

    async def _fake_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        return _bundle()

    async def _fake_analyze(*, session, payload):
        call_counter["analyze"] += 1
        return SimpleNamespace(
            trust_score=91.2,
            grade="high",
            total_reviews=1,
            model_version="heuristic-v1+gemini-rejudge-v1",
            analyzed_at=datetime(2026, 3, 20, 10, 30, 0),
        )

    monkeypatch.setattr(
        "app.collector.clients.kakao_local.KakaoLocalClient.search_keyword",
        _fake_kakao,
    )
    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _fake_google,
    )
    monkeypatch.setattr("app.controller.search.analyze_review_reliability", _fake_analyze)

    out = await search_areas(session, "test cafe")

    assert len(out.results) == 1
    result = out.results[0]
    assert result.review_data_status == "analyzed"
    assert result.review_trust_score == pytest.approx(91.2)
    assert result.review_model_version == "heuristic-v1+gemini-rejudge-v1"
    assert call_counter["analyze"] == 1


@pytest.mark.asyncio
async def test_search_areas_keeps_fresh_snapshot_without_reanalysis(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    monkeypatch.setenv("ENABLE_GOOGLE_REVIEW_ENRICH", "true")
    monkeypatch.setenv("REVIEW_SNAPSHOT_MAX_AGE_HOURS", "24")

    fresh_snapshot = SimpleNamespace(
        place_key="kakao:123",
        trust_score=73.5,
        total_reviews=23,
        model_version="heuristic-v1",
        analyzed_at=datetime.now() - timedelta(hours=2),
    )
    session = _FakeSession(
        [
            _ExecuteResult(rows=[]),  # local rows
            _ExecuteResult(scalars=[fresh_snapshot]),
        ]
    )

    async def _fake_kakao(self, session, query):
        return [_doc()]

    async def _never_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        raise AssertionError("Google fetch should not run for fresh snapshots")

    async def _never_analyze(*, session, payload):
        raise AssertionError("Review analysis should not run for fresh snapshots")

    monkeypatch.setattr(
        "app.collector.clients.kakao_local.KakaoLocalClient.search_keyword",
        _fake_kakao,
    )
    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _never_google,
    )
    monkeypatch.setattr("app.controller.search.analyze_review_reliability", _never_analyze)

    out = await search_areas(session, "test cafe")

    assert len(out.results) == 1
    result = out.results[0]
    assert result.review_data_status == "analyzed"
    assert result.review_trust_score == pytest.approx(73.5)
    assert result.review_total_reviews == 23
    assert result.review_model_version == "heuristic-v1"
