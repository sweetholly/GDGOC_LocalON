from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.controller.search import search_areas
from app.domain import get_db
from app.schema.search import SearchOut

router = APIRouter()


@router.get('/search', response_model=SearchOut)
async def search_endpoint(
    q: Annotated[str, Query(min_length=1, description='Search keyword')],
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    return await search_areas(session=db, q=q)
