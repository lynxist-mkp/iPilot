from __future__ import annotations

from ipilot.agent.types import AgentRunResult


class AgentLoop:
    def __init__(self, graph, context_factory) -> None:
        self.graph = graph
        self.context_factory = context_factory

    async def process_direct(
        self,
        message: str,
        session_key: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> AgentRunResult:
        context = self.context_factory(session_key=session_key, channel=channel, chat_id=chat_id)
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": session_key}},
            context=context,
        )
        messages = result["messages"]
        last = messages[-1]
        return AgentRunResult(
            content=getattr(last, "content", None),
            messages=messages,
            finish_reason="stop",
        )

    async def process_direct_stream(
        self,
        message: str,
        session_key: str,
        on_stream=None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> AgentRunResult:
        result = await self.process_direct(
            message,
            session_key,
            channel=channel,
            chat_id=chat_id,
        )

        if on_stream is not None and result.content:
            maybe_result = on_stream(result.content)
            if hasattr(maybe_result, "__await__"):
                await maybe_result

        return result
