from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MessageKind = Literal["text", "image", "face"]
ActionKind = Literal["follow", "interrupt", "mute"]


@dataclass(frozen=True)
class IncomingMessage:
    kind: MessageKind
    fingerprint: str
    sender_id: str
    sender_name: str
    chat_key: str
    text: str = ""
    image_url: str = ""
    image_local: str = ""
    image_file: str = ""
    face_id: str = ""
    sticker_url: str = ""
    is_tome: bool = False
    is_command: bool = False
    is_recalled: bool = False
    preview: str = ""


@dataclass(frozen=True)
class EngineConfig:
    text_threshold: int = 3
    image_threshold: int = 3
    face_threshold: int = 2
    reread_prob: float = 0.72
    interrupt_prob: float = 0.18
    need_different: bool = True
    cooldown_sec: float = 8.0
    max_text_len: int = 72
    blocked_words: tuple[str, ...] = ()
    blocked_users: frozenset[str] = field(default_factory=frozenset)
    skip_commands: bool = True
    skip_tome: bool = True
    mute_prob: float = 0.0
    mute_seconds: int = 0
    enable_text: bool = True
    enable_image: bool = True
    enable_face: bool = True
    interrupt_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    action: ActionKind
    kind: MessageKind
    fingerprint: str
    combo: int
    interrupt_text: str = ""
    mute_seconds: int = 0


@dataclass
class LastEvent:
    action: ActionKind
    kind: MessageKind
    combo: int
    preview: str
    at: float
