from datetime import datetime

from pydantic import BaseModel


class WatchlistPinRead(BaseModel):
    strike_price: float
    created_at: datetime


class WatchlistPinCollection(BaseModel):
    strikes: list[float]


class WatchlistPinToggleResponse(BaseModel):
    strike_price: float
    pinned: bool
    strikes: list[float]

