---
name: clickup-ops
description: 'Create and manage ClickUp workspaces, spaces, folders, lists, tasks, assignees, deadlines, and follow-up comments. Use this after planning and HR delegation are complete to push everything into ClickUp. Trigger keywords: create task, assign, deadline, clickup, list, space, folder, update task, comment, follow up, add to clickup, sync clickup.'
argument-hint: 'Describe what you want to create or update in ClickUp (project, task, assignee, deadline).'
user-invocable: true
disable-model-invocation: false
---

# ClickUp Ops

Push project plans and task assignments into ClickUp. Manage the full hierarchy: Space → Folder → List → Task → Subtask.

## When to Use
- After a project plan is confirmed — create Space/List/Tasks in ClickUp
- When assigning tasks to people
- When updating deadlines, status, or adding follow-up comments
- When fetching live task data for status reports

## ClickUp Hierarchy

```
Workspace (Team)
└── Space           ← one per major department or project area
    └── Folder      ← one per project (optional)
        └── List    ← one per phase or sprint
            └── Task
                └── Subtask
```

## Scripts

| Script | Purpose |
|---|---|
| `skills/clickup-ops/scripts/clickup_client.py` | Low-level ClickUp REST API wrapper |
| `skills/clickup-ops/scripts/create_project.py` | Create a full Space + Folder + Lists from a plan JSON |
| `skills/clickup-ops/scripts/sync_tasks.py` | Create or update tasks with assignees and deadlines |
| `skills/clickup-ops/scripts/add_comment.py` | Post a follow-up comment on a task |

## Steps — Create a New Project in ClickUp

1. Confirm the project plan JSON from `outputs/{slug}/step_1_project_plan.json`.
2. Show the user the full structure to be created (space, lists, tasks, owners) — **wait for explicit approval**.
3. Run `create_project.py --plan outputs/{slug}/step_1_project_plan.json`.
4. Run `sync_tasks.py` to create tasks with assignees and due dates.
5. Save ClickUp IDs back to `data/project_priorities.json` (space_id, list_ids, task_ids).

## Steps — Update Existing Tasks

1. `sync_tasks.py --task-id <id> --status "in progress" --assignee <member_id>`
2. `add_comment.py --task-id <id> --comment "Follow-up: ..."` (confirm with user first)

## Environment Variables Required

| Variable | Purpose |
|---|---|
| `CLICKUP_API_TOKEN` | Personal API token from ClickUp settings |
| `CLICKUP_TEAM_ID` | Workspace/team ID (visible in ClickUp URL) |

## Outputs

After creation, save IDs to `data/project_priorities.json`:
```json
{
  "clickup_space_id": "...",
  "clickup_folder_id": "...",
  "clickup_list_ids": { "Phase 1": "...", "Phase 2": "..." }
}
```

## Task Hierarchy Decision Guide

Before creating any task, decide: **main task or subtask?**

| Signal | Main Task | Subtask |
|---|---|---|
| Deliverable scope | Standalone, independently shippable | A step that must complete for the parent to close |
| Assignee | Different from sibling tasks | Same person or same sub-team |
| Duration | Multi-day | < 1 day |
| Blocking risk | Could independently block the project | Only blocks the parent task |
| Board visibility | Should appear on the board for tracking | Would clutter the board as standalone |

**Rule of thumb:** If you'd track its completion separately from the parent and it could be independently delayed → main task. If it's a step in a recipe → subtask.

**When a group of tasks shares a parent deliverable, always prefer subtasks.** This keeps the board clean and groups related work under one parent that shows aggregate progress.

## Task Quality Standard (Required for Every Task)

Every task created in ClickUp MUST have:
- **Title**: `[Verb] + [Object]` — actionable verb first, concise, no filler words.
  - ✅ "Order Motor Coupler", "Assemble V2 Extruder", "Test Pellet Extrusion"
  - ❌ "Motor Coupler", "Final Assembly", "Pellet Extrusion Test", "V2 Extruder — Full Assembly"
  - Use the most specific verb: "Machine" not "Make", "Measure" not "Check", "Send" not "Handle"
- **Assignee**: At least one named person — never leave unassigned
- **Due date**: A specific date — never leave blank
- **Description** — content depends on whether the task has subtasks (see below)

## Parent Task vs Subtask Content Rules

**When a task breaks down into 2+ distinct steps or deliverables, always create a parent task + subtasks. Never flatten everything into a single task description.**

### Parent task description (lean — 3–5 lines max)
```
[What this task delivers overall — 1-2 sentences]

Prerequisites: [what must be ready before this can start, or "none"]
Done when: [the rollup acceptance criterion — i.e. all subtasks closed]
```
Do NOT put step-by-step checklists in the parent. The subtasks ARE the checklist.

### Subtask description (detailed)
```
[What this specific step delivers — 1-2 sentences]

Steps / Checklist:
- [ ] Step 1
- [ ] Step 2

Prerequisites: [what must be done first, or "none"]
Done when: [clear, verifiable acceptance criterion for this step only]
```

### Decision rule — when to split into subtasks
If the task has **2 or more discrete deliverables** OR **steps that can be done by different people or at different times**, create subtasks. Examples:

| Scenario | Do this |
|----------|---------|
| "Create GitHub repo for manufacturing drawings" → has 5 distinct setup steps | Parent task + 5 subtasks |
| "Order motor coupler" → single atomic action | Plain task, no subtasks |
| "Write and deliver user manual" → writing + review + handover are separate steps | Parent + 3 subtasks |
| "Send email to vendor" → one action | Plain task, no subtasks |

## Status Semantics

Use ClickUp statuses with explicit meaning:
- **backlog** = expected work that is not yet planned in detail
- **to do** = planned work with an owner and due date, ready to be executed
- **in process** = work that has started
- **review** = work completed by the owner and waiting for verification/review
- **closed** = done

**Rule:** Once a task is planned, assigned, and dated, move it out of `backlog` and into `to do` or `in process`.

## Edge Cases
- If the Space already exists, do NOT create a duplicate — update the existing one.
- If an assignee member ID is unknown, run `clickup_client.py --list-members` to find them.
- Never delete tasks automatically — always ask for confirmation.
- Rate limit: ClickUp API allows 100 req/min. If you hit 429, wait 60 s and retry once.
- Archiving: `PUT /task/{id}` with `{"archived": true}` hides a task from all views without deleting it. Reversible. Use for old/obsolete tasks instead of deletion.
