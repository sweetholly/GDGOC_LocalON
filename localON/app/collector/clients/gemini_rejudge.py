from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiRejudgeResult:
    ad_suspect_ratio: float
    ai_suspect_ratio: float
    confidence: float
    notes: list[str]


class GeminiRejudgeClient:
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout_seconds: float = 8.0,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.model)

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _extract_json_text(response_json: dict[str, Any]) -> str | None:
        candidates = response_json.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        content = first.get("content")
        if not isinstance(content, dict):
            return None
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            return None
        part = parts[0] if isinstance(parts[0], dict) else {}
        text = part.get("text")
        if not isinstance(text, str):
            return None
        return text.strip()

    async def rejudge_reviews(
        self,
        *,
        place_name: str,
        reviews: list[dict[str, Any]],
    ) -> GeminiRejudgeResult | None:
        if not self.enabled or not reviews:
            return None

        limited_reviews = []
        for idx, review in enumerate(reviews[:20], start=1):
            text = str(review.get("text") or "").strip()
            if not text:
                continue
            limited_reviews.append(
                {
                    "index": idx,
                    "rating": review.get("rating"),
                    "text": text[:700],
                }
            )
        if not limited_reviews:
            return None

        prompt_payload = {
            "task": "Classify ad-like and AI-generated-like review signals.",
            "place_name": place_name,
            "rules": {
                "ad_like_examples": [
                    "sponsorship disclosure",
                    "paid partnership language",
                    "promotional coupon-heavy wording",
                ],
                "ai_like_examples": [
                    "overly generic summary style",
                    "unnatural repetitive phrasing",
                    "template-like sentence flow",
                ],
            },
            "reviews": limited_reviews,
            "response_schema": {
                "ad_suspect_count": "int",
                "ai_suspect_count": "int",
                "confidence": "float(0~1)",
                "notes": ["string"],
            },
            "must": "Return JSON only. No markdown.",
        }

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(prompt_payload, ensure_ascii=True)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        url = f"{self._BASE_URL}/models/{self.model}:generateContent"
        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    url,
                    params={"key": self.api_key},
                    json=request_body,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Gemini rejudge request failed: %s", exc)
            return None

        text = self._extract_json_text(data)
        if not text:
            return None

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Gemini returned non-JSON content for rejudge")
            return None

        total = len(limited_reviews)
        ad_count = int(parsed.get("ad_suspect_count", 0))
        ai_count = int(parsed.get("ai_suspect_count", 0))
        confidence = float(parsed.get("confidence", 0.0))
        notes_raw = parsed.get("notes", [])
        notes: list[str] = []
        if isinstance(notes_raw, list):
            notes = [str(item) for item in notes_raw[:5]]

        return GeminiRejudgeResult(
            ad_suspect_ratio=self._clamp(ad_count / total, 0.0, 1.0),
            ai_suspect_ratio=self._clamp(ai_count / total, 0.0, 1.0),
            confidence=self._clamp(confidence, 0.0, 1.0),
            notes=notes,
        )
