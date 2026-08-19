"""复读姬。

群友连续发送同一条文本 / 图片 / 表情时，按阈值和概率跟读或打断。
"""

try:
    from .plugin import plugin
except ModuleNotFoundError as exc:
    if exc.name != "nekro_agent":
        raise
    plugin = None  # type: ignore[assignment]

__all__ = ["plugin"]
