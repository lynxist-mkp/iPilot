from __future__ import annotations

from contextlib import asynccontextmanager
import types
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


try:
    import mcp.client.session  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    mcp = types.ModuleType("mcp")
    mcp.__path__ = []  # type: ignore[attr-defined]

    client_pkg = types.ModuleType("mcp.client")
    client_pkg.__path__ = []  # type: ignore[attr-defined]

    session_mod = types.ModuleType("mcp.client.session")

    class ClientSession:
        def __init__(self, read_stream, write_stream):
            self.read_stream = read_stream
            self.write_stream = write_stream

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def initialize(self):
            return types.SimpleNamespace(protocolVersion="2024-11-05")

        async def list_tools(self, cursor=None, params=None):
            return types.SimpleNamespace(tools=[])

        async def call_tool(
            self,
            name,
            arguments=None,
            read_timeout_seconds=None,
            progress_callback=None,
            meta=None,
        ):
            return types.SimpleNamespace(isError=False, content=[], structuredContent=None)

    session_mod.ClientSession = ClientSession

    streamable_http_mod = types.ModuleType("mcp.client.streamable_http")

    @asynccontextmanager
    async def streamable_http_client(url, *, http_client=None, terminate_on_close=True):
        yield (object(), object(), lambda: "session-1")

    streamable_http_mod.streamable_http_client = streamable_http_client

    server_pkg = types.ModuleType("mcp.server")
    server_pkg.__path__ = []  # type: ignore[attr-defined]

    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

    class FastMCP:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.settings = types.SimpleNamespace(host=None, port=None, streamable_http_path=None)

        def tool(self):
            def decorator(fn):
                return fn

            return decorator

        def run(self, transport):
            self.transport = transport

    fastmcp_mod.FastMCP = FastMCP

    client_pkg.session = session_mod
    client_pkg.streamable_http = streamable_http_mod
    server_pkg.fastmcp = fastmcp_mod
    mcp.client = client_pkg
    mcp.server = server_pkg

    sys.modules["mcp"] = mcp
    sys.modules["mcp.client"] = client_pkg
    sys.modules["mcp.client.session"] = session_mod
    sys.modules["mcp.client.streamable_http"] = streamable_http_mod
    sys.modules["mcp.server"] = server_pkg
    sys.modules["mcp.server.fastmcp"] = fastmcp_mod
