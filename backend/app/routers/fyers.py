import logging
import secrets

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/fyers", tags=["fyers"])
logger = logging.getLogger(__name__)


@router.get("/auth-url")
async def get_auth_url(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    if not settings.fyers_client_id or not settings.fyers_redirect_uri:
        raise HTTPException(status_code=400, detail="FYERS_CLIENT_ID and FYERS_REDIRECT_URI are required")

    state = secrets.token_urlsafe(16)
    await request.app.state.redis.set(f"fyers:oauth-state:{state}", "1", ex=5 * 60)

    client = request.app.state.fyers_client
    auth_url = client.build_auth_url(state=state)
    return {"auth_url": auth_url, "state": state, "redirect_uri": settings.fyers_redirect_uri}


@router.get("/callback")
async def fyers_callback(
    request: Request,
    state: str | None = None,
    auth_code: str | None = None,
    code: str | None = None,
) -> dict[str, str]:
    resolved_code = (auth_code or code or "").strip()
    resolved_state = (state or "").strip()
    if not resolved_code or not resolved_state:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing auth_code/state. Start the flow from /api/v1/fyers/auth-url and complete the FYERS login; "
                "FYERS will redirect back here with the required query params."
            ),
        )

    redis = request.app.state.redis
    key = f"fyers:oauth-state:{resolved_state}"
    ok = await redis.get(key)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid/expired state; please restart the auth flow")
    await redis.delete(key)

    client = request.app.state.fyers_client
    try:
        token = await client.exchange_auth_code(auth_code=resolved_code)
    except Exception as exc:
        logger.exception("FYERS token exchange failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Return a short response; we keep the token in Redis (and optionally in env via FYERS_ACCESS_TOKEN).
    return {"status": "ok", "stored": "redis", "access_token_preview": token[:8] + "..."}


@router.get("/status")
async def fyers_status(request: Request) -> dict[str, str | bool]:
    client = request.app.state.fyers_client
    try:
        token = await client.get_access_token()
    except Exception:
        return {"authenticated": False, "stored": "none"}
    return {"authenticated": True, "stored": "redis/env", "access_token_preview": token[:8] + "..."}


@router.get("/option-chain")
async def fyers_option_chain(request: Request) -> dict:
    client = request.app.state.fyers_client
    try:
        payload = await client.fetch_option_chain()
    except Exception as exc:
        logger.exception("FYERS option chain fetch failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return payload
