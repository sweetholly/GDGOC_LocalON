from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha1
import logging
import os
import re
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import MapPlaceCache

logger = logging.getLogger(__name__)


class KakaoLocalClient:
    def __init__(self, rest_api_key: str):
        self.rest_api_key = rest_api_key
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"KakaoAK {self.rest_api_key}"}

    @staticmethod
    def _truthy(raw: str | None, *, default: bool = False) -> bool:
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    def _search_size(self) -> int:
        raw = os.getenv("KAKAO_SEARCH_SIZE", "15").strip()
        try:
            return max(1, min(15, int(raw)))
        except ValueError:
            return 15

    def _max_pages(self) -> int:
        raw = os.getenv("KAKAO_SEARCH_MAX_PAGES", "3").strip()
        try:
            return max(1, min(45, int(raw)))
        except ValueError:
            return 3

    def _cache_ttl_days(self) -> int:
        raw = os.getenv("KAKAO_CACHE_TTL_DAYS", "7").strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return 7

    def _result_cap(self) -> int:
        raw = os.getenv("KAKAO_SEARCH_RESULT_CAP", "30").strip()
        try:
            return max(1, min(100, int(raw)))
        except ValueError:
            return 30

    def _search_rect(self) -> str | None:
        use_rect = self._truthy(os.getenv("KAKAO_SEARCH_USE_SEOUL_RECT"), default=True)
        if not use_rect:
            return None
        # Seoul bounding box: min_lng,min_lat,max_lng,max_lat
        raw = os.getenv("KAKAO_SEARCH_RECT", "126.764,37.428,127.184,37.701").strip()
        return raw or None

    def _search_seoul_only(self) -> bool:
        return self._truthy(os.getenv("KAKAO_SEARCH_SEOUL_ONLY"), default=True)

    @staticmethod
    def _parse_rect(rect: str | None) -> tuple[float, float, float, float] | None:
        if not rect:
            return None
        parts = [item.strip() for item in rect.split(",")]
        if len(parts) != 4:
            return None
        try:
            min_lng, min_lat, max_lng, max_lat = (float(x) for x in parts)
        except ValueError:
            return None
        return min_lng, min_lat, max_lng, max_lat

    def _is_seoul_doc(
        self,
        row: dict[str, Any],
        *,
        seoul_bounds: tuple[float, float, float, float] | None,
    ) -> bool:
        address = str(row.get("address_name") or row.get("road_address_name") or "").strip()
        if address:
            lowered = address.lower()
            if "\uC11C\uC6B8" in address or "seoul" in lowered:
                return True

        if seoul_bounds is None:
            return False
        min_lng, min_lat, max_lng, max_lat = seoul_bounds
        try:
            lng = float(row.get("x"))
            lat = float(row.get("y"))
        except (TypeError, ValueError):
            return False
        return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat

    def _query_variants(self, query: str) -> list[str]:
        base = " ".join(query.split())
        if not base:
            return []
        variants = [base]
        lowered = base.lower()
        if "\uC11C\uC6B8" not in base and "seoul" not in lowered:
            variants.extend([f"\uC11C\uC6B8 {base}", f"{base} \uC11C\uC6B8"])

        compact = re.sub(r"\s+", "", base)
        suffix_tokens = (
            "\uCE74\uD398",  # 카페
            "\uB9DB\uC9D1",  # 맛집
            "\uC220\uC9D1",  # 술집
            "\uC2DD\uB2F9",  # 식당
            "\uC5ED",  # 역
            "\uAC70\uB9AC",  # 거리
            "\uC2DC\uC7A5",  # 시장
            "\uACF5\uC6D0",  # 공원
        )
        for token in suffix_tokens:
            if compact.endswith(token) and compact != token:
                head = compact[: -len(token)].strip()
                if head:
                    variants.append(f"{head} {token}")
                break

        deduped: list[str] = []
        seen: set[str] = set()
        for item in variants:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item.strip())
        return deduped

    def _build_cache_key(
        self,
        *,
        query: str,
        size: int,
        pages: int,
        rect: str | None,
    ) -> str:
        base = f"v2|q={query}|size={size}|pages={pages}|rect={rect or '-'}"
        if len(base) <= 190:
            return base
        digest = sha1(base.encode("utf-8")).hexdigest()[:16]
        return f"v2|h={digest}|q={query[:80]}"

    async def search_keyword(self, session: AsyncSession, query: str) -> list[dict[str, Any]]:
        if not self.rest_api_key:
            logger.warning("KAKAO_REST_API_KEY is not set. Skipping external search.")
            return []

        search_size = self._search_size()
        max_pages = self._max_pages()
        search_rect = self._search_rect()
        seoul_bounds = self._parse_rect(search_rect)
        seoul_only = self._search_seoul_only()
        result_cap = self._result_cap()
        query_variants = self._query_variants(query)
        if not query_variants:
            return []

        cache_key = self._build_cache_key(
            query=query,
            size=search_size,
            pages=max_pages,
            rect=search_rect,
        )

        # 1. Check cache first
        cache_stmt = select(MapPlaceCache).where(
            MapPlaceCache.query_key == cache_key,
            MapPlaceCache.expires_at > datetime.now(),
        )
        cache_rows = (await session.execute(cache_stmt)).scalars().all()

        if cache_rows:
            logger.info(f"Kakao Local cache hit for query: {query}")
            return [row.payload_json for row in cache_rows]

        # 2. Fetch from API (query expansion + pagination + dedupe)
        logger.info(f"Kakao Local API call for query: {query}")
        documents: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        try:
            async with httpx.AsyncClient() as client:
                for q in query_variants:
                    for page in range(1, max_pages + 1):
                        params: dict[str, Any] = {
                            "query": q,
                            "size": search_size,
                            "page": page,
                            "sort": "accuracy",
                        }
                        if search_rect:
                            params["rect"] = search_rect

                        resp = await client.get(
                            self.base_url,
                            headers=self._headers(),
                            params=params,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        rows = data.get("documents", [])
                        if not isinstance(rows, list):
                            rows = []

                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            if seoul_only and not self._is_seoul_doc(
                                row,
                                seoul_bounds=seoul_bounds,
                            ):
                                continue
                            place_id = str(row.get("id") or "").strip()
                            fallback = (
                                f"{row.get('place_name') or ''}|"
                                f"{row.get('road_address_name') or row.get('address_name') or ''}"
                            )
                            dedupe_key = place_id or fallback
                            if dedupe_key in seen_keys:
                                continue
                            seen_keys.add(dedupe_key)
                            documents.append(row)
                            if len(documents) >= result_cap:
                                break

                        if len(documents) >= result_cap:
                            break

                        meta = data.get("meta", {})
                        is_end = bool(meta.get("is_end")) if isinstance(meta, dict) else False
                        if is_end or not rows:
                            break

                    if len(documents) >= result_cap:
                        break
        except httpx.HTTPError as e:
            logger.error(f"Kakao API Error: {e}")
            return []

        # 3. Save to cache
        if documents:
            try:
                expires_at = datetime.now() + timedelta(days=self._cache_ttl_days())

                # Replace existing cache rows for this key to prevent stale mixed result sets.
                await session.execute(delete(MapPlaceCache).where(MapPlaceCache.query_key == cache_key))

                for doc in documents:
                    new_cache = MapPlaceCache(
                        query_key=cache_key,
                        map_place_id=doc.get("id"),
                        place_name=doc.get("place_name"),
                        lat=float(doc.get("y")) if doc.get("y") else None,
                        lng=float(doc.get("x")) if doc.get("x") else None,
                        payload_json=doc,
                        expires_at=expires_at,
                    )
                    session.add(new_cache)

                # The caller should commit the transaction
            except Exception as e:
                logger.error(f"Failed to cache Kakao results: {e}")

        return documents
