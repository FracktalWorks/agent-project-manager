---
name: hr-structure
description: 'Query the company HR structure to find the right person for a task or role. Understands departments, teams, seniority, skills (including resume-derived expertise), and live ClickUp workload. Use this before delegating any task. Trigger keywords: who should handle, delegate, assign, available, capacity, team, department, org chart, skills, responsibility, who is free, workload, underloaded, interns.'
argument-hint: 'Describe the role or skills needed, or the task to delegate.'
user-invocable: true
disable-model-invocation: false
---

# HR Structure

Know who does what in the company, who has capacity, and who is the best fit for any given task.
Skills are enriched from parsed resumes. Live workload is computed from ClickUp open tasks.

## When to Use
- Before assigning any task — check who is available and qualified
- User asks "who should handle X?" or "who is free?"
- User wants to see department / team breakdown
- User adds new resumes or hires
- User wants to know current ClickUp workload per person

## Data Sources

| File | Contents |
|---|---|
| `data/hr_structure.json` | Single source of truth: all members, roles, skills, capacity, ClickUp IDs |
| `data/resume_profiles.json` | Full parsed resume profiles (education, experience summary, domain) |
| `outputs/workload_report.json` | Latest ClickUp workload snapshot (regenerated on demand) |

### Member record schema
```json
{
  "name": "Pavan Siddapuram",
  "email": "pavan.siddapuram@fracktal.in",
  "role": "Software Engineer",
  "skills": ["Python", "React", "FastAPI", "..."],
  "status": "active",
  "capacity_hours_per_week": 40,
  "current_load_hours_per_week": 12,
  "available_hours_per_week": 28,
  "clickup_user_id": 100862267,
  "resume_profile": {
    "source_file": "data/Interns Resume/PavanS_Resume.pdf",
    "education": ["B.Tech Computer Science, ..."],
    "experience_summary": "...",
    "years_experience": 2,
    "domain": "Software"
  }
}
```

## ⚠️ Getting ClickUp User IDs for Task Assignment

When assigning tasks in ClickUp, you need the integer `clickup_user_id`. Always read it from `data/hr_structure.json` — do NOT call the ClickUp API to look up members.

```python
import json
hr = json.loads(open("data/hr_structure.json").read())
# Walk departments → teams → members to find clickup_user_id
# Example known IDs:
# Vijay Raghav Varada: 236494607
# Ayush Sarkar:        100842373
# Suryansh Lal:        100842374
# Sridhar:             101085101
```

When using these IDs in ClickUp API calls, pass them as **flat integers** in a list — see `clickup-ops` SKILL for the correct format.

## Scripts

| Script | Purpose |
|---|---|
| `.github/skills/hr-structure/scripts/query_hr.py` | Query HR by role, skill, or availability |
| `scripts/ingest_resumes.py` | Parse PDF resumes → update skills in hr_structure.json |
| `scripts/workload_analysis.py` | Fetch ClickUp tasks → compute workload → identify free capacity |

## Workflow: Ingest New Resumes

Run whenever new resumes are added to `data/Resumes/Full-Time/` or `data/Resumes/Interns/`:

```bash
# With LLM (best quality — requires OPENAI_API_KEY in .env)
python scripts/ingest_resumes.py

# Heuristic-only (no API key needed)
python scripts/ingest_resumes.py --no-llm

# Preview without writing
python scripts/ingest_resumes.py --dry-run --no-llm
```

What it does:
1. Extracts text from each PDF (PyMuPDF).
2. Parses skills, education, experience via GPT-4o-mini (or keyword heuristics).
3. Fuzzy-matches each resume to an existing HR record by name.
4. Merges skills into `hr_structure.json`; adds unmatched people as Interns.
5. Writes full profiles to `data/resume_profiles.json`.

## Workflow: Live Workload Analysis

Run to get current ClickUp task load per person:

```bash
# Show workload table + underloaded people
python scripts/workload_analysis.py

# Write computed load back to hr_structure.json
python scripts/workload_analysis.py --update-hr

# Find best assignee for a task
python scripts/workload_analysis.py --suggest python react --effort 6

# Filter to one person
python scripts/workload_analysis.py --person "Pavan"
```

What it does:
1. Fetches all open tasks from every Space/Folder/List in the ClickUp workspace.
2. Estimates effort per task by priority (Urgent=8h, High=6h, Normal=4h, Low=2h).
3. Aggregates load per ClickUp user ID.
4. Joins with `hr_structure.json` to get role, skills, and capacity.
5. Outputs `outputs/workload_report.json` + a summary table to stdout.
6. With `--update-hr`: writes `current_load_hours_per_week` back to hr_structure.json.

## Workflow: Suggest Assignee for a Task

After running workload analysis (or reading `outputs/workload_report.json`):

1. Extract required skills from the task description.
2. Identify minimum effort hours.
3. Call `workload_analysis.py --suggest <skills> --effort <hours>` **OR** reason over the report directly.
4. Rank candidates: skill match score first, then available hours.
5. Present top 3 to the user with their current tasks listed.

## Delegation Rules

1. Match task **skill requirements** to member `skills` array first (resume-enriched).
2. Then check `available_hours_per_week ≥ task_effort_hours`.
3. Prefer the most **senior** available match; if equal seniority, prefer more available hours.
4. If no one has capacity, **flag over-capacity** to the user and propose: extend deadline, use an intern, or re-prioritise.
5. Never assign more than 80% of a person's weekly capacity across all tasks.
6. For interns: always confirm with the user before assigning non-trivial tasks.

## Outputs

- Inline response: ranked list of candidates with role, skills, available hours, and current task list.
- `outputs/workload_report.json`: full machine-readable report.

## Edge Cases
- If HR file is empty, ask user to populate `data/hr_structure.json` first.
- If member is on leave, `available_hours_per_week` should be 0 — check `status` field.
- If a resume person has no ClickUp ID, they won't appear in workload; note this to the user.
- If `outputs/workload_report.json` is stale (> 24h), recommend re-running `workload_analysis.py`.
