#!/usr/bin/env python3
"""
Sync skills from skills/fk-*.md to:
1. .agents/skills/fk-<name>/SKILL.md (for Antigravity IDE)
2. .claude/commands/fk-<name>.md (for Claude Code)
3. AGENTS.md (for Codex CLI)
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_SKILLS_DIR = ROOT / ".agents" / "skills"

def discover_skills():
    skills = []
    for path in sorted(SKILLS_DIR.glob("fk-*.md")):
        name = path.stem[len("fk-"):]
        content = path.read_text(encoding="utf-8")
        
        # Check description
        desc = ""
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("---"):
                desc = re.sub(r'^[#\s\-*]+', '', line).strip()
                break
        if not desc:
            desc = f"{name} workflow skill"
            
        skills.append({"name": name, "description": desc, "path": path, "content": content})
    return skills

def sync_antigravity(skills):
    AGENTS_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for s in skills:
        name = s["name"]
        skill_id = f"fk-{name}"
        desc = s["description"].replace("'", "''").replace("\n", " ").strip()
        content = s["content"]
        
        # Strip existing frontmatter if any
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].lstrip()
            else:
                body = content
        else:
            body = content

        dest_dir = AGENTS_SKILLS_DIR / skill_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "SKILL.md"

        skill_md = (
            f"---\n"
            f"name: {skill_id}\n"
            f"description: '{desc}'\n"
            f"---\n\n"
            f"{body}\n"
        )
        dest_file.write_text(skill_md, encoding="utf-8")
        count += 1
        print(f"  [OK] .agents/skills/{skill_id}/SKILL.md")
    print(f"Synchronized {count} skills to Antigravity (.agents/skills/)")
    return count

if __name__ == "__main__":
    skills = discover_skills()
    print(f"Discovered {len(skills)} skills in skills/")
    sync_antigravity(skills)
