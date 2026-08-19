from types import SimpleNamespace

from reread.parse import parse_incoming, split_cq


def _msg(**kwargs):
    data = {
        "chat_key": "onebot_v11-group_100",
        "sender_id": "10",
        "sender_name": "甲",
        "sender_nickname": "甲",
        "content_text": "",
        "content_data": [],
        "raw_cq_code": "",
        "is_tome": 0,
        "is_recalled": False,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_split_cq_face_and_text():
    parts = split_cq("hi[CQ:face,id=178]")
    assert parts[0][0] == "text"
    assert parts[1] == ("face", {"id": "178"})


def test_parse_plain_text():
    incoming = parse_incoming(_msg(content_text="草"))
    assert incoming is not None
    assert incoming.kind == "text"
    assert incoming.fingerprint == "text:草"
    assert incoming.text == "草"


def test_parse_face_from_cq():
    incoming = parse_incoming(_msg(raw_cq_code="[CQ:face,id=178]"))
    assert incoming is not None
    assert incoming.kind == "face"
    assert incoming.fingerprint == "face:178"
    assert incoming.face_id == "178"


def test_parse_image_from_cq():
    incoming = parse_incoming(_msg(raw_cq_code="[CQ:image,file=abc.jpg,url=https://x.test/a.jpg?t=1]"))
    assert incoming is not None
    assert incoming.kind == "image"
    assert incoming.fingerprint == "image:abc.jpg"
    assert incoming.image_url == "https://x.test/a.jpg?t=1"


def test_parse_sticker_from_mface():
    incoming = parse_incoming(_msg(raw_cq_code="[CQ:mface,id=99,url=https://x.test/sticker.png]"))
    assert incoming is not None
    assert incoming.kind == "face"
    assert incoming.fingerprint == "sticker:99"
    assert incoming.sticker_url == "https://x.test/sticker.png"


def test_parse_skips_mixed_segments():
    assert parse_incoming(_msg(raw_cq_code="草[CQ:face,id=1]")) is None


def test_parse_command_flag():
    incoming = parse_incoming(_msg(content_text="/复读姬"))
    assert incoming is not None
    assert incoming.is_command is True
    named = parse_incoming(_msg(content_text="复读榜"))
    assert named is not None
    assert named.is_command is True


def test_parse_image_from_content_data():
    image = SimpleNamespace(type="image", file_name="hash.jpg", remote_url="https://x.test/h.jpg", local_path="")
    incoming = parse_incoming(_msg(content_data=[image]))
    assert incoming is not None
    assert incoming.kind == "image"
    assert incoming.fingerprint == "image:hash.jpg"
