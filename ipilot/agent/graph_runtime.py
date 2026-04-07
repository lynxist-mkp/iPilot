from __future__ import annotations

from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt


def build_agent_graph(*, model, tools, middleware, sqlite_path):
    del middleware

    tool_node = ToolNode(tools)

    def call_model(state: MessagesState, runtime):
        response = model.invoke(state["messages"], context=runtime.context)
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
    text = getattr(last_message, "content", "") or ""
    if "rm -rf" not in text:
        return {}

    interrupt(
        {
            "kind": "approval",
            "question": "检测到高风险命令，是否继续？",
            "session_key": runtime.context.session_key,
        }
    )
    return {}
