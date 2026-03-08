from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.areas import get_area_detail
from app.domain import get_db
from app.schema.areas import AreaDetailOut

router = APIRouter()


@router.get('/areas/{area_id}', response_model=AreaDetailOut)
async def area_detail_endpoint(
    area_id: Annotated[int, Path(gt=0, description='Area ID')],
    date: Annotated[
        Optional[date], Query(description='Date for hourly timeseries (default: today)')
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> AreaDetailOut:
    result = await get_area_detail(session=db, area_id=area_id, stat_date=date)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={'error': 'NOT_FOUND', 'message': '해당 지역을 찾을 수 없습니다'},
        )
    return result
