from __future__ import annotations

from pydantic import BaseModel


from typing import Literal


class SearchResultOut(BaseModel):
    result_type: Literal["localon_area", "external_place"] = "localon_area"
    area_id: str | int # Can be string for kakao IDs
    area_cd: str | None = None
    name: str
    address: str | None = None
    category: str | None
    lat: float | None
    lng: float | None
    congestion_level: str | None = None
    citydata_score: float | None = None
    sdot_score: float | None = None


class SearchOut(BaseModel):
    query: str
    results: list[SearchResultOut]
