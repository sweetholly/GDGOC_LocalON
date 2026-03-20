from __future__ import annotations

import pytest

from app.collector.clients.kakao_local import KakaoLocalClient
from app.domain import MapPlaceCache


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, *, scalars=None):
        self._scalars = scalars or []

    def scalars(self):
        return _ScalarsResult(self._scalars)


class _FakeSession:
    def __init__(self):
        self.execute_count = 0
        self.added = []

    async def execute(self, stmt):
        self.execute_count += 1
        if self.execute_count == 1:
            # cache miss
            return _ExecuteResult(scalars=[])
        # delete statement result
        return _ExecuteResult(scalars=[])

    def add(self, obj):
        self.added.append(obj)


class _FakeResponse:
    @staticmethod
    def raise_for_status():
        return None

    @staticmethod
    def json():
        return {
            "documents": [
                {
                    "id": "100",
                    "place_name": "Cafe One",
                    "y": "37.5001",
                    "x": "127.0101",
                }
            ]
        }


class _FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers=None, params=None):
        return _FakeResponse()


@pytest.mark.asyncio
async def test_kakao_search_keyword_caches_documents(monkeypatch):
    monkeypatch.setattr("app.collector.clients.kakao_local.httpx.AsyncClient", _FakeAsyncClient)

    session = _FakeSession()
    client = KakaoLocalClient(rest_api_key="dummy-key")

    docs = await client.search_keyword(session, "test query")

    assert len(docs) == 1
    assert session.execute_count == 2  # cache lookup + expired cache cleanup
    assert len(session.added) == 1
    cached = session.added[0]
    assert isinstance(cached, MapPlaceCache)
    assert cached.query_key == "test query"
    assert cached.map_place_id == "100"
