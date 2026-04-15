from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import Settings


logger = logging.getLogger(__name__)


class FyersClient:
    """Minimal async FYERS client for auth + option-chain-v3 market data."""

    source = "fyers"

    _AUTH_BASE = "https://api-t1.fyers.in/api/v3"
    _DATA_BASE = "https://api-t1.fyers.in/data"

    _ACCESS_TOKEN_KEY = "fyers:access-token"

    def __init__(self, http_client: httpx.AsyncClient, redis: Redis, settings: Settings) -> None:
        self._http_client = http_client
        self._redis = redis
        self._settings = settings

    def build_auth_url(self, *, state: str) -> str:
        if not self._settings.fyers_client_id or not self._settings.fyers_redirect_uri:
            raise RuntimeError("FYERS_CLIENT_ID and FYERS_REDIRECT_URI are required")
        params = {
            "client_id": self._settings.fyers_client_id,
            "redirect_uri": self._settings.fyers_redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{self._AUTH_BASE}/generate-authcode?{urlencode(params)}"

    def _app_id_hash(self) -> str:
        if not self._settings.fyers_client_id or not self._settings.fyers_secret_key:
            raise RuntimeError("FYERS_CLIENT_ID and FYERS_SECRET_KEY are required")
        return hashlib.sha256(f"{self._settings.fyers_client_id}:{self._settings.fyers_secret_key}".encode()).hexdigest()

    async def exchange_auth_code(self, *, auth_code: str) -> str:
        payload = {
            "grant_type": "authorization_code",
            "appIdHash": self._app_id_hash(),
            "code": auth_code,
        }
        response = await self._http_client.post(f"{self._AUTH_BASE}/validate-authcode", json=payload)
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError(f"FYERS token exchange failed: {data!r}")
        token = token.strip()
        await self._redis.set(self._ACCESS_TOKEN_KEY, token)
        return token

    async def get_access_token(self) -> str:
        token = (self._settings.fyers_access_token or "").strip()
        if token:
            return token
        cached = await self._redis.get(self._ACCESS_TOKEN_KEY)
        if cached:
            if isinstance(cached, bytes):
                return cached.decode("utf-8").strip()
            return str(cached).strip()
        raise RuntimeError("Missing FYERS access token. Use /api/v1/fyers/auth-url + /api/v1/fyers/callback first.")

    def _auth_header(self, access_token: str) -> str:
        # FYERS expects `Authorization: <client_id>:<access_token>`
        return f"{self._settings.fyers_client_id}:{access_token}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.ReadError))
    )
    async def fetch_option_chain(self) -> dict[str, Any]:
        access_token = await self.get_access_token()
        params = {
            "symbol": self._settings.fyers_symbol,
            "strikecount": int(self._settings.fyers_strikecount),
        }
        url = f"{self._DATA_BASE}/options-chain-v3"
        response = await self._http_client.get(
            url,
            params=params,
            headers={"Authorization": self._auth_header(access_token)},
            timeout=30.0
        )
        response.raise_for_status()
        payload = response.json()
        payload.setdefault("_generated_at", datetime.now(UTC).isoformat())
        return payload