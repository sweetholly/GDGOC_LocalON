from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CitydataEvStation(Base):
    __tablename__ = "citydata_ev_stations"
    __table_args__ = (Index("idx_ev_stn_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    stat_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    stat_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    stat_addr: Mapped[Any] = mapped_column(String(200), nullable=True)
    stat_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    stat_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    stat_usetime: Mapped[Any] = mapped_column(String(100), nullable=True)
    stat_parkpay: Mapped[Any] = mapped_column(String(10), nullable=True)
    stat_limityn: Mapped[Any] = mapped_column(String(10), nullable=True)
    stat_limitdetail: Mapped[Any] = mapped_column(String(200), nullable=True)
    stat_kinddetail: Mapped[Any] = mapped_column(String(50), nullable=True)


class CitydataEvCharger(Base):
    __tablename__ = "citydata_ev_chargers"
    __table_args__ = (Index("idx_ev_chg_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    stat_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    charger_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    charger_type: Mapped[Any] = mapped_column(String(20), nullable=True)
    charger_stat: Mapped[Any] = mapped_column(String(20), nullable=True)
    statuppdt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    lasttsdt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    lasttedt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    nowtsdt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    output: Mapped[Any] = mapped_column(String(20), nullable=True)
    method: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataBikeStation(Base):
    __tablename__ = "citydata_bike_stations"
    __table_args__ = (Index("idx_bk_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    sbike_spot_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    sbike_spot_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    sbike_shared: Mapped[Any] = mapped_column(Numeric(5, 2), nullable=True)
    sbike_parking_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    sbike_rack_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    sbike_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    sbike_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)


class CitydataWeatherWarning(Base):
    __tablename__ = "citydata_weather_warnings"
    __table_args__ = (Index("idx_ww_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    warn_val: Mapped[Any] = mapped_column(String(30), nullable=True)
    warn_stress: Mapped[Any] = mapped_column(String(30), nullable=True)
    announce_time: Mapped[Any] = mapped_column(DateTime, nullable=True)
    command: Mapped[Any] = mapped_column(String(20), nullable=True)
    cancel_yn: Mapped[Any] = mapped_column(String(1), nullable=True)
    warn_msg: Mapped[Any] = mapped_column(Text, nullable=True)


class CitydataWeatherForecast(Base):
    __tablename__ = "citydata_weather_forecasts"
    __table_args__ = (Index("idx_wf_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    fcst_dt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    temp: Mapped[Any] = mapped_column(Numeric(4, 1), nullable=True)
    precipitation: Mapped[Any] = mapped_column(Numeric(5, 1), nullable=True)
    precpt_type: Mapped[Any] = mapped_column(String(10), nullable=True)
    rain_chance: Mapped[Any] = mapped_column(Integer, nullable=True)
    sky_stts: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataCulturalEvent(Base):
    __tablename__ = "citydata_cultural_events"
    __table_args__ = (Index("idx_ce_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    event_nm: Mapped[Any] = mapped_column(String(200), nullable=True)
    event_period: Mapped[Any] = mapped_column(String(100), nullable=True)
    event_place: Mapped[Any] = mapped_column(String(200), nullable=True)
    event_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    event_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    pay_yn: Mapped[Any] = mapped_column(String(10), nullable=True)
    thumbnail: Mapped[Any] = mapped_column(Text, nullable=True)
    url: Mapped[Any] = mapped_column(Text, nullable=True)
    event_etc_detail: Mapped[Any] = mapped_column(Text, nullable=True)


class CitydataDisasterMessage(Base):
    __tablename__ = "citydata_disaster_messages"
    __table_args__ = (Index("idx_dm_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    dst_se_nm: Mapped[Any] = mapped_column(String(30), nullable=True)
    emrg_step_nm: Mapped[Any] = mapped_column(String(30), nullable=True)
    msg_cn: Mapped[Any] = mapped_column(Text, nullable=True)
    crt_dt: Mapped[Any] = mapped_column(DateTime, nullable=True)


class CitydataYnaNews(Base):
    __tablename__ = "citydata_yna_news"
    __table_args__ = (Index("idx_yn_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    yna_step_nm: Mapped[Any] = mapped_column(String(30), nullable=True)
    yna_ttl: Mapped[Any] = mapped_column(String(300), nullable=True)
    yna_cn: Mapped[Any] = mapped_column(Text, nullable=True)
    yna_ymd: Mapped[Any] = mapped_column(String(20), nullable=True)
    yna_wrtr_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
