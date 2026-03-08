from __future__ import annotations

from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

import httpx

from .settings import CollectorSettings


class CollectorHttpError(RuntimeError):
    """외부 API 통신 실패를 나타내는 예외."""


class SeoulOpenApiClient:
    """서울 열린데이터 API 호출 전용 클라이언트."""

    def __init__(
        self,
        settings: CollectorSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = False

    async def __aenter__(self) -> "SeoulOpenApiClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.timeout_seconds)
            self._owns_client = True
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def fetch_citydata(self, area_name: str) -> dict[str, Any]:
        """도시데이터 API를 장소 단위로 호출한다."""
        if self._client is None:
            raise RuntimeError("클라이언트 컨텍스트가 초기화되지 않았습니다.")

        # 경로 파라미터이므로 URL 인코딩 처리 후 템플릿에 주입한다.
        encoded_area_name = quote(area_name, safe="")
        url = self.settings.citydata_url_template.format(
            api_key=self.settings.citydata_api_key,
            area_name=encoded_area_name,
            area_name_raw=area_name,
            service_name=self.settings.sdot_service_name,
            limit=self.settings.sdot_limit,
        )
        return await self._request_payload(url)

    async def fetch_sdot(self) -> dict[str, Any]:
        """S-DoT 유동인구 API를 호출한다."""
        if self._client is None:
            raise RuntimeError("클라이언트 컨텍스트가 초기화되지 않았습니다.")

        url = self.settings.sdot_url_template.format(
            api_key=self.settings.citydata_api_key,
            service_name=self.settings.sdot_service_name,
            limit=self.settings.sdot_limit,
        )
        return await self._request_payload(url)

    async def _request_payload(self, url: str) -> dict[str, Any]:
        """HTTP GET 요청 결과를 JSON/XML 중 자동 판별하여 파싱한다."""
        if self._client is None:
            raise RuntimeError("클라이언트 컨텍스트가 초기화되지 않았습니다.")

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CollectorHttpError(f"API 호출 실패: {url} ({exc})") from exc

        raw_text = response.text
        content_type = (response.headers.get("content-type") or "").lower()
        response_format = self._infer_response_format(url, content_type, raw_text)

        if response_format == "json":
            try:
                payload = response.json()
            except ValueError as exc:
                preview = raw_text[:200].replace("\n", " ")
                raise CollectorHttpError(
                    f"JSON 파싱 실패: {url} (body preview={preview!r})"
                ) from exc

            if not isinstance(payload, dict):
                raise CollectorHttpError(f"JSON 루트가 dict가 아닙니다: {url}")
            return payload

        if response_format == "xml":
            try:
                return self._parse_xml_payload(raw_text)
            except ET.ParseError as exc:
                preview = raw_text[:200].replace("\n", " ")
                raise CollectorHttpError(
                    f"XML 파싱 실패: {url} (body preview={preview!r})"
                ) from exc

        preview = raw_text[:200].replace("\n", " ")
        raise CollectorHttpError(
            f"응답 포맷 식별 실패: {url} (content-type={content_type!r}, body preview={preview!r})"
        )

    def _infer_response_format(
        self, url: str, content_type: str, raw_text: str
    ) -> str | None:
        """URL/헤더/본문을 기준으로 응답 포맷(json/xml)을 추정한다."""
        lowered_url = url.lower()
        stripped = raw_text.lstrip()

        if "/json/" in lowered_url or "application/json" in content_type:
            return "json"
        if "/xml/" in lowered_url or "xml" in content_type:
            return "xml"
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"
        if stripped.startswith("<"):
            return "xml"
        return None

    def _parse_xml_payload(self, raw_xml: str) -> dict[str, Any]:
        """서울 열린데이터 XML 응답을 dict 구조로 변환한다."""
        root = ET.fromstring(raw_xml)
        root_tag = self._strip_namespace(root.tag)
        root_value = self._xml_node_to_value(root)

        if isinstance(root_value, dict):
            return {root_tag: root_value}
        return {root_tag: {"value": root_value}}

    def _xml_node_to_value(self, node: ET.Element) -> Any:
        """XML 노드를 재귀적으로 파싱해 dict/list/scalar로 변환한다."""
        children = list(node)
        if not children:
            return (node.text or "").strip()

        result: dict[str, Any] = {}
        for child in children:
            key = self._strip_namespace(child.tag)
            value = self._xml_node_to_value(child)

            if key not in result:
                result[key] = value
                continue

            existing = result[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]

        return result

    def _strip_namespace(self, tag: str) -> str:
        """XML 태그명에서 네임스페이스를 제거한다."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag
