from __future__ import annotations

from ipilot.agent.graph_runtime import build_agent_graph
from ipilot.agent.langchain_tools import build_langchain_tools
from ipilot.agent.loop import AgentLoop
from ipilot.agent.middleware import build_system_prompt, build_system_prompt_middleware
from ipilot.agent.runtime_context import AgentRuntimeContext
from ipilot.config.schema import Config
from ipilot.core import iPilot


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


def build_agent_loop(config: Config) -> AgentLoop:
    from ipilot.agent.models import build_chat_model
    model = build_chat_model(config)
    tools = build_langchain_tools(config.workspace_path)

    graph = build_agent_graph(
        model=model,
        tools=tools,
        middleware=[build_system_prompt],
        sqlite_path=str(config.workspace_path / "checkpoints.sqlite3"),
    )
    context_factory = build_runtime_context_factory(config)
    return AgentLoop(graph=graph, context_factory=context_factory)


def build_experiment_agent(config: Config):
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    from ipilot.agent.models import build_chat_model

    model = build_chat_model(config)
    tools = build_langchain_tools(config.workspace_path)
    checkpointer = InMemorySaver()
    middleware = [build_system_prompt_middleware] if build_system_prompt_middleware is not None else []

    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=checkpointer,
    )


def build_ipilot(config: Config) -> iPilot:
    return iPilot(build_agent_loop(config))
