---
name: hr-structure
description: 'Query the company HR structure to find the right person for a task or role. Understands departments, teams, seniority, skills, and current capacity. Use this before delegating any task. Trigger keywords: who should handle, delegate, assign, available, capacity, team, department, org chart, skills, responsibility.'
argument-hint: 'Describe the role or skills needed, or the task to delegate.'
user-invocable: true
disable-model-invocation: false
---

# HR Structure

Know who does what in the company, who has capacity, and who is the best fit for any given task.

## When to Use
- Before assigning any task — check who is available and qualified
- User asks "who should handle X?"
- User wants to see department / team breakdown
- User updates the team (new hire, role change, departure)

## Data Source

All HR data lives in `data/hr_structure.json`. This is the single source of truth.

Structure:
```json
{
  "company": "Acme Corp",
  "departments": [
    {
      "name": "Engineering",
      "head": "Alice Chen",
      "teams": [
        {
          "name": "Backend",
          "members": [
            {
              "name": "Bob Smith",
              "role": "Senior Engineer",
              "skills": ["Python", "PostgreSQL", "AWS"],
              "capacity_hours_per_week": 40,
              "current_load_hours_per_week": 30,
              "available_hours_per_week": 10
            }
          ]
        }
      ]
    }
  ]
}
```

## Scripts

| Script | Purpose |
|---|---|
| `skills/hr-structure/scripts/query_hr.py` | Query the HR structure by role, skill, or availability |

## Delegation Rules

1. Match task **skill requirements** to member `skills` array first.
2. Then check `available_hours_per_week ≥ task_effort_hours`.
3. Prefer the most **senior** available match; if equal seniority, prefer the one with more available hours.
4. If no one has capacity, **flag over-capacity** to the user and propose options: extend deadline, hire, or re-prioritise.
5. Never assign more than 80% of a person's weekly capacity across all their tasks.

## Steps

1. Read `data/hr_structure.json`.
2. Filter by role/skill if specified.
3. Sort by available_hours descending.
4. Return top 3 candidates with explanation.
5. After confirmation, update `data/hr_structure.json` to reflect the new assignment load.

## Outputs

Inline response: ranked list of candidates with role, skills, and available hours.

## Edge Cases
- If the HR file is empty or missing, ask the user to populate `data/hr_structure.json` first.
- If a member is on leave, their `available_hours_per_week` should be 0 — check the `status` field.
