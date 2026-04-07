from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from ipilot.config.schema import Config, McpServerConfig

from .client import McpServerClient
from .models import McpToolDescriptor, McpToolResult


def _sanitize_name(value: str) -> str:
    sanitized = re.sub(r"[^0-9a-zA-Z_]+", "_", value).strip("_").lower()
    return sanitized or "tool"


def _tool_name(server_name: str, tool_name: str) -> str:
    return f"mcp_{_sanitize_name(server_name)}_{_sanitize_name(tool_name)}"


def _schema_to_type(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")

    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        if len(non_null) == 1:
            inner = _schema_to_type({**schema, "type": non_null[0]})
            return inner | type(None)  # type: ignore[operator]
        return Any

    if "enum" in schema:
        return Any

    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        items_schema = schema.get("items") or {}
        return list[_schema_to_type(items_schema)]  # type: ignore[index]
    if schema_type == "object":
        return dict[str, Any]

    if "anyOf" in schema:
        return Any

    return Any


def _build_args_schema(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    properties = input_schema.get("properties") or {}
    required = set(input_schema.get("required") or [])
    fields: dict[str, tuple[Any, Any]] = {}

    for field_name, field_schema in properties.items():
        annotation = _schema_to_type(field_schema)
        if field_name in required:
            default = ...
        else:
            default = None
            if annotation is not Any:
                annotation = annotation | type(None)  # type: ignore[operator]
        fields[field_name] = (annotation, default)

    model_name = f"{_sanitize_name(tool_name).title().replace('_', '')}Args"
    return create_model(model_name, **fields)  # type: ignore[arg-type]


def _format_call_result(result: Any) -> McpToolResult:
    if getattr(result, "isError", False):
        text = getattr(result, "content", None)
        if text:
            return McpToolResult(text=str(text), raw=result, is_error=True)
        return McpToolResult(text="MCP tool call failed", raw=result, is_error=True)

    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text" and getattr(block, "text", None) is not None:
            parts.append(str(block.text))
            continue
        if getattr(block, "text", None) is not None:
            parts.append(str(block.text))
            continue
        parts.append(json.dumps(block, ensure_ascii=False, default=str))

    if not parts:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            parts.append(json.dumps(structured, ensure_ascii=False, default=str))

    return McpToolResult(text="\n".join(parts).strip(), raw=result, is_error=False)


async def discover_mcp_tool_descriptors_async(
    config: Config,
    *,
    client_factory: Callable[[McpServerConfig], McpServerClient] = McpServerClient,
) -> list[McpToolDescriptor]:
    descriptors: list[McpToolDescriptor] = []

    for server in config.mcp.servers:
        if not server.enabled:
            continue
        if server.transport != "streamable-http":
            raise ValueError(f"unsupported MCP transport: {server.transport}")

        async with client_factory(server) as client:
            tools = await client.list_tools()

        for tool in tools:
            descriptors.append(
                McpToolDescriptor(
                    server_name=server.name,
                    server_url=server.url,
                    tool_name=tool.name,
                    description=getattr(tool, "description", None),
                    input_schema=dict(getattr(tool, "inputSchema", None) or {}),
                    output_schema=dict(getattr(tool, "outputSchema", None) or {}) or None,
                    annotations=dict(getattr(tool, "annotations", None) or {}) or None,
                )
            )

    return descriptors


def discover_mcp_tool_descriptors(
    config: Config,
    *,
    client_factory: Callable[[McpServerConfig], McpServerClient] = McpServerClient,
) -> list[McpToolDescriptor]:
    return asyncio.run(discover_mcp_tool_descriptors_async(config, client_factory=client_factory))


def build_mcp_tools_from_descriptors(
    descriptors: list[McpToolDescriptor],
    *,
    client_factory: Callable[[McpServerConfig], McpServerClient] = McpServerClient,
) -> list[StructuredTool]:
    tools: list[StructuredTool] = []

    for descriptor in descriptors:
        args_schema = _build_args_schema(descriptor.tool_name, descriptor.input_schema)
        tool_name = _tool_name(descriptor.server_name, descriptor.tool_name)
        tool_description = descriptor.description or f"MCP tool {descriptor.tool_name} from {descriptor.server_name}"

        async def invoke(
            _descriptor: McpToolDescriptor = descriptor,
            **kwargs: Any,
        ) -> str:
            server = McpServerConfig(name=_descriptor.server_name, url=_descriptor.server_url)
            async with client_factory(server) as client:
                result = await client.call_tool(_descriptor.tool_name, kwargs)
            formatted = _format_call_result(result)
            if formatted.is_error:
                raise RuntimeError(formatted.text)
            return formatted.text

        tools.append(
            StructuredTool.from_function(
                coroutine=invoke,
                name=tool_name,
                description=tool_description,
                args_schema=args_schema,
                infer_schema=False,
                response_format="content",
            )
        )

    return tools


def build_mcp_tools(
    config: Config,
    *,
    client_factory: Callable[[McpServerConfig], McpServerClient] = McpServerClient,
) -> list[StructuredTool]:
    descriptors = discover_mcp_tool_descriptors(config, client_factory=client_factory)
    return build_mcp_tools_from_descriptors(descriptors, client_factory=client_factory)
