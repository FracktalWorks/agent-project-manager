---
description: "Plan a new project end-to-end: technical plan, WBS, Gantt, risk register, team assignment, ClickUp sync."
argument-hint: "project name + one-line description"
---

# Plan Project

Take a new project from idea to a ClickUp-ready plan.

## Steps

1. **Gather inputs** — project name, description/objectives, start + end dates, work streams,
   constraints. Check `data/hr_structure.json` for available team members.

2. **Surface prior context** — check `outputs/_memory/risk_log.json`, `follow_ups.json`, and
   `project_registry.json` for anything related.

3. **Generate the plan:**
   ```bash
   python .github/skills/technical-planning/scripts/generate_project_plan.py --help
   ```
   Output goes to `outputs/{slug}/project-plan/project_plan.md`.

4. **Review with the user** — adjust work streams, owners, milestones in the MD.

5. **Confirm, then sync to ClickUp** (never write without confirmation):
   ```bash
   python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py --plan outputs/{slug}/tasks.json --dry-run
   ```
   Drop `--dry-run` only after user approval.

6. **Document** — publish the plan as a ClickUp Doc via
   `.github/skills/clickup-docs/scripts/publish_plan_to_list.py --slug {slug}`.

7. **Persist** — register the project in `outputs/_memory/project_registry.json`; save risks
   to `risk_log.json` and decisions to `decision_journal.json` immediately.

Full skills: `.github/skills/technical-planning/SKILL.md`, `.github/skills/project-breakdown/SKILL.md`
