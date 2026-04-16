from fastapi import APIRouter, Request


router = APIRouter(tags=["health"])


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health")
async def healthcheck(request: Request) -> dict[str, int | str]:
    manager = request.app.state.connection_manager
    db_ready = getattr(request.app.state, "db_ready", True)
    return {
        "status": "ok",
        "connections": manager.count,
        "database": "ok" if db_ready else "degraded",
    }
