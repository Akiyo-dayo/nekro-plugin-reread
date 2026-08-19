from __future__ import annotations

from .models import MessageKind

INTERRUPT_POOL = (
    "打断！",
    "不许复读！",
    "复读机进水了。",
    "换个梗行不行。",
    "我宣布复读环节结束。",
    "打断施法！",
    "这首已经听过了。",
    "下一个！",
    "检测到复读，已就地解散。",
    "你们是复读协会派来的吗？",
)

MUTE_POOL = (
    "{name} 复读过头，先冷静 {sec} 秒。",
    "抓到复读犯 {name}，禁言套餐一份。",
    "{name} 因为 {combo} 连复读被请去面壁 {sec} 秒。",
)


def combo_title(combo: int) -> str:
    if combo >= 8:
        return "复读魔王"
    if combo >= 5:
        return "复读达人"
    if combo >= 3:
        return "复读学徒"
    return "围观群众"


def kind_label(kind: MessageKind) -> str:
    return {"text": "文本", "image": "图片", "face": "表情"}[kind]


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _safe_format(template: str, **kwargs) -> str:
    values = _SafeDict({key: str(value) for key, value in kwargs.items()})
    try:
        return template.format_map(values)
    except Exception:
        return template


def pick_interrupt_text(combo: int, texts: tuple[str, ...], choice) -> str:
    pool = texts or INTERRUPT_POOL
    return _safe_format(choice(pool), combo=combo)


def pick_mute_text(name: str, combo: int, seconds: int, choice) -> str:
    return choice(MUTE_POOL).format(name=name or "这位", combo=combo, sec=seconds)


def render_help() -> str:
    return (
        "复读姬会在群友连续发送同一条文本 / 图片 / 表情后，按概率跟读或打断。\n"
        "· 文本、图片、表情的阈值分开算\n"
        "· 先掷打断，没打断再掷复读\n"
        "· 默认要求不同人接力，一个人刷屏带不动\n\n"
        "指令：\n"
        "/复读姬  查看本群状态\n"
        "/复读榜  今日谁最爱复读\n"
        "/开启复读姬  /关闭复读姬  超管开关"
    )


def render_status(
    *,
    enabled: bool,
    text_threshold: int,
    image_threshold: int,
    face_threshold: int,
    reread_prob: float,
    interrupt_prob: float,
    combo: int,
    combo_kind: str,
    preview: str,
    king_name: str,
    king_count: int,
) -> str:
    power = "开机" if enabled else "关机"
    combo_line = "暂无连击"
    if combo:
        shown = preview or kind_label(combo_kind)  # type: ignore[arg-type]
        combo_line = f"{kind_label(combo_kind)}「{shown}」x{combo} · {combo_title(combo)}"  # type: ignore[arg-type]
    king_line = "今天还没人带头复读"
    if king_name:
        king_line = f"{king_name}（{king_count} 次）"
    return (
        f"复读姬 · {power}\n"
        f"当前连击：{combo_line}\n"
        f"今日复读王：{king_line}\n"
        f"阈值：文本 {text_threshold} / 图片 {image_threshold} / 表情 {face_threshold}\n"
        f"概率：复读 {int(reread_prob * 100)}% / 打断 {int(interrupt_prob * 100)}%"
    )


def render_stats(rows: list[tuple[str, str, int]], day: str) -> str:
    if not rows:
        return f"{day} 还没有复读记录。多说两句一样的试试？"
    lines = [f"今日复读榜 · {day}"]
    medals = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣")
    for index, (_uid, name, count) in enumerate(rows):
        medal = medals[index] if index < len(medals) else f"{index + 1}."
        lines.append(f"{medal} {name}  ×{count}")
    lines.append("复读不是罪，带头的才是王。")
    return "\n".join(lines)


def stats_payload(rows: list[tuple[str, str, int]], day: str) -> str:
    if not rows:
        return f"day={day}\nempty=true"
    lines = [f"day={day}", f"count={len(rows)}"]
    for index, (user_id, name, count) in enumerate(rows, 1):
        lines.append(f"{index}. {name}({user_id}) {count}")
    return "\n".join(lines)


def render_toggled(enabled: bool) -> str:
    return "复读姬已开机，开始蹲连击。" if enabled else "复读姬已关机，群友爱怎么复读怎么复读。"


def render_private() -> str:
    return "复读姬只在群聊里上班。"
