# 第 3 章：iPilot 侧 MCP Client 与桥接完整代码

这一章直接给你 iPilot 侧要手敲的代码：

```text
ipilot/mcp/
  __init__.py
  models.py
  client.py
  bridge.py
```

这一章结束后，你会得到：

- 通用 `MCP client`
- 多 server 管理器
- 把远端 MCP tools 动态变成 LangChain tools 的桥接层

## 3.1 `ipilot/mcp/__init__.py`

```python
from .bridge import build_mcp_tools, build_mcp_tools_async
from .client import McpClientManager, McpServerClient
from .models import McpConfig, McpServerConfig, RemoteToolSpec

__all__ = [
    "McpClientManager",
    "McpServerClient",
    "McpConfig",
    "McpServerConfig",
    "RemoteToolSpec",
    "build_mcp_tools",
    "build_mcp_tools_async",
]
```

## 3.2 `ipilot/mcp/models.py`

这个文件只放数据模型，不放连接逻辑。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class McpServerConfig:
    name: str
    url: str
    enabled: bool = True
    transport: str = "streamable_http"
    timeout_seconds: float = 30.0


@dataclass(slots=True)
class McpConfig:
    servers: list[McpServerConfig] = field(default_factory=list)


@dataclass(slots=True)
class RemoteToolSpec:
    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any]
```

### 这段代码怎么读

- `McpServerConfig` 描述单个 MCP server
- `McpConfig` 描述整个 MCP 配置集合
- `RemoteToolSpec` 描述远端 tool 的 schema 元信息

## 3.3 `ipilot/mcp/client.py`

这个文件负责真正的 MCP 连接和远端调用。

```python
from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .models import McpConfig, McpServerConfig, RemoteToolSpec


@dataclass(slots=True)
class McpServerClient:
    config: McpServerConfig
    _stack: AsyncExitStack = field(default_factory=AsyncExitStack, init=False, repr=False)
    _session: ClientSession | None = field(default=None, init=False, repr=False)

    async def open(self) -> None:
        if self._session is not None:
            return

        read_stream, write_stream, _ = await self._stack.enter_async_context(
            streamable_http_client(self.config.url)
        )
        self._session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self._session.initialize()

    async def close(self) -> None:
        await self._stack.aclose()
        self._session = None

    async def list_tools(self) -> list[RemoteToolSpec]:
        await self.open()
        assert self._session is not None

        response = await self._session.list_tools()
        tools = getattr(response, "tools", []) or []

        specs: list[RemoteToolSpec] = []
        for tool in tools:
            input_schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
            description = getattr(tool, "description", "") or ""
            name = getattr(tool, "name", "")
            specs.append(
                RemoteToolSpec(
                    server_name=self.config.name,
                    name=name,
                    description=description,
                    input_schema=input_schema if isinstance(input_schema, dict) else {},
                )
            )
        return specs

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        await self.open()
        assert self._session is not None
        return await self._session.call_tool(tool_name, arguments)


@dataclass(slots=True)
class McpClientManager:
    config: McpConfig
    clients: dict[str, McpServerClient] = field(default_factory=dict, init=False, repr=False)

    def _ensure_clients(self) -> None:
        if self.clients:
            return

        for server in self.config.servers:
            if not server.enabled:
                continue
            if server.name in self.clients:
                raise ValueError(f"duplicate MCP server name: {server.name}")
            self.clients[server.name] = McpServerClient(server)

    async def open(self) -> None:
        self._ensure_clients()
        for client in self.clients.values():
            await client.open()

    async def close(self) -> None:
        for client in self.clients.values():
            await client.close()

    async def describe_tools(self) -> list[RemoteToolSpec]:
        await self.open()
        specs: list[RemoteToolSpec] = []
        for client in self.clients.values():
            specs.extend(await client.list_tools())
        return specs

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        await self.open()
        if server_name not in self.clients:
            raise KeyError(f"unknown MCP server: {server_name}")
        return await self.clients[server_name].call_tool(tool_name, arguments)
