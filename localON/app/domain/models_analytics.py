from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SearchQueryLog(Base):
    __tablename__ = "search_query_log"
    __table_args__ = (Index("idx_sql_query", "query"), Index("idx_sql_created", "created_at"))

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query: Mapped[Any] = mapped_column(String(200), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SdotTrafficRaw(Base):
    __tablename__ = "sdot_traffic_raw"
    __table_args__ = (
        Index("idx_sdot_region_time", "sdot_region_key", "sensing_time"),
        Index("idx_sdot_area_time", "area_id", "sensing_time"),
    )

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sdot_region_key: Mapped[Any] = mapped_column(String(50), nullable=False)
    sdot_region_name: Mapped[Any] = mapped_column(String(100), nullable=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="SET NULL"), nullable=True
    )
    visitor_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    sensing_time: Mapped[Any] = mapped_column(DateTime, nullable=False)
    fetched_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    source_serial: Mapped[Any] = mapped_column(String(20), nullable=True)
    quality_flag: Mapped[Any] = mapped_column(String(10), nullable=True)


class TrafficHourlyAvg(Base):
    __tablename__ = "traffic_hourly_avg"
    __table_args__ = (
        UniqueConstraint("sdot_region_key", "day_of_week", "hour", name="uq_tha_region_dow_hr"),
        Index("idx_tha_area", "area_id"),
    )

    id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sdot_region_key: Mapped[Any] = mapped_column(String(50), nullable=False)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="SET NULL"), nullable=True
    )
    day_of_week: Mapped[Any] = mapped_column(SmallInteger, nullable=False)
    hour: Mapped[Any] = mapped_column(SmallInteger, nullable=False)
    avg_count: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=True)
    sample_weeks: Mapped[Any] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class SdotSensorMeta(Base):
    __tablename__ = "sdot_sensor_meta"
    __table_args__ = (UniqueConstraint("serial", name="uq_sensor_serial"),)

    sensor_id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial: Mapped[Any] = mapped_column(String(20), nullable=False)
    gu_name: Mapped[Any] = mapped_column(String(30), nullable=True)
    lat: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    lng: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    installed_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[Any] = mapped_column(Boolean, nullable=False, default=True)


