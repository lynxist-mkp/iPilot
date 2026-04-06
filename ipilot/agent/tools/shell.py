import asyncio
from pathlib import Path
from typing import Any

from ipilot.agent.tools.base import Tool


class ExecTool(Tool):
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command in the working directory and return its output as a string."
    
    @property
    def parameters(self) -> dict[str, str]:
        return {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        process = await asyncio.create_subprocess_shell(
            kwargs["command"],
            cwd=self.working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, stderr = await process.communicate()
        return stdout.decode("utf-8", errors="replace")
