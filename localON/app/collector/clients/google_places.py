from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GooglePlaceReview:
    text: str
    rating: float | None
    published_at: datetime | None
    author_name: str | None


@dataclass
class GooglePlaceReviewBundle:
    google_place_id: str | None
    place_name: str | None
    rating: float | None
    user_rating_count: int | None
    reviews: list[GooglePlaceReview]


class GooglePlacesClient:
    _TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    _DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

    def __init__(self, api_key: str, timeout_seconds: float = 8.0):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        candidate = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    @staticmethod
    def _extract_review_text(raw: dict[str, Any]) -> str:
        original_text = raw.get("originalText")
        if isinstance(original_text, dict):
            text = original_text.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

        text_obj = raw.get("text")
        if isinstance(text_obj, dict):
            text = text_obj.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

        legacy_text = raw.get("text")
        if isinstance(legacy_text, str) and legacy_text.strip():
            return legacy_text.strip()
        return ""

    async def _search_place_id(
        self,
        query: str,
        language_code: str = "ko",
        region_code: str = "KR",
    ) -> str | None:
        payload = {
            "textQuery": query,
            "languageCode": language_code,
            "regionCode": region_code,
            "maxResultCount": 1,
        }
        field_mask = "places.id,places.displayName,places.formattedAddress"
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                self._TEXT_SEARCH_URL,
                headers=self._headers(field_mask),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places")
        if not isinstance(places, list) or not places:
            return None

        place = places[0] if isinstance(places[0], dict) else {}
        place_id = place.get("id")
        return str(place_id).strip() if place_id else None

    async def _fetch_place_details(
        self,
        place_id: str,
        language_code: str = "ko",
        region_code: str = "KR",
    ) -> GooglePlaceReviewBundle | None:
        field_mask = "id,displayName,rating,userRatingCount,reviews"
        params = {"languageCode": language_code, "regionCode": region_code}
        timeout = httpx.Timeout(self.timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                self._DETAILS_URL.format(place_id=place_id),
                headers=self._headers(field_mask),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        reviews_raw = data.get("reviews")
        review_items: list[GooglePlaceReview] = []
        if isinstance(reviews_raw, list):
            for raw in reviews_raw:
                if not isinstance(raw, dict):
                    continue
                text = self._extract_review_text(raw)
                if not text:
                    continue
                review_items.append(
                    GooglePlaceReview(
                        text=text,
                        rating=float(raw["rating"]) if raw.get("rating") is not None else None,
                        published_at=self._parse_iso_datetime(raw.get("publishTime")),
                        author_name=(
                            raw.get("authorAttribution", {}).get("displayName")
                            if isinstance(raw.get("authorAttribution"), dict)
                            else None
                        ),
                    )
                )

        display_name = data.get("displayName")
        place_name = (
            display_name.get("text")
            if isinstance(display_name, dict)
            else None
        )
        rating = float(data["rating"]) if data.get("rating") is not None else None
        user_rating_count = (
            int(data["userRatingCount"])
            if data.get("userRatingCount") is not None
            else None
        )

        return GooglePlaceReviewBundle(
            google_place_id=str(data.get("id") or place_id),
            place_name=place_name,
            rating=rating,
            user_rating_count=user_rating_count,
            reviews=review_items,
        )

    async def fetch_reviews_for_place(
        self,
        place_name: str,
        address: str | None = None,
        language_code: str = "ko",
        region_code: str = "KR",
    ) -> GooglePlaceReviewBundle | None:
        if not self.enabled:
            return None

        query = place_name.strip()
        if address and address.strip():
            query = f"{query} {address.strip()}"

        try:
            place_id = await self._search_place_id(
                query=query,
                language_code=language_code,
                region_code=region_code,
            )
            if not place_id:
                return None
            return await self._fetch_place_details(
                place_id=place_id,
                language_code=language_code,
                region_code=region_code,
            )
        except httpx.HTTPError as exc:
            logger.warning("Google Places API error for query '%s': %s", query, exc)
            return None
