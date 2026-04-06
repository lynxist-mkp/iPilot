from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

@dataclass
class Session:
    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)

    def add_message(self, role: str, content: str, **extra: Any) -> None:
        message = {"role": role, "content": content}
        message.update(extra)
        self.messages.append(message)

class SessionManager:
    def __init__(self, workspace_path: str | Path):
        self.workspace_path = Path(workspace_path)
        self.sessions_dir = self.workspace_path / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}

    def get_or_create(self, key: str) -> Session:
        if key in self._cache:
            return self._cache[key]
        session = self._load(key)
        if session is None:
            session = Session(key=key)
        
        self._cache[key] = session
        return session

    def save(self, session: Session) -> None:
        self._cache[session.key] = session

        path = self._path_for(session.key)
        with path.open("w", encoding="utf-8") as f:
            for message in session.messages:
                f.write(json.dumps(message, ensure_ascii=False))
                f.write("\n")
        
    def _load(self, key: str) -> Session | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        
        messages: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                messages.append(json.loads(line))
        
        return Session(key=key, messages=messages)

    def _path_for(self, key: str) -> Path:
        return self.sessions_dir / f"{self._save_filename(key)}.jsonl"
    
    @staticmethod
    def _save_filename(key: str) -> str:
        return key.replace(":", "_")