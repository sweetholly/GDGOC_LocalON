from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain import (
    Area,
    AreaAlias,
    AreaHourlySample,
    AreaHourlyTimeseries,
    AreaLiveMetric,
    AreaSdotRegionMapping,
    CitydataLiveCommercialSummary,
    CitydataLivePopulation,
    CitydataRoadSummary,
    CitydataSnapshot,
    CitydataWeatherCurrent,
    CollectorRun,
    RawCitydataResponse,
    RawSdotResponse,
    SdotSensorMeta,
    SdotTrafficRaw,
    get_session_maker,
)

from .normalizers import (
    as_dict,
    extract_openapi_container,
    extract_openapi_rows,
    hash_payload,
    normalize_region_key,
    normalize_text,
    now_utc_naive,
    pick_first,
    to_datetime,
    to_decimal,
    to_int,
)
from .openapi_client import SeoulOpenApiClient
from .sdot_sensor_seed import SEOUL_SDOT_SENSOR_META
from .settings import CollectorSettings
from .top120_places import SEOUL_TOP120_PLACES


class SeoulDataCollector:
    """서울시 도시데이터 + S-DoT 데이터를 수집/통합하는 메인 서비스."""

    def __init__(
        self,
        settings: CollectorSettings,
        *,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.settings = settings
        self.session_maker = session_maker or get_session_maker()
        self.logger = logging.getLogger("collector")

    async def run_once(self) -> None:
        """한 번의 수집 사이클을 실행한다."""
        self._ensure_input_files()

        async with self.session_maker() as session:
            area_count = await self._sync_area_master(session)
            sensor_meta_count = await self._sync_sensor_meta(session)
            await session.commit()
            self.logger.info(
                "마스터 동기화 완료: areas=%s, sensor_meta=%s",
                area_count,
                sensor_meta_count,
            )

            async with SeoulOpenApiClient(self.settings) as client:
                await self._run_citydata_cycle(session, client)
                await session.commit()

                await self._run_sdot_cycle(session, client)
                await self._refresh_area_live_metrics(session)
                await session.commit()

    async def run_forever(self) -> None:
        """설정된 주기로 수집 사이클을 무한 반복한다."""
        while True:
            started_at = now_utc_naive()
            try:
                await self.run_once()
            except Exception:
                self.logger.exception("수집 사이클 실패")

            elapsed = (now_utc_naive() - started_at).total_seconds()
            sleep_seconds = max(1, self.settings.interval_seconds - int(elapsed))
            await asyncio.sleep(sleep_seconds)

    def _ensure_input_files(self) -> None:
        """파일 입력 의존성을 제거했으므로 현재는 검사 대상이 없다."""
        return None

    async def _sync_area_master(self, session: AsyncSession) -> int:
        """코드 내장 120장소 목록을 기준으로 areas 테이블을 업서트한다."""
        records = SEOUL_TOP120_PLACES

        existing_areas = {
            area.area_cd: area for area in (await session.scalars(select(Area))).all()
        }
        touched_areas: list[Area] = []

        for record in records:
            area_cd = normalize_text(record.get("AREA_CD"))
            area_nm = normalize_text(record.get("AREA_NM"))
            if not area_cd or not area_nm:
                continue

            area = existing_areas.get(area_cd)
            if area is None:
                area = Area(
                    area_cd=area_cd,
                    area_nm=area_nm,
                    radius_m=500,
                    is_active=True,
                )
                session.add(area)
                existing_areas[area_cd] = area

            area.area_nm = area_nm
            area.eng_nm = normalize_text(record.get("ENG_NM"))
            area.ui_category = normalize_text(record.get("CATEGORY"))
            area.lat = to_decimal(record.get("LAT"))
            area.lng = to_decimal(record.get("LNG")) 
            area.is_active = True
            touched_areas.append(area)

        await session.flush()
        await self._sync_area_aliases(session, touched_areas)
        return len(touched_areas)

    async def _sync_area_aliases(self, session: AsyncSession, areas: list[Area]) -> None:
        """검색/매핑 정확도를 위해 area_aliases를 자동 보강한다."""
        area_ids = [area.area_id for area in areas if area.area_id is not None]
        if not area_ids:
            return

        alias_rows = (
            await session.execute(
                select(AreaAlias.area_id, AreaAlias.alias_value).where(
                    AreaAlias.area_id.in_(area_ids)
                )
            )
        ).all()
        existing_aliases = {(row[0], row[1]) for row in alias_rows}

        for area in areas:
            if area.area_id is None:
                continue

            aliases = {area.area_nm}
            compact_name = re.sub(r"\s+", "", area.area_nm)
            if compact_name:
                aliases.add(compact_name)

            for alias in aliases:
                key = (area.area_id, alias)
                if key in existing_aliases:
                    continue
                session.add(
                    AreaAlias(
                        area_id=area.area_id,
                        alias_type="search",
                        alias_value=alias,
                    )
                )
                existing_aliases.add(key)

    async def _sync_sensor_meta(self, session: AsyncSession) -> int:
        """코드 내장 센서 메타 목록을 기준으로 sdot_sensor_meta를 업서트한다."""
        records = SEOUL_SDOT_SENSOR_META

        existing_meta = {
            meta.serial: meta
            for meta in (await session.scalars(select(SdotSensorMeta))).all()
        }
        touched = 0

        for record in records:
            serial = normalize_text(pick_first(record, "SERIAL", "serial", "SERIAL_NO"))
            if not serial:
                continue

            sensor_meta = existing_meta.get(serial)
            if sensor_meta is None:
                sensor_meta = SdotSensorMeta(serial=serial, is_active=True)
                session.add(sensor_meta)
                existing_meta[serial] = sensor_meta

            address = normalize_text(pick_first(record, "ADDRESS", "address"))
            gu_name = normalize_text(pick_first(record, "GU_NAME")) or self._extract_gu_name(
                address
            )
            sensor_meta.gu_name = gu_name
            sensor_meta.lat = to_decimal(pick_first(record, "LAT", "lat"))
            sensor_meta.lng = to_decimal(pick_first(record, "LNG", "lng"))
            sensor_meta.is_active = True
            touched += 1

        return touched

    async def _run_citydata_cycle(
        self, session: AsyncSession, client: SeoulOpenApiClient
    ) -> None:
        """120장소를 순회하며 도시데이터를 수집하고 스냅샷으로 저장한다."""
        areas = (
            await session.scalars(
                select(Area).where(Area.is_active.is_(True)).order_by(Area.area_cd)
            )
        ).all()
        run = await self._start_run(session, source_name="citydata", target_count=len(areas))
        error_messages: list[str] = []

        try:
            for area in areas:
                try:
                    payload = await client.fetch_citydata(area.area_nm)
                    await self._save_citydata_payload(session, area, payload)
                    run.success_count = (run.success_count or 0) + 1
                except Exception as exc:
                    run.fail_count = (run.fail_count or 0) + 1
                    message = f"{area.area_nm}: {exc}"
                    if len(error_messages) < 5:
                        error_messages.append(message)
                    self.logger.warning("도시데이터 수집 실패 - %s", message)
        finally:
            await self._finish_run(session, run, error_messages)

    async def _save_citydata_payload(
        self, session: AsyncSession, area: Area, payload: dict[str, Any]
    ) -> None:
        """도시데이터 원본 + 요약 테이블을 함께 적재한다."""
        container = extract_openapi_container(payload, preferred_key="CITYDATA")
        if not container:
            container = extract_openapi_container(payload, preferred_key="citydata")

        row: dict[str, Any] = {}
        result: dict[str, Any] = {}
        if isinstance(container, dict):
            result = as_dict(pick_first(container, "RESULT", "Result"))

            citydata = pick_first(container, "CITYDATA", "citydata")
            if isinstance(citydata, dict):
                row = citydata
            elif isinstance(citydata, list):
                row = as_dict(citydata)

            if row and "AREA_CD" not in row:
                nested_rows = pick_first(row, "row", "ROW")
                if isinstance(nested_rows, dict):
                    row = nested_rows
                elif isinstance(nested_rows, list):
                    row = as_dict(nested_rows)

            if not row:
                rows = pick_first(container, "row", "ROW")
                if isinstance(rows, dict):
                    row = rows
                elif isinstance(rows, list):
                    row = as_dict(rows)

        fetched_at = self._extract_citydata_time(row) or now_utc_naive()
        raw = RawCitydataResponse(
            area_id=area.area_id,
            request_area_nm=area.area_nm,
            request_area_cd=area.area_cd,
            fetched_at=fetched_at,
            result_code=normalize_text(
                pick_first(result, "CODE", "RESULT.CODE", "resultCode")
            ),
            result_message=normalize_text(
                pick_first(result, "MESSAGE", "RESULT.MESSAGE", "resultMsg")
            ),
            payload_json=payload,
            payload_hash=hash_payload(payload),
        )
        session.add(raw)
        await session.flush()

        snapshot = await session.scalar(
            select(CitydataSnapshot).where(
                CitydataSnapshot.area_id == area.area_id,
                CitydataSnapshot.fetched_at == fetched_at,
            )
        )
        if snapshot is None:
            snapshot = CitydataSnapshot(
                area_id=area.area_id,
                raw_id=raw.raw_id,
                area_cd=normalize_text(pick_first(row, "AREA_CD")) or area.area_cd,
                area_nm=normalize_text(pick_first(row, "AREA_NM")) or area.area_nm,
                replace_yn=normalize_text(pick_first(row, "REPLACE_YN")),
                fetched_at=fetched_at,
            )
            session.add(snapshot)
            await session.flush()
        else:
            snapshot.raw_id = raw.raw_id

        await self._upsert_citydata_live_tables(session, snapshot.snapshot_id, row)

    async def _upsert_citydata_live_tables(
        self, session: AsyncSession, snapshot_id: int, row: dict[str, Any]
    ) -> None:
        """서비스 조회에 필요한 도시데이터 핵심 live 요약 테이블만 갱신한다."""
        # 기존 1:1 레코드를 삭제한 뒤 재삽입하면 재수집 시에도 일관성이 유지된다.
        await session.execute(
            delete(CitydataLivePopulation).where(
                CitydataLivePopulation.snapshot_id == snapshot_id
            )
        )
        await session.execute(
            delete(CitydataLiveCommercialSummary).where(
                CitydataLiveCommercialSummary.snapshot_id == snapshot_id
            )
        )
        await session.execute(
            delete(CitydataRoadSummary).where(CitydataRoadSummary.snapshot_id == snapshot_id)
        )
        await session.execute(
            delete(CitydataWeatherCurrent).where(
                CitydataWeatherCurrent.snapshot_id == snapshot_id
            )
        )

        live_pop = self._build_live_population(snapshot_id, row)
        if live_pop:
            session.add(live_pop)

        live_cmrcl = self._build_live_commercial(snapshot_id, row)
        if live_cmrcl:
            session.add(live_cmrcl)

        road = self._build_road_summary(snapshot_id, row)
        if road:
            session.add(road)

        weather = self._build_weather_current(snapshot_id, row)
        if weather:
            session.add(weather)

    def _build_live_population(
        self, snapshot_id: int, row: dict[str, Any]
    ) -> CitydataLivePopulation | None:
        """LIVE_PPLTN_STTS에서 인구 요약 데이터를 매핑한다."""
        section = as_dict(pick_first(row, "LIVE_PPLTN_STTS", "live_ppltn_stts"))
        section = self._unwrap_single_wrapper(
            section, "LIVE_PPLTN_STTS", "live_ppltn_stts"
        )
        source = section or row
        fcst_payload = pick_first(source, "FCST_PPLTN", "FCST_PPLTN_LIST")
        fcst_container = as_dict(fcst_payload)
        if fcst_container:
            nested_fcst = pick_first(fcst_container, "FCST_PPLTN", "row", "ROW")
            if nested_fcst is not None:
                fcst_payload = nested_fcst
        fcst_first = as_dict(fcst_payload)

        payload = CitydataLivePopulation(
            snapshot_id=snapshot_id,
            source_updated_at=to_datetime(
                pick_first(source, "PPLTN_TIME", "PPLTN_TM", "UPDATE_TIME")
            ),
            area_congest_lvl=normalize_text(
                pick_first(source, "AREA_CONGEST_LVL", "CONGESTION_LEVEL")
            ),
            area_congest_msg=normalize_text(pick_first(source, "AREA_CONGEST_MSG")),
            area_ppltn_min=to_int(pick_first(source, "AREA_PPLTN_MIN", "LIVE_PPLTN_MIN")),
            area_ppltn_max=to_int(pick_first(source, "AREA_PPLTN_MAX", "LIVE_PPLTN_MAX")),
            male_ppltn_rate=to_decimal(pick_first(source, "MALE_PPLTN_RATE")),
            female_ppltn_rate=to_decimal(pick_first(source, "FEMALE_PPLTN_RATE")),
            ppltn_rate_0=to_decimal(pick_first(source, "PPLTN_RATE_0")),
            ppltn_rate_10=to_decimal(pick_first(source, "PPLTN_RATE_10")),
            ppltn_rate_20=to_decimal(pick_first(source, "PPLTN_RATE_20")),
            ppltn_rate_30=to_decimal(pick_first(source, "PPLTN_RATE_30")),
            ppltn_rate_40=to_decimal(pick_first(source, "PPLTN_RATE_40")),
            ppltn_rate_50=to_decimal(pick_first(source, "PPLTN_RATE_50")),
            ppltn_rate_60=to_decimal(pick_first(source, "PPLTN_RATE_60")),
            ppltn_rate_70=to_decimal(pick_first(source, "PPLTN_RATE_70")),
            resnt_ppltn_rate=to_decimal(pick_first(source, "RESNT_PPLTN_RATE")),
            non_resnt_ppltn_rate=to_decimal(pick_first(source, "NON_RESNT_PPLTN_RATE")),
            fcst_yn=normalize_text(pick_first(source, "FCST_YN")),
            fcst_ppltn=fcst_payload if isinstance(fcst_payload, (list, dict)) else None,
            fcst_time=to_datetime(pick_first(fcst_first, "FCST_TIME", "PPLTN_TIME")),
            fcst_congest_lvl=normalize_text(
                pick_first(fcst_first, "FCST_CONGEST_LVL", "AREA_CONGEST_LVL")
            ),
            fcst_ppltn_min=to_int(pick_first(fcst_first, "FCST_PPLTN_MIN")),
            fcst_ppltn_max=to_int(pick_first(fcst_first, "FCST_PPLTN_MAX")),
        )

        if self._is_empty_model(payload, ignore_fields={"snapshot_id"}):
            return None
        return payload

    def _build_live_commercial(
        self, snapshot_id: int, row: dict[str, Any]
    ) -> CitydataLiveCommercialSummary | None:
        """LIVE_CMRCL_STTS에서 상권 요약 데이터를 매핑한다."""
        section = as_dict(pick_first(row, "LIVE_CMRCL_STTS", "live_cmrcl_stts"))
        section = self._unwrap_single_wrapper(
            section, "LIVE_CMRCL_STTS", "live_cmrcl_stts"
        )
        if not section:
            return None

        payload = CitydataLiveCommercialSummary(
            snapshot_id=snapshot_id,
            source_updated_at=to_datetime(
                pick_first(section, "CMRCL_TIME", "UPDATE_TIME", "PPLTN_TIME")
            ),
            area_cmrcl_lvl=normalize_text(
                pick_first(section, "AREA_CMRCL_LVL", "CMRCL_LVL")
            ),
            area_sh_payment_cnt=to_int(
                pick_first(section, "AREA_SH_PAYMENT_CNT", "PAYMENT_CNT")
            ),
            area_sh_payment_amt_min=to_int(
                pick_first(section, "AREA_SH_PAYMENT_AMT_MIN", "PAYMENT_AMT_MIN")
            ),
            area_sh_payment_amt_max=to_int(
                pick_first(section, "AREA_SH_PAYMENT_AMT_MAX", "PAYMENT_AMT_MAX")
            ),
            cmrcl_male_rate=to_decimal(pick_first(section, "CMRCL_MALE_RATE")),
            cmrcl_female_rate=to_decimal(pick_first(section, "CMRCL_FEMALE_RATE")),
            cmrcl_10_rate=to_decimal(pick_first(section, "CMRCL_10_RATE")),
            cmrcl_20_rate=to_decimal(pick_first(section, "CMRCL_20_RATE")),
            cmrcl_30_rate=to_decimal(pick_first(section, "CMRCL_30_RATE")),
            cmrcl_40_rate=to_decimal(pick_first(section, "CMRCL_40_RATE")),
            cmrcl_50_rate=to_decimal(pick_first(section, "CMRCL_50_RATE")),
            cmrcl_60_rate=to_decimal(pick_first(section, "CMRCL_60_RATE")),
            cmrcl_personal_rate=to_decimal(pick_first(section, "CMRCL_PERSONAL_RATE")),
            cmrcl_corporation_rate=to_decimal(
                pick_first(section, "CMRCL_CORPORATION_RATE")
            ),
        )
        if self._is_empty_model(payload, ignore_fields={"snapshot_id"}):
            return None
        return payload

    def _build_road_summary(
        self, snapshot_id: int, row: dict[str, Any]
    ) -> CitydataRoadSummary | None:
        """ROAD_TRAFFIC_STTS에서 교통 요약 데이터를 매핑한다."""
        section = as_dict(pick_first(row, "ROAD_TRAFFIC_STTS", "road_traffic_stts"))
        if not section:
            return None
        source = as_dict(pick_first(section, "AVG_ROAD_DATA", "avg_road_data")) or section

        payload = CitydataRoadSummary(
            snapshot_id=snapshot_id,
            source_updated_at=to_datetime(
                pick_first(source, "ROAD_TRAFFIC_TIME", "UPDATE_TIME")
            ),
            road_traffic_spd=to_decimal(
                pick_first(source, "ROAD_TRAFFIC_SPD", "AVG_SPD", "ROAD_AVG_SPD")
            ),
            road_traffic_idx=normalize_text(
                pick_first(source, "ROAD_TRAFFIC_IDX", "ROAD_TRAFFIC_INDEX")
            ),
            road_msg=normalize_text(pick_first(source, "ROAD_MSG", "ROAD_TRAFFIC_MSG")),
        )
        if self._is_empty_model(payload, ignore_fields={"snapshot_id"}):
            return None
        return payload

    def _build_weather_current(
        self, snapshot_id: int, row: dict[str, Any]
    ) -> CitydataWeatherCurrent | None:
        """WEATHER_STTS에서 날씨 요약 데이터를 매핑한다."""
        section = as_dict(pick_first(row, "WEATHER_STTS", "weather_stts"))
        section = self._unwrap_single_wrapper(section, "WEATHER_STTS", "weather_stts")
        if not section:
            return None

        payload = CitydataWeatherCurrent(
            snapshot_id=snapshot_id,
            source_updated_at=to_datetime(
                pick_first(section, "WEATHER_TIME", "UPDATE_TIME")
            ),
            temp=to_decimal(pick_first(section, "TEMP")),
            sensible_temp=to_decimal(pick_first(section, "SENSIBLE_TEMP")),
            max_temp=to_decimal(pick_first(section, "MAX_TEMP")),
            min_temp=to_decimal(pick_first(section, "MIN_TEMP")),
            humidity=to_int(pick_first(section, "HUMIDITY")),
            wind_dirct=normalize_text(pick_first(section, "WIND_DIRCT")),
            wind_spd=to_decimal(pick_first(section, "WIND_SPD")),
            precipitation=to_decimal(pick_first(section, "PRECIPITATION")),
            precpt_type=normalize_text(pick_first(section, "PRECPT_TYPE")),
            pcp_msg=normalize_text(pick_first(section, "PCP_MSG")),
            sunrise=normalize_text(pick_first(section, "SUNRISE")),
            sunset=normalize_text(pick_first(section, "SUNSET")),
            uv_index_lvl=normalize_text(pick_first(section, "UV_INDEX_LVL")),
            uv_index=to_decimal(pick_first(section, "UV_INDEX")),
            uv_msg=normalize_text(pick_first(section, "UV_MSG")),
            pm25_index=normalize_text(pick_first(section, "PM25_INDEX")),
            pm25=to_decimal(pick_first(section, "PM25")),
            pm10_index=normalize_text(pick_first(section, "PM10_INDEX")),
            pm10=to_decimal(pick_first(section, "PM10")),
            air_idx=normalize_text(pick_first(section, "AIR_IDX")),
            air_idx_mvl=to_decimal(pick_first(section, "AIR_IDX_MVL")),
            air_idx_main=normalize_text(pick_first(section, "AIR_IDX_MAIN")),
            air_msg=normalize_text(pick_first(section, "AIR_MSG")),
        )
        if self._is_empty_model(payload, ignore_fields={"snapshot_id"}):
            return None
        return payload

    async def _run_sdot_cycle(
        self, session: AsyncSession, client: SeoulOpenApiClient
    ) -> None:
        """S-DoT 센서 데이터를 수집하고 REGION 기준으로 area와 매핑한다."""
        run = await self._start_run(session, source_name="sdot", target_count=None)
        error_messages: list[str] = []

        try:
            payload = await client.fetch_sdot()
            rows = extract_openapi_rows(payload, preferred_key=self.settings.sdot_service_name)
            if not rows:
                rows = extract_openapi_rows(
                    payload, preferred_key=self.settings.sdot_service_name.upper()
                )
            if not rows:
                rows = extract_openapi_rows(
                    payload, preferred_key=self.settings.sdot_service_name.lower()
                )
            if not rows:
                rows = extract_openapi_rows(payload)

            run.target_count = len(rows)
            fetched_at = now_utc_naive()
            raw = RawSdotResponse(
                fetched_at=fetched_at,
                payload_json=payload,
                payload_hash=hash_payload(payload),
            )
            session.add(raw)

            mapping_by_region, area_lookup, area_has_primary = await self._prepare_region_context(
                session
            )
            sensor_area_lookup = await self._build_sensor_area_lookup(session)

            for row in rows:
                source_serial = normalize_text(
                    pick_first(row, "SERIAL_NO", "SERIAL", "DEVICE_ID")
                )
                normalized_sensor_code = self._normalize_sensor_code(source_serial)

                region_name = normalize_text(
                    pick_first(
                        row,
                        "REGION",
                        "REGION_NM",
                        "AREA_NM",
                        "region",
                        "지역",
                        "위치명",
                    )
                )
                region_key = normalize_region_key(
                    pick_first(row, "REGION_KEY", "REGION_CD", "region_key")
                ) or normalize_region_key(region_name)

                resolved_area_id, confidence = self._resolve_area_by_region(
                    session=session,
                    region_key=region_key,
                    region_name=region_name,
                    mapping_by_region=mapping_by_region,
                    area_lookup=area_lookup,
                    area_has_primary=area_has_primary,
                )
                if resolved_area_id is None and normalized_sensor_code:
                    sensor_mapped = sensor_area_lookup.get(normalized_sensor_code)
                    if sensor_mapped:
                        resolved_area_id, confidence = sensor_mapped

                record = SdotTrafficRaw(
                    sdot_region_key=region_key or "UNKNOWN",
                    sdot_region_name=region_name,
                    area_id=resolved_area_id,
                    visitor_count=self._extract_sdot_visitor_count(row),
                    sensing_time=to_datetime(
                        pick_first(
                            row,
                            "SENSING_TIME",
                            "TM",
                            "COLLECT_TIME",
                            "STDR_DE",
                            "PPLTN_TIME",
                            "PPLTN_TIME_SE",
                            "REG_YMDHMS",
                            "PRCSS_YMD",
                        )
                    )
                    or fetched_at,
                    fetched_at=fetched_at,
                    source_serial=normalized_sensor_code or source_serial,
                    quality_flag=normalize_text(
                        pick_first(row, "QUALITY_FLAG", "DATA_QUALITY", "STATUS")
                    ),
                )
                session.add(record)
                run.success_count = (run.success_count or 0) + 1

                if resolved_area_id and confidence is not None:
                    self.logger.debug(
                        "REGION 매핑 성공: region_key=%s -> area_id=%s (confidence=%s)",
                        region_key,
                        resolved_area_id,
                        confidence,
                    )
        except Exception as exc:
            run.fail_count = (run.fail_count or 0) + 1
            error_messages.append(str(exc))
            self.logger.warning("S-DoT 수집 실패 - %s", exc)
        finally:
            await self._finish_run(session, run, error_messages)

    async def _prepare_region_context(
        self, session: AsyncSession
    ) -> tuple[dict[str, tuple[int | None, Decimal | None]], dict[str, int], set[int]]:
        """REGION 매핑에 필요한 캐시를 구성한다."""
        mapping_rows = (
            await session.scalars(
                select(AreaSdotRegionMapping).order_by(
                    desc(AreaSdotRegionMapping.is_primary),
                    desc(AreaSdotRegionMapping.confidence),
                    AreaSdotRegionMapping.mapping_id,
                )
            )
        ).all()

        mapping_by_region: dict[str, tuple[int | None, Decimal | None]] = {}
        area_has_primary: set[int] = set()
        for mapping in mapping_rows:
            if mapping.is_primary and mapping.area_id is not None:
                area_has_primary.add(mapping.area_id)
            key = normalize_region_key(mapping.sdot_region_key)
            if key and key not in mapping_by_region:
                mapping_by_region[key] = (mapping.area_id, mapping.confidence)

        area_lookup = await self._build_area_lookup(session)
        return mapping_by_region, area_lookup, area_has_primary

    def _resolve_area_by_region(
        self,
        *,
        session: AsyncSession,
        region_key: str | None,
        region_name: str | None,
        mapping_by_region: dict[str, tuple[int | None, Decimal | None]],
        area_lookup: dict[str, int],
        area_has_primary: set[int],
    ) -> tuple[int | None, Decimal | None]:
        """REGION 값으로 area_id를 찾고, 필요시 자동 매핑 행을 생성한다."""
        if not region_key:
            return None, None

        if region_key in mapping_by_region:
            return mapping_by_region[region_key]

        area_id = area_lookup.get(region_key)
        if area_id is None and region_name:
            area_id = area_lookup.get(normalize_region_key(region_name) or "")

        if area_id is None:
            return None, None

        # 신규 REGION이지만 area 매칭이 가능하면 자동 매핑을 생성한다.
        confidence = Decimal("0.55")
        new_mapping = AreaSdotRegionMapping(
            area_id=area_id,
            sdot_region_key=region_key,
            sdot_region_name=region_name,
            is_primary=area_id not in area_has_primary,
            confidence=confidence,
            note="collector 자동 매핑",
        )
        session.add(new_mapping)

        mapping_by_region[region_key] = (area_id, confidence)
        if new_mapping.is_primary:
            area_has_primary.add(area_id)
        return area_id, confidence

    async def _build_area_lookup(self, session: AsyncSession) -> dict[str, int]:
        """지역명/별칭/코드 기반 AREA 조회 딕셔너리를 구성한다."""
        lookup: dict[str, int] = {}

        areas = (await session.scalars(select(Area).where(Area.is_active.is_(True)))).all()
        for area in areas:
            for candidate in (area.area_nm, area.area_cd, area.eng_nm):
                key = normalize_region_key(candidate)
                if key and key not in lookup:
                    lookup[key] = area.area_id

        alias_rows = (
            await session.execute(select(AreaAlias.area_id, AreaAlias.alias_value))
        ).all()
        for area_id, alias_value in alias_rows:
            key = normalize_region_key(alias_value)
            if key and key not in lookup:
                lookup[key] = area_id
        return lookup

    async def _build_sensor_area_lookup(
        self, session: AsyncSession
    ) -> dict[str, tuple[int, Decimal]]:
        """Build SENSOR_CODE -> nearest area_id mapping using seed coordinates."""
        max_distance_m = self.settings.sdot_sensor_max_distance_m
        if max_distance_m <= 0:
            return {}

        areas = (
            await session.scalars(
                select(Area).where(
                    Area.is_active.is_(True),
                    Area.lat.is_not(None),
                    Area.lng.is_not(None),
                )
            )
        ).all()
        if not areas:
            return {}

        area_points = [
            (area.area_id, float(area.lat), float(area.lng))
            for area in areas
            if area.lat is not None and area.lng is not None
        ]
        if not area_points:
            return {}

        lookup: dict[str, tuple[int, Decimal]] = {}
        for sensor in SEOUL_SDOT_SENSOR_META:
            sensor_code = self._normalize_sensor_code(
                pick_first(sensor, "SENSOR_CODE", "sensor_code")
            )
            if not sensor_code or sensor_code in lookup:
                continue

            sensor_lat = to_decimal(pick_first(sensor, "LAT", "lat"))
            sensor_lng = to_decimal(pick_first(sensor, "LNG", "lng"))
            if sensor_lat is None or sensor_lng is None:
                continue

            sensor_lat_f = float(sensor_lat)
            sensor_lng_f = float(sensor_lng)
            best_area_id: int | None = None
            best_distance: float | None = None

            for area_id, area_lat, area_lng in area_points:
                distance = self._haversine_distance_m(
                    sensor_lat_f, sensor_lng_f, area_lat, area_lng
                )
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_area_id = area_id

            if (
                best_area_id is None
                or best_distance is None
                or best_distance > max_distance_m
            ):
                continue

            confidence = self._distance_to_confidence(
                best_distance, max_distance_m=max_distance_m
            )
            lookup[sensor_code] = (best_area_id, confidence)

        return lookup

    def _normalize_sensor_code(self, value: Any) -> str | None:
        """Normalize sensor code into a zero-padded 11-digit string."""
        text = normalize_text(value)
        if text is None:
            return None
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return None
        try:
            return f"{int(digits):011d}"
        except ValueError:
            return None

    def _distance_to_confidence(
        self, distance_m: float, *, max_distance_m: int
    ) -> Decimal:
        """Convert distance to confidence score."""
        if max_distance_m <= 0:
            return Decimal("0.55")
        ratio = min(1.0, max(0.0, distance_m / float(max_distance_m)))
        score = 0.95 - (0.40 * ratio)
        return Decimal(str(round(score, 2)))

    def _haversine_distance_m(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate great-circle distance in meters."""
        earth_radius_m = 6_371_000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return 2 * earth_radius_m * math.asin(math.sqrt(a))

    async def _refresh_area_live_metrics(self, session: AsyncSession) -> None:
        """최신 도시데이터 + 센서데이터를 통합해 area_live_metrics를 갱신한다."""
        now = now_utc_naive()
        areas = (
            await session.scalars(
                select(Area).where(Area.is_active.is_(True)).order_by(Area.area_id)
            )
        ).all()

        confidence_map = await self._load_mapping_confidence_map(session)
        sensor_area_lookup = await self._build_sensor_area_lookup(session)
        for area in areas:
            snapshot = await session.scalar(
                select(CitydataSnapshot)
                .where(CitydataSnapshot.area_id == area.area_id)
                .order_by(desc(CitydataSnapshot.fetched_at), desc(CitydataSnapshot.snapshot_id))
                .limit(1)
            )

            live_pop = (
                await session.get(CitydataLivePopulation, snapshot.snapshot_id)
                if snapshot
                else None
            )
            live_cmrcl = (
                await session.get(CitydataLiveCommercialSummary, snapshot.snapshot_id)
                if snapshot
                else None
            )
            weather = (
                await session.get(CitydataWeatherCurrent, snapshot.snapshot_id)
                if snapshot
                else None
            )

            sdot_latest = await session.scalar(
                select(SdotTrafficRaw)
                .where(SdotTrafficRaw.area_id == area.area_id)
                .order_by(desc(SdotTrafficRaw.sensing_time), desc(SdotTrafficRaw.id))
                .limit(1)
            )

            sdot_baseline_avg = await session.scalar(
                select(func.avg(SdotTrafficRaw.visitor_count))
                .where(SdotTrafficRaw.area_id == area.area_id)
                .where(SdotTrafficRaw.visitor_count.is_not(None))
                .where(SdotTrafficRaw.sensing_time >= now - timedelta(days=14))
            )

            metric = await session.get(AreaLiveMetric, area.area_id)
            if metric is None:
                metric = AreaLiveMetric(area_id=area.area_id)
                session.add(metric)

            metric.base_snapshot_id = snapshot.snapshot_id if snapshot else None
            metric.base_time = snapshot.fetched_at if snapshot else None
            metric.congestion_level = live_pop.area_congest_lvl if live_pop else None
            metric.congestion_msg = live_pop.area_congest_msg if live_pop else None
            metric.population_min = live_pop.area_ppltn_min if live_pop else None
            metric.population_max = live_pop.area_ppltn_max if live_pop else None
            metric.resident_rate = live_pop.resnt_ppltn_rate if live_pop else None
            metric.non_resident_rate = (
                live_pop.non_resnt_ppltn_rate if live_pop else None
            )

            metric.sdot_current_count = sdot_latest.visitor_count if sdot_latest else None
            metric.sdot_baseline_count = (
                int(round(float(sdot_baseline_avg)))
                if sdot_baseline_avg is not None
                else None
            )
            metric.sdot_region_key_used = sdot_latest.sdot_region_key if sdot_latest else None
            metric.mapping_confidence = (
                confidence_map.get(sdot_latest.sdot_region_key) if sdot_latest else None
            )
            if metric.mapping_confidence is None and sdot_latest and sdot_latest.source_serial:
                sensor_mapped = sensor_area_lookup.get(
                    self._normalize_sensor_code(sdot_latest.source_serial) or ""
                )
                if sensor_mapped and sensor_mapped[0] == area.area_id:
                    metric.mapping_confidence = sensor_mapped[1]

            metric.commercial_level = live_cmrcl.area_cmrcl_lvl if live_cmrcl else None
            metric.payment_cnt = live_cmrcl.area_sh_payment_cnt if live_cmrcl else None
            metric.payment_amt_min = (
                live_cmrcl.area_sh_payment_amt_min if live_cmrcl else None
            )
            metric.payment_amt_max = (
                live_cmrcl.area_sh_payment_amt_max if live_cmrcl else None
            )
            metric.weather_temp = weather.temp if weather else None
            metric.air_idx = weather.air_idx if weather else None

            city_score, sensor_score, combined_score = self._calculate_scores(
                congestion_level=metric.congestion_level,
                current_count=metric.sdot_current_count,
                baseline_count=metric.sdot_baseline_count,
            )
            metric.citydata_score = city_score
            metric.sdot_score = sensor_score
            metric.congestion_score = combined_score
            metric.is_estimated = snapshot is None or sdot_latest is None

            await self._upsert_hourly_timeseries(
                session=session,
                area_id=area.area_id,
                snapshot=snapshot,
                live_pop=live_pop,
                sdot_latest=sdot_latest,
                baseline_count=metric.sdot_baseline_count,
            )

    async def _upsert_hourly_timeseries(
        self,
        *,
        session: AsyncSession,
        area_id: int,
        snapshot: CitydataSnapshot | None,
        live_pop: CitydataLivePopulation | None,
        sdot_latest: SdotTrafficRaw | None,
        baseline_count: int | None,
    ) -> None:
        """시간대 변화 그래프용 1시간 버킷 테이블을 최신값 기준으로 갱신한다."""
        reference_time = (
            (live_pop.source_updated_at if live_pop else None)
            or (snapshot.fetched_at if snapshot else None)
            or (sdot_latest.sensing_time if sdot_latest else None)
            or now_utc_naive()
        )
        stat_date = reference_time.date()
        hour = reference_time.hour
        actual_count = (
            sdot_latest.visitor_count
            if sdot_latest and sdot_latest.visitor_count is not None
            else self._estimate_citydata_count(live_pop)
        )
        citydata_ppltn_min = live_pop.area_ppltn_min if live_pop else None
        citydata_ppltn_max = live_pop.area_ppltn_max if live_pop else None
        congestion_level = live_pop.area_congest_lvl if live_pop else None

        timeseries = await session.scalar(
            select(AreaHourlyTimeseries).where(
                AreaHourlyTimeseries.area_id == area_id,
                AreaHourlyTimeseries.stat_date == stat_date,
                AreaHourlyTimeseries.hour == hour,
            )
        )
        if timeseries is None:
            timeseries = AreaHourlyTimeseries(
                area_id=area_id,
                stat_date=stat_date,
                hour=hour,
            )
            session.add(timeseries)

        timeseries.actual_count = actual_count
        timeseries.baseline_count = baseline_count
        timeseries.citydata_ppltn_min = citydata_ppltn_min
        timeseries.citydata_ppltn_max = citydata_ppltn_max
        timeseries.congestion_level = congestion_level

        session.add(
            AreaHourlySample(
                area_id=area_id,
                stat_date=stat_date,
                hour=hour,
                sample_time=reference_time,
                actual_count=actual_count,
                baseline_count=baseline_count,
                citydata_ppltn_min=citydata_ppltn_min,
                citydata_ppltn_max=citydata_ppltn_max,
                congestion_level=congestion_level,
                is_estimated=snapshot is None or sdot_latest is None,
            )
        )

    def _estimate_citydata_count(
        self, live_pop: CitydataLivePopulation | None
    ) -> int | None:
        """S-DoT 최신값이 없을 때 citydata min/max 중간값으로 시간대 인구를 추정한다."""
        if live_pop is None:
            return None
        if live_pop.area_ppltn_min is not None and live_pop.area_ppltn_max is not None:
            return int(round((live_pop.area_ppltn_min + live_pop.area_ppltn_max) / 2))
        return live_pop.area_ppltn_min or live_pop.area_ppltn_max

    def _extract_sdot_visitor_count(self, row: dict[str, Any]) -> int | None:
        """S-DoT row에서 방문자 수를 추출한다."""
        direct_count = to_int(
            pick_first(
                row,
                "VISITOR_COUNT",
                "PPLTN_CNT",
                "AREA_PPLTN",
                "LIVE_PPLTN",
                "COUNT",
            )
        )
        if direct_count is not None:
            return direct_count

        # 실시간 API가 min/max만 제공할 때 평균값으로 환산한다.
        ppltn_min = to_int(pick_first(row, "AREA_PPLTN_MIN", "PPLTN_MIN"))
        ppltn_max = to_int(pick_first(row, "AREA_PPLTN_MAX", "PPLTN_MAX"))
        if ppltn_min is not None and ppltn_max is not None:
            return int(round((ppltn_min + ppltn_max) / 2))
        return ppltn_min or ppltn_max

    async def _load_mapping_confidence_map(
        self, session: AsyncSession
    ) -> dict[str, Decimal | None]:
        """REGION별 대표 신뢰도 맵을 로드한다."""
        rows = (
            await session.scalars(
                select(AreaSdotRegionMapping).order_by(
                    desc(AreaSdotRegionMapping.is_primary),
                    desc(AreaSdotRegionMapping.confidence),
                    AreaSdotRegionMapping.mapping_id,
                )
            )
        ).all()

        mapping: dict[str, Decimal | None] = {}
        for row in rows:
            if row.sdot_region_key not in mapping:
                mapping[row.sdot_region_key] = row.confidence
        return mapping

    def _extract_citydata_time(self, row: dict[str, Any]) -> Any:
        """도시데이터 row에서 시각 컬럼 후보를 우선순위로 추출한다."""
        live_pop = as_dict(pick_first(row, "LIVE_PPLTN_STTS", "live_ppltn_stts"))
        live_pop = self._unwrap_single_wrapper(
            live_pop, "LIVE_PPLTN_STTS", "live_ppltn_stts"
        )
        weather = as_dict(pick_first(row, "WEATHER_STTS", "weather_stts"))
        weather = self._unwrap_single_wrapper(weather, "WEATHER_STTS", "weather_stts")
        return to_datetime(
            pick_first(
                row,
                "PPLTN_TIME",
                "UPDATE_TIME",
                "FCST_TIME",
                pick_first(live_pop, "PPLTN_TIME"),
                pick_first(weather, "WEATHER_TIME"),
            )
        )

    def _unwrap_single_wrapper(
        self, section: dict[str, Any], *wrapper_keys: str
    ) -> dict[str, Any]:
        """Unwrap one-level wrapper key in OpenAPI payload sections."""
        if not section or len(section) != 1:
            return section
        for key in wrapper_keys:
            if key not in section:
                continue
            nested = as_dict(section.get(key))
            if nested:
                return nested
        return section

    def _extract_gu_name(self, address: str | None) -> str | None:
        """설치 주소에서 자치구명을 추출한다."""
        if not address:
            return None
        match = re.search(r"서울특별시\s+([^\s]+구)", address)
        return match.group(1) if match else None

    async def _start_run(
        self, session: AsyncSession, *, source_name: str, target_count: int | None
    ) -> CollectorRun:
        """collector_runs 시작 레코드를 생성한다."""
        run = CollectorRun(
            source_name=source_name,
            started_at=now_utc_naive(),
            status="running",
            target_count=target_count,
            success_count=0,
            fail_count=0,
        )
        session.add(run)
        await session.flush()
        return run

    async def _finish_run(
        self,
        session: AsyncSession,
        run: CollectorRun,
        error_messages: list[str],
    ) -> None:
        """collector_runs 종료 상태를 반영한다."""
        run.ended_at = now_utc_naive()
        if (run.fail_count or 0) == 0:
            run.status = "success"
            run.error_message = None
        elif (run.success_count or 0) > 0:
            run.status = "partial"
            run.error_message = " | ".join(error_messages[:3])
        else:
            run.status = "failed"
            run.error_message = " | ".join(error_messages[:3])
        await session.flush()

    def _calculate_scores(
        self,
        *,
        congestion_level: str | None,
        current_count: int | None,
        baseline_count: int | None,
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """도시데이터 점수, 센서 점수, 합산 점수를 각각 산출한다."""
        level_score_map = {
            "여유": Decimal("25"),
            "보통": Decimal("50"),
            "약간 붐빔": Decimal("70"),
            "붐빔": Decimal("90"),
            "원활": Decimal("30"),
            "서행": Decimal("60"),
            "정체": Decimal("90"),
            "LOW": Decimal("30"),
            "MEDIUM": Decimal("60"),
            "HIGH": Decimal("85"),
        }
        level_score = (
            level_score_map.get(congestion_level.strip().upper())
            if congestion_level
            else None
        )
        if level_score is None and congestion_level:
            level_score = level_score_map.get(congestion_level.strip())

        sensor_score: Decimal | None = None
        if current_count is not None and baseline_count and baseline_count > 0:
            ratio = Decimal(current_count) / Decimal(baseline_count)
            sensor_score = max(Decimal("0"), min(Decimal("100"), ratio * Decimal("50")))

        combined: Decimal | None = None
        if level_score is not None and sensor_score is not None:
            combined = ((level_score + sensor_score) / Decimal("2")).quantize(Decimal("0.01"))
        elif level_score is not None:
            combined = level_score.quantize(Decimal("0.01"))
        elif sensor_score is not None:
            combined = sensor_score.quantize(Decimal("0.01"))

        return (
            level_score.quantize(Decimal("0.01")) if level_score is not None else None,
            sensor_score.quantize(Decimal("0.01")) if sensor_score is not None else None,
            combined,
        )

    def _is_empty_model(self, obj: Any, *, ignore_fields: set[str]) -> bool:
        """모델 객체에 의미 있는 값이 없는지 확인한다."""
        for key, value in obj.__dict__.items():
            if key.startswith("_"):
                continue
            if key in ignore_fields:
                continue
            if value is not None:
                return False
        return True
