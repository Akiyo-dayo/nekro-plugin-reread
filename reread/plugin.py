"""NekroAgent 复读姬插件入口。"""

from __future__ import annotations

from dataclasses import replace
from typing import List

from pydantic import Field

from nekro_agent.api import core, i18n
from nekro_agent.api.plugin import (
    CmdCtl,
    CommandExecutionContext,
    CommandPermission,
    CommandResponse,
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.schemas.chat_message import ChatMessage
from nekro_agent.schemas.signal import MsgSignal

from .chat import is_group_chat, parse_group_id
from .models import EngineConfig, IncomingMessage, Plan
from .parse import parse_incoming
from .render import (
    render_help,
    render_private,
    render_stats,
    render_status,
    render_toggled,
    stats_payload,
)
from .service import RereadService

plugin = NekroPlugin(
    name="复读姬",
    module_name="reread",
    description="群聊复读姬：文本/图片/表情分开设阈值，可配置复读概率、打断概率、屏蔽与冷却。",
    version="1.0.0",
    author="reread",
    url="https://github.com/Akiyo-dayo/nekro-plugin-reread",
    support_adapter=["onebot_v11"],
    allow_sleep=True,
    sleep_brief="复读姬在消息回调里跟读，不依赖 AI 醒来。",
    i18n_name=i18n.i18n_text(zh_CN="复读姬", en_US="Reread"),
    i18n_description=i18n.i18n_text(
        zh_CN="群聊复读姬：文本/图片/表情分开设阈值，可配置复读概率、打断概率、屏蔽与冷却。",
        en_US="Group repeater with separate thresholds, probabilities, interrupts and filters.",
    ),
)


@plugin.mount_config()
class RereadConfig(ConfigBase):
    """复读姬配置"""

    ENABLED: bool = Field(default=True, title="默认开机", description="新群默认是否启用复读姬")
    ENABLE_TEXT: bool = Field(default=True, title="复读文本")
    ENABLE_IMAGE: bool = Field(default=True, title="复读图片")
    ENABLE_FACE: bool = Field(default=True, title="复读表情", description="QQ 系统表情和表情包")
    TEXT_THRESHOLD: int = Field(default=3, title="文本阈值", description="同一句话连续出现几次后才可能触发")
    IMAGE_THRESHOLD: int = Field(default=3, title="图片阈值")
    FACE_THRESHOLD: int = Field(default=2, title="表情阈值")
    REREAD_PROB: float = Field(default=0.72, title="复读概率", description="未打断时，跟着复读的概率，0~1")
    INTERRUPT_PROB: float = Field(default=0.18, title="打断概率", description="达到阈值后先掷打断，0~1")
    NEED_DIFFERENT: bool = Field(default=True, title="必须不同人", description="同一人连刷不会触发，防止广告哥带节奏")
    COOLDOWN_SEC: float = Field(default=8.0, title="冷却秒数", description="触发一次后多久内不再动手")
    MAX_TEXT_LEN: int = Field(default=72, title="最长文本", description="超过这个长度的句子不跟读")
    SKIP_COMMANDS: bool = Field(default=True, title="忽略指令")
    SKIP_TOME: bool = Field(default=True, title="忽略 @机器人")
    SKIP_BOT: bool = Field(default=True, title="忽略机器人自己")
    SILENCE_AI: bool = Field(
        default=True,
        title="复读时拦 AI",
        description="跟读或打断时，这条消息记入历史，但不叫醒 Agent，避免它跟着起哄",
    )
    MUTE_PROB: float = Field(default=0.0, title="禁言概率", description="默认关闭。需要机器人有禁言权限")
    MUTE_SECONDS: int = Field(default=30, title="禁言秒数", description="设为 0 则不会禁言")
    BLOCKED_WORDS: List[str] = Field(
        default_factory=list,
        title="屏蔽词",
        description="文本包含任一屏蔽词时不参与复读",
        json_schema_extra=ExtraField(sub_item_name="屏蔽词").model_dump(),
    )
    BLOCKED_USERS: List[str] = Field(
        default_factory=list,
        title="屏蔽 QQ",
        description="这些人不参与复读统计，也不会被跟读",
        json_schema_extra=ExtraField(sub_item_name="QQ号").model_dump(),
    )
    GROUP_WHITELIST: List[str] = Field(
        default_factory=list,
        title="群白名单",
        description="填写后只在这些群生效，留空表示全部群",
        json_schema_extra=ExtraField(sub_item_name="群号").model_dump(),
    )
    GROUP_BLACKLIST: List[str] = Field(
        default_factory=list,
        title="群黑名单",
        description="这些群不启用复读姬",
        json_schema_extra=ExtraField(sub_item_name="群号").model_dump(),
    )
    INTERRUPT_TEXTS: List[str] = Field(
        default_factory=list,
        title="打断文案",
        description="留空则用内置吐槽池。可用 {combo} 表示当前连击",
        json_schema_extra=ExtraField(sub_item_name="文案", is_textarea=True).model_dump(),
    )
    COMMAND_PREFIXES: List[str] = Field(
        default_factory=lambda: ["/", "!", "！", ".", "#"],
        title="指令前缀",
        json_schema_extra=ExtraField(sub_item_name="前缀").model_dump(),
    )


config = plugin.get_config(RereadConfig)
_service: RereadService | None = None
_loaded_chats: set[str] = set()
_bot_id_cache = ""


class PluginKVStore:
    async def get(self, chat_key: str, store_key: str = "enabled") -> str | None:
        return await plugin.store.get(chat_key=chat_key, store_key=store_key)

    async def set(self, chat_key: str, store_key: str = "enabled", value: str = "") -> None:
        await plugin.store.set(chat_key=chat_key, store_key=store_key, value=value)


def get_service() -> RereadService:
    global _service
    if _service is None:
        _service = RereadService(PluginKVStore())
    return _service


def _engine_config() -> EngineConfig:
    return EngineConfig(
        text_threshold=config.TEXT_THRESHOLD,
        image_threshold=config.IMAGE_THRESHOLD,
        face_threshold=config.FACE_THRESHOLD,
        reread_prob=config.REREAD_PROB,
        interrupt_prob=config.INTERRUPT_PROB,
        need_different=config.NEED_DIFFERENT,
        cooldown_sec=config.COOLDOWN_SEC,
        max_text_len=config.MAX_TEXT_LEN,
        blocked_words=tuple(item.strip() for item in config.BLOCKED_WORDS if str(item).strip()),
        blocked_users=frozenset(str(item).strip() for item in config.BLOCKED_USERS if str(item).strip()),
        skip_commands=config.SKIP_COMMANDS,
        skip_tome=config.SKIP_TOME,
        mute_prob=config.MUTE_PROB,
        mute_seconds=config.MUTE_SECONDS,
        enable_text=config.ENABLE_TEXT,
        enable_image=config.ENABLE_IMAGE,
        enable_face=config.ENABLE_FACE,
        interrupt_texts=tuple(item.strip() for item in config.INTERRUPT_TEXTS if str(item).strip()),
    )


def _normalize_id(value: str) -> str:
    return str(value or "").strip()


def _group_allowed(chat_key: str, channel_id: str | None = None) -> bool:
    try:
        group_id = parse_group_id(chat_key, channel_id)
    except ValueError:
        return False
    whitelist = {_normalize_id(item) for item in config.GROUP_WHITELIST if _normalize_id(item)}
    blacklist = {_normalize_id(item) for item in config.GROUP_BLACKLIST if _normalize_id(item)}
    if whitelist and group_id not in whitelist:
        return False
    if group_id in blacklist:
        return False
    return True


def _unsupported(adapter_key: str | None, chat_key: str, channel_id: str | None = None, channel_type: str | None = None) -> str | None:
    if adapter_key and adapter_key != "onebot_v11":
        return "复读姬目前只支持 QQ OneBot 群聊"
    if not is_group_chat(chat_key, channel_id=channel_id, channel_type=channel_type):
        return render_private()
    if not _group_allowed(chat_key, channel_id):
        return "这个群没有开放复读姬"
    return None


def _command_prefixes() -> tuple[str, ...]:
    items = tuple(str(item) for item in config.COMMAND_PREFIXES if str(item))
    return items or ("/", "!", "！", ".", "#")


async def _bot_id(ctx: AgentCtx) -> str:
    global _bot_id_cache
    if _bot_id_cache:
        return _bot_id_cache
    try:
        bot = await ctx.get_onebot_v11_bot()
        _bot_id_cache = str(bot.self_id)
    except Exception:
        _bot_id_cache = ""
    return _bot_id_cache


async def _ensure_loaded(chat_key: str) -> bool:
    if chat_key not in _loaded_chats:
        await get_service().load_enabled(chat_key, config.ENABLED)
        _loaded_chats.add(chat_key)
    return get_service().is_enabled(chat_key)


def _combo_snapshot(chat_key: str) -> tuple[int, str, str]:
    state = get_service().snapshot(chat_key)
    best_combo = 0
    best_kind = "text"
    preview = ""
    for kind in ("text", "image", "face"):
        combo = state.combo(kind)
        if combo > best_combo:
            best_combo = combo
            best_kind = kind
            if state.messages[kind]:
                preview = state.messages[kind][-1]["fp"].split(":", 1)[-1][:24]
    return best_combo, best_kind, preview


def _status_text(chat_key: str, enabled: bool) -> str:
    combo, kind, preview = _combo_snapshot(chat_key)
    rows = get_service().snapshot(chat_key).top_repeaters(1)
    king_name = rows[0][1] if rows else ""
    king_count = rows[0][2] if rows else 0
    return render_status(
        enabled=enabled,
        text_threshold=config.TEXT_THRESHOLD,
        image_threshold=config.IMAGE_THRESHOLD,
        face_threshold=config.FACE_THRESHOLD,
        reread_prob=config.REREAD_PROB,
        interrupt_prob=config.INTERRUPT_PROB,
        combo=combo,
        combo_kind=kind,
        preview=preview,
        king_name=king_name,
        king_count=king_count,
    )


async def _send_image(ctx: AgentCtx, incoming: IncomingMessage) -> None:
    source = incoming.image_url or incoming.sticker_url or incoming.image_local
    if not source:
        raise ValueError("没有可发送的图片")
    sandbox_path = await ctx.fs.mixed_forward_file(source, file_name=incoming.image_file or "reread.jpg")
    await ctx.send_image(sandbox_path, record=False)


async def _send_face(ctx: AgentCtx, incoming: IncomingMessage) -> None:
    if incoming.sticker_url or incoming.image_url:
        await _send_image(ctx, incoming)
        return
    if not incoming.face_id:
        raise ValueError("没有可发送的表情")
    bot = await ctx.get_onebot_v11_bot()
    group_id = parse_group_id(ctx.chat_key, ctx.channel_id)
    from nonebot.adapters.onebot.v11 import MessageSegment

    await bot.send_group_msg(group_id=int(group_id), message=MessageSegment.face(int(incoming.face_id)))


async def _mute(ctx: AgentCtx, incoming: IncomingMessage, seconds: int) -> bool:
    try:
        bot = await ctx.get_onebot_v11_bot()
        group_id = parse_group_id(ctx.chat_key, ctx.channel_id)
        await bot.set_group_ban(group_id=int(group_id), user_id=int(incoming.sender_id), duration=int(seconds))
        return True
    except Exception as exc:
        core.logger.warning(f"复读姬禁言失败: {exc}")
        return False


async def _execute(ctx: AgentCtx, incoming: IncomingMessage, plan: Plan) -> None:
    if plan.action == "mute":
        await _mute(ctx, incoming, plan.mute_seconds)
        if plan.interrupt_text:
            await ctx.send_text(plan.interrupt_text, record=True)
        return
    if plan.action == "interrupt":
        await ctx.send_text(plan.interrupt_text or "打断！", record=True)
        return

    try:
        if incoming.kind == "text":
            await ctx.send_text(incoming.text, record=False)
        elif incoming.kind == "image":
            await _send_image(ctx, incoming)
        else:
            await _send_face(ctx, incoming)
    except Exception as exc:
        core.logger.warning(f"复读姬跟读失败: {exc}")
        fallback = incoming.text or incoming.preview
        if fallback:
            await ctx.send_text(fallback, record=False)


@plugin.mount_on_user_message()
async def on_user_message(_ctx: AgentCtx, message: ChatMessage) -> MsgSignal | None:
    try:
        if _unsupported(_ctx.adapter_key, message.chat_key or _ctx.chat_key, _ctx.channel_id, _ctx.channel_type):
            return None
        chat_key = message.chat_key or _ctx.chat_key
        if not await _ensure_loaded(chat_key):
            return None
        incoming = parse_incoming(message, command_prefixes=_command_prefixes())
        if incoming is None:
            return None
        if config.SKIP_BOT:
            bot_id = await _bot_id(_ctx)
            if bot_id and incoming.sender_id == bot_id:
                return None
        incoming = replace(incoming, chat_key=chat_key)
        plan = get_service().observe(incoming, _engine_config())
        if plan is None:
            return None
        await _execute(_ctx, incoming, plan)
        if config.SILENCE_AI:
            return MsgSignal.BLOCK_TRIGGER
        return None
    except Exception as exc:
        core.logger.warning(f"复读姬处理消息失败: {exc}")
        return None


@plugin.mount_command(
    name="reread",
    description="查看复读姬状态",
    aliases=["复读姬"],
    permission=CommandPermission.PUBLIC,
    usage="reread",
    category="复读姬",
    tags=["reread", "fun", "group"],
)
async def reread_status_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    enabled = await _ensure_loaded(context.chat_key)
    return CmdCtl.success(_status_text(context.chat_key, enabled))


@plugin.mount_command(
    name="reread_stats",
    description="查看今日复读榜",
    aliases=["复读榜", "今日复读王"],
    permission=CommandPermission.PUBLIC,
    usage="reread_stats",
    category="复读姬",
    tags=["reread", "fun"],
)
async def reread_stats_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    state = get_service().snapshot(context.chat_key)
    day = state.stats_day or "今天"
    return CmdCtl.success(render_stats(state.top_repeaters(), day))


@plugin.mount_command(
    name="reread_help",
    description="复读姬帮助",
    aliases=["复读姬帮助"],
    permission=CommandPermission.PUBLIC,
    usage="reread_help",
    category="复读姬",
    tags=["reread", "help"],
)
async def reread_help_cmd(context: CommandExecutionContext) -> CommandResponse:
    return CmdCtl.success(render_help())


@plugin.mount_command(
    name="reread_on",
    description="开启本群复读姬",
    aliases=["开启复读姬"],
    permission=CommandPermission.SUPER_USER,
    usage="reread_on",
    category="复读姬",
    tags=["reread", "admin"],
)
async def reread_on_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    await get_service().set_enabled(context.chat_key, True)
    _loaded_chats.add(context.chat_key)
    return CmdCtl.success(render_toggled(True))


@plugin.mount_command(
    name="reread_off",
    description="关闭本群复读姬",
    aliases=["关闭复读姬"],
    permission=CommandPermission.SUPER_USER,
    usage="reread_off",
    category="复读姬",
    tags=["reread", "admin"],
)
async def reread_off_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    await get_service().set_enabled(context.chat_key, False)
    _loaded_chats.add(context.chat_key)
    return CmdCtl.success(render_toggled(False))


@plugin.mount_command(
    name="reread_reset",
    description="清空本群复读连击",
    aliases=["重置复读"],
    permission=CommandPermission.SUPER_USER,
    usage="reread_reset",
    category="复读姬",
    tags=["reread", "admin"],
)
async def reread_reset_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    get_service().reset(context.chat_key)
    return CmdCtl.success("本群复读连击已清空。")


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="查看复读榜",
    description="查询当前群今日复读榜，看谁最爱接同一句话。",
)
async def query_reread_board(_ctx: AgentCtx) -> str:
    """查询当前群今日复读榜。

    Returns:
        str: 排名数据。用一两句吐槽承接即可，不要把整张榜原文复述一遍。
    """
    reason = _unsupported(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    state = get_service().snapshot(_ctx.chat_key)
    return stats_payload(state.top_repeaters(), state.stats_day or "今天")


@plugin.mount_collect_methods()
async def collect_available_methods(_ctx: AgentCtx):
    if _unsupported(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type):
        return []
    return [query_reread_board]


@plugin.mount_cleanup_method()
async def clean_up():
    global _service, _bot_id_cache
    if _service is not None:
        _service.states.clear()
    _service = None
    _loaded_chats.clear()
    _bot_id_cache = ""
    core.logger.info("复读姬插件资源已清理")
