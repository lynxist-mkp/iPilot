from __future__ import annotations

from datetime import timedelta
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ipilot.config.schema import McpServerConfig


@dataclass(slots=True)
class McpServerClient:
    server: McpServerConfig
    _stack: AsyncExitStack | None = field(default=None, init=False, repr=False)
    _session: ClientSession | None = field(default=None, init=False, repr=False)
    _session_id: str | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "McpServerClient":
        self._stack = AsyncExitStack()
        read_stream, write_stream, get_session_id = await self._stack.enter_async_context(
            streamable_http_client(
                self.server.url,
                timeout=timedelta(seconds=self.server.timeout_seconds),
                sse_read_timeout=timedelta(seconds=self.server.timeout_seconds),
                terminate_on_close=True,
            )
        )
        self._session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self._session.initialize()
        self._session_id = get_session_id()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is None:
            return None
        await self._stack.aclose()
        self._stack = None
        self._session = None
        self._session_id = None
        return None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        return self._session

    async def list_tools(self):
        session = self._require_session()
        result = await session.list_tools()
        return list(result.tools or [])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        session = self._require_session()
        return await session.call_tool(
            name,
            arguments or {},
            read_timeout_seconds=timedelta(seconds=self.server.timeout_seconds),
        )
