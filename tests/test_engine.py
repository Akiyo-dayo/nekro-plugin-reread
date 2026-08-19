from reread.chat import is_group_chat, parse_group_id
from reread.engine import evaluate
from reread.models import EngineConfig, IncomingMessage
from reread.state import ChatState


class Scripted:
    def __init__(self, rolls, pick=None):
        self.rolls = list(rolls)
        self.pick = pick

    def random(self):
        return self.rolls.pop(0)

    def choice(self, seq):
        if self.pick is not None:
            return self.pick
        return seq[0]


def _text(sender: str, text: str = "草", name: str = "") -> IncomingMessage:
    return IncomingMessage(
        kind="text",
        fingerprint=f"text:{text}",
        sender_id=sender,
        sender_name=name or sender,
        chat_key="onebot_v11-group_1",
        text=text,
        preview=text,
    )


def _cfg(**kwargs) -> EngineConfig:
    data = dict(
        text_threshold=3,
        image_threshold=3,
        face_threshold=2,
        reread_prob=1.0,
        interrupt_prob=0.0,
        cooldown_sec=0.0,
        mute_prob=0.0,
        mute_seconds=0,
    )
    data.update(kwargs)
    return EngineConfig(**data)


def test_follow_after_three_different_users():
    state = ChatState()
    cfg = _cfg()
    assert evaluate(state, _text("1"), cfg, Scripted([]), 1) is None
    assert evaluate(state, _text("2"), cfg, Scripted([]), 2) is None
    plan = evaluate(state, _text("3"), cfg, Scripted([0.1]), 3)
    assert plan is not None
    assert plan.action == "follow"
    assert plan.combo == 3


def test_same_sender_does_not_trigger_when_need_different():
    state = ChatState()
    cfg = _cfg()
    assert evaluate(state, _text("1"), cfg, Scripted([]), 1) is None
    assert evaluate(state, _text("1"), cfg, Scripted([]), 2) is None
    assert evaluate(state, _text("1"), cfg, Scripted([]), 3) is None
    assert state.combo("text") == 1


def test_blocked_word_skips():
    state = ChatState()
    cfg = _cfg(blocked_words=("广告",))
    assert evaluate(state, _text("1", "免费广告"), cfg, Scripted([]), 1) is None
    assert not state.messages["text"]


def test_interrupt_happens_before_follow():
    state = ChatState()
    cfg = _cfg(interrupt_prob=1.0, reread_prob=1.0)
    evaluate(state, _text("1"), cfg, Scripted([]), 1)
    evaluate(state, _text("2"), cfg, Scripted([]), 2)
    plan = evaluate(state, _text("3"), cfg, Scripted([0.0], pick="打断！"), 3)
    assert plan is not None
    assert plan.action == "interrupt"
    assert plan.interrupt_text == "打断！"


def test_failed_roll_can_retry_on_next_same_message():
    state = ChatState()
    cfg = _cfg(reread_prob=0.5, interrupt_prob=0.0)
    evaluate(state, _text("1"), cfg, Scripted([]), 1)
    evaluate(state, _text("2"), cfg, Scripted([]), 2)
    assert evaluate(state, _text("3"), cfg, Scripted([0.9]), 3) is None
    plan = evaluate(state, _text("4"), cfg, Scripted([0.1]), 4)
    assert plan is not None
    assert plan.action == "follow"


def test_same_fingerprint_not_handled_twice():
    state = ChatState()
    cfg = _cfg()
    evaluate(state, _text("1"), cfg, Scripted([]), 1)
    evaluate(state, _text("2"), cfg, Scripted([]), 2)
    first = evaluate(state, _text("3"), cfg, Scripted([0.1]), 3)
    assert first is not None
    evaluate(state, _text("1"), cfg, Scripted([]), 10)
    evaluate(state, _text("2"), cfg, Scripted([]), 11)
    again = evaluate(state, _text("3"), cfg, Scripted([0.1]), 12)
    assert again is None


def test_cooldown_blocks_different_content():
    state = ChatState()
    cfg = _cfg(cooldown_sec=10)
    evaluate(state, _text("1", "草"), cfg, Scripted([]), 1)
    evaluate(state, _text("2", "草"), cfg, Scripted([]), 2)
    assert evaluate(state, _text("3", "草"), cfg, Scripted([0.1]), 3) is not None
    evaluate(state, _text("1", "哈哈"), cfg, Scripted([]), 4)
    evaluate(state, _text("2", "哈哈"), cfg, Scripted([]), 5)
    assert evaluate(state, _text("3", "哈哈"), cfg, Scripted([0.1]), 6) is None
    plan = evaluate(state, _text("4", "哈哈"), cfg, Scripted([0.1]), 20)
    assert plan is not None
    assert plan.fingerprint == "text:哈哈"


def test_repeat_stats_count_followers_not_starter():
    state = ChatState()
    cfg = _cfg(reread_prob=0.0, interrupt_prob=0.0)
    evaluate(state, _text("1", name="甲"), cfg, Scripted([]), 1, day="2026-08-20")
    evaluate(state, _text("2", name="乙"), cfg, Scripted([]), 2, day="2026-08-20")
    evaluate(state, _text("3", name="丙"), cfg, Scripted([]), 3, day="2026-08-20")
    rows = state.top_repeaters()
    names = {name for _uid, name, _count in rows}
    assert "乙" in names
    assert "丙" in names
    assert "甲" not in names


def test_image_and_face_use_separate_windows():
    state = ChatState()
    cfg = _cfg(face_threshold=2, image_threshold=2, text_threshold=3)
    face = IncomingMessage(kind="face", fingerprint="face:1", sender_id="1", sender_name="甲", chat_key="g", face_id="1")
    image = IncomingMessage(kind="image", fingerprint="image:a.jpg", sender_id="2", sender_name="乙", chat_key="g", image_file="a.jpg")
    assert evaluate(state, face, cfg, Scripted([]), 1) is None
    plan = evaluate(state, IncomingMessage(kind="face", fingerprint="face:1", sender_id="2", sender_name="乙", chat_key="g", face_id="1"), cfg, Scripted([0.1]), 2)
    assert plan is not None
    assert plan.kind == "face"
    assert evaluate(state, image, cfg, Scripted([]), 3) is None


def test_blocked_user_skips():
    state = ChatState()
    cfg = _cfg(blocked_users=frozenset({"9"}))
    assert evaluate(state, _text("9"), cfg, Scripted([]), 1) is None
    assert not state.messages["text"]


def test_commands_and_tome_are_ignored():
    state = ChatState()
    cfg = _cfg()
    cmd = _text("1")
    cmd = IncomingMessage(**{**cmd.__dict__, "is_command": True})
    tome = IncomingMessage(**{**_text("1").__dict__, "is_tome": True})
    assert evaluate(state, cmd, cfg, Scripted([]), 1) is None
    assert evaluate(state, tome, cfg, Scripted([]), 2) is None
    assert not state.messages["text"]


def test_group_chat_parser():
    assert parse_group_id("onebot_v11-group_123456") == "123456"
    assert is_group_chat("onebot_v11-group_123456")
    assert not is_group_chat("onebot_v11-private_1")
