from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner

from ipilot.cli.commands import app
from ipilot.config.schema import Config


runner = CliRunner()


def test_status_prints_default_config(monkeypatch, tmp_path):
    config = Config(
        agents={"defaults": {"workspace": str(tmp_path), "provider": "stepfun", "model": "step-3.5-flash"}},
    )
    monkeypatch.setattr("ipilot.cli.commands.load_config", lambda: config)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert str(tmp_path) in result.stdout
    assert "stepfun" in result.stdout


def test_agent_stream_prints_deltas(monkeypatch):
    class FakeBot:
        async def run_stream(self, message: str, session_key: str, on_delta, channel=None, chat_id=None):
            on_delta("hel")
            on_delta("lo")
            return SimpleNamespace(content="hello")

    monkeypatch.setattr("ipilot.cli.commands.iPilot.from_config", lambda: FakeBot())

    result = runner.invoke(app, ["agent", "-m", "hello", "--stream"])

    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_heartbeat_command_invokes_runner(monkeypatch):
    called = {}

    async def fake_run_forever(service, bot, interval_seconds):
        called["interval_seconds"] = interval_seconds
        called["service"] = service
        called["bot"] = bot

    monkeypatch.setattr("ipilot.cli.commands.run_forever", fake_run_forever)
    monkeypatch.setattr("ipilot.cli.commands.load_config", lambda: Config())
    monkeypatch.setattr("ipilot.cli.commands.build_ipilot", lambda config: SimpleNamespace())

    result = runner.invoke(app, ["heartbeat", "--interval-seconds", "5"])

    assert result.exit_code == 0
    assert called["interval_seconds"] == 5


def test_channel_twitch_command_requires_enabled_config(monkeypatch):
    monkeypatch.setattr("ipilot.cli.commands.load_config", lambda: Config())

    result = runner.invoke(app, ["channel", "twitch"])

    assert result.exit_code != 0
    assert "enabled" in result.stdout.lower()
