from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VisitTimeSlotOut(BaseModel):
    day_of_week: int
    day_label: str
    hour: int
    time_range: str
    avg_population: int | None
    congestion_ratio: float | None
    hot_score: float
    visit_score: float
    confidence: float
    primary_cause: str | None


class PopulationForecastOut(BaseModel):
    at: datetime
    expected_population: int | None
    confidence: float
    cause_factors: list[str]


class EventSignalOut(BaseModel):
    name: str
    mention_count: int
    period: str | None
    place: str | None


class VisitInsightOut(BaseModel):
    area_id: int
    area_name: str
    lookback_days: int
    generated_at: datetime
    hottest_slots: list[VisitTimeSlotOut]
    recommended_slots: list[VisitTimeSlotOut]
    next_hours_forecast: list[PopulationForecastOut]
    event_signals: list[EventSignalOut]


class ReviewItemIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    created_at: datetime | None = None
    source: str | None = None


class ReviewReliabilityIn(BaseModel):
    place_name: str = Field(min_length=1, max_length=200)
    place_id: str | None = Field(default=None, max_length=60)
    area_id: int | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, max_length=30)
    reviews: list[ReviewItemIn] = Field(default_factory=list)


class SuspiciousReviewOut(BaseModel):
    reason: str
    preview: str


class ReviewReliabilityOut(BaseModel):
    place_key: str
    place_name: str
    total_reviews: int
    ad_suspect_ratio: float
    ai_suspect_ratio: float
    duplicate_ratio: float
    trust_score: float
    grade: str
    suspicious_reviews: list[SuspiciousReviewOut]
    analyzed_at: datetime
    model_version: str
