from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from .models import IncomingMessage, MessageKind

_CQ_RE = re.compile(r"\[CQ:(?P<type>[a-zA-Z0-9_]+)(?P<params>[^\]]*)\]")
_DEFAULT_PREFIXES = ("/", "!", "！", ".", "#", "／")
_COMMAND_NAMES = frozenset(
    {
        "reread",
        "reread_on",
        "reread_off",
        "reread_help",
        "reread_stats",
        "复读姬",
        "开启复读姬",
        "关闭复读姬",
        "复读姬帮助",
        "复读榜",
        "今日复读王",
    }
)


def _segment_type(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value).lower()
    return str(value or "").lower()


def _strip_query(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme:
        return raw
    return urlunparse(parsed._replace(query="", fragment=""))


def _parse_cq_params(raw: str) -> dict[str, str]:
    params: dict[str, str] = {}
    text = (raw or "").lstrip(",")
    if not text:
        return params
    for part in text.split(","):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        if key:
            params[key] = value.strip()
    return params


def split_cq(raw: str) -> list[tuple[str, dict[str, str]]]:
    text = (raw or "").strip()
    if not text:
        return []
    pieces: list[tuple[str, dict[str, str]]] = []
    cursor = 0
    for match in _CQ_RE.finditer(text):
        prefix = text[cursor : match.start()].strip()
        if prefix:
            pieces.append(("text", {"text": prefix}))
        pieces.append((match.group("type").lower(), _parse_cq_params(match.group("params"))))
        cursor = match.end()
    suffix = text[cursor:].strip()
    if suffix:
        pieces.append(("text", {"text": suffix}))
    return pieces


def _looks_command(text: str, prefixes: tuple[str, ...]) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if stripped in _COMMAND_NAMES:
        return True
    first = stripped.split(None, 1)[0]
    if first in _COMMAND_NAMES:
        return True
    return any(stripped.startswith(prefix) for prefix in prefixes if prefix)


def _image_fingerprint(file_name: str = "", url: str = "", local_path: str = "") -> str:
    file_name = (file_name or "").strip()
    if file_name:
        return f"image:{file_name}"
    cleaned = _strip_query(url)
    if cleaned:
        return f"image:{cleaned}"
    local_path = (local_path or "").replace("\\", "/").strip()
    if local_path:
        return f"image:{local_path.rsplit('/', 1)[-1]}"
    return ""


def _content_items(message: Any) -> list[Any]:
    return list(getattr(message, "content_data", None) or [])


def parse_incoming(
    message: Any,
    *,
    command_prefixes: tuple[str, ...] = _DEFAULT_PREFIXES,
) -> IncomingMessage | None:
    chat_key = str(getattr(message, "chat_key", "") or "")
    sender_id = str(getattr(message, "sender_id", "") or getattr(message, "platform_userid", "") or "")
    sender_name = str(
        getattr(message, "sender_nickname", "")
        or getattr(message, "sender_name", "")
        or sender_id
    )
    is_tome = bool(getattr(message, "is_tome", 0))
    is_recalled = bool(getattr(message, "is_recalled", False))
    raw_cq = str(getattr(message, "raw_cq_code", "") or "")
    content_text = str(getattr(message, "content_text", "") or "")
    cq_parts = split_cq(raw_cq)
    real_cq = [item for item in cq_parts if item[0] != "text" or item[1].get("text", "").strip()]

    if len(real_cq) == 1:
        cq_type, params = real_cq[0]
        if cq_type == "face":
            face_id = params.get("id", "").strip()
            if face_id:
                return IncomingMessage(
                    kind="face",
                    fingerprint=f"face:{face_id}",
                    sender_id=sender_id,
                    sender_name=sender_name,
                    chat_key=chat_key,
                    face_id=face_id,
                    is_tome=is_tome,
                    is_recalled=is_recalled,
                    preview=f"[表情:{face_id}]",
                )
        if cq_type in {"mface", "face_sticker"}:
            sticker_id = (params.get("id") or params.get("emoji_id") or "").strip()
            sticker_url = (params.get("url") or params.get("file") or "").strip()
            token = sticker_id or _strip_query(sticker_url) or "mface"
            return IncomingMessage(
                kind="face",
                fingerprint=f"sticker:{token}",
                sender_id=sender_id,
                sender_name=sender_name,
                chat_key=chat_key,
                face_id=sticker_id,
                sticker_url=sticker_url,
                image_url=sticker_url,
                is_tome=is_tome,
                is_recalled=is_recalled,
                preview="[表情包]",
            )
        if cq_type == "image":
            file_name = (params.get("file") or params.get("file_id") or "").strip()
            url = (params.get("url") or "").strip()
            fingerprint = _image_fingerprint(file_name, url)
            if fingerprint:
                return IncomingMessage(
                    kind="image",
                    fingerprint=fingerprint,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    chat_key=chat_key,
                    image_url=url,
                    image_file=file_name,
                    is_tome=is_tome,
                    is_recalled=is_recalled,
                    preview="[图片]",
                )
        if cq_type == "text":
            text = params.get("text", "")
            return _text_incoming(
                text,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_key=chat_key,
                is_tome=is_tome,
                is_recalled=is_recalled,
                command_prefixes=command_prefixes,
            )
        return None

    if len(real_cq) > 1:
        return None

    items = _content_items(message)
    kinds = [_segment_type(getattr(item, "type", "")) for item in items]
    useful = [(item, kind) for item, kind in zip(items, kinds) if kind and kind != "reference"]
    if len(useful) > 1:
        return None
    if len(useful) == 1:
        item, kind = useful[0]
        if kind == "image":
            file_name = str(getattr(item, "file_name", "") or "")
            url = str(getattr(item, "remote_url", "") or "")
            local_path = str(getattr(item, "local_path", "") or "")
            fingerprint = _image_fingerprint(file_name, url, local_path)
            if not fingerprint:
                return None
            return IncomingMessage(
                kind="image",
                fingerprint=fingerprint,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_key=chat_key,
                image_url=url,
                image_local=local_path,
                image_file=file_name,
                is_tome=is_tome,
                is_recalled=is_recalled,
                preview="[图片]",
            )
        if kind == "text":
            text = str(getattr(item, "text", "") or content_text)
            return _text_incoming(
                text,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_key=chat_key,
                is_tome=is_tome,
                is_recalled=is_recalled,
                command_prefixes=command_prefixes,
            )
        return None

    if content_text.strip():
        return _text_incoming(
            content_text,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_key=chat_key,
            is_tome=is_tome,
            is_recalled=is_recalled,
            command_prefixes=command_prefixes,
        )
    return None


def _text_incoming(
    text: str,
    *,
    sender_id: str,
    sender_name: str,
    chat_key: str,
    is_tome: bool,
    is_recalled: bool,
    command_prefixes: tuple[str, ...],
) -> IncomingMessage | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    return IncomingMessage(
        kind="text",
        fingerprint=f"text:{cleaned}",
        sender_id=sender_id,
        sender_name=sender_name,
        chat_key=chat_key,
        text=cleaned,
        is_tome=is_tome,
        is_command=_looks_command(cleaned, command_prefixes),
        is_recalled=is_recalled,
        preview=cleaned if len(cleaned) <= 24 else cleaned[:21] + "...",
    )


def kind_enabled(kind: MessageKind, enable_text: bool, enable_image: bool, enable_face: bool) -> bool:
    if kind == "text":
        return enable_text
    if kind == "image":
        return enable_image
    return enable_face
