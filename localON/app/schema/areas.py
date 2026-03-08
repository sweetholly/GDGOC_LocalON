from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CongestionOut(BaseModel):
    level: str | None
    score: float | None
    msg: str | None
    population_min: int | None
    population_max: int | None
    sdot_current: int | None
    sdot_baseline: int | None
    is_estimated: bool
    updated_at: datetime | None


class HourlyOut(BaseModel):
    hour: int
    actual: int | None
    baseline: int | None
    level: str | None


class RecommendationOut(BaseModel):
    time_range: str
    expected_level: str
    avg_population: int


class DemographicsOut(BaseModel):
    male_rate: float | None
    female_rate: float | None
    age_0: float | None
    age_10: float | None
    age_20: float | None
    age_30: float | None
    age_40: float | None
    age_50: float | None
    age_60: float | None
    age_70: float | None


class DemandOut(BaseModel):
    type: str
    resident_rate: float | None
    non_resident_rate: float | None
    demographics: DemographicsOut


class CommercialOut(BaseModel):
    level: str | None
    payment_cnt: int | None
    payment_amt_min: int | None
    payment_amt_max: int | None


class WeatherOut(BaseModel):
    temp: float | None
    sensible_temp: float | None
    humidity: int | None
    wind_spd: float | None
    pm25: float | None
    pm25_index: str | None
    pm10: float | None
    pm10_index: str | None


class AreaDetailOut(BaseModel):
    area_id: int
    area_cd: str
    name: str
    eng_name: str | None
    category: str | None
    lat: float | None
    lng: float | None
    congestion: CongestionOut
    hourly: list[HourlyOut]
    recommendations: list[RecommendationOut]
    demand: DemandOut
    commercial: CommercialOut
    weather: WeatherOut
