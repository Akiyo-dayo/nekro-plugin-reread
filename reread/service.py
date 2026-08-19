from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Protocol

from .engine import evaluate
from .models import EngineConfig, IncomingMessage, Plan
from .state import ChatState, StateManager


class EnableStore(Protocol):
    async def get(self, chat_key: str, store_key: str = "enabled") -> str | None: ...

    async def set(self, chat_key: str, store_key: str = "enabled", value: str = "") -> None: ...


class MemoryEnableStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], str] = {}

    async def get(self, chat_key: str, store_key: str = "enabled") -> str | None:
        return self._data.get((chat_key, store_key))

    async def set(self, chat_key: str, store_key: str = "enabled", value: str = "") -> None:
        self._data[(chat_key, store_key)] = value


class RereadService:
    def __init__(
        self,
        store: EnableStore | None = None,
        rng_factory=random.Random,
        clock=time.time,
    ) -> None:
        self.states = StateManager()
        self.store = store or MemoryEnableStore()
        self._rng_factory = rng_factory
        self._clock = clock
        self._disabled: set[str] = set()

    def observe(self, incoming: IncomingMessage, config: EngineConfig) -> Plan | None:
        if incoming.chat_key in self._disabled:
            return None
        state = self.states.get(incoming.chat_key)
        now = float(self._clock())
        day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        return evaluate(state, incoming, config, self._rng_factory(), now, day=day)

    def snapshot(self, chat_key: str) -> ChatState:
        return self.states.get(chat_key)

    def is_enabled(self, chat_key: str) -> bool:
        return chat_key not in self._disabled

    async def load_enabled(self, chat_key: str, default: bool = True) -> bool:
        raw = await self.store.get(chat_key, "enabled")
        if raw is None:
            enabled = default
        else:
            enabled = raw.strip() not in {"0", "false", "off", "no"}
        if enabled:
            self._disabled.discard(chat_key)
        else:
            self._disabled.add(chat_key)
        return enabled

    async def set_enabled(self, chat_key: str, enabled: bool) -> None:
        await self.store.set(chat_key, "enabled", "1" if enabled else "0")
        if enabled:
            self._disabled.discard(chat_key)
        else:
            self._disabled.add(chat_key)

    def reset(self, chat_key: str) -> None:
        self.states.reset(chat_key)
        self._disabled.discard(chat_key)
