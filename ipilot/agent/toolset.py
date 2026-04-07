from __future__ import annotations

from langchain_core.tools import BaseTool

from ipilot.agent.langchain_tools import build_langchain_tools
from ipilot.config.schema import Config
from ipilot.mcp.bridge import build_mcp_tools


def build_agent_tools(config: Config) -> list[BaseTool]:
    tools = list(build_langchain_tools(config.workspace_path))
    tools.extend(build_mcp_tools(config))
    return tools
