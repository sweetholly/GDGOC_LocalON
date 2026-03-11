from __future__ import annotations

from pydantic import BaseModel


class SearchResultOut(BaseModel):
    area_id: int
    area_cd: str
    name: str
    category: str | None
    lat: float | None
    lng: float | None
    congestion_level: str | None
    citydata_score: float | None
    sdot_score: float | None


class SearchOut(BaseModel):
    query: str
    results: list[SearchResultOut]
