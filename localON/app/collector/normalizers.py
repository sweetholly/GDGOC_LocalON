from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any


def now_utc_naive() -> datetime:
    """DB 저장용 현재 UTC 시간을 timezone 없는 datetime으로 반환한다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_text(value: Any) -> str | None:
    """입력값을 trim된 문자열로 정규화한다."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_region_key(value: Any) -> str | None:
    """REGION 문자열을 매핑키 형태로 정규화한다."""
    text = normalize_text(value)
    if text is None:
        return None
    compact = re.sub(r"\s+", "", text)
    return compact.upper() or None


def to_int(value: Any) -> int | None:
    """다양한 타입의 숫자 입력을 정수로 변환한다."""
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def to_decimal(value: Any) -> Decimal | None:
    """입력값을 Decimal로 변환한다."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_datetime(value: Any) -> datetime | None:
    """주요 포맷 문자열/숫자를 datetime으로 변환한다."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def pick_first(data: dict[str, Any], *keys: str) -> Any:
    """키 후보 중 첫 번째 유효 값을 반환한다."""
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def as_dict(value: Any) -> dict[str, Any]:
    """dict 또는 list[dict]를 dict로 변환한다."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def extract_openapi_container(
    payload: dict[str, Any], preferred_key: str | None = None
) -> dict[str, Any]:
    """서울 열린데이터 JSON 응답에서 데이터 컨테이너를 추출한다."""
    if preferred_key:
        if isinstance(payload.get(preferred_key), dict):
            return payload[preferred_key]

        # XML 응답 루트 태그의 대소문자 차이를 허용한다.
        preferred_lower = preferred_key.lower()
        for key, value in payload.items():
            if key.lower() == preferred_lower and isinstance(value, dict):
                return value

    for value in payload.values():
        if not isinstance(value, dict):
            continue
        if (
            "row" in value
            or "ROW" in value
            or "Result" in value
            or "RESULT" in value
        ):
            return value
    return {}


def extract_openapi_rows(
    payload: dict[str, Any], preferred_key: str | None = None
) -> list[dict[str, Any]]:
    """서울 열린데이터 JSON 응답에서 row 배열을 안전하게 추출한다."""
    container = extract_openapi_container(payload, preferred_key=preferred_key)
    rows = container.get("row")
    if rows is None:
        rows = container.get("ROW")
    if rows is None:
        return []

    # row가 단건일 때 dict로 내려오는 경우를 보정한다.
    if isinstance(rows, dict):
        return [rows]
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def hash_payload(payload: dict[str, Any]) -> str:
    """원본 payload를 해시하여 중복/변경 추적에 사용한다."""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()