```

### 这段代码怎么读

- `McpServerClient` 只管一个 server
- `McpClientManager` 管多个 server
- `list_tools()` 先连接，再拉 schema
- `call_tool()` 直接把参数透传到远端

### 这一层的完成标志

先别接 LangChain，先跑一个最小脚本：

```python
import asyncio
from ipilot.mcp.models import McpConfig, McpServerConfig
from ipilot.mcp.client import McpClientManager

async def main():
    manager = McpClientManager(
        McpConfig(
            servers=[
                McpServerConfig(
                    name="lightrag",
                    url="http://127.0.0.1:8091/mcp",
                )
            ]
        )
    )
    tools = await manager.describe_tools()
    print([tool.name for tool in tools])
    print(await manager.call_tool("lightrag", "rag_query", {"question": "hello"}))

asyncio.run(main())
```

## 3.4 `ipilot/mcp/bridge.py`

这个文件负责把远端 MCP tools 变成 LangChain tools。

```python
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

from .client import McpClientManager
from .models import McpConfig, RemoteToolSpec


def _camel_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in value.replace("-", "_").split("_") if part)


def _annotation_from_schema(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0] if schema_type else "string")

    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        items = schema.get("items", {}) or {}
        item_annotation = _annotation_from_schema(items)
        if item_annotation is int:
            return list[int]
        if item_annotation is float:
            return list[float]
        if item_annotation is bool:
            return list[bool]
        return list[str]
    if schema_type == "object":
        return dict[str, Any]
    return str


def _build_args_schema(server_name: str, tool: RemoteToolSpec) -> type[BaseModel]:
    properties = tool.input_schema.get("properties", {}) or {}
    required = set(tool.input_schema.get("required", []) or [])
    field_definitions: dict[str, tuple[Any, Any]] = {}

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            field_schema = {}
        annotation = _annotation_from_schema(field_schema)
        if field_name in required:
            field_definitions[field_name] = (annotation, ...)
        else:
            field_definitions[field_name] = (annotation | None, None)

    model_name = f"{_camel_case(server_name)}{_camel_case(tool.name)}Args"
    return create_model(model_name, **field_definitions)  # type: ignore[arg-type]


def _normalize_mcp_result(result: Any) -> str:
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, indent=2, default=str)

    content = getattr(result, "content", None)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
                continue
            parts.append(json.dumps(getattr(item, "__dict__", item), ensure_ascii=False, default=str))
        if parts:
            return "\n".join(parts)

    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    return str(result)


def _build_langchain_tool(manager: McpClientManager, tool: RemoteToolSpec) -> BaseTool:
    args_schema = _build_args_schema(tool.server_name, tool)

    async def _invoke(**kwargs: Any) -> str:
        result = await manager.call_tool(tool.server_name, tool.name, kwargs)
        return _normalize_mcp_result(result)

    return StructuredTool.from_function(
        name=f"mcp_{tool.server_name}_{tool.name}",
        description=tool.description or f"MCP tool from {tool.server_name}: {tool.name}",
        coroutine=_invoke,
        args_schema=args_schema,
    )


async def build_mcp_tools_async(config: McpConfig) -> list[BaseTool]:
    manager = McpClientManager(config)
    tool_specs = await manager.describe_tools()
    return [_build_langchain_tool(manager, tool) for tool in tool_specs]


def build_mcp_tools(config: McpConfig) -> list[BaseTool]:
    return asyncio.run(build_mcp_tools_async(config))
```

### 这段代码怎么读

- `RemoteToolSpec` 先变成 Pydantic schema
- 再用 `StructuredTool.from_function(...)` 生成 LangChain tool
- 工具名统一加 `mcp_<server>_<tool>`
- tool 调用时再转发到远端 MCP server

### 你要注意的地方

- 第一版只支持基础 JSON Schema
- 复杂嵌套对象先降级成 `dict[str, Any]`
- `build_mcp_tools()` 用 `asyncio.run(...)`，所以它适合启动阶段调用

### 本章完成标志

桥接层跑通后，你应该能看到：

```text
mcp_lightrag_rag_query
mcp_lightrag_rag_index_paths
mcp_lightrag_rag_rebuild
```
