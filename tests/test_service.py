import asyncio

from reread.models import EngineConfig, IncomingMessage
from reread.service import MemoryEnableStore, RereadService


class AlwaysFollow:
    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]


def test_service_can_disable_a_chat():
    service = RereadService(MemoryEnableStore(), rng_factory=AlwaysFollow, clock=lambda: 100.0)
    cfg = EngineConfig(text_threshold=2, interrupt_prob=0.0, reread_prob=1.0, cooldown_sec=0.0, need_different=True)

    async def _run():
        await service.set_enabled("g1", False)
        first = IncomingMessage(kind="text", fingerprint="text:草", sender_id="1", sender_name="甲", chat_key="g1", text="草")
        second = IncomingMessage(kind="text", fingerprint="text:草", sender_id="2", sender_name="乙", chat_key="g1", text="草")
        assert service.observe(first, cfg) is None
        assert service.observe(second, cfg) is None
        await service.set_enabled("g1", True)
        service.observe(first, cfg)
        plan = service.observe(second, cfg)
        assert plan is not None
        assert plan.action == "follow"

    asyncio.run(_run())
