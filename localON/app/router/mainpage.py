from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.mainpage import get_main
from app.domain import get_db
from app.schema.mainpage import MainOut

router = APIRouter()


@router.get('/main', response_model=MainOut)
async def main_endpoint(
    lat: Annotated[Optional[float], Query(description='User latitude')] = None,
    lng: Annotated[Optional[float], Query(description='User longitude')] = None,
    db: AsyncSession = Depends(get_db),
) -> MainOut:
    return await get_main(session=db, lat=lat, lng=lng)
