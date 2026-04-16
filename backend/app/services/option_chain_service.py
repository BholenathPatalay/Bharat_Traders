import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.option_chain import (
    OptionChainRow,
    OptionChainSnapshot,
    OptionChainSummary,
    OptionLegMetrics,
    UnderlyingQuote,
)
from app.services.fyers import FyersClient

logger = logging.getLogger(__name__)


class OptionChainService:
    _CACHE_KEY = "option_chain:latest"
    _LAST_GOOD_KEY = "option_chain:last_good"

    def __init__(self, redis: Redis, client: FyersClient, settings: Settings) -> None:
        self._redis = redis
        self._client = client
        self._settings = settings

    async def get_option_chain(self, force_refresh: bool = False) -> dict[str, Any]:
        """Return raw cached option chain dict from FYERS."""
        if not force_refresh:
            cached = await self._redis.get(self._CACHE_KEY)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in option chain cache, will refresh.")

        try:
            fresh = await self._client.fetch_option_chain()
            fresh["_cached_at"] = datetime.now(timezone.utc).isoformat()

            await self._redis.set(
                self._CACHE_KEY,
                json.dumps(fresh),
                ex=self._settings.option_chain_cache_ttl_seconds,
            )
            await self._redis.set(
                self._LAST_GOOD_KEY,
                json.dumps(fresh),
                ex=self._settings.option_chain_last_good_ttl_seconds,
            )
            return fresh

        except Exception as e:
            logger.exception("Failed to fetch fresh option chain from FYERS: %s", e)
            last_good = await self._redis.get(self._LAST_GOOD_KEY)
            if last_good:
                try:
                    data = json.loads(last_good)
                    data["_stale"] = True
                    data["_error"] = str(e)
                    return data
                except json.JSONDecodeError:
                    pass
            raise

    async def get_snapshot(self) -> OptionChainSnapshot:
        """Return a fully parsed OptionChainSnapshot model."""
        raw = await self.get_option_chain()
        return self._parse_fyers_response(raw)

    def with_pins(self, snapshot: OptionChainSnapshot, pinned_strikes: list[float]) -> OptionChainSnapshot:
        """Return a new snapshot with the given pinned_strikes list set."""
        return snapshot.model_copy(update={"pinned_strikes": pinned_strikes})

    # ------------------------------------------------------------------
    # Private: convert FYERS response to OptionChainSnapshot
    # ------------------------------------------------------------------
    def _parse_fyers_response(self, data: dict[str, Any]) -> OptionChainSnapshot:
        # Unwrap outer envelope
        if data.get("s") == "ok" and "data" in data:
            inner = data["data"]
        else:
            inner = data

        options_chain = inner.get("optionsChain", [])
        if not options_chain:
            raise ValueError("No optionsChain found in FYERS response")

        # Extract underlying quote from the first item (index data)
        index_item = options_chain[0]
        spot_price = index_item.get("ltp", 0.0)
        change = index_item.get("ltpch")
        change_percent = index_item.get("ltpchp")

        # Get expiry from the first expiry in expiryData
        expiry_data_list = inner.get("expiryData", [])
        expiry_str = ""
        if expiry_data_list:
            expiry_ts = expiry_data_list[0].get("expiry")
            try:
                expiry_str = datetime.fromtimestamp(int(expiry_ts)).strftime("%d-%b-%Y")
            except (ValueError, TypeError):
                expiry_str = str(expiry_ts)

        # Build a dict to pair calls and puts by strike price
        strikes_dict: dict[float, dict[str, Any]] = {}

        for item in options_chain[1:]:  # Skip the index item
            strike_price = item.get("strike_price")
            if strike_price is None or strike_price <= 0:
                continue

            option_type = item.get("option_type", "").upper()
            if strike_price not in strikes_dict:
                strikes_dict[strike_price] = {"call": None, "put": None}

            if option_type == "CE":
                strikes_dict[strike_price]["call"] = item
            elif option_type == "PE":
                strikes_dict[strike_price]["put"] = item

        # Helper to extract numeric values (handle strings like "12,345")
        def to_float(val):
            if val is None:
                return 0.0
            if isinstance(val, str):
                val = val.replace(",", "")
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        # Build rows and aggregate summary
        rows = []
        total_call_oi = 0.0
        total_put_oi = 0.0
        total_call_change_oi = 0.0
        total_put_change_oi = 0.0
        strongest_call_oi_strike = None
        strongest_put_oi_strike = None
        max_call_oi = 0.0
        max_put_oi = 0.0

        for strike_price, pair in sorted(strikes_dict.items()):
            call_data = pair.get("call") or {}
            put_data = pair.get("put") or {}

            call_metrics = OptionLegMetrics(
                last_price=to_float(call_data.get("ltp")),
                open_interest=to_float(call_data.get("oi")),
                change_in_oi=to_float(call_data.get("oich") or call_data.get("change")),
                volume=to_float(call_data.get("volume") or call_data.get("vol")),
                implied_volatility=to_float(call_data.get("iv")) if call_data.get("iv") is not None else None,
            )
            put_metrics = OptionLegMetrics(
                last_price=to_float(put_data.get("ltp")),
                open_interest=to_float(put_data.get("oi")),
                change_in_oi=to_float(put_data.get("oich") or put_data.get("change")),
                volume=to_float(put_data.get("volume") or put_data.get("vol")),
                implied_volatility=to_float(put_data.get("iv")) if put_data.get("iv") is not None else None,
            )

            rows.append(
                OptionChainRow(
                    strike_price=strike_price,
                    call=call_metrics,
                    put=put_metrics,
                    pcr=None,
                )
            )

            # Aggregate totals
            total_call_oi += call_metrics.open_interest
            total_put_oi += put_metrics.open_interest
            total_call_change_oi += call_metrics.change_in_oi
            total_put_change_oi += put_metrics.change_in_oi

            if call_metrics.open_interest > max_call_oi:
                max_call_oi = call_metrics.open_interest
                strongest_call_oi_strike = strike_price
            if put_metrics.open_interest > max_put_oi:
                max_put_oi = put_metrics.open_interest
                strongest_put_oi_strike = strike_price

        # Sort rows by strike price (already sorted from dict iteration)
        rows.sort(key=lambda r: r.strike_price)

        # Build summary
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else None
        summary = OptionChainSummary(
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            total_call_change_oi=total_call_change_oi,
            total_put_change_oi=total_put_change_oi,
            put_call_ratio=pcr,
            strongest_call_oi_strike=strongest_call_oi_strike,
            strongest_put_oi_strike=strongest_put_oi_strike,
        )

        # Underlying quote
        underlying = UnderlyingQuote(
            symbol=self._settings.fyers_symbol,
            spot_price=spot_price,
            change=change,
            change_percent=change_percent,
            expiry=expiry_str,
        )

        generated_at = datetime.now(timezone.utc)

        return OptionChainSnapshot(
            generated_at=generated_at,
            source="fyers",
            pinned_strikes=[],
            underlying=underlying,
            summary=summary,
            rows=rows,
        )
