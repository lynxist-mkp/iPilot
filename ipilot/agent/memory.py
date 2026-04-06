from pathlib import Path

class MemoryStore:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_file = self.workspace / "memory" / "MEMORY.md"
    
    def get_memory_context(self) -> str:
        if not self.memory_file.exists():
            return ""
        return self.memory_file.read_text(encoding="utf-8").strip()