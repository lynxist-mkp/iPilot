from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipilot.channels.twitch import TwitchChannel


class RecordingBot:
    def __init__(self):
        self.calls: list[tuple[str, str, str, str]] = []

    async def run(self, message: str, session_key: str, channel: str | None = None, chat_id: str | None = None):
        self.calls.append((message, session_key, channel or "", chat_id or ""))
        return SimpleNamespace(content="hello from ipilot")


class RecordingAPIClient:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_chat_message(self, **payload):
        self.sent.append(payload)


class FakeEventClient:
    async def connect(self):
        return None

    async def subscribe_chat_messages(self):
        return None

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_twitch_channel_maps_chat_messages_to_bot_runner():
    bot = RecordingBot()
    api = RecordingAPIClient()
    channel = TwitchChannel(
        config=SimpleNamespace(sender_id="999"),
        bus=None,
        bot_runner=bot,
        event_client=FakeEventClient(),
        api_client=api,
    )

    await channel.handle_event(
        {
            "subscription": {"type": "channel.chat.message"},
            "event": {
                "broadcaster_user_id": "123",
                "chatter_user_id": "456",
                "chatter_user_login": "demo-user",
                "chatter_user_name": "Demo User",
                "message_id": "mid-1",
                "message": {"text": "hello there"},
                "reply": {"parent_message_id": "parent-1"},
            },
        }
    )

    assert bot.calls == [("hello there", "twitch:123", "twitch", "123")]
    assert api.sent == [
        {
            "broadcaster_id": "123",
            "sender_id": "999",
            "text": "hello from ipilot",
        }
    ]


@pytest.mark.asyncio
async def test_twitch_channel_ignores_non_chat_messages():
    bot = RecordingBot()
    api = RecordingAPIClient()
    channel = TwitchChannel(
        config=SimpleNamespace(sender_id="999"),
        bus=None,
        bot_runner=bot,
        event_client=FakeEventClient(),
        api_client=api,
    )

    await channel.handle_event({"subscription": {"type": "channel.follow"}, "event": {}})

    assert bot.calls == []
    assert api.sent == []

