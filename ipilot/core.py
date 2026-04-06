from ipilot.agent.loop import AgentLoop
from ipilot.config.loader import load_config


class iPilot:
    def __init__(self, loop: AgentLoop):
        self._loop = loop
    
    @classmethod
    def from_config(cls):
        from ipilot.runtime import build_agent_loop

        return cls(build_agent_loop(load_config()))
    
    async def run(
        self,
        message: str,
        session_key: str = "sdk:default",
        channel: str | None = None,
        chat_id: str | None = None,
    ):
        return await self._loop.process_direct(message, session_key, channel=channel, chat_id=chat_id)

    async def run_stream(
        self,
        message: str,
        session_key: str = "sdk:default",
        on_delta=None,
        channel: str | None = None,
        chat_id: str | None = None,
    ):
        return await self._loop.process_direct_stream(
            message,
            session_key,
            on_stream=on_delta,
            channel=channel,
            chat_id=chat_id,
        )

__all__ = ["iPilot"]

