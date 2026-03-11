from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import Area, AreaAlias, AreaLiveMetric
from app.schema.search import SearchOut, SearchResultOut


async def search_areas(session: AsyncSession, q: str) -> SearchOut:
    keyword = f"%{q}%"

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
    rows = (await session.execute(stmt)).all()

    results = [
        SearchResultOut(
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
        for area, metric, _ in rows
    ]

    return SearchOut(query=q, results=results)
