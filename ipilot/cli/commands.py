from __future__ import annotations

import asyncio

import typer

from ipilot import __version__
from ipilot import iPilot
from ipilot.channels.manager import ChannelManager
from ipilot.channels.twitch import TwitchChannel, TwitchEventSubClient, TwitchHelixClient
from ipilot.config.loader import load_config, save_config
from ipilot.cron.service import CronService
from ipilot.heartbeat.service import run_forever
from ipilot.runtime import build_agent_loop, build_ipilot


app = typer.Typer()
channel_app = typer.Typer()
app.add_typer(channel_app, name="channel")


def version_callback(value: bool):
    if value:
        print(f"iPilot version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
    ),
):
    return None


def build_channel_manager(channels: dict[str, object] | None = None) -> ChannelManager:
    manager = ChannelManager()
    for name, channel in (channels or {}).items():
        manager.register(name, channel)
    return manager


def build_runtime(config):
    return build_agent_loop(config)


def build_twitch_channel(config, bot):
    twitch = config.channels.twitch
    if not twitch.enabled:
        typer.echo("Twitch channel is not enabled in config.")
        raise typer.Exit(code=1)

    missing = [
        field_name
        for field_name in ("client_id", "access_token", "broadcaster_id", "sender_id")
        if not getattr(twitch, field_name)
    ]
    if missing:
        typer.echo(f"Twitch channel config is missing: {', '.join(missing)}")
        raise typer.Exit(code=1)

    event_client = TwitchEventSubClient(
        client_id=twitch.client_id,
        access_token=twitch.access_token,
        broadcaster_id=twitch.broadcaster_id,
        sender_id=twitch.sender_id,
        eventsub_ws_url=twitch.eventsub_ws_url,
        helix_api_base=twitch.helix_api_base,
    )
    api_client = TwitchHelixClient(
        client_id=twitch.client_id,
        access_token=twitch.access_token,
        helix_api_base=twitch.helix_api_base,
    )
    return TwitchChannel(
        config=twitch,
        bus=None,
        bot_runner=bot,
        event_client=event_client,
        api_client=api_client,
    )


@app.command()
def onboard():
    """Create config and workspace if they do not exist."""
    config = load_config()
    workspace_path = config.workspace_path
    workspace_path.mkdir(parents=True, exist_ok=True)
    save_config(config)
    print(f"Onboarding complete! Workspace created at: {workspace_path}")


@app.command()
def status():
    config = load_config()
    print(f"Workspace path: {config.workspace_path}")
    print(f"Default provider: {config.agents.defaults.provider}")
    print(f"Default model: {config.agents.defaults.model}")
    print(f"Twitch enabled: {config.channels.twitch.enabled}")


@app.command()
def agent(
    message: str = typer.Option(..., "--message", "-m", help="The initial message to start the agent with."),
    stream: bool = typer.Option(False, "--stream", help="Stream the assistant response to stdout."),
):
    bot = iPilot.from_config()
    if not stream:
        response = asyncio.run(bot.run(message, session_key="cli:default", channel="cli", chat_id="default"))
        print(response.content or "")
        return

    printed: list[str] = []

    def on_delta(delta: str) -> None:
        printed.append(delta)
        print(delta, end="", flush=True)

    response = asyncio.run(
        bot.run_stream(
            message,
            session_key="cli:default",
            on_delta=on_delta,
            channel="cli",
            chat_id="default",
        )
    )
    if not printed and response.content:
        print(response.content, end="", flush=True)
    print()


@app.command()
def heartbeat(interval_seconds: int = typer.Option(60, "--interval-seconds", min=1)):
    config = load_config()
    bot = build_ipilot(config)
    service = CronService(config.workspace_path)
    asyncio.run(run_forever(service, bot, interval_seconds))


async def _run_manager(manager: ChannelManager):
    try:
        await manager.start_all()
    finally:
        await manager.stop_all()


@channel_app.command("twitch")
def channel_twitch():
    config = load_config()
    twitch = config.channels.twitch
    if not twitch.enabled:
        typer.echo("Twitch channel is not enabled in config.")
        raise typer.Exit(code=1)

    missing = [
        field_name
        for field_name in ("client_id", "access_token", "broadcaster_id", "sender_id")
        if not getattr(twitch, field_name)
    ]
    if missing:
        typer.echo(f"Twitch channel config is missing: {', '.join(missing)}")
        raise typer.Exit(code=1)

    bot = build_ipilot(config)
    manager = build_channel_manager({"twitch": build_twitch_channel(config, bot)})
    asyncio.run(_run_manager(manager))

