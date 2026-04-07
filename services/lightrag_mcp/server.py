from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import LightRAGServerConfig, load_server_config
from .rag_service import LightRAGService
from .tool_handlers import LightRAGToolHandlers


def build_server(config: LightRAGServerConfig | None = None) -> FastMCP:
    config = config or load_server_config()
    service = LightRAGService(config)
    handlers = LightRAGToolHandlers(service)

    mcp = FastMCP(
        "iPilot LightRAG MCP",
        json_response=True,
        stateless_http=True,
    )
    mcp.settings.host = config.host
    mcp.settings.port = config.port
    mcp.settings.streamable_http_path = "/mcp"

    @mcp.tool()
    async def rag_query(question: str, mode: str = "hybrid", top_k: int | None = None) -> dict[str, Any]:
        """Query the LightRAG knowledge base."""
        return await handlers.rag_query(question=question, mode=mode, top_k=top_k)

    @mcp.tool()
    async def rag_index_paths(paths: list[str]) -> dict[str, Any]:
        """Index a list of workspace-relative paths."""
        return await handlers.rag_index_paths(paths=paths)

    @mcp.tool()
    async def rag_rebuild(paths: list[str] | None = None) -> dict[str, Any]:
        """Rebuild the knowledge base from scratch."""
        return await handlers.rag_rebuild(paths=paths)

    return mcp


def main() -> None:
    config = load_server_config()
    server = build_server(config)
    server.run(transport=config.transport)


if __name__ == "__main__":
    main()
