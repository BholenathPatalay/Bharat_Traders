from contextlib import asynccontextmanager

import httpx
import asyncio  # ✅ ADDED
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from redis.asyncio import from_url as redis_from_url

from app.auth import auth_backend, fastapi_users, google_oauth_client
from app.core.config import get_settings
from app.db import create_db_and_tables
from app.routers import fyers, health, option_chain, watchlist
from app.schemas.user import UserRead, UserUpdate
from app.services.broadcaster import ConnectionManager
from app.services.fyers import FyersClient
from app.services.option_chain_service import OptionChainService
from app.services.poller import OptionChainPoller


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()

    redis = redis_from_url(settings.redis_url)
    app.state.settings = settings

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5),
    )

    connection_manager = ConnectionManager()
    fyers_client = FyersClient(http_client=http_client, redis=redis, settings=settings)

    option_chain_service = OptionChainService(
        redis=redis,
        client=fyers_client,
        settings=settings,
    )

    poller = OptionChainPoller(
        service=option_chain_service,
        manager=connection_manager,
        refresh_seconds=settings.option_chain_refresh_seconds,
    )

    app.state.redis = redis
    app.state.http_client = http_client
    app.state.connection_manager = connection_manager
    app.state.option_chain_service = option_chain_service
    app.state.option_chain_poller = poller
    app.state.fyers_client = fyers_client

    # ✅ FIX: run poller in background (NON-BLOCKING)
    try:
        asyncio.create_task(poller.start())
        print("✅ Poller started in background")
    except Exception as e:
        print("❌ Poller start failed:", e)

    try:
        yield
    finally:
        await poller.stop()
        await http_client.aclose()
        await redis.aclose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix=f"{settings.api_v1_prefix}/auth/jwt",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix=f"{settings.api_v1_prefix}/users",
    tags=["users"],
)

app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        settings.secret_key,
        redirect_url=settings.google_oauth_redirect_url,
        associate_by_email=True,
        is_verified_by_default=True,
    ),
    prefix=f"{settings.api_v1_prefix}/auth/google",
    tags=["auth"],
)

app.include_router(option_chain.router, prefix=settings.api_v1_prefix)
app.include_router(watchlist.router, prefix=settings.api_v1_prefix)
app.include_router(fyers.router, prefix=settings.api_v1_prefix)


@app.websocket("/ws/option-chain")
async def websocket_alias(websocket: WebSocket):
    await option_chain.option_chain_socket(websocket)