class AreaLiveMetric(Base):
    __tablename__ = "area_live_metrics"

    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), primary_key=True
    )
    base_snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="SET NULL"), nullable=True
    )
    base_time: Mapped[Any] = mapped_column(DateTime, nullable=True)
    congestion_level: Mapped[Any] = mapped_column(String(10), nullable=True)
    congestion_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    citydata_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    sdot_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    congestion_msg: Mapped[Any] = mapped_column(Text, nullable=True)
    sdot_current_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    sdot_baseline_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    sdot_region_key_used: Mapped[Any] = mapped_column(String(50), nullable=True)
    population_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    population_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    resident_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    non_resident_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    commercial_level: Mapped[Any] = mapped_column(String(10), nullable=True)
    payment_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    payment_amt_min: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    payment_amt_max: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    weather_temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    air_idx: Mapped[Any] = mapped_column(String(10), nullable=True)
    mapping_confidence: Mapped[Any] = mapped_column(Numeric(3, 2), nullable=True)
    is_estimated: Mapped[Any] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class AreaPopulationBaseline5m(Base):
    __tablename__ = "area_population_baseline_5m"

    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), primary_key=True
    )
    day_type: Mapped[Any] = mapped_column(
        Enum(
            "all",
            "weekday",
            "weekend",
            "holiday",
            name="enum_area_population_baseline_5m_day_type",
            native_enum=False,
        ),
        primary_key=True,
        default="all",
    )
    slot_5m: Mapped[Any] = mapped_column(SmallInteger, primary_key=True)
    avg_ppltn_min: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=True)
    avg_ppltn_max: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=True)
    sample_days: Mapped[Any] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class AreaCommercialBaseline(Base):
    __tablename__ = "area_commercial_baseline"

    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), primary_key=True
    )
    day_of_week: Mapped[Any] = mapped_column(SmallInteger, primary_key=True)
    time_bucket: Mapped[Any] = mapped_column(String(10), primary_key=True)
    avg_payment_cnt: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=True)
    avg_payment_amt_min: Mapped[Any] = mapped_column(Numeric(15, 2), nullable=True)
    avg_payment_amt_max: Mapped[Any] = mapped_column(Numeric(15, 2), nullable=True)
    sample_days: Mapped[Any] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class AreaHourlyTimeseries(Base):
    __tablename__ = "area_hourly_timeseries"
    __table_args__ = (
        UniqueConstraint("area_id", "stat_date", "hour", name="uq_ts_area_date_hr"),
        Index("idx_ts_date", "stat_date"),
    )

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    stat_date: Mapped[Any] = mapped_column(Date, nullable=False)
    hour: Mapped[Any] = mapped_column(SmallInteger, nullable=False)
    actual_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    baseline_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    citydata_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    citydata_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    congestion_level: Mapped[Any] = mapped_column(String(10), nullable=True)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class AreaHourlySample(Base):
    __tablename__ = "area_hourly_samples"
    __table_args__ = (
        Index("idx_ahs_area_date_hour", "area_id", "stat_date", "hour"),
        Index("idx_ahs_area_sample_time", "area_id", "sample_time"),
    )

    sample_id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    stat_date: Mapped[Any] = mapped_column(Date, nullable=False)
    hour: Mapped[Any] = mapped_column(SmallInteger, nullable=False)
    sample_time: Mapped[Any] = mapped_column(DateTime, nullable=False)
    actual_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    baseline_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    citydata_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    citydata_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    congestion_level: Mapped[Any] = mapped_column(String(10), nullable=True)
    is_estimated: Mapped[Any] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class TrendHotPlace(Base):
    __tablename__ = "trend_hot_places"
    __table_args__ = (Index("idx_thp_area", "area_id"),)

    snapshot_time: Mapped[Any] = mapped_column(DateTime, primary_key=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[Any] = mapped_column(SmallInteger, primary_key=True)
    rank_change: Mapped[Any] = mapped_column(SmallInteger, nullable=True, default=0)
    congestion_level: Mapped[Any] = mapped_column(String(10), nullable=True)
    congestion_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    citydata_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    sdot_score: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    visitor_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class TrendRisingRegion(Base):
    __tablename__ = "trend_rising_regions"
    __table_args__ = (Index("idx_trr_area", "mapped_area_id"),)

    snapshot_time: Mapped[Any] = mapped_column(DateTime, primary_key=True)
    sdot_region_key: Mapped[Any] = mapped_column(String(50), primary_key=True)
    label: Mapped[Any] = mapped_column(String(50), nullable=True)
    visitor_avg: Mapped[Any] = mapped_column(Integer, nullable=True)
    change_pct: Mapped[Any] = mapped_column(Numeric(6, 2), nullable=True)
    change_label: Mapped[Any] = mapped_column(String(20), nullable=True)
    mapped_area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class ReviewSnapshot(Base):
    __tablename__ = "review_snapshots"
    __table_args__ = (Index("idx_rv_area", "area_id", "crawled_at"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    review_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    avg_rating: Mapped[Any] = mapped_column(Numeric(2, 1), nullable=True)
    source: Mapped[Any] = mapped_column(String(30), nullable=True)
    crawled_at: Mapped[Any] = mapped_column(DateTime, nullable=True)


class MapPalceCache(Base):
    __tablename__ = "map_palce_cache"
    __table_args__ = (
        Index("idx_mpc_query", "query_key"),
        Index("idx_mpc_expires", "expires_at"),
    )

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_key: Mapped[Any] = mapped_column(String(200), nullable=False)
    map_palce_id: Mapped[Any] = mapped_column(String(30), nullable=True)
    place_name: Mapped[Any] = mapped_column(String(200), nullable=True)
    lat: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    lng: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    payload_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
