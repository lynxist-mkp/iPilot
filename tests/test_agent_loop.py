from __future__ import annotations

from pathlib import Path

import pytest

from ipilot.agent.context import ContextBuilder
from ipilot.agent.hook import AgentHook
from ipilot.agent.loop import AgentLoop
from ipilot.agent.tools.registry import ToolRegistry
from ipilot.providers.base import LLMResponse
from ipilot.session.manager import SessionManager


class RecordingHook(AgentHook):
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def before_iteration(self, context):
        self.events.append(("before", context))

    async def after_iteration(self, context):
        self.events.append(("after", context))


class RecordingProvider:
    def __init__(self, *, chat_response: LLMResponse | None = None, stream_response: LLMResponse | None = None):
        self.chat_response = chat_response or LLMResponse(content="ok")
        self.stream_response = stream_response or LLMResponse(content="streamed")
        self.last_messages = None
        self.stream_messages = None

    async def chat(self, messages, tools=None, model=None):
        self.last_messages = messages
        return self.chat_response

    async def chat_stream(self, messages, tools=None, model=None, on_delta=None):
        self.stream_messages = messages
        if on_delta:
            await maybe_call(on_delta, "part-1")
            await maybe_call(on_delta, "part-2")
        return self.stream_response


async def maybe_call(callback, value):
    result = callback(value)
    if hasattr(result, "__await__"):
        await result


@pytest.mark.asyncio
async def test_process_direct_passes_runtime_context_and_saves_session(tmp_path):
    provider = RecordingProvider(chat_response=LLMResponse(content="done"))
    loop = AgentLoop(
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
        tool_registry=ToolRegistry(),
        context_builder=ContextBuilder(tmp_path),
    )

    response = await loop.process_direct(
        "hello",
        "cli:default",
        channel="cli",
        chat_id="default",
    )

    assert response.content == "done"
    assert provider.last_messages[-1]["content"] == "[Runtime Context]\nChannel: cli\nChat ID: default\n\nhello"
    session_file = tmp_path / "sessions" / "cli_default.jsonl"
    assert session_file.exists()
    assert '"content": "done"' in session_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_process_direct_stream_emits_deltas_and_triggers_hooks(tmp_path):
    hook = RecordingHook()
    provider = RecordingProvider(stream_response=LLMResponse(content="part-1part-2"))
    loop = AgentLoop(
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
        tool_registry=ToolRegistry(),
        context_builder=ContextBuilder(tmp_path),
        hooks=[hook],
    )
    deltas: list[str] = []

    response = await loop.process_direct_stream(
        "stream please",
        "cli:stream",
        on_stream=deltas.append,
        channel="cli",
        chat_id="stream",
    )

    assert response.content == "part-1part-2"
    assert deltas == ["part-1", "part-2"]
    assert [event[0] for event in hook.events] == ["before", "after"]
    session_file = tmp_path / "sessions" / "cli_stream.jsonl"
    assert '"content": "part-1part-2"' in session_file.read_text(encoding="utf-8")

