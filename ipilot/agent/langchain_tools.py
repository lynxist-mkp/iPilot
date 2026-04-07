

from pathlib import Path

from langchain.tools import tool


def build_langchain_tools(workspace: Path):
    @tool
    def read_file(path: str) -> str:
        return (workspace / path).read_text(encoding="utf-8")
    
    @tool
    def list_dir(path: str = ".") -> list[str]:
        return sorted(item.name for item in (workspace / path).iterdir())
    
    @tool
    def write_file(path: str, content: str) -> str:
        full_path = workspace / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Wrote to {full_path}"
    
    @tool
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        full_path = workspace / path
        content = full_path.read_text(encoding="utf-8")
        updated = content.replace(old_text, new_text, 1)
        full_path.write_text(updated, encoding="utf-8")
        return f"Edited {full_path}"

    @tool
    def exec(command: str) -> str:
        import subprocess

        completed = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        return (completed.stdout or "") + (completed.stderr or "")
    
    return [read_file, list_dir, write_file, edit_file, exec]


