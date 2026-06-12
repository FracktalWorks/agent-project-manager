---
applyTo: ".github/skills/**/SKILL.md"
description: "Standards for writing and updating SKILL.md files across all skills."
---

# SKILL.md Authoring Standards

## Frontmatter (Required)

Every SKILL.md MUST start with YAML frontmatter:
- `name`: lowercase+hyphens, max 64 chars, must match folder name
- `description`: what the skill does AND when to use it, max 1024 chars, include trigger keywords

Optional fields: `argument-hint`, `user-invocable` (false = hide from slash menu),
`disable-model-invocation` (true = prevent auto-load)

## Body Structure

1. H1 title matching folder name
2. One-line summary of what this skill accomplishes
3. When to Use section with 3-5 trigger conditions
4. Scripts table with purpose and when to use each
5. How to Run section with copy-pasteable bash examples (always show `--help` first)
6. Outputs section listing files created and their key fields
7. Edge Cases section with failure modes and recovery steps

## Rules When Editing Skills

- Never remove the YAML frontmatter
- Keep `name` matching the parent folder
- Update `description` if the skill scope changes
- New edge cases use: `### [Title] (Added YYYY-MM-DD)` with Trigger, Fix, Source
- Reference skill scripts with full repo-relative paths: `.github/skills/<name>/scripts/script.py`
- Reference shared scripts as `scripts/script_name.py` (repo root)
- Keep command examples copy-pasteable from repo root
- When a pattern repeats 3+ times, promote it from edge case to main instructions
