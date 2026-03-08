# LOCAL ON Collector

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

