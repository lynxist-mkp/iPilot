from pathlib import Path
from typing import Any

from ipilot.agent.memory import MemoryStore
from ipilot.agent.skills import SkillsLoader


class ContextBuilder:
    BOOTSTRAP_FILE = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def _load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for name in self.BOOTSTRAP_FILE:
            path = self.workspace / name
            if path.exists():
                parts.append(f"## {name}\n\n{path.read_text(encoding='utf-8').strip()}")
        return "\n\n".join(parts)
    
    def build_system_prompt(self) -> str:
        parts = [
            "You are iPilot.",
            f"Workspace: {self.workspace.resolve()}",
        ]

        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"## Memory\n\n{memory}")
        
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"## Skills\n\n{skills_summary}")
        
        return "\n\n---\n\n".join(parts)
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        runtime_lines = []
        if channel:
            runtime_lines.append(f"Channel: {channel}")
        if chat_id:
            runtime_lines.append(f"Chat ID: {chat_id}")
        
        user_content = current_message
        if runtime_lines:
            runtime_block = "[Runtime Context]\n" + "\n".join(runtime_lines)
            user_content = f"{runtime_block}\n\n{current_message}"
        
        return [
            {"role": "system", "content": self.build_system_prompt()},
            *history,
            {"role": "user", "content": user_content},
        ]
