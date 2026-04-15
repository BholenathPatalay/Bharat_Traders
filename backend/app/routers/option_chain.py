import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import optional_current_active_user
from app.core.config import get_settings
from app.db import User, WatchlistPin, get_async_session
from app.schemas.option_chain import OptionChainSnapshot


router = APIRouter(prefix="/option-chain", tags=["option-chain"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("", response_model=OptionChainSnapshot)
async def get_option_chain(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User | None = Depends(optional_current_active_user),
) -> OptionChainSnapshot:
    service = request.app.state.option_chain_service
    try:
        snapshot = await service.get_snapshot()
    except httpx.HTTPStatusError as exc:
        logger.exception("Option chain upstream request failed: %s", exc.response.status_code)
        detail: str | dict = "Option chain upstream request failed"
        if settings.environment.lower() == "development":
            body = (exc.response.text or "").strip()
            if len(body) > 800:
                body = body[:800] + "..."
            detail = {
                "message": "Option chain upstream request failed",
                "upstream_status": exc.response.status_code,
                "upstream_body": body,
            }
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        logger.exception("Option chain upstream request failed")
        raise HTTPException(status_code=502, detail="Option chain upstream request failed") from exc
    except Exception as exc:
        logger.exception("Option chain service failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if user is None:
        return snapshot

    result = await session.execute(
        select(WatchlistPin.strike_price).where(WatchlistPin.user_id == user.id)
    )
    pinned_strikes = result.scalars().all()
    return service.with_pins(snapshot, pinned_strikes)

@router.websocket("/ws")
async def option_chain_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    app = websocket.scope.get("app")
    if app is None:
        await websocket.close(code=1011)
        return

    manager = app.state.connection_manager
    service = app.state.option_chain_service

    # Track immediately so poller can broadcast to this client
    await manager.track(websocket)
    client = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connected: client=%s", client)

    # Attempt to send cached snapshot, but never fail
    try:
        snapshot = await service.get_snapshot()
        await websocket.send_json(snapshot.model_dump(mode="json"))
    except Exception as e:
        logger.warning("Initial snapshot unavailable: %s", e)
        try:
            await websocket.send_json({"type": "waiting", "message": "Loading data..."})
        except Exception:
            # Client may have already disconnected – no problem
            pass

    # Main loop – keep connection alive, poller will send updates
    try:
        while True:
            # Wait for any message (like ping) or disconnect
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: client=%s", client)
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
    finally:
        await manager.disconnect(websocket)