from __future__ import annotations

from collections import deque
from typing import TypedDict

from .models import LastEvent, MessageKind

_KINDS: tuple[MessageKind, ...] = ("text", "image", "face")
_WINDOW = 24


class MsgRecord(TypedDict):
    send_id: str
    fp: str


class ChatState:
    def __init__(self, window_size: int = _WINDOW) -> None:
        self.messages: dict[str, deque[MsgRecord]] = {
            kind: deque(maxlen=window_size) for kind in _KINDS
        }
        self.last_handled_fingerprint: str | None = None
        self.last_action_at: float = 0.0
        self.last_event: LastEvent | None = None
        self.stats_day: str = ""
        self.repeat_counts: dict[str, int] = {}
        self.repeat_names: dict[str, str] = {}

    def clear_if_same_sender(self, kind: str, send_id: str, need_different: bool) -> None:
        if not need_different:
            return
        window = self.messages[kind]
        if window and window[-1]["send_id"] == send_id:
            window.clear()

    def push(self, kind: str, send_id: str, fingerprint: str) -> None:
        self.messages[kind].append({"send_id": send_id, "fp": fingerprint})

    def uniform_tail(self, kind: str, count: int) -> str | None:
        if count <= 0:
            return None
        window = self.messages[kind]
        if len(window) < count:
            return None
        tail = list(window)[-count:]
        first = tail[0]["fp"]
        if any(item["fp"] != first for item in tail):
            return None
        return first

    def combo(self, kind: str) -> int:
        window = self.messages[kind]
        if not window:
            return 0
        fingerprint = window[-1]["fp"]
        total = 0
        for item in reversed(window):
            if item["fp"] != fingerprint:
                break
            total += 1
        return total

    def clear_windows(self) -> None:
        for window in self.messages.values():
            window.clear()

    def mark_handled(self, fingerprint: str, now: float, event: LastEvent) -> None:
        self.last_handled_fingerprint = fingerprint
        self.last_action_at = now
        self.last_event = event
        self.clear_windows()

    def note_repeat(self, sender_id: str, sender_name: str, day: str) -> None:
        if self.stats_day != day:
            self.stats_day = day
            self.repeat_counts.clear()
            self.repeat_names.clear()
        self.repeat_counts[sender_id] = self.repeat_counts.get(sender_id, 0) + 1
        if sender_name:
            self.repeat_names[sender_id] = sender_name

    def top_repeaters(self, limit: int = 5) -> list[tuple[str, str, int]]:
        ranked = sorted(self.repeat_counts.items(), key=lambda item: (-item[1], item[0]))
        result: list[tuple[str, str, int]] = []
        for sender_id, count in ranked[:limit]:
            result.append((sender_id, self.repeat_names.get(sender_id, sender_id), count))
        return result


class StateManager:
    def __init__(self) -> None:
        self._states: dict[str, ChatState] = {}

    def get(self, chat_key: str) -> ChatState:
        state = self._states.get(chat_key)
        if state is None:
            state = ChatState()
            self._states[chat_key] = state
        return state

    def reset(self, chat_key: str) -> None:
        self._states.pop(chat_key, None)

    def clear(self) -> None:
        self._states.clear()
