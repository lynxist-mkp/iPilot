from __future__ import annotations

from pathlib import Path

from ipilot.agent.runtime_context import AgentRuntimeContext

BOOTSTRAP_FILES = ("AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md")


def _load_bootstrap_files(workspace: Path) -> str:
    parts: list[str] = []
    for name in BOOTSTRAP_FILES:
        path = workspace / name
        if path.exists():
            parts.append(f"## {name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def _load_memory_context(workspace: Path) -> str:
    memory_file = workspace / "memory" / "MEMORY.md"
    if not memory_file.exists():
        return ""
    return memory_file.read_text(encoding="utf-8").strip()


def _load_skills_summary(workspace: Path) -> str:
    skills_dir = workspace / "skills"
    if not skills_dir.exists():
        return ""

    lines: list[str] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            lines.append(f"- {skill_dir.name}")
    return "\n".join(lines)


def build_system_prompt(context: AgentRuntimeContext) -> str:
    parts = [
        "You are iPilot.",
        f"Workspace: {context.workspace_path.resolve()}",
        f"Provider: {context.provider}",
        f"Model: {context.model}",
    ]
    if context.channel:
        parts.append(f"Channel: {context.channel}")
    if context.chat_id:
        parts.append(f"Chat ID: {context.chat_id}")

    bootstrap = _load_bootstrap_files(context.workspace_path)
    if bootstrap:
        parts.append(bootstrap)

    memory = _load_memory_context(context.workspace_path)
    if memory:
        parts.append(f"## Memory\n\n{memory}")

    skills_summary = _load_skills_summary(context.workspace_path)
    if skills_summary:
        parts.append(f"## Skills\n\n{skills_summary}")

    return "\n\n---\n\n".join(parts)


try:
    from langchain.agents.middleware import dynamic_prompt
except Exception:  # pragma: no cover - fallback for environments without langchain middleware
    build_system_prompt_middleware = None
else:

    @dynamic_prompt
    def build_system_prompt_middleware(request) -> str:
        return build_system_prompt(request.runtime.context)
