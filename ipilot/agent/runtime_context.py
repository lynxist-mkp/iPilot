from dataclasses import dataclass
from pathlib import Path

@dataclass(slots=True)
class AgentRuntimeContext:
    session_key: str
    channel: str | None
    chat_id: str | None
    workspace_path: Path
    provider: str
    model: str