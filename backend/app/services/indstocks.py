from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import httpx
import orjson
from redis.asyncio import Redis
import logging

from app.core.config import Settings
from app.schemas.option_chain import (
    OptionChainDelta,
    OptionChainRow,
    OptionChainSnapshot,
    OptionChainSummary,
    OptionLegMetrics,
    UnderlyingQuote,
)

logger = logging.getLogger(__name__)


class OptionChainUpstreamClient:
    source: str

    async def fetch_option_chain(self) -> dict[str, Any]:
        raise NotImplementedError


class DhanClient:
    """Async client for Dhan API option chain."""

    source = "dhan"

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings
        self._cached_expiry: str | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "access-token": self._settings.dhan_access_token,
            "client-id": self._settings.dhan_client_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def fetch_expiry_list(self) -> list[str]:
        response = await self._http_client.post(
            f"{self._settings.dhan_option_chain_path.rstrip('/')}/expirylist",
            headers=self._headers(),
            json={
                "UnderlyingScrip": self._settings.dhan_underlying_scrip,
                "UnderlyingSeg": self._settings.dhan_underlying_seg,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Dhan expirylist failed: status=%s body=%s",
                response.status_code,
                (response.text or "").strip()[:800],
            )
            raise
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]

    async def _resolve_expiry(self) -> str | None:
        if self._settings.dhan_expiry:
            return self._settings.dhan_expiry
        if self._cached_expiry:
            return self._cached_expiry
        expiries = await self.fetch_expiry_list()
        if not expiries:
            return None
        # Dhan returns expiries as YYYY-MM-DD strings; list is typically ascending.
        # Pick the first expiry that isn't in the past, else fall back to the last one.
        today = datetime.now(timezone.utc).date()
        for expiry in expiries:
            try:
                if datetime.fromisoformat(expiry).date() >= today:
                    self._cached_expiry = expiry
                    return expiry
            except ValueError:
                continue
        self._cached_expiry = expiries[-1]
        return self._cached_expiry

    async def fetch_option_chain(self) -> dict[str, Any]:
        expiry = await self._resolve_expiry()
        if not expiry:
            raise RuntimeError(
                "No option-chain expiry could be resolved from Dhan. "
                "Set DHAN_EXPIRY in .env or fix Dhan expirylist/auth."
            )
        request_body: dict[str, Any] = {
            "UnderlyingScrip": self._settings.dhan_underlying_scrip,
            "UnderlyingSeg": self._settings.dhan_underlying_seg,
        }
        request_body["Expiry"] = expiry

        headers = {
            **self._headers(),
        }
        response = await self._http_client.post(
            self._settings.dhan_option_chain_path,
            headers=headers,
            json=request_body,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Dhan optionchain failed: status=%s body=%s request=%s",
                response.status_code,
                (response.text or "").strip()[:800],
                request_body,
            )
            raise
        payload = response.json()
        if isinstance(payload, dict):
            payload["_dhan_request"] = {
                "symbol": self._settings.dhan_symbol,
                "UnderlyingScrip": self._settings.dhan_underlying_scrip,
                "UnderlyingSeg": self._settings.dhan_underlying_seg,
                "Expiry": expiry,
            }
        return payload


