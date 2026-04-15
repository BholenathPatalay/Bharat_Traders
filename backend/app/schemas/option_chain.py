from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OptionLegMetrics(BaseModel):
    last_price: float = 0.0
    open_interest: float = 0.0
    change_in_oi: float = 0.0
    volume: float = 0.0
    implied_volatility: float | None = None


class OptionChainRow(BaseModel):
    strike_price: float
    call: OptionLegMetrics
    put: OptionLegMetrics
    pcr: float | None = None


class UnderlyingQuote(BaseModel):
    symbol: str
    spot_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    expiry: str | None = None


class OptionChainSummary(BaseModel):
    total_call_oi: float = 0.0
    total_put_oi: float = 0.0
    total_call_change_oi: float = 0.0
    total_put_change_oi: float = 0.0
    put_call_ratio: float | None = None
    strongest_call_oi_strike: float | None = None
    strongest_put_oi_strike: float | None = None


class OptionChainSnapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    generated_at: datetime
    source: str = "indstocks"
    pinned_strikes: list[float] = Field(default_factory=list)
    underlying: UnderlyingQuote
    summary: OptionChainSummary
    rows: list[OptionChainRow]


class OptionChainDelta(BaseModel):
    type: Literal["delta"] = "delta"
    generated_at: datetime
    changed_rows: list[OptionChainRow] = Field(default_factory=list)
    removed_strikes: list[float] = Field(default_factory=list)
    underlying: UnderlyingQuote | None = None
    summary: OptionChainSummary | None = None

