# Data Directory — agent-project-manager

This directory contains reference data used by the agent.

## Files

| File | Purpose | Updated by |
|---|---|---|
| `hr_structure.json` | Company org chart — departments, teams, people, roles, capacity | User or `hr-structure` skill |
| `project_priorities.json` | Active projects with priority scores, status, and ClickUp IDs | `project-planning` and `clickup-ops` skills |
| `resume_profiles.json` | Inferred skills extracted from all resumes — keyed by person name | `ingest_resumes` script in `.tmp/scripts/` |
| `Resumes/Full-Time/` | PDF resumes for full-time employees — parsed by `ingest_resumes` | User |
| `Resumes/Interns/` | PDF resumes for interns — parsed by `ingest_resumes` | User |

## hr_structure.json

Schema per member:
```json
{
  "name": "Alice Chen",
  "role": "Engineering Manager",
  "skills": ["Python", "AWS"],
  "status": "active",                    // active | on_leave | departed
  "capacity_hours_per_week": 40,
  "current_load_hours_per_week": 32,
  "available_hours_per_week": 8,         // keep this updated after each assignment
  "clickup_user_id": null                // fill in after first ClickUp sync
}
```

## project_priorities.json

Schema per project:
```json
{
  "name": "Website Redesign",
  "slug": "website-redesign",
  "status": "active",                    // active | completed | on_hold
  "priority_score": 75,
  "deadline": "2026-09-30",
  "clickup_space_id": "...",
  "clickup_folder_id": "...",
  "clickup_list_ids": {
    "Phase 1 — Discovery": "...",
    "Phase 2 — Execution": "..."
  }
}
```

## Updating Data Files

- Edit `hr_structure.json` directly when team changes occur (new hire, departure, leave).
- `project_priorities.json` is auto-updated by `create_project.py` after ClickUp sync.
- Never store credentials or personal contact details in these files.
