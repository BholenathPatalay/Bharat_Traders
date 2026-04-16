from __future__ import annotations

import time
from typing import Any


class InMemoryRedis:
    """Small async Redis-like store used as a runtime fallback."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._expirations: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        expiry = self._expirations.get(key)
        if expiry is None:
            return False
        if time.time() >= expiry:
            self._store.pop(key, None)
            self._expirations.pop(key, None)
            return True
        return False

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> Any:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self._store[key] = value
        if ex is not None:
            self._expirations[key] = time.time() + ex
        else:
            self._expirations.pop(key, None)
        return True

    async def delete(self, key: str) -> int:
        existed = key in self._store and not self._is_expired(key)
        self._store.pop(key, None)
        self._expirations.pop(key, None)
        return 1 if existed else 0

    async def aclose(self) -> None:
        self._store.clear()
        self._expirations.clear()
