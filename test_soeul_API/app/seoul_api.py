import httpx
import os
from dotenv import load_dotenv

load_dotenv()

SEOUL_API_KEY = os.getenv("SEOUL_API_KEY")
BASE_URL = "http://openapi.seoul.go.kr:8088"


async def fetch_sdot_people(start: int = 1, end: int = 5) -> dict:
    """
    OA-22832 : S-DoT 유동인구 실시간
    - 서비스명: sDoTPeople (실시간 전용, start=1부터 현재 데이터)
    - 측정 방식: WiFi MAC 카운팅 + CCTV 피플카운팅
    - 갱신 주기: 10분
    - 센서 수: 126개
    - 주요 필드: SERIAL, SENSING_TIME, REGION, VISITOR_COUNT, DATA_NO
    """
    url = f"{BASE_URL}/{SEOUL_API_KEY}/json/sDoTPeople/{start}/{end}/"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def fetch_city_population(area_name: str = "광화문·덕수궁") -> dict:
    """
    OA-21778 : 서울시 실시간 인구데이터 (인구 항목만)
    - 갱신 주기: 5분 (KT/SKT 기지국 기반)
    - 120개 주요 POI, 한 번에 1개 장소씩만 호출 가능
    - 제공: 혼잡도 단계, 인구 추정(min/max), 성별·연령대 비율, 거주/비거주 비율
    - ※ 샘플키 → '광화문·덕수궁'만 가능
    """
    url = f"{BASE_URL}/{SEOUL_API_KEY}/json/citydata_ppltn/1/1/{area_name}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def fetch_city_all_data(area_name: str = "광화문·덕수궁") -> dict:
    """
    OA-21285 : 서울시 실시간 도시데이터 (통합)
    - 인구 + 상권 + 도로소통 + 대중교통 + 날씨/환경 + 문화행사 통합
    - 갱신 주기: 항목마다 다름 (인구 5분, 상권 10분 등)
    - 120개 주요 POI, 한 번에 1개 장소씩만 호출 가능
    - ※ 샘플키 → '광화문·덕수궁'만 가능
    """
    url = f"{BASE_URL}/{SEOUL_API_KEY}/json/citydata/1/1/{area_name}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()