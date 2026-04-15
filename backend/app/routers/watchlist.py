from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_user
from app.db import User, WatchlistPin, get_async_session
from app.schemas.watchlist import WatchlistPinCollection, WatchlistPinToggleResponse


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/pins", response_model=WatchlistPinCollection)
async def get_watchlist_pins(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> WatchlistPinCollection:
    result = await session.execute(
        select(WatchlistPin.strike_price).where(WatchlistPin.user_id == user.id)
    )
    return WatchlistPinCollection(strikes=sorted(result.scalars().all()))


@router.post("/pins/{strike_price}", response_model=WatchlistPinToggleResponse)
async def toggle_watchlist_pin(
    strike_price: float,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> WatchlistPinToggleResponse:
    existing = await session.execute(
        select(WatchlistPin).where(
            WatchlistPin.user_id == user.id,
            WatchlistPin.strike_price == strike_price,
        )
    )
    pin = existing.scalar_one_or_none()

    if pin:
        await session.delete(pin)
        pinned = False
    else:
        session.add(WatchlistPin(user_id=user.id, strike_price=strike_price))
        pinned = True

    await session.commit()

    result = await session.execute(
        select(WatchlistPin.strike_price).where(WatchlistPin.user_id == user.id)
    )
    strikes = sorted(result.scalars().all())

    return WatchlistPinToggleResponse(
        strike_price=strike_price,
        pinned=pinned,
        strikes=strikes,
    )
