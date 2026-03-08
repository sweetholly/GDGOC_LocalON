from __future__ import annotations

from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.app import create_app
from app.domain import get_db


@pytest_asyncio.fixture
async def client():
    """DB 연결 없이 동작하는 테스트 클라이언트."""
    app = create_app()

    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
