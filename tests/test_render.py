from reread.render import combo_title, render_stats, render_status, stats_payload


def test_combo_titles():
    assert combo_title(2) == "围观群众"
    assert combo_title(3) == "复读学徒"
    assert combo_title(5) == "复读达人"
    assert combo_title(9) == "复读魔王"


def test_status_and_stats_copy():
    text = render_status(
        enabled=True,
        text_threshold=3,
        image_threshold=3,
        face_threshold=2,
        reread_prob=0.72,
        interrupt_prob=0.18,
        combo=5,
        combo_kind="text",
        preview="草",
        king_name="甲",
        king_count=8,
    )
    assert "开机" in text
    assert "复读达人" in text
    assert "甲" in text
    board = render_stats([("1", "甲", 8), ("2", "乙", 3)], "2026-08-20")
    assert "今日复读榜" in board
    assert "甲" in board


def test_stats_payload_for_agent():
    payload = stats_payload([("1", "甲", 8), ("2", "乙", 3)], "2026-08-20")
    assert "day=2026-08-20" in payload
    assert "甲(1) 8" in payload
    assert stats_payload([], "今天") == "day=今天\nempty=true"
