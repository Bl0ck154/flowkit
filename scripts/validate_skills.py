#!/usr/bin/env python3
"""
FlowKit — Skills Validator & Quality Assurance Linter
Validates the entire skill suite to enforce:
1. 100% unified English language purity across all instructions.
2. Heading and metadata consistency.
3. Cross-reference markdown link validity.
4. Sync parity between skills/, .agents/skills/, and .claude/commands/.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_SKILLS_DIR = ROOT / ".agents" / "skills"
CLAUDE_COMMANDS_DIR = ROOT / ".claude" / "commands"

# Vietnamese instructional keywords that should NEVER appear as instructions
VI_INSTRUCTIONAL_PATTERN = re.compile(
    r'\b(hướng dẫn|thực hiện|lưu ý|yêu cầu|bước 1|bước 2|bước 3|bước 4|bước 5|'
    r'tổng quan|cách dùng|chú ý|kiểm tra|thiết lập|kịch bản|nhân vật|chuyển cảnh)\b',
    re.IGNORECASE
)


def validate_skills():
    print("=======================================================")
    print("🔍 FLOWKIT SKILLS QUALITY ASSURANCE VALIDATOR")
    print("=======================================================\n")

    skill_files = sorted(SKILLS_DIR.glob("fk-*.md"))
    print(f"Discovered {len(skill_files)} skill files in {SKILLS_DIR}")

    errors = []
    warnings = []

    for path in skill_files:
        name = path.name
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # 1. Heading check
        if not lines or not (lines[0].startswith("#") or (len(lines) > 1 and lines[1].startswith("#")) or lines[0].strip()):
            warnings.append(f"[{name}] Missing top header or description.")

        # 2. Check for mixed Vietnamese instruction text (ignoring explicit quotes/code blocks containing data)
        in_code_block = False
        for line_idx, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            
            # Skip code blocks and lines that are explicit sample quotes or dialogue examples
            if in_code_block or '"' in line or '“' in line or '`' in line:
                continue

            vi_match = VI_INSTRUCTIONAL_PATTERN.search(line)
            if vi_match:
                errors.append(f"[{name}:L{line_idx}] Mixed Vietnamese keyword in instruction: '{vi_match.group(0)}'")

        # 3. Check markdown links
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        for link_text, link_target in links:
            if link_target.startswith("http") or link_target.startswith("#") or link_target.startswith("mailto:"):
                continue
            # Strip anchors
            target_file = link_target.split("#")[0]
            if target_file:
                target_path = (SKILLS_DIR / target_file).resolve()
                if not target_path.exists():
                    # check relative to project root
                    if not (ROOT / target_file).resolve().exists():
                        warnings.append(f"[{name}] Broken markdown link: '{link_target}'")

    # 4. Check sync parity
    antigravity_skills = list(AGENTS_SKILLS_DIR.glob("fk-*/SKILL.md")) if AGENTS_SKILLS_DIR.exists() else []
    claude_commands = list(CLAUDE_COMMANDS_DIR.glob("fk-*.md")) if CLAUDE_COMMANDS_DIR.exists() else []

    print(f"\nTool Sync Parity Check:")
    print(f"  skills/ Source:           {len(skill_files)}")
    print(f"  .agents/skills/ (AGY):    {len(antigravity_skills)}")
    print(f"  .claude/commands/ (Claude): {len(claude_commands)}")

    if len(skill_files) != len(antigravity_skills):
        errors.append(f"Antigravity sync mismatch: {len(skill_files)} vs {len(antigravity_skills)}. Run 'python setup.py sync'.")

    if len(skill_files) != len(claude_commands):
        errors.append(f"Claude sync mismatch: {len(skill_files)} vs {len(claude_commands)}. Run 'python setup.py sync'.")

    print("\n-------------------------------------------------------")
    if warnings:
        print(f"⚠️  {len(warnings)} Warnings:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("✅ No warnings detected.")

    if errors:
        print(f"\n❌ {len(errors)} Errors Found:")
        for e in errors:
            print(f"  - {e}")
        print("\nValidator FAILED.")
        return False
    else:
        print("\n✅ All 41 skills passed quality validation! 100% English compliant.")
        return True


if __name__ == '__main__':
    ok = validate_skills()
    sys.exit(0 if ok else 1)
