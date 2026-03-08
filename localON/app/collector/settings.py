from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # Allow runtime even when python-dotenv is not installed.
    pass


@dataclass(slots=True)
class CollectorSettings:
    """Collector runtime settings loaded from environment variables."""

    citydata_api_key: str
    citydata_url_template: str
    sdot_url_template: str
    sdot_service_name: str
    sdot_limit: int
    interval_seconds: int
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "CollectorSettings":
        """Load collector settings from env vars."""
        citydata_api_key = os.getenv("CITYDATA_API_KEY", "").strip()
        if not citydata_api_key:
            raise ValueError("CITYDATA_API_KEY environment variable is required.")

        return cls(
            citydata_api_key=citydata_api_key,
            citydata_url_template=os.getenv(
                "CITYDATA_URL_TEMPLATE",
                "http://openapi.seoul.go.kr:8088/{api_key}/xml/citydata/1/5/{area_name}",
            ),
            sdot_url_template=os.getenv(
                "SDOT_URL_TEMPLATE",
                "http://openapi.seoul.go.kr:8088/{api_key}/xml/{service_name}/1/{limit}",
            ),
            sdot_service_name=os.getenv("SDOT_SERVICE_NAME", "sDoTPeople"),
            sdot_limit=int(os.getenv("SDOT_LIMIT", "1000")),
            interval_seconds=int(os.getenv("COLLECTOR_INTERVAL_SECONDS", "600")),
            timeout_seconds=float(os.getenv("COLLECTOR_TIMEOUT_SECONDS", "10")),
        )
