from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchResultOut(BaseModel):
    result_type: Literal["localon_area", "external_place"] = "localon_area"
    area_id: str | int  # Can be string for kakao IDs
    area_cd: str | None = None
    name: str
    address: str | None = None
    category: str | None
    lat: float | None
    lng: float | None
    congestion_level: str | None = None
    citydata_score: float | None = None
    sdot_score: float | None = None
    review_trust_score: float | None = None
    review_trust_grade: Literal["high", "medium", "low", "unknown"] | None = None
    review_total_reviews: int | None = None
    review_model_version: str | None = None
    review_analyzed_at: datetime | None = None
    review_data_status: Literal["analyzed", "insufficient_data"] | None = None


class SearchOut(BaseModel):
    query: str
    results: list[SearchResultOut]


class ExternalPlaceReviewReliabilityIn(BaseModel):
    place_name: str = Field(min_length=1, max_length=200)
    place_id: str | None = Field(default=None, max_length=60)
    address: str | None = Field(default=None, max_length=300)
    source: str = Field(default="kakao", max_length=30)
    force_refresh: bool = False


class ExternalPlaceReviewReliabilityOut(BaseModel):
    place_id: str | None
    place_key: str
    place_name: str
    review_data_status: Literal["analyzed", "cached", "insufficient_data"]
    review_trust_score: float | None = None
    review_trust_grade: Literal["high", "medium", "low", "unknown"] | None = None
    review_total_reviews: int | None = None
    review_model_version: str | None = None
    review_analyzed_at: datetime | None = None
    kakao_place_url: str | None = None
