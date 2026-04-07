from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class AgentRunResult:
    content: str | None
    messages: list[Any] = field(default_factory=list)
    finish_reason: str = "stop"
    interrupts: list[Any] = field(default_factory=list)