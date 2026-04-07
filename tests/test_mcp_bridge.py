from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipilot.config.schema import Config, McpConfig, McpServerConfig


@pytest.mark.asyncio
async def test_build_mcp_tools_from_descriptors_wraps_remote_call():
    from ipilot.mcp.bridge import McpToolDescriptor, build_mcp_tools_from_descriptors

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, server):
            self.server = server

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def call_tool(self, name, arguments=None):
            calls.append((name, dict(arguments or {})))
            return SimpleNamespace(
                isError=False,
                content=[SimpleNamespace(type="text", text="remote answer")],
                structuredContent={"answer": "remote answer"},
            )

    descriptor = McpToolDescriptor(
        server_name="light-rag",
        server_url="http://127.0.0.1:8091/mcp",
        tool_name="rag_query",
        description="Query the knowledge base",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["question"],
        },
    )

    tools = build_mcp_tools_from_descriptors(
        [descriptor],
        client_factory=lambda server: FakeClient(server),
    )

    tool = tools[0]
    assert tool.name == "mcp_light_rag_rag_query"

    result = await tool.ainvoke({"question": "what is the main chain?", "top_k": 3})

    assert result == "remote answer"
    assert calls == [("rag_query", {"question": "what is the main chain?", "top_k": 3})]


def test_build_mcp_tools_uses_configured_servers(monkeypatch):
    from ipilot.mcp import bridge as mcp_bridge

    captured = {}

    config = Config(
        mcp=McpConfig(
            servers=[
                McpServerConfig(name="light-rag", url="http://127.0.0.1:8091/mcp"),
            ]
        )
    )

    monkeypatch.setattr(
        mcp_bridge,
        "discover_mcp_tool_descriptors",
        lambda cfg, client_factory=None: (
            captured.__setitem__("client_factory", client_factory)
            or [
                mcp_bridge.McpToolDescriptor(
                    server_name="light-rag",
                    server_url="http://127.0.0.1:8091/mcp",
                    tool_name="rag_query",
                    description="Query the knowledge base",
                    input_schema={
                        "type": "object",
                        "properties": {"question": {"type": "string"}},
                        "required": ["question"],
                    },
                )
            ]
        ),
    )

    fake_client_factory = object()
    tools = mcp_bridge.build_mcp_tools(config, client_factory=fake_client_factory)

    assert [tool.name for tool in tools] == ["mcp_light_rag_rag_query"]
    assert captured["client_factory"] is fake_client_factory
