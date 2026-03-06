# LOCAL ON - API 테스트 서버

서울시 실시간 데이터 2종을 FastAPI로 호출해보는 테스트 서버입니다.

## 호출하는 API

| 엔드포인트 | 서울시 데이터 | 설명 |
|---|---|---|
| `GET /sdot/people` | OA-22832 | S-DoT 유동인구 실시간 (10분 단위, 126개 센서) |
| `GET /city/population` | OA-21778 | 서울시 실시간 인구데이터 (1시간 단위, 115개 POI) |

---

## 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
`.env` 파일에 발급받은 키 입력:
```
SEOUL_API_KEY=여기에_발급받은_키_입력
```

> 서울 열린데이터광장(data.seoul.go.kr) 로그인 후 마이페이지 > 인증키 발급

### 3. 서버 실행
```bash
uvicorn main:app --reload
```

### 4. 테스트
브라우저에서 Swagger UI 접속:
```
http://localhost:8000/docs
```

또는 직접 호출:
```bash
# S-DoT 유동인구
curl http://localhost:8000/sdot/people?start=1&end=5

# 서울시 실시간 인구 (강남)
curl http://localhost:8000/city/population?area=강남

# 다른 지역 예시
curl http://localhost:8000/city/population?area=명동
curl http://localhost:8000/city/population?area=홍대입구
curl http://localhost:8000/city/population?area=잠실
```

---

## 프로젝트 구조

```
local_on_api/
├── main.py            # FastAPI 앱, 라우터
├── app/
│   └── seoul_api.py   # 서울시 API 호출 함수
├── .env               # API 키 (git에 올리지 말것!)
├── requirements.txt
└── README.md
```

---

## 응답 구조 (OA-21778 예시)

```json
{
  "source": "OA-21778",
  "description": "서울시 실시간 인구데이터",
  "area": "강남",
  "raw": {
    "SeoulRtd.citydata_ppltn": [
      {
        "AREA_NM": "강남 MICE 관광특구",
        "AREA_CD": "POI001",
        "LIVE_PPLTN_STTS": [
          {
            "AREA_CONGEST_LVL": "보통",        // 혼잡도 단계
            "AREA_CONGEST_MSG": "...",
            "AREA_PPLTN_MIN": "30000",         // 최소 인구 추정
            "AREA_PPLTN_MAX": "35000",         // 최대 인구 추정
            "MALE_PPLTN_RATE": "45.3",         // 남성 비율
            "FEMALE_PPLTN_RATE": "54.7",       // 여성 비율
            "PPLTN_RATE_0": "...",             // 연령대별 비율 (0~10대)
            "PPLTN_RATE_10": "...",
            ...
            "RESNT_PPLTN_RATE": "30.2",        // 거주인구 비율
            "NON_RESNT_PPLTN_RATE": "69.8"     // 비거주(방문) 인구 비율
          }
        ]
      }
    ]
  }
}
```

---

## LOCAL ON 활용 포인트

- `AREA_CONGEST_LVL` → 혼잡도 단계 색상 표시 (여유/보통/붐빔/매우붐빔)
- `AREA_PPLTN_MIN/MAX` → 현재 인구 추정 범위
- `NON_RESNT_PPLTN_RATE` → 방문객 비율 (수요 분석)
- `MALE/FEMALE_PPLTN_RATE` + 연령대 → 타겟 고객 분석