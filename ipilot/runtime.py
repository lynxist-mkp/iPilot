from __future__ import annotations


from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from ipilot.agent.context import ContextBuilder
from ipilot.agent.langchain_tools import build_langchain_tools
from ipilot.agent.loop import AgentLoop
from ipilot.agent.middleware import build_system_prompt
from ipilot.agent.models import build_chat_model
from ipilot.agent.runtime_context import AgentRuntimeContext
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

def build_toolset(config: Config):
    return build_langchain_tools(config.workspace_path)

def  build_agent_loop(config: Config):
    chat_model = build_chat_model(config)
    ...

# def build_agent_loop(config: Config) -> AgentLoop:
#     workspace = config.workspace_path
#     provider_name = config.agents.defaults.provider
#     provider_config = getattr(config.providers, provider_name)

#     provider = OpenAICompatibleProvider(
#         api_key=provider_config.api_key,
#         api_base=provider_config.api_base,
#         model=config.agents.defaults.model,
#     )
#     sessions = SessionManager(workspace)
#     context = ContextBuilder(workspace)
#     return AgentLoop(provider, workspace, sessions, build_tool_registry(workspace), context)

def build_experiment_agent(config: Config):
    model = build_chat_model(config)
    tools = build_langchain_tools(config.workspace_path)
    checkpointer = InMemorySaver()

    return create_agent(
        model=model,
        tools=tools,
        middleware=[build_system_prompt],
        checkpointer=checkpointer,
    )

def build_runtime_context_factory(config: Config):
    def factory(*, session_key: str, channel: str | None, chat_id: str | None):
        return AgentRuntimeContext(
            session_key=session_key,
            channel=channel,
            chat_id=chat_id,
            workspace_path=config.workspace_path,
            provider=config.agents.defaults.provider,
            model=config.agents.defaults.model,
        )
    return factory

def build_ipilot(config: Config) -> iPilot:
    return iPilot(build_agent_loop(config))

