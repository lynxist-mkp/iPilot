from __future__ import annotations

from typing import Any

from ipilot.agent.middleware import build_system_prompt
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt


def build_agent_graph(*, model, tools, middleware, sqlite_path):
    bound_model = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    def render_system_prompt(context) -> str:
        prompts: list[str] = []
        for item in middleware or []:
            prompt = item(context)
            if prompt:
                prompts.append(prompt)
        if not prompts:
            return build_system_prompt(context)
        return "\n\n---\n\n".join(prompts)

    def call_model(state: MessagesState, runtime):
        messages = [{"role": "system", "content": render_system_prompt(runtime.context)}, *state["messages"]]
        response = bound_model.invoke(messages, context=runtime.context)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("confirm", confirm_dangerous_action)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", "confirm")
    builder.add_conditional_edges("confirm", tools_condition, {"tools": "tools", "__end__": END})
    builder.add_edge("tools", "call_model")

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ModuleNotFoundError:
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()
    else:
        checkpointer = SqliteSaver.from_conn_string(str(sqlite_path))
    return builder.compile(checkpointer=checkpointer)


def confirm_dangerous_action(state, runtime):
    last_message = state["messages"][-1]
    for tool_call in _extract_tool_calls(last_message):
        if _tool_call_name(tool_call) != "exec":
            continue

        arguments = _tool_call_arguments(tool_call)
        command = arguments.get("command", "")
        if "rm -rf" in command:
            interrupt(
                {
                    "kind": "approval",
                    "question": "检测到高风险命令，是否继续？",
                    "session_key": runtime.context.session_key,
                    "tool_name": "exec",
                    "command": command,
                }
            )

    return {}


def _extract_tool_calls(message) -> list[Any]:
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls", [])
    else:
        tool_calls = getattr(message, "tool_calls", [])
    return list(tool_calls or [])


def _tool_call_name(tool_call) -> str | None:
    if isinstance(tool_call, dict):
        return tool_call.get("name") or tool_call.get("tool_name")
    return getattr(tool_call, "name", None) or getattr(tool_call, "tool_name", None)


def _tool_call_arguments(tool_call) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        arguments = tool_call.get("args") or tool_call.get("arguments") or {}
    else:
        arguments = getattr(tool_call, "args", None) or getattr(tool_call, "arguments", None) or {}
    if isinstance(arguments, dict):
        return arguments
    return {}
