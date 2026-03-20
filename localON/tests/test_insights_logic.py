from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.controller import insights
from app.collector.clients.gemini_rejudge import GeminiRejudgeResult
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


@pytest.fixture(autouse=True)
def _disable_gemini_by_default(monkeypatch):
    monkeypatch.setenv("ENABLE_GEMINI_REJUDGE", "false")


def test_build_place_key_with_source_prefix():
    assert build_place_key("12345", "Test Cafe", "kakao") == "kakao:12345"


def test_build_place_key_keeps_existing_prefix():
    assert build_place_key("kakao:12345", "Test Cafe", "kakao") == "kakao:12345"


def test_build_place_key_without_id_normalizes_name():
    assert build_place_key(None, "  Test   Cafe  ", "kakao") == "test_cafe"


def test_ad_patterns_match_korean_markers():
    samples = [
        "#\uad11\uace0 \ud3ec\uc2a4\ud2b8\uc785\ub2c8\ub2e4",
        "\uc5c5\uccb4\ub85c\ubd80\ud130 \ud611\ucc2c\uc744 \ubc1b\uc544 \uc791\uc131\ud588\uc2b5\ub2c8\ub2e4",
        "\uc81c\uacf5\ubc1b\uc544 \uccb4\ud5d8\ud55c \ud6c4\uae30",
        "\uc11c\ud3ec\ud130\uc988 \ud65c\ub3d9 \ub9ac\ubdf0\uc785\ub2c8\ub2e4",
    ]
    for text in samples:
        assert any(pattern.search(text) for pattern in insights._AD_PATTERNS)


def test_ad_pattern_word_boundary_avoids_false_positive():
    benign = "broad road quality and reading room access"
    assert not any(pattern.search(benign) for pattern in insights._AD_PATTERNS)


def test_ai_style_patterns_match_korean_markers():
    text = "\uc804\ubc18\uc801\uc73c\ub85c \ud6c4\uae30\ub97c \uc815\ub9ac\ud558\uc790\uba74 \ub9cc\uc871\uc2a4\ub7fd\uace0 \uacb0\ub860\uc801\uc73c\ub85c \ucd94\ucc9c\ud55c\ub2e4."
    normalized = " ".join(text.split()).lower()
    assert insights._review_ai_suspect(text, normalized)


def test_ai_repetition_rule_catches_low_variance_text():
    text = ("great " * 20).strip()
    normalized = " ".join(text.split()).lower()
    assert insights._review_ai_suspect(text, normalized)


def test_ai_rule_keeps_clean_short_review():
    text = "Great coffee and kind staff. Cozy place with stable quality."
    normalized = " ".join(text.split()).lower()
    assert not insights._review_ai_suspect(text, normalized)


@pytest.mark.asyncio
async def test_analyze_review_reliability_clean_reviews_with_small_sample_penalty():
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
    assert out.trust_score == pytest.approx(80.0)
    assert out.grade == "medium"
    assert len(out.suspicious_reviews) == 0
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_analyze_review_reliability_uses_total_reviews_hint_for_output():
    session = _FakeSession()
    payload = ReviewReliabilityIn(
        place_name="Hinted Count Cafe",
        place_id="kakao:101",
        source="google_places",
        total_reviews_hint=128,
        reviews=[
            ReviewItemIn(text="Great coffee and cozy seating", rating=4.6),
            ReviewItemIn(text="Friendly staff and quick service", rating=4.5),
            ReviewItemIn(text="Dessert quality stays consistent", rating=4.7),
        ],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.total_reviews == 128
    assert out.ad_suspect_ratio == pytest.approx(0.0)
    assert out.ai_suspect_ratio == pytest.approx(0.0)
    assert out.duplicate_ratio == pytest.approx(0.0)


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


@pytest.mark.asyncio
async def test_analyze_review_reliability_with_gemini_rejudge(monkeypatch):
    async def _fake_rejudge(self, *, place_name, reviews, total_reviews_hint=None):
        return GeminiRejudgeResult(
            ad_suspect_ratio=1.0,
            ai_suspect_ratio=1.0,
            confidence=0.92,
            notes=["llm_rejudge_applied"],
        )

    monkeypatch.setenv("ENABLE_GEMINI_REJUDGE", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("GEMINI_REJUDGE_MIN_REVIEWS", "1")
    monkeypatch.setenv("GEMINI_REJUDGE_TRUST_MIN", "0")
    monkeypatch.setenv("GEMINI_REJUDGE_TRUST_MAX", "100")
    monkeypatch.setattr(
        "app.collector.clients.gemini_rejudge.GeminiRejudgeClient.rejudge_reviews",
        _fake_rejudge,
    )

    session = _FakeSession()
    payload = ReviewReliabilityIn(
        place_name="LLM Blend Cafe",
        source="google_places",
        reviews=[
            ReviewItemIn(text="Great coffee and kind service", rating=4.6),
            ReviewItemIn(text="Comfortable seats and quiet atmosphere", rating=4.7),
        ],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.model_version == "heuristic-v1+gemini-rejudge-v1"
    assert out.trust_score < 80.0
    assert out.grade in {"medium", "low"}


def test_grade_threshold_medium_starts_at_70():
    assert insights._grade_from_trust(69.99) == "low"
    assert insights._grade_from_trust(70.0) == "medium"
    assert insights._grade_from_trust(84.99) == "medium"
    assert insights._grade_from_trust(85.0) == "high"


@pytest.mark.asyncio
async def test_analyze_review_reliability_penalizes_low_sample_coverage(monkeypatch):
    session = _FakeSession()
    payload = ReviewReliabilityIn(
        place_name="Sparse Sample Cafe",
        place_id="kakao:300",
        source="google_places",
        total_reviews_hint=500,
        reviews=[
            ReviewItemIn(text="Great coffee and calm seats", rating=4.6),
            ReviewItemIn(text="Staff are friendly and quick", rating=4.5),
            ReviewItemIn(text="Clean tables and stable taste", rating=4.7),
            ReviewItemIn(text="Comfortable environment for study", rating=4.4),
            ReviewItemIn(text="Dessert quality is consistently good", rating=4.5),
        ],
    )

    out = await analyze_review_reliability(session=session, payload=payload)

    assert out.total_reviews == 500
    assert out.trust_score == pytest.approx(80.0)
    assert out.grade == "medium"
