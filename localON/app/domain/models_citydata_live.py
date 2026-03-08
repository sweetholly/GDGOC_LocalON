from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CitydataLivePopulation(Base):
    __tablename__ = "citydata_live_population"

    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), primary_key=True
    )
    source_updated_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    area_congest_lvl: Mapped[Any] = mapped_column(String(10), nullable=True)
    area_congest_msg: Mapped[Any] = mapped_column(Text, nullable=True)
    area_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    area_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    male_ppltn_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    female_ppltn_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_0: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_10: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_20: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_30: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_40: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_50: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_60: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    ppltn_rate_70: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    resnt_ppltn_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    non_resnt_ppltn_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    fcst_yn: Mapped[Any] = mapped_column(String(1), nullable=True)
    fcst_ppltn: Mapped[Any] = mapped_column(JSON, nullable=True)
    fcst_time: Mapped[Any] = mapped_column(DateTime, nullable=True)
    fcst_congest_lvl: Mapped[Any] = mapped_column(String(10), nullable=True)
    fcst_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    fcst_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)


class CitydataLiveCommercialSummary(Base):
    __tablename__ = "citydata_live_commercial_summary"

    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), primary_key=True
    )
    source_updated_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    area_cmrcl_lvl: Mapped[Any] = mapped_column(String(10), nullable=True)
    area_sh_payment_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    area_sh_payment_amt_min: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    area_sh_payment_amt_max: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    cmrcl_male_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_female_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_10_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_20_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_30_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_40_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_50_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_60_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_personal_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    cmrcl_corporation_rate: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)


class CitydataRoadSummary(Base):
    __tablename__ = "citydata_road_summary"

    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), primary_key=True
    )
    source_updated_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    road_traffic_spd: Mapped[Any] = mapped_column(Numeric(5, 1), nullable=True)
    road_traffic_idx: Mapped[Any] = mapped_column(String(10), nullable=True)
    road_msg: Mapped[Any] = mapped_column(Text, nullable=True)


class CitydataWeatherCurrent(Base):
    __tablename__ = "citydata_weather_current"

    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), primary_key=True
    )
    source_updated_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    sensible_temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    max_temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    min_temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    humidity: Mapped[Any] = mapped_column(Integer, nullable=True)
    wind_dirct: Mapped[Any] = mapped_column(String(10), nullable=True)
    wind_spd: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    precipitation: Mapped[Any] = mapped_column(Numeric(5, 1), nullable=True)
    precpt_type: Mapped[Any] = mapped_column(String(10), nullable=True)
    pcp_msg: Mapped[Any] = mapped_column(Text, nullable=True)
    sunrise: Mapped[Any] = mapped_column(String(10), nullable=True)
    sunset: Mapped[Any] = mapped_column(String(10), nullable=True)
    uv_index_lvl: Mapped[Any] = mapped_column(String(10), nullable=True)
    uv_index: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    uv_msg: Mapped[Any] = mapped_column(Text, nullable=True)
    pm25_index: Mapped[Any] = mapped_column(String(10), nullable=True)
    pm25: Mapped[Any] = mapped_column(Numeric(6, 1), nullable=True)
    pm10_index: Mapped[Any] = mapped_column(String(10), nullable=True)
    pm10: Mapped[Any] = mapped_column(Numeric(6, 1), nullable=True)
    air_idx: Mapped[Any] = mapped_column(String(10), nullable=True)
    air_idx_mvl: Mapped[Any] = mapped_column(Numeric(6, 1), nullable=True)
    air_idx_main: Mapped[Any] = mapped_column(String(20), nullable=True)
    air_msg: Mapped[Any] = mapped_column(Text, nullable=True)
