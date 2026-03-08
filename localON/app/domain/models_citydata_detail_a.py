from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CitydataCommercialCategory(Base):
    __tablename__ = "citydata_commercial_categories"
    __table_args__ = (Index("idx_cc_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    rsb_lrg_ctgr: Mapped[Any] = mapped_column(String(50), nullable=True)
    rsb_mid_ctgr: Mapped[Any] = mapped_column(String(50), nullable=True)
    rsb_payment_lvl: Mapped[Any] = mapped_column(String(10), nullable=True)
    rsb_sh_payment_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    rsb_sh_payment_amt_min: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    rsb_sh_payment_amt_max: Mapped[Any] = mapped_column(BigInteger, nullable=True)
    rsb_mct_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    rsb_mct_time: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataRoadLink(Base):
    __tablename__ = "citydata_road_links"
    __table_args__ = (Index("idx_rl_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    road_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    start_nd_cd: Mapped[Any] = mapped_column(String(20), nullable=True)
    start_nd_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    start_nd_xy: Mapped[Any] = mapped_column(String(50), nullable=True)
    end_nd_cd: Mapped[Any] = mapped_column(String(20), nullable=True)
    end_nd_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    end_nd_xy: Mapped[Any] = mapped_column(String(50), nullable=True)
    dist: Mapped[Any] = mapped_column(Numeric(10, 2), nullable=True)
    spd: Mapped[Any] = mapped_column(Numeric(5, 1), nullable=True)
    idx_value: Mapped[Any] = mapped_column("idx", String(10), nullable=True)
    xylist: Mapped[Any] = mapped_column(Text, nullable=True)


class CitydataParkingLot(Base):
    __tablename__ = "citydata_parking_lots"
    __table_args__ = (Index("idx_pk_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    prk_cd: Mapped[Any] = mapped_column(String(20), nullable=True)
    prk_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    prk_type: Mapped[Any] = mapped_column(String(20), nullable=True)
    cpcty: Mapped[Any] = mapped_column(Integer, nullable=True)
    cur_prk_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    cur_prk_time: Mapped[Any] = mapped_column(DateTime, nullable=True)
    cur_prk_yn: Mapped[Any] = mapped_column(String(1), nullable=True)
    pay_yn: Mapped[Any] = mapped_column(String(1), nullable=True)
    rates: Mapped[Any] = mapped_column(Integer, nullable=True)
    time_rates: Mapped[Any] = mapped_column(Integer, nullable=True)
    add_rates: Mapped[Any] = mapped_column(Integer, nullable=True)
    add_time_rates: Mapped[Any] = mapped_column(Integer, nullable=True)
    road_addr: Mapped[Any] = mapped_column(String(200), nullable=True)
    address: Mapped[Any] = mapped_column(String(200), nullable=True)
    lat: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    lng: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)


class CitydataSubwayStation(Base):
    __tablename__ = "citydata_subway_stations"
    __table_args__ = (Index("idx_ss_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    sub_stn_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_stn_line: Mapped[Any] = mapped_column(String(10), nullable=True)
    sub_stn_raddr: Mapped[Any] = mapped_column(String(200), nullable=True)
    sub_stn_jibun: Mapped[Any] = mapped_column(String(200), nullable=True)
    sub_stn_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    sub_stn_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    live_sub_ppltn: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_acml_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_acml_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_acml_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_acml_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_30wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_30wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_30wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_30wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_10wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_10wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_10wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_10wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_5wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_5wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_5wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_5wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_stn_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_stn_time: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataSubwayArrival(Base):
    __tablename__ = "citydata_subway_arrivals"
    __table_args__ = (Index("idx_sa_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    sub_stn_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_route_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_line: Mapped[Any] = mapped_column(String(10), nullable=True)
    sub_ord: Mapped[Any] = mapped_column(Integer, nullable=True)
    sub_dir: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_terminal: Mapped[Any] = mapped_column(String(50), nullable=True)
    sub_arvtime: Mapped[Any] = mapped_column(String(20), nullable=True)
    sub_armg1: Mapped[Any] = mapped_column(String(200), nullable=True)
    sub_armg2: Mapped[Any] = mapped_column(String(200), nullable=True)
    sub_arvinfo: Mapped[Any] = mapped_column(String(20), nullable=True)
    sub_nt_stn: Mapped[Any] = mapped_column(String(20), nullable=True)
    sub_bf_stn: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataSubwayFacility(Base):
    __tablename__ = "citydata_subway_facilities"
    __table_args__ = (Index("idx_sf_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    sub_stn_nm: Mapped[Any] = mapped_column(String(50), nullable=True)
    elvtr_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    opr_sec: Mapped[Any] = mapped_column(String(100), nullable=True)
    instl_pstn: Mapped[Any] = mapped_column(String(100), nullable=True)
    use_yn: Mapped[Any] = mapped_column(String(10), nullable=True)
    elvtr_se: Mapped[Any] = mapped_column(String(20), nullable=True)


class CitydataBusStop(Base):
    __tablename__ = "citydata_bus_stops"
    __table_args__ = (Index("idx_bs_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    bus_stn_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    bus_ars_id: Mapped[Any] = mapped_column(String(20), nullable=True)
    bus_stn_nm: Mapped[Any] = mapped_column(String(100), nullable=True)
    bus_stn_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    bus_stn_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    live_bus_ppltn: Mapped[Any] = mapped_column(String(50), nullable=True)
    bus_acml_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_acml_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_acml_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_acml_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_30wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_30wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_30wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_30wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_10wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_10wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_10wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_10wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_5wthn_gton_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_5wthn_gton_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_5wthn_gtoff_ppltn_min: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_5wthn_gtoff_ppltn_max: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_stn_cnt: Mapped[Any] = mapped_column(Integer, nullable=True)
    bus_stn_time: Mapped[Any] = mapped_column(String(20), nullable=True)
    bus_result_msg: Mapped[Any] = mapped_column(String(200), nullable=True)


class CitydataAccident(Base):
    __tablename__ = "citydata_accidents"
    __table_args__ = (Index("idx_ac_snap", "snapshot_id"),)

    id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, ForeignKey("citydata_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False
    )
    acdnt_occr_dt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    exp_clr_dt: Mapped[Any] = mapped_column(DateTime, nullable=True)
    acdnt_type: Mapped[Any] = mapped_column(String(30), nullable=True)
    acdnt_dtype: Mapped[Any] = mapped_column(String(30), nullable=True)
    acdnt_info: Mapped[Any] = mapped_column(Text, nullable=True)
    acdnt_x: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    acdnt_y: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    acdnt_time: Mapped[Any] = mapped_column(DateTime, nullable=True)
