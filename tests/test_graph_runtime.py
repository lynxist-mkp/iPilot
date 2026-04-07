from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from ipilot.agent import graph_runtime


class RecordingModel:
    def __init__(self):
        self.bound_tools = None
        self.invocations: list[dict] = []

    def bind_tools(self, tools):
        self.bound_tools = list(tools)
        return BoundModel(self)


class BoundModel:
    def __init__(self, owner: RecordingModel):
        self.owner = owner

    def invoke(self, messages, context=None):
        self.owner.invocations.append({"messages": messages, "context": context})
        return SimpleNamespace(content="final")


class FakeToolNode:
    def __init__(self, tools):
        self.tools = list(tools)


class FakeStateGraph:
    last_instance = None

    def __init__(self, state_type):
        self.state_type = state_type
        self.nodes: dict[str, object] = {}
        self.edges: list[tuple[object, object]] = []
        self.conditional_edges: list[tuple[object, object, dict[str, object]]] = []
        self.checkpointer = None
        FakeStateGraph.last_instance = self

    def add_node(self, name, action):
        self.nodes[name] = action

    def add_edge(self, source, target):
        self.edges.append((source, target))

    def add_conditional_edges(self, source, condition, mapping):
        self.conditional_edges.append((source, condition, mapping))

    def compile(self, checkpointer=None):
        self.checkpointer = checkpointer
        return self


def test_build_agent_graph_binds_tools_and_uses_middleware(monkeypatch):
    model = RecordingModel()
    tools = [object(), object()]

    monkeypatch.setattr(graph_runtime, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(graph_runtime, "ToolNode", FakeToolNode)

    graph_runtime.build_agent_graph(
        model=model,
        tools=tools,
        middleware=[lambda context: f"prompt:{context.channel}:{context.chat_id}"],
        sqlite_path="ignored.sqlite3",
    )

    builder = FakeStateGraph.last_instance
    assert model.bound_tools == tools

    call_model = builder.nodes["call_model"]
    runtime = SimpleNamespace(
        context=SimpleNamespace(
            session_key="cli:default",
            channel="cli",
            chat_id="default",
            workspace_path=Path("."),
            provider="stepfun",
            model="step-3.5-flash",
        )
    )
    result = call_model({"messages": [{"role": "user", "content": "hello"}]}, runtime)

    assert result["messages"][0].content == "final"
    assert model.invocations[0]["messages"][0]["content"] == "prompt:cli:default"
    assert model.invocations[0]["messages"][1]["content"] == "hello"


def test_confirm_dangerous_action_interrupts_on_exec_tool_call(monkeypatch):
    class ApprovalRequested(RuntimeError):
        pass

    captured = {}

    def fake_interrupt(payload):
        captured["payload"] = payload
        raise ApprovalRequested("approval requested")

    monkeypatch.setattr(graph_runtime, "interrupt", fake_interrupt)
    state = {
        "messages": [
            SimpleNamespace(
                tool_calls=[
                    {
                        "name": "exec",
                        "args": {"command": "rm -rf /tmp/workspace"},
                    }
                ]
            )
        ]
    }
    runtime = SimpleNamespace(context=SimpleNamespace(session_key="cli:danger"))

    with pytest.raises(ApprovalRequested):
        graph_runtime.confirm_dangerous_action(state, runtime)

    assert captured["payload"]["tool_name"] == "exec"
    assert captured["payload"]["command"] == "rm -rf /tmp/workspace"
