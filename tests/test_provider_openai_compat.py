from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipilot.providers.base import LLMResponse
from ipilot.providers.openai_compat_provider import OpenAICompatibleProvider


def build_response(*, content: str | None = None, finish_reason: str = "stop", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def build_stream_chunk(*, content: str | None = None, finish_reason: str | None = None):
    delta = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


class FakeCompletionsAPI:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        current = self._responses.pop(0)
        if isinstance(current, Exception):
            raise current
        return current


class FakeChatAPI:
    def __init__(self, responses):
        self.completions = FakeCompletionsAPI(responses)


class FakeClient:
    def __init__(self, responses):
        self.chat = FakeChatAPI(responses)


@pytest.mark.asyncio
async def test_chat_retries_and_returns_normalized_response(monkeypatch):
    provider = OpenAICompatibleProvider(api_key="test-key", model="demo-model")
    provider.client = FakeClient(
        [
            RuntimeError("temporary failure"),
            build_response(content="hello"),
        ]
    )
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("ipilot.providers.openai_compat_provider.asyncio.sleep", fake_sleep)

    response = await provider.chat([{"role": "user", "content": "hi"}])

    assert isinstance(response, LLMResponse)
    assert response.content == "hello"
    assert provider.client.chat.completions.calls == 2
    assert sleep_calls == [1]


@pytest.mark.asyncio
async def test_chat_stream_emits_deltas_and_returns_final_response():
    provider = OpenAICompatibleProvider(api_key="test-key", model="demo-model")

    async def fake_stream():
        for chunk in [
            build_stream_chunk(content="hel"),
            build_stream_chunk(content="lo"),
            build_stream_chunk(finish_reason="stop"),
        ]:
            yield chunk

    provider.client = FakeClient([fake_stream()])
    deltas: list[str] = []

    response = await provider.chat_stream(
        [{"role": "user", "content": "hi"}],
        on_delta=deltas.append,
    )

    assert deltas == ["hel", "lo"]
    assert response.content == "hello"
    assert response.finish_reason == "stop"

