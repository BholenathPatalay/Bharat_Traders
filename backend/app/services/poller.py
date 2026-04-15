import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.option_chain_service import OptionChainService
    from app.services.broadcaster import ConnectionManager

logger = logging.getLogger(__name__)


class OptionChainPoller:
    def __init__(self, service: "OptionChainService", manager: "ConnectionManager", refresh_seconds: int):
        self._service = service
        self._manager = manager
        self._refresh_seconds = refresh_seconds
        self._task: asyncio.Task | None = None

    async def start(self):
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self):
        while True:
            try:
                data = await self._service.get_option_chain(force_refresh=True)
                # Use broadcast_json instead of broadcast
                await self._manager.broadcast_json(data)
            except Exception as e:
                logger.exception("Polling error: %s", e)
            await asyncio.sleep(self._refresh_seconds)