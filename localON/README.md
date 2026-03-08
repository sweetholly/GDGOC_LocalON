<<<<<<< HEAD
# LOCAL ON

서울 120개 주요 지역의 혼잡도 데이터를 수집하고, 조회 API로 제공하는 프로젝트입니다.  
수집기는 `main.py`, API 서버는 `api.py`로 실행합니다.

## 1. 실행방법

### 1-1. 사전 준비
- `uv` 설치
- Python `3.11` 이상 (`.python-version` 기준, uv가 자동으로 관리)
- MySQL 8.x

### 1-2. 의존성 동기화 (uv)
```bash
uv sync
```

### 1-3. 환경변수 설정
`.env.example`을 복사해 `.env`를 만들고 값을 채웁니다.

```bash
copy .env.example .env
```

필수 값:
- `DATABASE_URL`
- `CITYDATA_API_KEY`

예시:
```env
DATABASE_URL=mysql+aiomysql://localon:your_password@127.0.0.1:3306/local_on
CITYDATA_API_KEY=your_seoul_openapi_key
```

### 1-4. MySQL DB 생성 (최초 1회)
```bash
mysql -h 127.0.0.1 -u root -p -e "CREATE DATABASE IF NOT EXISTS local_on CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

필요하면 앱 전용 계정도 생성:
```sql
CREATE USER 'localon'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON local_on.* TO 'localon'@'localhost';
FLUSH PRIVILEGES;
```

### 1-5. 스키마 생성
```bash
uv run python -c "import asyncio; from app.domain import create_schema; asyncio.run(create_schema())"
```

### 1-6. 수집기 실행
1회 실행:
```bash
uv run python main.py --once
```

주기 실행:
```bash
uv run python main.py
```

주기(초)는 `.env`의 `COLLECTOR_INTERVAL_SECONDS`로 제어합니다.

### 1-7. API 서버 실행
```bash
uv run python api.py
```

접속:
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### 1-8. 테스트 실행 (선택)
```bash
uv run pytest
```

## 2. API 설명 (종류 / 발급방법)

### 2-1. 내부 API (클라이언트가 호출)

1. `GET /main`
- 메인 화면용 지역 목록 + 트렌드 반환
- 파라미터: `lat`, `lng` (선택)
- `lat/lng`를 주면 거리순으로 정렬하지만, 현재는 활성 지역 전체를 반환

2. `GET /areas/{area_id}`
- 특정 지역 상세 정보 반환
- 파라미터: `area_id`(필수), `date`(선택, `YYYY-MM-DD`)
- 혼잡도, 시간대 그래프, 추천시간, 수요/상권/날씨 포함

3. `GET /search`
- 지역 키워드 검색
- 파라미터: `q`(필수)

### 2-2. 외부 API (수집기(collector)가 호출)

이 프로젝트는 서울 열린데이터광장 OpenAPI를 사용합니다.

1. `citydata` API
- 지역별 실시간 도시데이터(혼잡/날씨/상권 등)
- 템플릿: `CITYDATA_URL_TEMPLATE`

2. `sDoTPeople` API
- S-DoT 유동인구(센서) 데이터
- 템플릿: `SDOT_URL_TEMPLATE`
- 서비스명: `SDOT_SERVICE_NAME` (기본값 `sDoTPeople`)

키 정책:
- `CITYDATA_API_KEY` 하나를 `citydata`/`sDoTPeople` 모두에 공통 사용

### 2-3. 외부 API 키 발급방법 (서울 열린데이터광장)

1. 서울 열린데이터광장 접속: `https://data.seoul.go.kr`
2. 회원가입/로그인
3. Open API 메뉴에서 인증키 신청
4. 발급된 일반 인증키 확인
5. `.env`의 `CITYDATA_API_KEY`에 설정
=======
﻿# LOCAL ON Collector

?쒖슱???꾩떆?곗씠??+ S-DoT ?쇱꽌 ?곗씠?곕? 二쇨린 ?섏쭛?섏뿬 DB???듯빀 ??ν븯???섏쭛湲곗엯?덈떎.

## ?듭떖 蹂寃쎌젏

- 120媛??μ냼 紐⑸줉? 肄붾뱶 ?곸닔濡??댁옣?섏뼱 ?덉뒿?덈떎.
- ?쇱꽌 硫뷀?(?쒕━??二쇱냼/醫뚰몴)??肄붾뱶 ?곸닔濡??댁옣?섏뼱 ?덉뒿?덈떎.
- ?고??꾩뿉 `.xls/.xlsx` ?뚯씪???쎌? ?딆뒿?덈떎.
- S-DoT API 湲곕낯 ?붾뱶?ъ씤?몃뒗 `xml/sDoTPeople` ?낅땲??

## ?꾩닔 ?섍꼍蹂??
- `DATABASE_URL`  
?? `mysql+aiomysql://root:password@localhost:3306/local_on`
- `CITYDATA_API_KEY`

## ?좏깮 ?섍꼍蹂??
- `CITYDATA_URL_TEMPLATE`  
湲곕낯媛? `http://openapi.seoul.go.kr:8088/{api_key}/xml/citydata/1/5/{area_name}`
- `SDOT_URL_TEMPLATE`  
湲곕낯媛? `http://openapi.seoul.go.kr:8088/{api_key}/xml/{service_name}/1/{limit}`
- `SDOT_SERVICE_NAME` (湲곕낯 `sDoTPeople`)
- `SDOT_LIMIT` (湲곕낯 `1000`)
- `COLLECTOR_INTERVAL_SECONDS` (湲곕낯 `300`)
- `COLLECTOR_TIMEOUT_SECONDS` (湲곕낯 `15`)

## ?ㅽ뻾

```bash
python main.py --once
```

二쇨린 ?ㅽ뻾:

```bash
python main.py
```

>>>>>>> 0ae59683f20e6d0fde262362acbc80197da2ce83
