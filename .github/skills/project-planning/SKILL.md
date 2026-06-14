---
name: project-planning
description: 'Plan new company projects: decompose goals into phases and tasks, score priority using impact/effort/urgency, set milestones and deadlines, identify dependencies, and produce a structured plan ready for ClickUp import. Trigger keywords: new project, plan project, roadmap, milestones, priority, sprint, kickoff, project brief.'
argument-hint: 'Describe the project goal and any known constraints (deadline, team, budget).'
user-invocable: true
disable-model-invocation: false
---

# Project Planning

Break down any company initiative into a structured, prioritised plan with tasks, milestones, owners, and deadlines — ready to push into ClickUp.

## When to Use
- User asks to plan a new project or initiative
- User provides a goal and wants a breakdown into tasks/milestones
- User asks "what should we work on next?" (priority scoring)
- User wants a sprint plan or quarterly roadmap

> **For deep technical decomposition** (WBS, PERT, Gantt, ADRs, Risk Register), invoke the `project-breakdown` skill after priority scoring here is complete. This skill handles *what to build*; `project-breakdown` handles *how to build it*.

## Priority Matrix

Score each project on three axes (1–5 each):

| Axis | Question |
|---|---|
| **Impact** | How much does this move company goals forward? |
| **Urgency** | How time-sensitive is this? (deadline, opportunity window) |
| **Effort** | How hard is this? (inverted: 5 = very easy, 1 = very hard) |

**Priority Score = Impact × Urgency × Effort**  
Rank projects by score descending. Surface score ≥ 50 as **high priority**.

## Scripts

| Script | Purpose |
|---|---|
| `.github/skills/project-planning/scripts/plan_project.py` | Generates structured project plan JSON |

## Steps

1. Collect: project name, goal, hard deadline (if any), known constraints.
2. Run priority scoring against active projects in `data/project_priorities.json`.
3. Decompose into phases → tasks → subtasks.
4. For each task: assign estimated effort (hours), look up owner by name in `data/hr_structure.json` (use `clickup_user_id` field), set due date.
5. Save plan to `outputs/{project-slug}/step_1_project_plan.json`.
6. Present plan to user for confirmation before proceeding to ClickUp.

> **Before passing any task to `clickup-ops`:** every task MUST have a named assignee with their integer `clickup_user_id`, a due date in `YYYY-MM-DD` format, and a verb+object title. Incomplete tasks will be rejected.

## Outputs

`outputs/{slug}/step_1_project_plan.json` — key fields:
```json
{
  "project_name": "...",
  "priority_score": 75,
  "phases": [
    {
      "name": "Phase 1 — Discovery",
      "due_date": "2026-07-01",
      "tasks": [
        {
          "title": "...",
          "owner_role": "...",
          "effort_hours": 8,
          "due_date": "2026-06-15",
          "dependencies": []
        }
      ]
    }
  ]
}
```

## Delegation Best Practices

When assigning any task, always provide:

1. **Who** — named person (from `hr_structure.json`), not just a role title
2. **What** — specific deliverable, not a vague label ("Machine cross flat" not "Machining")
3. **Why** — brief context so the person understands the purpose
4. **How** (if non-obvious) — key steps or method, especially for tasks that could be done multiple ways
5. **Prerequisites** — what must be ready before they can start
6. **Done when** — a clear, verifiable acceptance criterion so there's no ambiguity about completion

**Before creating tasks, ask clarifying questions for anything where the acceptance criteria or method is unclear.** It is better to ask one question upfront than to create a task that gets misinterpreted.

**Never assign a task to someone without checking their current load** (`hr_structure.json` capacity field). If they are at capacity, flag it and propose an alternative or a due date shift.

**For hardware/manufacturing tasks**, always clarify:
- In-house or external vendor?
- Specs/drawings confirmed or still TBD?
- Any dependency on a part arriving first?

**For software tasks**, always clarify:
- What is the test/verification method?
- Which hardware must be available before this can start?

## Planning Pipeline — Full Flow

When a user brings a new project, follow this pipeline in order:

1. **Score priority** — `project-planning` (this skill): Impact × Urgency × Effort.
2. **Break it down** — `project-breakdown` skill: WBS, PERT, Gantt, ADRs, Risk Register.
3. **Staff it** — `hr-structure` skill: match tasks to named people with capacity checks.
4. **Push to ClickUp** — `clickup-ops` skill: create tasks with verb+object titles, assignees, dates, descriptions.
5. **Document it** — `clickup-docs` skill: create/update the Folder Doc with a PRD page for the project.
6. **Link external resources** — `external-integrations` skill: GitHub repo, Google Drive, Notion pages.
7. **Remember it** — `project-memory` skill: save risks, decisions, open questions to the memory store.

Never skip Step 2 (breakdown) for projects with >3 unknowns or >2 weeks duration.

## Inversion Check

Before endorsing any project plan, run the inversion check:
> "What would make this fail? What are we not seeing? Are we optimising for the right variable?"

Surface at least three failure modes before declaring a plan ready. This is not pessimism — it is the fastest route to a plan that survives contact with reality.

## Sprint Planning

When the user asks for a sprint or two-week plan:
1. Pull active tasks from ClickUp (status = `to do` or `in process`) via `clickup-ops`.
2. Filter by team member and remaining capacity from `hr_structure.json`.
3. Score tasks by priority (RICE: Reach × Impact × Confidence / Effort).
4. Propose the sprint as a table: task, owner, days, status.
5. Confirm with user before moving tasks to `in process` in ClickUp.

## Edge Cases
- If no deadline is provided, propose one based on PERT effort estimates from `project-breakdown`.
- If priority score conflicts with user's stated urgency, flag it and ask for clarification.
- If a similar project already exists in `data/project_priorities.json`, suggest merging or linking.
- If the user describes a project with >5 open unknowns, do not proceed to ClickUp. Ask the clarifying questions first.
