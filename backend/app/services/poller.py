import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.option_chain_service import OptionChainService
    from app.services.broadcaster import ConnectionManager

logger = logging.getLogger(__name__)


class OptionChainPoller:
    def __init__(
        self,
        service: "OptionChainService",
        manager: "ConnectionManager",
        refresh_seconds: int,
    ):
        self._service = service
        self._manager = manager
        self._refresh_seconds = refresh_seconds
        self._task: asyncio.Task | None = None
        self._running = False  # control flag

    async def start(self):
        """
        Start poller safely.
        Will NOT crash if FYERS token is missing.
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("✅ Poller started in background")

    async def stop(self):
        """
        Stop poller gracefully.
        """
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Poller stopped")

    async def _poll_loop(self):
        """
        Main polling loop.
        Handles missing FYERS token safely without crashing.
        """
        while self._running:
            try:
                # ✅ Step 1: Check FYERS token availability
                try:
                    await self._service._client.get_access_token()
                except Exception as e:
                    logger.warning("⏳ FYERS token not available yet. Skipping poll cycle: %s", e)
                    await asyncio.sleep(self._refresh_seconds)
                    continue

                # ✅ Step 2: Fetch data
                data = await self._service.get_option_chain(force_refresh=True)

                # ✅ Step 3: Broadcast to clients
                await self._manager.broadcast_json(data)

            except Exception as e:
                # ⚠️ Never crash loop
                logger.exception("❌ Polling error: %s", e)

            # ✅ Step 4: Wait before next cycle
            await asyncio.sleep(self._refresh_seconds)
