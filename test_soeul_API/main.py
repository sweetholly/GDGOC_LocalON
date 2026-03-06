from fastapi import FastAPI, HTTPException, Query
from app.seoul_api import fetch_sdot_people, fetch_city_population, fetch_city_all_data

app = FastAPI(
    title="LOCAL ON - Seoul Data API",
    description="서울시 실시간 유동인구 & 생활인구 데이터 테스트 서버",
    version="0.2.0",
)

AREA_DESC = (
    "지역명. 샘플키는 '광화문·덕수궁'만 가능. "
    "인증키는 120개 장소 전체 조회 가능 "
    "(예: 강남 MICE 관광특구, 홍대 관광특구, 잠실 관광특구, 명동 관광특구)"
)


# ──────────────────────────────────────────────
# 1) S-DoT 유동인구 실시간  (OA-22832)
# ──────────────────────────────────────────────
@app.get(
    "/sdot/people",
    summary="S-DoT 유동인구 실시간 (OA-22832)",
    tags=["S-DoT 센서"],
)
async def get_sdot_people(
    start: int = Query(default=1, description="시작 인덱스"),
    end: int = Query(default=5, description="끝 인덱스 (최대 1000)"),
):
    """
    S-DoT 물리 센서 기반 유동인구 데이터.

    - 측정 방식: WiFi MAC 카운팅 + CCTV 피플카운팅
    - 갱신 주기: **10분**
    - 센서 수: 126개
    - 설치 장소: 전통시장, 주요거리, 공원, 공공시설
    - 주요 필드: VISITOR_COUNT, REGION, AUTONOMOUS_DISTRICT, ADMINISTRATIVE_DISTRICT
    """
    try:
        data = await fetch_sdot_people(start, end)
        return {
            "source": "OA-22832",
            "description": "S-DoT 유동인구 실시간",
            "raw": data,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ──────────────────────────────────────────────
# 2) 서울시 실시간 인구데이터  (OA-21778)
# ──────────────────────────────────────────────
@app.get(
    "/city/population",
    summary="서울시 실시간 인구데이터 (OA-21778)",
    tags=["도시 빅데이터"],
)
async def get_city_population(
    area: str = Query(default="광화문·덕수궁", description=AREA_DESC),
):
    """
    KT/SKT 통신 기지국 데이터 기반 POI 단위 실시간 인구. 인구 항목만 제공.

    - 갱신 주기: **5분**
    - 커버리지: 서울 전역 120개 주요 POI
    - 1회 호출 시 1개 장소만 조회 가능
    - 주요 필드: AREA_CONGEST_LVL(혼잡도), AREA_PPLTN_MIN/MAX,
      MALE/FEMALE_PPLTN_RATE, PPLTN_RATE_10~60(연령대), RESNT/NON_RESNT_PPLTN_RATE
    - ⚠️ 샘플키는 '광화문·덕수궁'만 조회 가능
    """
    try:
        data = await fetch_city_population(area)
        return {
            "source": "OA-21778",
            "description": "서울시 실시간 인구데이터",
            "area": area,
            "raw": data,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ──────────────────────────────────────────────
# 3) 서울시 실시간 도시데이터  (OA-21285) — 통합
# ──────────────────────────────────────────────
@app.get(
    "/city/all_data",
    summary="서울시 실시간 도시데이터 통합 (OA-21285)",
    tags=["도시 빅데이터"],
)
async def get_city_all_data(
    area: str = Query(default="광화문·덕수궁", description=AREA_DESC),
):
    """
    인구 + 상권 + 도로소통 + 대중교통 + 날씨/환경 + 문화행사 **통합** 데이터.

    - 갱신 주기: 항목마다 다름 (인구 5분 / 상권 10분 / 날씨 1시간 등)
    - 커버리지: 서울 전역 120개 주요 POI
    - 1회 호출 시 1개 장소만 조회 가능
    - 포함 도메인:
        - LIVE_PPLTN_STTS     : 실시간 인구 (OA-21778과 동일)
        - LIVE_CMRCL_STTS     : 실시간 상권 (결제건수, 매출 추정)
        - ROAD_TRAFFIC_STTS   : 도로소통 현황
        - SUB_STTS / BUS_STTS : 지하철/버스 현황
        - WEATHER_STTS        : 날씨/환경
        - EVENT_STTS          : 문화행사
    - ⚠️ 샘플키는 '광화문·덕수궁'만 조회 가능
    """
    try:
        data = await fetch_city_all_data(area)
        return {
            "source": "OA-21285",
            "description": "서울시 실시간 도시데이터 (통합)",
            "area": area,
            "raw": data,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ──────────────────────────────────────────────
# 헬스체크
# ──────────────────────────────────────────────
@app.get("/", tags=["기타"])
async def root():
    return {
        "service": "LOCAL ON API Test Server v0.2",
        "endpoints": {
            "① S-DoT 유동인구 실시간 (OA-22832)":     "GET /sdot/people?start=1&end=5",
            "② 서울시 실시간 인구 (OA-21778)":         "GET /city/population?area=광화문·덕수궁",
            "③ 서울시 실시간 도시데이터 통합 (OA-21285)": "GET /city/all_data?area=광화문·덕수궁",
            "Swagger UI":                            "GET /docs",
        },
    }


# ──────────────────────────────────────────────
# 디버그: 전체 센서 REGION 분포 확인
# ──────────────────────────────────────────────
@app.get("/debug/sdot/region_stats", tags=["디버그"])
async def debug_sdot_region_stats():
    """
    126개 센서 전체를 한 번에 가져와서
    REGION / AUTONOMOUS_DISTRICT 분포를 집계합니다.
    """
    try:
        data = await fetch_sdot_people(start=1, end=200)
        rows = data.get("sDoTPeople", {}).get("row", [])

        region_count = {}
        district_count = {}
        region_district_map = {}

        for r in rows:
            region = r.get("REGION", "unknown")
            district = r.get("AUTONOMOUS_DISTRICT", "unknown")

            region_count[region] = region_count.get(region, 0) + 1
            district_count[district] = district_count.get(district, 0) + 1

            if region not in region_district_map:
                region_district_map[region] = []
            if district not in region_district_map[region]:
                region_district_map[region].append(district)

        return {
            "total_rows": len(rows),
            "region_types": list(region_count.keys()),
            "region_count": region_count,
            "region_district_map": region_district_map,
            "district_count": district_count,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ──────────────────────────────────────────────
# 디버그: REGION별 실시간 유동인구 집계
# ──────────────────────────────────────────────
@app.get("/debug/sdot/region_traffic", tags=["디버그"])
async def debug_sdot_region_traffic():
    """
    126개 센서 전체를 가져와서
    REGION / AUTONOMOUS_DISTRICT 별 유동인구 합계·평균·최대를 집계합니다.
    """
    try:
        data = await fetch_sdot_people(start=1, end=200)
        rows = data.get("sDoTPeople", {}).get("row", [])

        # ── REGION별 집계 ──
        region_stats = {}
        for r in rows:
            region = r.get("REGION", "unknown")
            count = int(r.get("VISITOR_COUNT", 0))
            if region not in region_stats:
                region_stats[region] = {"total": 0, "sensor_count": 0, "max": 0, "sensors": []}
            region_stats[region]["total"] += count
            region_stats[region]["sensor_count"] += 1
            region_stats[region]["max"] = max(region_stats[region]["max"], count)
            region_stats[region]["sensors"].append({
                "serial": r.get("SERIAL"),
                "district": r.get("AUTONOMOUS_DISTRICT"),
                "admin": r.get("ADMINISTRATIVE_DISTRICT"),
                "visitor_count": count,
            })

        # 평균 계산
        for region, s in region_stats.items():
            s["avg"] = round(s["total"] / s["sensor_count"], 1) if s["sensor_count"] > 0 else 0
            # 센서 목록은 visitor_count 내림차순 정렬
            s["sensors"] = sorted(s["sensors"], key=lambda x: x["visitor_count"], reverse=True)

        # ── AUTONOMOUS_DISTRICT별 집계 ──
        district_stats = {}
        for r in rows:
            district = r.get("AUTONOMOUS_DISTRICT", "unknown")
            count = int(r.get("VISITOR_COUNT", 0))
            if district not in district_stats:
                district_stats[district] = {"total": 0, "sensor_count": 0, "max": 0}
            district_stats[district]["total"] += count
            district_stats[district]["sensor_count"] += 1
            district_stats[district]["max"] = max(district_stats[district]["max"], count)

        for district, s in district_stats.items():
            s["avg"] = round(s["total"] / s["sensor_count"], 1) if s["sensor_count"] > 0 else 0

        # 전체 합계 기준 내림차순 정렬
        sorted_region = dict(sorted(region_stats.items(), key=lambda x: x[1]["total"], reverse=True))
        sorted_district = dict(sorted(district_stats.items(), key=lambda x: x[1]["total"], reverse=True))

        sensing_time = rows[0].get("SENSING_TIME") if rows else None

        return {
            "sensing_time": sensing_time,
            "total_sensors": len(rows),
            "by_region": sorted_region,
            "by_district": sorted_district,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))