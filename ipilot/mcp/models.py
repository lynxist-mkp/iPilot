from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class McpToolDescriptor:
    server_name: str
    server_url: str
    tool_name: str
    description: str | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None


@dataclass(slots=True)
class McpToolResult:
    text: str
    raw: Any | None = None
    is_error: bool = False
