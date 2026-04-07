from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipilot.agent.loop import AgentLoop
from ipilot.agent.types import AgentRunResult


class RecordingGraph:
    def __init__(self):
        self.calls: list[dict] = []

    async def ainvoke(self, payload, config=None, context=None):
        self.calls.append(
            {
                "payload": payload,
                "config": config,
                "context": context,
            }
        )
        return {"messages": [SimpleNamespace(content="done")]}


def context_factory(*, session_key: str, channel: str | None, chat_id: str | None):
    return {
        "session_key": session_key,
        "channel": channel,
        "chat_id": chat_id,
    }


@pytest.mark.asyncio
async def test_process_direct_uses_graph_and_context_factory():
    graph = RecordingGraph()
    loop = AgentLoop(graph=graph, context_factory=context_factory)

    response = await loop.process_direct(
        "hello",
        "cli:default",
        channel="cli",
        chat_id="default",
    )

    assert isinstance(response, AgentRunResult)
    assert response.content == "done"
    assert response.finish_reason == "stop"
    assert response.messages[-1].content == "done"
    assert graph.calls == [
        {
            "payload": {"messages": [{"role": "user", "content": "hello"}]},
            "config": {"configurable": {"thread_id": "cli:default"}},
            "context": {
                "session_key": "cli:default",
                "channel": "cli",
                "chat_id": "default",
            },
        }
    ]


@pytest.mark.asyncio
async def test_process_direct_stream_emits_final_content_once():
    graph = RecordingGraph()
    loop = AgentLoop(graph=graph, context_factory=context_factory)
    deltas: list[str] = []

    response = await loop.process_direct_stream(
        "stream please",
        "cli:stream",
        on_stream=deltas.append,
        channel="cli",
        chat_id="stream",
    )

    assert response.content == "done"
    assert deltas == ["done"]
    assert graph.calls[0]["config"] == {"configurable": {"thread_id": "cli:stream"}}
