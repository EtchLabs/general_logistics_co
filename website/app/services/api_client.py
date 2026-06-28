from typing import Any

import httpx

from app.config import get_settings


class GatewayClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.api_gateway_url.rstrip("/")

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(correlation_id),
            )

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.post(
                f"{self.base_url}{path}",
                json=json,
                headers=self._headers(correlation_id),
            )


gateway_client = GatewayClient()
