from pathlib import Path


class SkillsLoader:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.skills_dir = self.workspace / "skills"
    
    def build_skills_summary(self) -> str:
        if not self.skills_dir.exists():
            return ""
        
        lines: list[str] = []
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                lines.append(f"- {skill_dir.name}")
        return "\n".join(lines)
