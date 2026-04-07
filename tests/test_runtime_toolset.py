from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ipilot.config.schema import Config


def test_build_agent_loop_uses_build_agent_tools(monkeypatch):
    from ipilot import runtime

    captured = {}

    monkeypatch.setattr(runtime, "build_agent_tools", lambda config: [SimpleNamespace(name="read_file")])
    monkeypatch.setattr(runtime, "build_chat_model", lambda config: SimpleNamespace())
    monkeypatch.setattr(
        runtime,
        "build_agent_graph",
        lambda model, tools, middleware, sqlite_path: captured.update(
            {
                "model": model,
                "tools": tools,
                "middleware": middleware,
                "sqlite_path": sqlite_path,
            }
        )
        or SimpleNamespace(),
    )

    config = Config(
        agents={"defaults": {"workspace": str(Path("."))}},
    )

    runtime.build_agent_loop(config)

    assert [tool.name for tool in captured["tools"]] == ["read_file"]
    assert captured["sqlite_path"].endswith("checkpoints.sqlite3")
