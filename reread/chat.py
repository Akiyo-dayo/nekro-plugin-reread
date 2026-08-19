from __future__ import annotations

_GROUP_KINDS = {"group", "guild"}
_PRIVATE_KINDS = {"private"}


def _extract_channel(chat_key: str) -> tuple[str, str] | None:
    for kind in (*_GROUP_KINDS, *_PRIVATE_KINDS):
        marker = f"-{kind}_"
        pos = chat_key.find(marker)
        if pos != -1:
            return kind, chat_key[pos + len(marker) :]
    return None


def parse_group_id(chat_key: str, channel_id: str | None = None) -> str:
    if channel_id:
        raw = channel_id.strip()
        if "_" in raw:
            kind, _, rest = raw.partition("_")
            kind = kind.lower()
            if kind in _PRIVATE_KINDS:
                raise ValueError("复读姬只支持群聊")
            if kind in _GROUP_KINDS and rest:
                return rest
        if raw.isdigit():
            return raw

    parsed = _extract_channel(chat_key)
    if parsed is None:
        raise ValueError("复读姬只支持群聊")
    kind, ident = parsed
    if kind in _PRIVATE_KINDS or not ident:
        raise ValueError("复读姬只支持群聊")
    return ident


def is_group_chat(
    chat_key: str,
    channel_id: str | None = None,
    channel_type: str | None = None,
) -> bool:
    if channel_type:
        return channel_type.lower() in _GROUP_KINDS
    try:
        parse_group_id(chat_key, channel_id)
    except ValueError:
        return False
    return True
