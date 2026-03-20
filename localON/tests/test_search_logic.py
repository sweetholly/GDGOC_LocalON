from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.collector.clients.google_places import GooglePlaceReview, GooglePlaceReviewBundle
from app.controller.search import analyze_external_place_review_reliability, search_areas
from app.schema.search import ExternalPlaceReviewReliabilityIn


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
                text=f"Great coffee and kind staff #{idx}",
                rating=4.6,
                published_at=datetime(2026, 3, 20, 9, 0, 0),
                author_name="alice",
            )
            for idx in range(1, 6)
        ],
    )


@pytest.mark.asyncio
async def test_search_areas_returns_insufficient_data_when_snapshot_missing(monkeypatch):
    session = _FakeSession(
        [
            _ExecuteResult(rows=[]),  # local rows
            _ExecuteResult(scalars=[]),  # no existing review snapshot
        ]
    )

    async def _fake_kakao(self, session, query):
        return [_doc()]

    async def _never_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        raise AssertionError("Google fetch should not run during /search")

    async def _never_analyze(*, session, payload):
        raise AssertionError("Review analysis should not run during /search")

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
    assert result.result_type == "external_place"
    assert result.review_data_status == "insufficient_data"
    assert result.review_trust_score is None
    assert result.review_model_version is None
    assert session.commit_count == 1
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_search_areas_returns_stale_snapshot_without_reanalysis(monkeypatch):
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

    async def _fake_kakao(self, session, query):
        return [_doc()]

    async def _never_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        raise AssertionError("Google fetch should not run during /search")

    async def _never_analyze(*, session, payload):
        raise AssertionError("Review analysis should not run during /search")

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
    assert result.review_trust_score == pytest.approx(55.0)
    assert result.review_total_reviews == 9
    assert result.review_model_version == "heuristic-v1"


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


@pytest.mark.asyncio
async def test_external_place_reliability_returns_cached_when_snapshot_fresh(monkeypatch):
    monkeypatch.setenv("REVIEW_SNAPSHOT_MAX_AGE_HOURS", "24")
    fresh_snapshot = SimpleNamespace(
        id=1,
        place_key="kakao:777",
        trust_score=84.2,
        total_reviews=44,
        model_version="heuristic-v1",
        analyzed_at=datetime.now() - timedelta(hours=1),
    )
    session = _FakeSession([_ExecuteResult(scalars=[fresh_snapshot])])

    async def _never_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        raise AssertionError("Google fetch should not run for fresh snapshot")

    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _never_google,
    )

    out = await analyze_external_place_review_reliability(
        session,
        ExternalPlaceReviewReliabilityIn(
            place_id="777",
            place_name="Test Cafe",
            address="Seoul",
        ),
    )

    assert out.review_data_status == "cached"
    assert out.review_trust_score == pytest.approx(84.2)
    assert out.review_total_reviews == 44
    assert out.kakao_place_url == "https://place.map.kakao.com/777"


@pytest.mark.asyncio
async def test_external_place_reliability_analyzes_when_snapshot_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    session = _FakeSession([_ExecuteResult(scalars=[])])

    async def _fake_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        return _bundle()

    async def _fake_analyze(*, session, payload):
        assert payload.total_reviews_hint == 321
        return SimpleNamespace(
            place_key="kakao:999",
            place_name="Test Cafe",
            trust_score=89.7,
            grade="high",
            total_reviews=321,
            model_version="heuristic-v1+gemini-rejudge-v1",
            analyzed_at=datetime(2026, 3, 20, 13, 0, 0),
        )

    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _fake_google,
    )
    monkeypatch.setattr("app.controller.search.analyze_review_reliability", _fake_analyze)

    out = await analyze_external_place_review_reliability(
        session,
        ExternalPlaceReviewReliabilityIn(
            place_id="999",
            place_name="Test Cafe",
            address="Seoul",
            force_refresh=True,
        ),
    )

    assert out.review_data_status == "analyzed"
    assert out.review_trust_score == pytest.approx(89.7)
    assert out.review_model_version == "heuristic-v1+gemini-rejudge-v1"
    assert out.review_total_reviews == 321


@pytest.mark.asyncio
async def test_external_place_reliability_skips_analysis_for_too_few_reviews(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    monkeypatch.setenv("EXTERNAL_REVIEW_MIN_ANALYSIS_SAMPLES", "5")
    session = _FakeSession([_ExecuteResult(scalars=[])])

    async def _fake_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        return GooglePlaceReviewBundle(
            google_place_id="g-888",
            place_name="Few Reviews Cafe",
            rating=4.1,
            user_rating_count=42,
            reviews=[
                GooglePlaceReview(
                    text="Nice place",
                    rating=4.0,
                    published_at=datetime(2026, 3, 20, 11, 0, 0),
                    author_name="alice",
                ),
                GooglePlaceReview(
                    text="Friendly owner",
                    rating=4.2,
                    published_at=datetime(2026, 3, 20, 11, 5, 0),
                    author_name="bob",
                ),
            ],
        )

    async def _never_analyze(*, session, payload):
        raise AssertionError("analysis should not run when sample count is below threshold")

    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _fake_google,
    )
    monkeypatch.setattr("app.controller.search.analyze_review_reliability", _never_analyze)

    out = await analyze_external_place_review_reliability(
        session,
        ExternalPlaceReviewReliabilityIn(
            place_id="888",
            place_name="Few Reviews Cafe",
            address="Seoul",
            force_refresh=True,
        ),
    )

    assert out.review_data_status == "insufficient_data"
    assert out.review_trust_score is None
    assert out.review_total_reviews == 42


@pytest.mark.asyncio
async def test_external_place_reliability_returns_count_when_reviews_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-key")
    session = _FakeSession([_ExecuteResult(scalars=[])])

    async def _fake_google(self, *, place_name, address=None, language_code="ko", region_code="KR"):
        return GooglePlaceReviewBundle(
            google_place_id="g-777",
            place_name="No Review Cafe",
            rating=4.2,
            user_rating_count=87,
            reviews=[],
        )

    monkeypatch.setattr(
        "app.collector.clients.google_places.GooglePlacesClient.fetch_reviews_for_place",
        _fake_google,
    )

    out = await analyze_external_place_review_reliability(
        session,
        ExternalPlaceReviewReliabilityIn(
            place_id="777",
            place_name="No Review Cafe",
            address="Seoul",
            force_refresh=True,
        ),
    )

    assert out.review_data_status == "insufficient_data"
    assert out.review_total_reviews == 87
    assert out.review_trust_score is None