class OptionChainService:
    CACHE_KEY = "option-chain:latest"
    LAST_GOOD_KEY = "option-chain:last-good"

    def __init__(self, redis: Redis, client: OptionChainUpstreamClient, settings: Settings) -> None:
        self._redis = redis
        self._client = client
        self._settings = settings
        self._last_broadcast_snapshot: OptionChainSnapshot | None = None

    async def get_snapshot(self, force_refresh: bool = False) -> OptionChainSnapshot:
        cached_latest = None
        if not force_refresh:
            cached_latest = await self._redis.get(self.CACHE_KEY)
            if cached_latest:
                return OptionChainSnapshot.model_validate(orjson.loads(cached_latest))

        cached_last_good = await self._redis.get(self.LAST_GOOD_KEY)
        cached_fallback = cached_latest or cached_last_good

        try:
            payload = await self._client.fetch_option_chain()
            snapshot = self._normalize_payload(payload)
        except Exception as exc:
            if cached_fallback:
                logger.warning("Serving cached option chain due to upstream failure")
                return OptionChainSnapshot.model_validate(orjson.loads(cached_fallback))
            if self._settings.environment.lower() == "development":
                logger.warning("Serving mock option chain due to upstream failure: %s", exc)
                return self._mock_snapshot()
            raise

        snapshot_json = snapshot.model_dump_json()
        await self._redis.set(
            self.CACHE_KEY,
            snapshot_json,
            ex=self._settings.option_chain_cache_ttl_seconds,
        )
        await self._redis.set(
            self.LAST_GOOD_KEY,
            snapshot_json,
            ex=self._settings.option_chain_last_good_ttl_seconds,
        )
        return snapshot

    async def warm(self) -> OptionChainSnapshot:
        snapshot = await self.get_snapshot(force_refresh=True)
        self._last_broadcast_snapshot = snapshot
        return snapshot

    def build_delta(self, current: OptionChainSnapshot) -> OptionChainDelta | None:
        previous = self._last_broadcast_snapshot
        self._last_broadcast_snapshot = current
        if previous is None:
            return None

        previous_rows = {row.strike_price: row for row in previous.rows}
        current_rows = {row.strike_price: row for row in current.rows}

        changed_rows = [
            row
            for strike_price, row in current_rows.items()
            if previous_rows.get(strike_price) != row
        ]
        removed_strikes = sorted(set(previous_rows) - set(current_rows))
        summary_changed = previous.summary != current.summary
        underlying_changed = previous.underlying != current.underlying

        if not changed_rows and not removed_strikes and not summary_changed and not underlying_changed:
            return None

        return OptionChainDelta(
            generated_at=current.generated_at,
            changed_rows=changed_rows,
            removed_strikes=removed_strikes,
            summary=current.summary if summary_changed else None,
            underlying=current.underlying if underlying_changed else None,
        )

    def with_pins(
        self,
        snapshot: OptionChainSnapshot,
        pinned_strikes: Iterable[float],
    ) -> OptionChainSnapshot:
        return snapshot.model_copy(update={"pinned_strikes": sorted(set(pinned_strikes))})

    def _normalize_payload(self, payload: dict[str, Any]) -> OptionChainSnapshot:
        generated_at = datetime.now(timezone.utc)

        if isinstance(payload.get("data"), dict) and "oc" in payload["data"]:
            return self._normalize_dhan_payload(payload, generated_at=generated_at)

        data_root = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        underlying_root = data_root.get("underlying") if isinstance(data_root.get("underlying"), dict) else {}

        spot_price = self._coerce_number(
            payload.get("spot")
            or payload.get("ltp")
            or payload.get("last_price")
            or underlying_root.get("spot")
            or underlying_root.get("ltp")
            or underlying_root.get("last_price")
            or data_root.get("spot")
            or data_root.get("ltp")
            or data_root.get("last_price")
        )
        expiry = data_root.get("expiry") or underlying_root.get("expiry") or payload.get("expiry")
        symbol = (
            data_root.get("symbol")
            or underlying_root.get("symbol")
            or payload.get("symbol")
            or self._settings.dhan_symbol
        )

        rows_data: Any = None
        if isinstance(data_root.get("optionsChain"), list):
            # FYERS optionchain response shape: response["data"]["optionsChain"] = list[...]
            rows_data = data_root["optionsChain"]
        elif isinstance(payload.get("data"), list):
            rows_data = payload.get("data")
        elif isinstance(payload.get("d"), list):
            rows_data = payload["d"]
        elif isinstance(payload.get("d"), dict):
            rows_data = payload["d"].get("data") if isinstance(payload["d"].get("data"), list) else None
            if rows_data is None:
                rows_data = self._find_option_rows(payload["d"])
        else:
            rows_data = payload.get("data") or self._find_option_rows(payload)
        if not isinstance(rows_data, list):
            rows_data = []
        rows = [self._normalize_row(item) for item in rows_data]
        rows = [row for row in rows if row is not None]
        rows.sort(key=lambda r: r.strike_price)

        total_call_oi = sum(r.call.open_interest for r in rows)
        total_put_oi = sum(r.put.open_interest for r in rows)
        total_call_change_oi = sum(r.call.change_in_oi for r in rows)
        total_put_change_oi = sum(r.put.change_in_oi for r in rows)
        strongest_call = max(rows, key=lambda r: r.call.open_interest, default=None)
        strongest_put = max(rows, key=lambda r: r.put.open_interest, default=None)
        put_call_ratio = round(total_put_oi / total_call_oi, 4) if total_call_oi else None

        underlying = UnderlyingQuote(
            symbol=symbol,
            spot_price=spot_price,
            change=None,
            change_percent=None,
            expiry=expiry,
        )

        return OptionChainSnapshot(
            generated_at=generated_at,
            source=getattr(self._client, "source", "upstream"),
            underlying=underlying,
            summary=OptionChainSummary(
                total_call_oi=total_call_oi,
                total_put_oi=total_put_oi,
                total_call_change_oi=total_call_change_oi,
                total_put_change_oi=total_put_change_oi,
                put_call_ratio=put_call_ratio,
                strongest_call_oi_strike=strongest_call.strike_price if strongest_call else None,
                strongest_put_oi_strike=strongest_put.strike_price if strongest_put else None,
            ),
            rows=rows,
        )

    def _mock_snapshot(self) -> OptionChainSnapshot:
        generated_at = datetime.now(timezone.utc)
        underlying = UnderlyingQuote(
            symbol=self._settings.dhan_symbol,
            spot_price=None,
            change=None,
            change_percent=None,
            expiry=None,
        )
        return OptionChainSnapshot(
            generated_at=generated_at,
            source="mock",
            underlying=underlying,
            summary=OptionChainSummary(),
            rows=[],
        )

    # ------------------------------------------------------------------
    # Helper methods (unchanged)
    # ------------------------------------------------------------------

    def _normalize_dhan_payload(
        self,
        payload: dict[str, Any],
        *,
        generated_at: datetime,
    ) -> OptionChainSnapshot:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        oc = data.get("oc") if isinstance(data, dict) else None
        oc = oc if isinstance(oc, dict) else {}

        request_meta = payload.get("_dhan_request") if isinstance(payload.get("_dhan_request"), dict) else {}
        expiry = request_meta.get("Expiry") or data.get("expiry")
        symbol = request_meta.get("symbol") or self._settings.dhan_symbol

        spot_price = self._coerce_number(data.get("last_price") or data.get("ltp") or data.get("spot"))  # best-effort

        rows: list[OptionChainRow] = []
        for strike_key, strike_value in oc.items():
            if not isinstance(strike_value, dict):
                continue
            strike = self._coerce_number(strike_key) or self._coerce_number(strike_value.get("strike"))
            if strike is None:
                continue
            call_raw = strike_value.get("ce") or strike_value.get("CE") or {}
            put_raw = strike_value.get("pe") or strike_value.get("PE") or {}
            call = self._normalize_leg(call_raw, prefix="call")
            put = self._normalize_leg(put_raw, prefix="put")
            pcr = round(put.open_interest / call.open_interest, 4) if call.open_interest else None
            rows.append(OptionChainRow(strike_price=strike, call=call, put=put, pcr=pcr))

        rows.sort(key=lambda r: r.strike_price)

        total_call_oi = sum(r.call.open_interest for r in rows)
        total_put_oi = sum(r.put.open_interest for r in rows)
        total_call_change_oi = sum(r.call.change_in_oi for r in rows)
        total_put_change_oi = sum(r.put.change_in_oi for r in rows)
        strongest_call = max(rows, key=lambda r: r.call.open_interest, default=None)
        strongest_put = max(rows, key=lambda r: r.put.open_interest, default=None)
        put_call_ratio = round(total_put_oi / total_call_oi, 4) if total_call_oi else None

        underlying = UnderlyingQuote(
            symbol=str(symbol),
            spot_price=spot_price,
            change=None,
            change_percent=None,
            expiry=str(expiry) if expiry else None,
        )

        return OptionChainSnapshot(
            generated_at=generated_at,
            source="dhan",
            underlying=underlying,
            summary=OptionChainSummary(
                total_call_oi=total_call_oi,
                total_put_oi=total_put_oi,
                total_call_change_oi=total_call_change_oi,
                total_put_change_oi=total_put_change_oi,
                put_call_ratio=put_call_ratio,
                strongest_call_oi_strike=strongest_call.strike_price if strongest_call else None,
                strongest_put_oi_strike=strongest_put.strike_price if strongest_put else None,
            ),
            rows=rows,
        )

    def _find_option_rows(self, payload: Any) -> list[dict[str, Any]]:
        candidates: list[list[dict[str, Any]]] = []

        def walk(node: Any) -> None:
            if isinstance(node, list) and node:
                if all(isinstance(item, dict) for item in node):
                    sample = node[0]
                    keys = {str(key).lower() for key in sample.keys()}
                    if (
                        {"ce", "pe"} <= keys
                        or {"call", "put"} <= keys
                        or {"strikeprice", "ce", "pe"} <= keys
                        or {"strike", "call", "put"} <= keys
                    ):
                        candidates.append(node)
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                for value in node.values():
                    walk(value)

        walk(payload)
        if candidates:
            return max(candidates, key=len)
        return []

    def _normalize_row(self, item: dict[str, Any]) -> OptionChainRow | None:
        strike = self._coerce_number(
            item.get("strikePrice")
            or item.get("strike_price")
            or item.get("strike")
            or item.get("strikeprice")
        )
        if strike is None:
            return None

        call_raw = item.get("CE") or item.get("ce") or item.get("call") or item.get("calls") or {}
        put_raw = item.get("PE") or item.get("pe") or item.get("put") or item.get("puts") or {}

        call = self._normalize_leg(call_raw, prefix="call")
        put = self._normalize_leg(put_raw, prefix="put")
        pcr = round(put.open_interest / call.open_interest, 4) if call.open_interest else None
        return OptionChainRow(strike_price=strike, call=call, put=put, pcr=pcr)

    def _normalize_leg(self, value: Any, prefix: str) -> OptionLegMetrics:
        payload = value if isinstance(value, dict) else {}
        change_in_oi = self._coerce_number(
            payload.get("changeinOpenInterest")
            or payload.get("changeInOi")
            or payload.get("changeOi")
            or payload.get("oiChange")
            or payload.get("change_in_oi")
            or payload.get(f"{prefix}_change_in_oi")
        )
        if change_in_oi is None:
            oi = self._coerce_number(payload.get("oi") or payload.get("openInterest") or payload.get("open_interest"))
            prev_oi = self._coerce_number(payload.get("previous_oi") or payload.get("prev_oi"))
            if oi is not None and prev_oi is not None:
                change_in_oi = oi - prev_oi
        return OptionLegMetrics(
            last_price=self._coerce_number(
                payload.get("lastPrice")
                or payload.get("ltp")
                or payload.get("last_price")
                or payload.get(f"{prefix}_ltp")
            )
            or 0.0,
            open_interest=self._coerce_number(
                payload.get("openInterest")
                or payload.get("oi")
                or payload.get("open_interest")
                or payload.get(f"{prefix}_oi")
            )
            or 0.0,
            change_in_oi=change_in_oi or 0.0,
            volume=self._coerce_number(
                payload.get("totalTradedVolume")
                or payload.get("volume")
                or payload.get("tradedVolume")
                or payload.get(f"{prefix}_volume")
            )
            or 0.0,
            implied_volatility=self._coerce_number(
                payload.get("impliedVolatility")
                or payload.get("iv")
                or payload.get("implied_volatility")
                or payload.get(f"{prefix}_iv")
            ),
        )

    def _find_first_numeric(self, payload: Any, keys: list[str]) -> float | None:
        value = self._find_first_value(payload, keys)
        return self._coerce_number(value)

    def _find_first_string(self, payload: Any, keys: list[str]) -> str | None:
        value = self._find_first_value(payload, keys)
        return str(value) if value is not None else None

    def _find_first_value(self, payload: Any, keys: list[str]) -> Any:
        lowered_keys = {key.lower() for key in keys}
        stack = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if str(key).lower() in lowered_keys:
                        return value
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return None

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            return None
