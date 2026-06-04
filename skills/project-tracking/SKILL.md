---
name: project-tracking
description: 'Track the status of active projects and tasks. Pulls data from ClickUp, detects at-risk or blocked items, generates status reports, and sends follow-ups. Trigger keywords: status, update, progress, report, at risk, blocked, overdue, weekly review, follow up, check in, milestone, deadline.'
argument-hint: 'Specify a project name or slug, or leave blank for all active projects.'
user-invocable: true
disable-model-invocation: false
---

# Project Tracking

Keep a live view of all active projects — surface what is on track, what is at risk, and what needs action.

## When to Use
- User asks for a project status report
- Scheduled weekly review (Monday 09:00 cron trigger)
- User asks "what is overdue?" or "what needs attention?"
- After tasks are created in ClickUp — verify they were assigned correctly
- Before a deadline — proactive check

## Status Codes

| Icon | Meaning | Criteria |
|---|---|---|
| ✅ | On track | All tasks on schedule, no blockers |
| ⚠️ | At risk | ≥1 task due within 3 days with no progress, or assignee over-capacity |
| ❌ | Blocked | Task status = "blocked" in ClickUp, or dependency unmet |

## Scripts

| Script | Purpose |
|---|---|
| `skills/project-tracking/scripts/fetch_status.py` | Pull task status from ClickUp for a project/list |
| `skills/project-tracking/scripts/generate_report.py` | Format a human-readable status report |

## Steps

1. Load project list from `data/project_priorities.json` (or a specific project if named).
2. For each project, call `fetch_status.py --list-id <clickup_list_id>` to get live task data.
3. Apply status rules: flag ⚠️ if any task is due ≤ 3 days with 0% progress; flag ❌ if status = blocked.
4. Run `generate_report.py` to format the output.
5. Save report to `outputs/{slug}/tracking_{date}.json`.
6. Present report to user. Ask if they want to add follow-up comments in ClickUp.

## Follow-up Pattern

When a task is ⚠️ or ❌:
1. Draft a follow-up comment: "@{assignee} — quick check-in: is there anything blocking [task title]?"
2. Confirm with user before posting to ClickUp.
3. Record follow-up in `outputs/{slug}/tracking_{date}.json` under `follow_ups`.

## Outputs

`outputs/{slug}/tracking_{date}.json` — key fields:
```json
{
  "report_date": "2026-06-03",
  "project_name": "...",
  "overall_status": "at_risk",
  "tasks": [
    {
      "id": "clickup_task_id",
      "title": "...",
      "assignee": "...",
      "due_date": "...",
      "status": "in_progress",
      "flag": "at_risk"
    }
  ],
  "follow_ups": []
}
```

## Edge Cases
- If ClickUp API is unavailable, load last known state from `outputs/{slug}/` and note that data may be stale.
- If a project has no ClickUp list ID, skip it and prompt user to run `clickup-ops` to create the list.
