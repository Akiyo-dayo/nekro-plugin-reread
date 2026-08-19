from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .models import EngineConfig, IncomingMessage, LastEvent, Plan
from .parse import kind_enabled
from .render import pick_interrupt_text, pick_mute_text
from .state import ChatState


class RNG(Protocol):
    def random(self) -> float: ...

    def choice(self, seq): ...


def threshold_of(kind: str, config: EngineConfig) -> int:
    if kind == "text":
        return config.text_threshold
    if kind == "image":
        return config.image_threshold
    return config.face_threshold


def _clamp_prob(value: float) -> float:
    if value <= 0:
        return 0.0
    if value >= 1:
        return 1.0
    return value


def _contains_blocked(text: str, words: tuple[str, ...]) -> bool:
    if not text or not words:
        return False
    lowered = text.lower()
    return any(word.lower() in lowered for word in words if word.strip())


def _is_repeat_contribution(state: ChatState, incoming: IncomingMessage) -> bool:
    window = state.messages[incoming.kind]
    return bool(window) and window[-1]["fp"] == incoming.fingerprint and window[-1]["send_id"] != incoming.sender_id


def evaluate(
    state: ChatState,
    incoming: IncomingMessage,
    config: EngineConfig,
    rng: RNG,
    now: float,
    day: str = "",
) -> Plan | None:
    if incoming.is_recalled:
        return None
    if config.skip_tome and incoming.is_tome:
        return None
    if config.skip_commands and incoming.is_command:
        return None
    if incoming.sender_id and incoming.sender_id in config.blocked_users:
        return None
    if incoming.kind == "text":
        if config.max_text_len > 0 and len(incoming.text) > config.max_text_len:
            return None
        if _contains_blocked(incoming.text, config.blocked_words):
            return None
    if not kind_enabled(incoming.kind, config.enable_text, config.enable_image, config.enable_face):
        return None

    threshold = threshold_of(incoming.kind, config)
    if threshold <= 1:
        return None

    if _is_repeat_contribution(state, incoming):
        state.note_repeat(incoming.sender_id, incoming.sender_name, day or _today(now))

    state.clear_if_same_sender(incoming.kind, incoming.sender_id, config.need_different)
    state.push(incoming.kind, incoming.sender_id, incoming.fingerprint)

    fingerprint = state.uniform_tail(incoming.kind, threshold)
    if not fingerprint:
        return None
    if state.last_handled_fingerprint == fingerprint:
        return None
    if config.cooldown_sec > 0 and state.last_action_at and now - state.last_action_at < config.cooldown_sec:
        return None

    combo = state.combo(incoming.kind)
    mute_seconds = max(0, int(config.mute_seconds))
    if mute_seconds > 0 and config.mute_prob > 0 and rng.random() < _clamp_prob(config.mute_prob):
        plan = Plan(
            action="mute",
            kind=incoming.kind,
            fingerprint=fingerprint,
            combo=combo,
            interrupt_text=pick_mute_text(incoming.sender_name, combo, mute_seconds, rng.choice),
            mute_seconds=mute_seconds,
        )
        _commit(state, plan, now, incoming.preview)
        return plan

    interrupt_prob = _clamp_prob(config.interrupt_prob)
    if interrupt_prob > 0 and rng.random() < interrupt_prob:
        plan = Plan(
            action="interrupt",
            kind=incoming.kind,
            fingerprint=fingerprint,
            combo=combo,
            interrupt_text=pick_interrupt_text(combo, config.interrupt_texts, rng.choice),
        )
        _commit(state, plan, now, incoming.preview)
        return plan

    if config.reread_prob > 0 and rng.random() < _clamp_prob(config.reread_prob):
        plan = Plan(
            action="follow",
            kind=incoming.kind,
            fingerprint=fingerprint,
            combo=combo,
        )
        _commit(state, plan, now, incoming.preview)
        return plan

    return None


def _commit(state: ChatState, plan: Plan, now: float, preview: str) -> None:
    state.mark_handled(
        plan.fingerprint,
        now,
        LastEvent(action=plan.action, kind=plan.kind, combo=plan.combo, preview=preview, at=now),
    )


def _today(now: float) -> str:
    return datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
