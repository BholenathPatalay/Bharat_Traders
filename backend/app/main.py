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
from app.services.in_memory_redis import InMemoryRedis
from app.services.option_chain_service import OptionChainService
from app.services.poller import OptionChainPoller


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Create DB tables (non-fatal in production so the API can still serve non-DB routes)
    app.state.db_ready = True
    try:
        await create_db_and_tables()
        print("✅ Database schema initialized")
    except Exception as e:
        app.state.db_ready = False
        print("⚠️ Database initialization failed; continuing without DB-backed routes:", e)

    # ✅ Initialize Redis (fallback to in-memory cache if unavailable)
    redis = redis_from_url(settings.redis_url)
    try:
        await redis.ping()
        print("✅ Redis connected successfully")
    except Exception as e:
        print("⚠️ Redis connection failed, using in-memory fallback:", e)
        redis = InMemoryRedis()

    app.state.settings = settings

    # ✅ HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5),
    )

    # ✅ Services
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

    # ✅ Store in app state
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
        # ✅ Graceful shutdown
        try:
            await poller.stop()
        except Exception as e:
            print("⚠️ Poller stop error:", e)

        await http_client.aclose()
        await redis.aclose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Routes
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

# ✅ WebSocket
@app.websocket("/ws/option-chain")
async def websocket_alias(websocket: WebSocket):
    await option_chain.option_chain_socket(websocket)
