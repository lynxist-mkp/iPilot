from pathlib import Path
from typing import Any

from ipilot.agent.tools.base import Tool

class ReadFileTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read a UTF-8 encoded text file from the workspace and return its contents as a string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        path = self.workspace / kwargs["path"]
        return path.read_text(encoding="utf-8")

class ListDirTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace
    
    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory in the workspace. Returns a list of file and subdirectory names."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
        }
    
    async def execute(self, **kwargs: Any) -> list[str]:
        path = self.workspace / kwargs.get("path", ".")
        return sorted(item.name for item in path.iterdir())

class WriteFileTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write a string to a UTF-8 encoded text file in the workspace. Overwrites the file if it already exists."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        }
    
    async def execute(self, **kwargs: Any) -> None:
        path = self.workspace / kwargs["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(kwargs["content"], encoding="utf-8")
        return f"Wrote to {path}"

class EditFileTool(Tool):
    def __init__(self, workspace: Path):
        self.workspace = workspace
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a UTF-8 encoded text file in the workspace by applying a simple find-and-replace operation. Returns the new contents of the file as a string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        path = self.workspace / kwargs["path"]
        content = path.read_text(encoding="utf-8")
        new_content = content.replace(kwargs["old_text"], kwargs["new_text"], 1)
        path.write_text(new_content, encoding="utf-8")
        return f"Edited {path}"
