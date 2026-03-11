from __future__ import annotations

import httpx
from datetime import datetime, timedelta
from typing import Any
import logging

from app.domain import MapPalceCache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

class KakaoLocalClient:
    def __init__(self, rest_api_key: str):
        self.rest_api_key = rest_api_key
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"KakaoAK {self.rest_api_key}"
        }
        
    async def search_keyword(self, session: AsyncSession, query: str) -> list[dict[str, Any]]:
        if not self.rest_api_key:
            logger.warning("KAKAO_REST_API_KEY is not set. Skipping external search.")
            return []
            
        # 1. Check cache first
        cache_stmt = select(MapPalceCache).where(
            MapPalceCache.query_key == query,
            MapPalceCache.expires_at > datetime.now()
        )
        cache_rows = (await session.execute(cache_stmt)).scalars().all()
        
        if cache_rows:
            logger.info(f"Kakao Local cache hit for query: {query}")
            return [row.payload_json for row in cache_rows]
            
        # 2. Fetch from API
        logger.info(f"Kakao Local API call for query: {query}")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.base_url,
                    headers=self._headers(),
                    params={"query": query, "size": 5} # Limit to top 5 results
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Kakao API Error: {e}")
            return []
            
        documents = data.get("documents", [])
        
        # 3. Save to cache
        if documents:
            try:
                expires_at = datetime.now() + timedelta(days=7) # 7 days TTL
                
                # Delete old cache for this query just in case some are expired
                # But simple way is just save new ones and search filter handles expires_at
                
                for doc in documents:
                    new_cache = MapPalceCache(
                        query_key=query,
                        map_palce_id=doc.get("id"),
                        place_name=doc.get("place_name"),
                        lat=float(doc.get("y")) if doc.get("y") else None,
                        lng=float(doc.get("x")) if doc.get("x") else None,
                        payload_json=doc,
                        expires_at=expires_at
                    )
                    session.add(new_cache)
                    
                # The caller should commit the transaction
            except Exception as e:
                logger.error(f"Failed to cache Kakao results: {e}")
                
        return documents
