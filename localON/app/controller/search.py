from __future__ import annotations

import asyncio
import os
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import Area, AreaAlias, AreaLiveMetric, SearchQueryLog
from app.schema.search import SearchOut, SearchResultOut
from app.collector.clients.kakao_local import KakaoLocalClient


async def search_areas(session: AsyncSession, q: str) -> SearchOut:
    keyword = f"%{q}%"

    # 로깅: 사용자가 검색한 키워드를 저장
    sql_log = SearchQueryLog(query=q)
    session.add(sql_log)
    # 다른 트랜잭션과 묶여서 커밋되거나, 상위에서 커밋됨을 가정

    # alias 일치 area_id 서브쿼리
    alias_subq = (
        select(AreaAlias.area_id)
        .where(AreaAlias.alias_value.like(keyword))
        .scalar_subquery()
    )

    exact_name = func.lower(Area.area_nm) == q.lower()
    has_alias = Area.area_id.in_(alias_subq)
    partial_name = Area.area_nm.like(keyword)
    partial_eng = Area.eng_nm.like(keyword)

    # 검색 우선순위: 완전 일치 > alias > 이름 부분 > 영문 부분
    priority_expr = case(
        (exact_name, 1),
        (has_alias, 2),
        (partial_name, 3),
        (partial_eng, 4),
        else_=5,
    )

    stmt = (
        select(Area, AreaLiveMetric, priority_expr.label("priority"))
        .outerjoin(AreaLiveMetric, Area.area_id == AreaLiveMetric.area_id)
        .where(
            Area.is_active == True,
            or_(exact_name, has_alias, partial_name, partial_eng),
        )
        .order_by(priority_expr)
    )
    
    # 카카오 로컬 검색을 병렬로 수행할 수 있도록 태스크 준비
    kakao_client = KakaoLocalClient(os.getenv("KAKAO_REST_API_KEY", ""))
    
    # 2가지 비동기 조회 작업을 동시 실행
    # (주의: search_keyword 안에서도 session을 쓰므로, async 환경에서 같은 session을
    # 동시 스레드로 못쓸 수 있습니다. SQLAlchemy AsyncSession은 동시 쿼리를 허용하지 않으므로
    # 순차적으로 실행하거나 각각 다른 세션을 써야합니다. 여기선 안전하게 await으로 순차 실행합니다)
    rows = (await session.execute(stmt)).all()
    
    try:
        kakao_results = await kakao_client.search_keyword(session, q)
    except Exception as e:
        kakao_results = []
        print(f"Kakao search error: {e}")

    results = []
    
    # 1. 내부 DB 결과 추가
    for area, metric, _ in rows:
        results.append(
            SearchResultOut(
                result_type="localon_area",
                area_id=area.area_id,
                area_cd=area.area_cd,
                name=area.area_nm,
                category=area.ui_category,
                lat=float(area.lat) if area.lat is not None else None,
                lng=float(area.lng) if area.lng is not None else None,
                congestion_level=metric.congestion_level if metric else None,
                citydata_score=float(metric.citydata_score) if metric and metric.citydata_score is not None else None,
                sdot_score=float(metric.sdot_score) if metric and metric.sdot_score is not None else None,
            )
        )

    # 2. 외부 Kakao 결과 추가
    for doc in kakao_results:
        results.append(
            SearchResultOut(
                result_type="external_place",
                area_id=doc.get("id"),
                name=doc.get("place_name"),
                address=doc.get("road_address_name") or doc.get("address_name"),
                category="외부장소",
                lat=float(doc.get("y")) if doc.get("y") else None,
                lng=float(doc.get("x")) if doc.get("x") else None,
            )
        )

    return SearchOut(query=q, results=results)
