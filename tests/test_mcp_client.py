from __future__ import annotations

from datetime import timedelta
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from ipilot.config.schema import McpServerConfig


@pytest.mark.asyncio
async def test_mcp_server_client_lists_tools_and_calls_remote_tool(monkeypatch):
    from ipilot.mcp import client as mcp_client_module

    events: list[object] = []

    class FakeSession:
        def __init__(self, read_stream, write_stream):
            self.read_stream = read_stream
            self.write_stream = write_stream

        async def __aenter__(self):
            events.append(("session_enter", self.read_stream, self.write_stream))
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append(("session_exit", exc_type, exc))

        async def initialize(self):
            events.append(("initialize",))
            return SimpleNamespace(protocolVersion="2024-11-05")

        async def list_tools(self, cursor=None, params=None):
            events.append(("list_tools", cursor, params))
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="rag_query",
                        description="Query the knowledge base",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                            },
                            "required": ["question"],
                        },
                    )
                ]
            )

        async def call_tool(self, name, arguments=None, read_timeout_seconds=None, progress_callback=None, meta=None):
            events.append(("call_tool", name, arguments, read_timeout_seconds))
            return SimpleNamespace(
                isError=False,
                content=[SimpleNamespace(type="text", text="remote answer")],
                structuredContent={"answer": "remote answer"},
            )

    @asynccontextmanager
    async def fake_streamable_http_client(
        url,
        *,
        http_client=None,
        timeout=None,
        sse_read_timeout=None,
        terminate_on_close=True,
    ):
        events.append(("transport_enter", url, timeout, sse_read_timeout, terminate_on_close))
        yield (object(), object(), lambda: "session-1")
        events.append(("transport_exit", url))

    monkeypatch.setattr(mcp_client_module, "streamable_http_client", fake_streamable_http_client)
    monkeypatch.setattr(mcp_client_module, "ClientSession", FakeSession)

    server = McpServerConfig(name="light-rag", url="http://127.0.0.1:8091/mcp")
    server.timeout_seconds = 12.5
    async with mcp_client_module.McpServerClient(server) as client:
        tools = await client.list_tools()
        result = await client.call_tool("rag_query", {"question": "what is the main chain?"})

    assert tools[0].name == "rag_query"
    assert result.content[0].text == "remote answer"
    assert events[0] == (
        "transport_enter",
        "http://127.0.0.1:8091/mcp",
        timedelta(seconds=12.5),
        timedelta(seconds=12.5),
        True,
    )
    assert any(event[0] == "initialize" for event in events)
    assert any(
        event[0] == "call_tool"
        and event[1] == "rag_query"
        and event[3] == timedelta(seconds=12.5)
        for event in events
    )
