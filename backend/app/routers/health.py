from fastapi import APIRouter, Request


router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(request: Request) -> dict[str, int | str]:
    manager = request.app.state.connection_manager
    return {
        "status": "ok",
        "connections": manager.count,
    }

