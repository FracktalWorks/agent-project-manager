---
description: "Project status report — fetch live ClickUp task status for one or all registered projects, flag at-risk and overdue work."
argument-hint: "[project-slug or 'all']"
---

# Project Status

Generate a status report for one project or all registered projects.

## Steps

1. **Fetch live status:**
   ```bash
   # All registered projects
   python .github/skills/project-tracking/scripts/fetch_status.py --all-projects

   # One project (look up the list ID in outputs/_memory/project_registry.json)
   python .github/skills/project-tracking/scripts/fetch_status.py --list-id <list_id>
   ```

2. **Format the report:**
   ```bash
   python .github/skills/project-tracking/scripts/generate_report.py --input <status.json> --project-name "..."
   ```

3. **Flag** at-risk (`due within 3 days`), overdue, and blocked tasks prominently.

4. **Cross-check memory** — mention any open risks or follow-ups for these projects from
   `outputs/_memory/risk_log.json` and `follow_ups.json`.

5. **Suggest follow-ups** — draft comments for stalled tasks (confirm before posting via
   `.github/skills/clickup-ops/scripts/add_comment.py`).

Full skill: `.github/skills/project-tracking/SKILL.md`
