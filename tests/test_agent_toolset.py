from __future__ import annotations

from types import SimpleNamespace

from ipilot.config.schema import Config, McpConfig, McpServerConfig


def test_build_agent_tools_merges_local_and_mcp_tools(monkeypatch):
    from ipilot.agent import toolset

    local_tool = SimpleNamespace(name="read_file")
    remote_tool = SimpleNamespace(name="mcp_light_rag_rag_query")

    monkeypatch.setattr(toolset, "build_langchain_tools", lambda workspace: [local_tool])
    monkeypatch.setattr(toolset, "build_mcp_tools", lambda config: [remote_tool])

    config = Config(
        agents={"defaults": {"workspace": "~/.ipilot/workspace"}},
        mcp=McpConfig(
            servers=[
                McpServerConfig(name="light-rag", url="http://127.0.0.1:8091/mcp"),
            ]
        ),
    )

    tools = toolset.build_agent_tools(config)

    assert [tool.name for tool in tools] == ["read_file", "mcp_light_rag_rag_query"]
