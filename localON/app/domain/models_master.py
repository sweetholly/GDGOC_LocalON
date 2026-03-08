from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (
        UniqueConstraint("area_cd", name="uq_area_cd"),
        UniqueConstraint("area_nm", name="uq_area_nm"),
    )

    area_id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_cd: Mapped[Any] = mapped_column(String(10), nullable=False)
    area_nm: Mapped[Any] = mapped_column(String(100), nullable=False)
    eng_nm: Mapped[Any] = mapped_column(String(200), nullable=True)
    district: Mapped[Any] = mapped_column(String(30), nullable=True)
    ui_category: Mapped[Any] = mapped_column(String(30), nullable=True)
    lat: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    lng: Mapped[Any] = mapped_column(Numeric(11, 8), nullable=True)
    radius_m: Mapped[Any] = mapped_column(Integer, nullable=False, default=500)
    description: Mapped[Any] = mapped_column(Text, nullable=True)
    is_active: Mapped[Any] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime, nullable=True, onupdate=text("CURRENT_TIMESTAMP")
    )


class AreaAlias(Base):
    __tablename__ = "area_aliases"
    __table_args__ = (
        Index("idx_alias_area", "area_id"),
        Index("idx_alias_value", "alias_value"),
    )

    alias_id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    alias_type: Mapped[Any] = mapped_column(
        Enum(
            "display",
            "search",
            "legacy",
            "map",
            name="enum_area_aliases_alias_type",
            native_enum=False,
        ),
        nullable=False,
        default="search",
    )
    alias_value: Mapped[Any] = mapped_column(String(200), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CollectorRun(Base):
    __tablename__ = "collector_runs"
    __table_args__ = (Index("idx_collector_src_time", "source_name", "started_at"),)

    run_id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[Any] = mapped_column(String(30), nullable=False)
    started_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    status: Mapped[Any] = mapped_column(
        Enum(
            "running",
            "success",
            "partial",
            "failed",
            name="enum_collector_runs_status",
            native_enum=False,
        ),
        nullable=False,
        default="running",
    )
    target_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    success_count: Mapped[Any] = mapped_column(Integer, nullable=True, default=0)
    fail_count: Mapped[Any] = mapped_column(Integer, nullable=True, default=0)
    error_message: Mapped[Any] = mapped_column(Text, nullable=True)


class RawCitydataResponse(Base):
    __tablename__ = "raw_citydata_responses"
    __table_args__ = (Index("idx_raw_city_area_time", "area_id", "fetched_at"),)

    raw_id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    request_area_nm: Mapped[Any] = mapped_column(String(100), nullable=False)
    request_area_cd: Mapped[Any] = mapped_column(String(10), nullable=True)
    fetched_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    result_code: Mapped[Any] = mapped_column(String(20), nullable=True)
    result_message: Mapped[Any] = mapped_column(String(200), nullable=True)
    payload_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[Any] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class CitydataSnapshot(Base):
    __tablename__ = "citydata_snapshots"
    __table_args__ = (
        UniqueConstraint("area_id", "fetched_at", name="uq_snap_area_fetched"),
        Index("idx_snap_fetched", "fetched_at"),
    )

    snapshot_id: Mapped[Any] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    raw_id: Mapped[Any] = mapped_column(
        BigInteger,
        ForeignKey("raw_citydata_responses.raw_id", ondelete="SET NULL"),
        nullable=True,
    )
    area_cd: Mapped[Any] = mapped_column(String(10), nullable=False)
    area_nm: Mapped[Any] = mapped_column(String(100), nullable=False)
    replace_yn: Mapped[Any] = mapped_column(String(1), nullable=True)
    fetched_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class AreaSdotRegionMapping(Base):
    __tablename__ = "area_sdot_region_mappings"
    __table_args__ = (
        Index("idx_sdot_map_region", "sdot_region_key"),
        Index("idx_sdot_map_area_pri", "area_id", "is_primary"),
    )

    mapping_id: Mapped[Any] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_id: Mapped[Any] = mapped_column(
        Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False
    )
    sdot_region_key: Mapped[Any] = mapped_column(String(50), nullable=False)
    sdot_region_name: Mapped[Any] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[Any] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[Any] = mapped_column(Numeric(3, 2), nullable=False, default=0.00)
    note: Mapped[Any] = mapped_column(Text, nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime, nullable=True, onupdate=text("CURRENT_TIMESTAMP")
    )


class RawSdotResponse(Base):
    __tablename__ = "raw_sdot_responses"
    __table_args__ = (Index("idx_raw_sdot_time", "fetched_at"),)

    raw_id: Mapped[Any] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fetched_at: Mapped[Any] = mapped_column(DateTime, nullable=False)
    payload_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[Any] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
