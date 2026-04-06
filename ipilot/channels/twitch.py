from __future__ import annotations

import json

import httpx
import websockets

from ipilot.bus.events import InboundMessage
from ipilot.channels.base import BaseChannel


class TwitchEventSubClient:
    def __init__(
        self,
        client_id: str,
        access_token: str,
        broadcaster_id: str,
        sender_id: str,
        eventsub_ws_url: str,
        helix_api_base: str,
        websocket_factory=None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.client_id = client_id
        self.access_token = access_token
        self.broadcaster_id = broadcaster_id
        self.sender_id = sender_id
        self.eventsub_ws_url = eventsub_ws_url
        self.helix_api_base = helix_api_base.rstrip("/")
        self.websocket_factory = websocket_factory or websockets.connect
        self.websocket = None
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(timeout=20.0)
        self.session_id: str | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }

    async def connect(self) -> str:
        self.websocket = await self.websocket_factory(self.eventsub_ws_url)
        welcome = await self.recv()
        self.session_id = str(welcome.get("payload", {}).get("session", {}).get("id") or "")
        if not self.session_id:
            raise RuntimeError("Twitch EventSub session id missing from welcome message.")
        return self.session_id

    async def subscribe_chat_messages(self) -> dict:
        if not self.session_id:
            raise RuntimeError("Twitch EventSub client must connect before subscribing.")
        response = await self.http_client.post(
            f"{self.helix_api_base}/eventsub/subscriptions",
            headers=self._headers,
            json={
                "type": "channel.chat.message",
                "version": "1",
                "condition": {
                    "broadcaster_user_id": self.broadcaster_id,
                    "user_id": self.sender_id,
                },
                "transport": {
                    "method": "websocket",
                    "session_id": self.session_id,
                },
            },
        )
        response.raise_for_status()
        return response.json()

    async def recv(self) -> dict:
        if self.websocket is None:
            raise RuntimeError("Twitch EventSub client is not connected.")
        payload = await self.websocket.recv()
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)

    async def close(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None
        if self._owns_http_client:
            await self.http_client.aclose()


class TwitchHelixClient:
    def __init__(
        self,
        client_id: str,
        access_token: str,
        helix_api_base: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.client_id = client_id
        self.access_token = access_token
        self.helix_api_base = helix_api_base.rstrip("/")
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(timeout=20.0)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }

    async def send_chat_message(self, *, broadcaster_id: str, sender_id: str, text: str) -> dict:
        response = await self.http_client.post(
            f"{self.helix_api_base}/chat/messages",
            headers=self._headers,
            json={
                "broadcaster_id": broadcaster_id,
                "sender_id": sender_id,
                "message": text,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()


class TwitchChannel(BaseChannel):
    def __init__(self, config, bus, bot_runner, event_client, api_client):
        super().__init__(config, bus)
        self.bot_runner = bot_runner
        self.events = event_client
        self.api = api_client
        self._running = False

    async def start(self):
        self._running = True
        await self.events.connect()
        await self.events.subscribe_chat_messages()
        try:
            while self._running:
                event = await self.events.recv()
                await self.handle_event(event)
        finally:
            await self.events.close()
            await self.api.close()

    async def stop(self):
        self._running = False
        await self.events.close()
        await self.api.close()

    async def handle_event(self, event: dict):
        if event.get("subscription", {}).get("type") != "channel.chat.message":
            return

        payload = event.get("event", {})
        text = str(payload.get("message", {}).get("text") or "").strip()
        if not text:
            return

        broadcaster_id = str(payload.get("broadcaster_user_id") or "")
        chatter_id = str(payload.get("chatter_user_id") or "")

        inbound = InboundMessage(
            channel="twitch",
            chat_id=broadcaster_id,
            sender_id=chatter_id,
            content=text,
            metadata={
                "message_id": payload.get("message_id"),
                "chatter_user_login": payload.get("chatter_user_login"),
                "chatter_user_name": payload.get("chatter_user_name"),
                "reply": payload.get("reply"),
            },
        )

        response = await self.bot_runner.run(
            inbound.content,
            session_key=inbound.session_key,
            channel=inbound.channel,
            chat_id=inbound.chat_id,
        )

        await self.api.send_chat_message(
            broadcaster_id=broadcaster_id,
            sender_id=self.config.sender_id,
            text=response.content or "",
        )

