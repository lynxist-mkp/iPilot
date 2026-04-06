from __future__ import annotations

from ipilot.agent.context import ContextBuilder
from ipilot.agent.loop import AgentLoop
from ipilot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from ipilot.agent.tools.registry import ToolRegistry
from ipilot.agent.tools.shell import ExecTool
from ipilot.config.schema import Config
from ipilot.core import iPilot
from ipilot.providers.openai_compat_provider import OpenAICompatibleProvider
from ipilot.session.manager import SessionManager


def build_tool_registry(workspace) -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(ReadFileTool(workspace))
    tools.register(ListDirTool(workspace))
    tools.register(WriteFileTool(workspace))
    tools.register(EditFileTool(workspace))
    tools.register(ExecTool(workspace))
    return tools


def build_agent_loop(config: Config) -> AgentLoop:
    workspace = config.workspace_path
    provider_name = config.agents.defaults.provider
    provider_config = getattr(config.providers, provider_name)

    provider = OpenAICompatibleProvider(
        api_key=provider_config.api_key,
        api_base=provider_config.api_base,
        model=config.agents.defaults.model,
    )
    sessions = SessionManager(workspace)
    context = ContextBuilder(workspace)
    return AgentLoop(provider, workspace, sessions, build_tool_registry(workspace), context)


def build_ipilot(config: Config) -> iPilot:
    return iPilot(build_agent_loop(config))

