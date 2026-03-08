from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AreaSummaryOut(BaseModel):
    area_id: int
    area_cd: str
    name: str
    category: str | None
    lat: float | None
    lng: float | None
    congestion_level: str | None
    congestion_score: float | None
    population_min: int | None
    population_max: int | None
    weather_temp: float | None
    air_idx: str | None
    distance_m: int | None = None
    updated_at: datetime | None


class HotPlaceOut(BaseModel):
    rank: int
    area_id: int
    name: str
    congestion_level: str | None
    congestion_score: float | None
    rank_change: int | None


class RisingOut(BaseModel):
    area_id: int | None
    name: str | None
    change_pct: float | None
    change_label: str | None


class TrendsOut(BaseModel):
    hot_places: list[HotPlaceOut]
    rising: list[RisingOut]


class MainOut(BaseModel):
    areas: list[AreaSummaryOut]
    trends: TrendsOut
