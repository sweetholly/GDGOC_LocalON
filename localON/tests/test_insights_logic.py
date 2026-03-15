from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.controller.insights import analyze_review_reliability, build_place_key
from app.schema.insights import ReviewItemIn, ReviewReliabilityIn


class _ScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, *, execute_results=None, commit_exc: Exception | None = None):
        self._execute_results = list(execute_results or [])
        self._commit_exc = commit_exc
        self.execute_calls = []
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, stmt):
        self.execute_calls.append(stmt)
        if self._execute_results:
            return self._execute_results.pop(0)
        return _ScalarOneOrNoneResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_count += 1
        if self._commit_exc is not None:
            raise self._commit_exc

    async def rollback(self):
        self.rollback_count += 1


def test_build_place_key_with_source_prefix():
    assert build_place_key("12345", "Test Cafe", "kakao") == "kakao:12345"


def test_build_place_key_keeps_existing_prefix():
    assert build_place_key("kakao:12345", "Test Cafe", "kakao") == "kakao:12345"


def test_build_place_key_without_id_normalizes_name():
    assert build_place_key(None, "  Test   Cafe  ", "kakao") == "test_cafe"


@pytest.mark.asyncio
async def test_analyze_review_reliability_clean_reviews_high_trust():
    session = _FakeSession()
    payload = ReviewReliabilityIn(
        place_name="Test Cafe",
        place_id="kakao:100",
        source="google_places",
        reviews=[
            ReviewItemIn(text="Great coffee and cozy seating for long work sessions", rating=4.6),
            ReviewItemIn(text="Friendly staff and fast service during lunch hours", rating=4.5),
            ReviewItemIn(text="Nice dessert selection and stable quality every visit", rating=4.7),
        ],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.total_reviews == 3
    assert out.ad_suspect_ratio == pytest.approx(0.0)
    assert out.ai_suspect_ratio == pytest.approx(0.0)
    assert out.duplicate_ratio == pytest.approx(0.0)
    assert out.trust_score >= 95.0
    assert out.grade == "high"
    assert len(out.suspicious_reviews) == 0
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_analyze_review_reliability_detects_ad_ai_and_duplicates():
    session = _FakeSession()
    repeated = (
        "Sponsored visit and ad disclosure, overall this place was excellent. "
        "In conclusion I strongly recommend this location."
    )
    payload = ReviewReliabilityIn(
        place_name="Promo Spot",
        place_id="kakao:200",
        source="google_places",
        reviews=[
            ReviewItemIn(text=repeated, rating=5.0),
            ReviewItemIn(text=repeated, rating=5.0),
            ReviewItemIn(text="Paid partnership ad post with discount details", rating=4.9),
        ],
    )

    out = await analyze_review_reliability(session=session, payload=payload)
    reasons = {item.reason for item in out.suspicious_reviews}

    assert out.total_reviews == 3
    assert out.ad_suspect_ratio > 0.0
    assert out.ai_suspect_ratio > 0.0
    assert out.duplicate_ratio > 0.0
    assert out.trust_score < 80.0
    assert "ad_suspected" in reasons
    assert "ai_generated_suspected" in reasons
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_analyze_review_reliability_no_reviews_uses_area_snapshot_fallback():
    latest_snapshot = SimpleNamespace(review_count=500)
    session = _FakeSession(execute_results=[_ScalarOneOrNoneResult(latest_snapshot)])
    payload = ReviewReliabilityIn(
        place_name="Fallback Place",
        area_id=1,
        source="google_places",
        reviews=[],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.total_reviews == 0
    assert out.ad_suspect_ratio == pytest.approx(0.0)
    assert out.ai_suspect_ratio == pytest.approx(0.0)
    assert out.duplicate_ratio == pytest.approx(0.0)
    assert out.trust_score == pytest.approx(100.0)
    assert out.grade == "high"
    assert len(session.execute_calls) == 1


@pytest.mark.asyncio
async def test_analyze_review_reliability_commit_failure_rolls_back():
    session = _FakeSession(commit_exc=RuntimeError("db failure"))
    payload = ReviewReliabilityIn(
        place_name="Rollback Test Cafe",
        reviews=[ReviewItemIn(text="Good quality and calm atmosphere", rating=4.5)],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.total_reviews == 1
    assert session.commit_count == 1
    assert session.rollback_count == 1
