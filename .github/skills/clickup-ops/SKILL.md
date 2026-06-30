---
name: clickup-ops
description: 'Create and manage ClickUp workspaces, spaces, folders, lists, tasks, assignees, deadlines, and follow-up comments. Use this after planning and HR delegation are complete to push everything into ClickUp. Trigger keywords: create task, assign, deadline, clickup, list, space, folder, update task, comment, follow up, add to clickup, sync clickup.'
argument-hint: 'Describe what you want to create or update in ClickUp (project, task, assignee, deadline).'
user-invocable: true
disable-model-invocation: false
---

# ClickUp Ops

Push project plans and task assignments into ClickUp. Manage the full hierarchy: Space → Folder → List → Task → Subtask.

---

## ⚡ Quick Command Reference (copy-paste these)

### Discover list IDs (do this before creating tasks in an unknown list)
```bash
# Dump all spaces/folders/lists as JSON
python .github/skills/clickup-ops/scripts/list_workspace.py

# Filter by name to find a specific list
python .github/skills/clickup-ops/scripts/list_workspace.py --filter "quality control"
python .github/skills/clickup-ops/scripts/list_workspace.py --filter "mds"

# Print only the list ID (for scripting)
python .github/skills/clickup-ops/scripts/list_workspace.py --filter "quality control" --id-only

# Cache the workspace map so agents can look up IDs without API calls
python .github/skills/clickup-ops/scripts/list_workspace.py --save-cache
python .github/skills/clickup-ops/scripts/list_workspace.py --from-cache --filter "julia"
```

### Create a task (canonical pattern)
```python
import httpx, os, time
from datetime import datetime
from load_env import load_env; load_env()
TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}

def ms(yyyy, mm, dd):
    return int(datetime(yyyy, mm, dd, 18, 0).timestamp() * 1000)

# Step 1: get exact status string for the target list
r = httpx.get("https://api.clickup.com/api/v2/list/{LIST_ID}", headers=H)
valid_statuses = [s["status"] for s in r.json().get("statuses", [])]
# e.g. ['backlog', 'to do', 'in process', 'review', 'done', 'Closed']

# Step 2: create task (assignees = flat list of int IDs)
r = httpx.post("https://api.clickup.com/api/v2/list/{LIST_ID}/task", headers=H, json={
    "name": "Task title here",
    "description": "What done looks like",
    "assignees": [100858676],          # Kiran; must be flat int list
    "due_date": ms(2026, 6, 10),
    "due_date_time": False,
    "status": "to do",                 # must match exact string from list
    "priority": 2,                     # 1=urgent 2=high 3=normal 4=low
    "notify_all": False,
})
task = r.json()
print(task["id"], task.get("url"))
```

### Known list IDs (registered projects)
| Project | List ID |
|---------|----------|
| Penrose Pellet Extruder | `901611050642` |
| Julia Series | `901611246751` |
| MDS (Material Drying System) | `901612525485` |
| Quality Control | `901613553036` |
| Manufacturing | `901615292726` |

### Known ClickUp user IDs
| Name | ID |
|------|----|
| Vijay Raghav Varada | `236494607` |
| Ayush Sarkar | `100842373` |
| Suryansh Lal | `100842374` |
| Sridhar | `101085101` |
| Anirudh Mohta | `101084653` |
| Kiran Kumar S | `100858676` |

---

## When to Use
- After a project plan is confirmed — create Space/List/Tasks in ClickUp
- When assigning tasks to people
- When updating deadlines, status, or adding follow-up comments
- When fetching live task data for status reports

---

## ⚠️ API Rules — Read Before Writing Any Code

These rules are non-negotiable. Violating them produces silent failures (200 OK with no effect).

### Rule 1 — Assignees can ONLY be set at creation time (POST), never via PUT

`PUT /api/v2/task/{id}` **silently ignores the `assignees` field.** It returns 200 OK but does not assign anyone.

✅ **The only way to set assignees is via `POST /api/v2/list/{list_id}/task`** at task creation.

If you need to change assignees on an existing task: **delete it and recreate it.** Do not attempt PUT.

### Rule 2 — Assignees must be a flat list of integer IDs

```python
# ✅ CORRECT — flat list of integer user IDs
"assignees": [100842373, 100842374]

# ❌ WRONG — list of objects (returns 200 but assigns no one)
"assignees": [{"id": 100842373}]
```

### Rule 3 — Always include `"Content-Type": "application/json"` in headers

```python
# ✅ CORRECT
H = {"Authorization": TOKEN, "Content-Type": "application/json"}

# ❌ WRONG — may cause silent field failures
H = {"Authorization": TOKEN}
```

### Rule 4 — Due dates must be Unix milliseconds at a fixed time, not midnight

```python
# ✅ CORRECT — use 18:00 local (avoids off-by-one on date display)
def ms(yyyy, mm, dd):
    return int(datetime(yyyy, mm, dd, 18, 0).timestamp() * 1000)

# ❌ WRONG — midnight UTC causes the date to appear as the previous day in IST
int(datetime(yyyy, mm, dd).timestamp() * 1000)
```

Always set `"due_date_time": False` alongside the due_date field.

### Rule 5 — Check list statuses before creating tasks

Status names vary per list (e.g., some lists use `"todo"`, others `"to do"`). Always fetch the list first:

```python
r = httpx.get(f"https://api.clickup.com/api/v2/list/{LIST_ID}", headers=H)
statuses = [s["status"] for s in r.json().get("statuses", [])]
```

Use the exact string from this list. Sending an invalid status returns `{"err":"Status not found","ECODE":"CRTSK_001"}`.

### Rule 6 — Subtasks use the same POST endpoint as tasks, with a `parent` field

```python
# POST /api/v2/list/{list_id}/task — same endpoint, add "parent"
payload = {
    "name": "Subtask name",
    "parent": "<parent_task_id>",
    "assignees": [user_id],          # flat int list
    "due_date": ms(2026, 6, 9),
    "due_date_time": False,
    "status": "todo",
    "notify_all": False,
}
```

Do NOT use `POST /api/v2/task/{parent_id}/subtask` — it returns 404.

### Rule 7 — Rate limiting: 429 → sleep 62 seconds, then retry once

```python
if r.status_code == 429:
    time.sleep(62)
    r = httpx.post(...)  # retry once only
```

### Canonical task creation template

```python
import httpx, os, time
from datetime import datetime
from load_env import load_env; load_env()
TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}

def ms(yyyy, mm, dd):
    return int(datetime(yyyy, mm, dd, 18, 0).timestamp() * 1000)

def create_task(list_id, name, desc, due, assignees, status="todo", priority=2):
    payload = {
        "name": name,
        "description": desc,
        "due_date": due,
        "due_date_time": False,
        "assignees": assignees,      # flat list of int IDs
        "priority": priority,
        "notify_all": False,
        "status": status,            # must match exact status name from the list
    }
    r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                   headers=H, json=payload, timeout=20)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                       headers=H, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def create_subtask(list_id, parent_id, name, assignees, status="todo", priority=2):
    payload = {
        "name": name,
        "parent": parent_id,
        "assignees": assignees,      # flat list of int IDs
        "due_date_time": False,
        "notify_all": False,
        "status": status,
        "priority": priority,
    }
    r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                   headers=H, json=payload, timeout=20)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                       headers=H, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()
```

---

## ClickUp Hierarchy

```
Workspace (Team)
└── Space           ← one per major department or project area
    └── Folder      ← one per project (optional)
        └── List    ← one per phase or sprint
            └── Task
                └── Subtask
```

## Task Status Convention (always apply)

This is the canonical meaning of each status. Apply it consistently when creating, updating, or reviewing tasks.

| Status | Meaning | When to use |
|--------|---------|-------------|
| **backlog** | Task is known and needed but not yet planned — no due date, no assignee, not actively worked on | Default for newly created tasks that aren't yet scheduled |
| **to do** | Task is scheduled — it has a due date AND an assignee. It is planned work in the queue | Set when assigning a due date + assignee to a backlog task |
| **in process** | Actively being worked on right now | Assignee sets this when they start the task |
| **on hold** | Work complete, awaiting review or approval | Assignee sets this when done; reviewer picks it up |
| **done** | Work verified and accepted | Set after review passes |
| **Closed** | Permanently finished — archived, no further action | Move all "done" tasks here during cleanup |

**Rules:**
- When creating a task with no due date or no assignee → status = `backlog`
- When creating a task WITH a due date AND an assignee → status = `to do`
- Never leave a task with a due date + assignee in `backlog` — that is a contradiction
- When scheduling backlog tasks (adding due date + assignee), update their status to `to do` at the same time
- Subtasks follow the same rules as their parent

**When reviewing workload:** tasks in `backlog` are unplanned scope. Tasks in `to do` are committed work. Report them separately.

---

## List Icon & Color Convention

Every project list in ClickUp uses two visual signals:

### Icon (set manually in ClickUp UI — cannot be changed via API)
| Icon | Meaning |
|------|---------|
| ▶️ Play | Active — people are currently working on this project |
| ⏸ Pause | On hold — project is paused or waiting but not cancelled |
| ⏹ Stop | Stopped — project is not proceeding |

### Color (set automatically by `scripts/update_list_colors.py`)
| Color | Meaning |
|-------|---------|
| 🟢 Green | All tasks on schedule — nothing overdue or due imminently |
| 🟡 Yellow | At least one task/subtask is due today or tomorrow |
| 🔴 Red | At least one task/subtask is overdue (past due, not closed) |

**API field confirmed working:** `PUT /api/v2/list/{list_id}` with `{"name": "<list name>", "status": "green" | "yellow" | "red"}`

**When to update colors:**
- After creating or updating tasks in a list, run `update_list_colors.py --list-id <id>`
- When doing a workload/status review, run across the whole folder: `update_list_colors.py --folder-id <id>`
- Always update before reporting project status to the user

```bash
# Update a single list
python scripts/update_list_colors.py --list-id 901612525485

# Update all lists in the Hardware folder
python scripts/update_list_colors.py --folder-id 90166940853

# Dry-run — report only, no writes
python scripts/update_list_colors.py --folder-id 90166940853 --dry-run
```

## Scripts

| Script | Purpose |
|---|---|
| `.github/skills/clickup-ops/scripts/clickup_client.py` | Low-level ClickUp REST API wrapper — `create_task`, `create_subtask`, `update_task`, `add_comment` |
| `.github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py` | **Primary script for creating parent tasks + subtasks from a JSON plan** |
| `.github/skills/clickup-ops/scripts/create_project.py` | Create a full Space + Folder + Lists from a plan JSON |
| `.github/skills/clickup-ops/scripts/sync_tasks.py` | Create or update flat tasks (no subtasks) from a plan JSON |
| `.github/skills/clickup-ops/scripts/add_comment.py` | Post a follow-up comment on a task |
| `scripts/update_list_colors.py` | Scan tasks/subtasks and update list status color (green/yellow/red) |

---

## Creating Tasks with Subtasks — Use `create_tasks_with_subtasks.py`

This is the **canonical way to add a structured task tree** to any ClickUp list.
Use it any time you have parent tasks with 2+ subtasks. Do not write one-off inline scripts.

### Quick usage

```bash
# Create from a plan file (recommended — plan survives session)
python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \
    --plan outputs/control-center/tasks.json

# Override list, assignee, and due date at runtime (no plan changes needed)
python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \
    --plan outputs/control-center/tasks.json \
    --list-id 901611246899 \
    --assignee-id 101084655 \
    --due 2026-06-13

# Dry run — see what would be created without calling the API
python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \
    --plan outputs/control-center/tasks.json --dry-run
```

### Plan JSON schema

Save plan files under `outputs/{project-slug}/tasks.json`:

```json
{
  "list_id": "901611246899",
  "default_assignees": [101084655],
  "default_due": "2026-06-13",
  "default_priority": 2,
  "tasks": [
    {
      "name": "Build Raspbian Lite baseline image",
      "description": "Done when baseline boots and setup script completes on target hardware.",
      "assignees": [101084655],
      "due": "2026-06-13",
      "priority": 2,
      "status": "to do",
      "subtasks": [
        {
          "name": "Lock target Raspberry Pi OS Lite version and architecture",
          "description": "Acceptance criterion: version pinned and documented in version manifest.",
          "priority": 3
        },
        {
          "name": "Install minimal required system packages",
          "priority": 3
        }
      ]
    }
  ]
}
```

**Key rules for the plan schema:**
- `list_id` is required unless `--list-id` is passed at runtime.
- `default_assignees` / `default_due` / `default_priority` apply to all tasks unless overridden per task.
- `assignees` at any level must be a **flat list of integer ClickUp user IDs**.
- `priority`: 1=urgent, 2=high, 3=normal, 4=low.
- Subtasks inherit the parent's `assignees` and `due` unless explicitly overridden.
- Leave `status` out to use `"to do"` as default.

### Safe `.env` loading

`create_tasks_with_subtasks.py` uses a safe `.env` parser that does **not** call `dotenv.find_dotenv()`.
It reads `{repo-root}/.env` explicitly. This works correctly in piped and subprocess contexts.
Never replace this with `from dotenv import load_dotenv; load_dotenv()` — that pattern
crashes when the script is not run from within the project tree.



**Every task created in ClickUp must be broken down into logical subtasks.** This is not optional.

- A task with no subtasks is not actionable — it is a label. Always decompose.
- Subtasks should be independently completable, assignable, and estimable.
- Each subtask inherits the parent assignee unless a different person owns that step.
- Aim for 3–8 subtasks per task. If more are needed, consider whether the task should be split into two parent tasks.
- Subtask descriptions should contain acceptance criteria (what "done" looks like).

**How to create subtasks via API:** Use the `create_subtask()` template from the ⚠️ API Rules section above. Key requirement: POST to the list endpoint with `"parent": parent_task_id` — do NOT use `/task/{id}/subtask`.

## Steps — Create a New Project in ClickUp

1. Confirm the project plan JSON from `outputs/{slug}/step_1_project_plan.json`.
2. Show the user the full structure to be created (space, lists, tasks, subtasks, owners) — **wait for explicit approval**.
3. Run `create_project.py --plan outputs/{slug}/step_1_project_plan.json`.
4. Run `sync_tasks.py` to create tasks with assignees and due dates.
5. For every task created, immediately create logical subtasks under it.
6. Save ClickUp IDs back to `data/project_priorities.json` (space_id, list_ids, task_ids).

## Steps — Update Existing Tasks

**What PUT `/api/v2/task/{id}` CAN update:** `name`, `description`, `due_date`, `status`, `priority`, `archived`

**What PUT CANNOT update:** `assignees` — silently ignored. To change assignees, delete and recreate the task.

```python
# Safe to update via PUT
r = httpx.put(f"https://api.clickup.com/api/v2/task/{task_id}",
              headers=H,
              json={"due_date": ms(2026, 6, 15), "status": "todo"},
              timeout=20)
```

1. `sync_tasks.py --task-id <id> --status "in progress"` — update status
2. `add_comment.py --task-id <id> --comment "Follow-up: ..."` — confirm with user first

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
- If an assignee member ID is unknown, look it up from `data/hr_structure.json` under `clickup_user_id`.
- Never delete tasks automatically — always ask for confirmation.
- Rate limit: ClickUp API allows 100 req/min. If you hit 429, wait 62 s and retry once.
- Archiving: `PUT /task/{id}` with `{"archived": true}` hides a task without deleting it. Use for old/obsolete tasks.

## Pre-Flight Checklist — Before Writing Any ClickUp Script

Before generating any script that writes to ClickUp, verify all of the following:

- [ ] Assignees are a flat list of integer IDs: `[100842373]` not `[{"id": 100842373}]`
- [ ] Headers include `"Content-Type": "application/json"`
- [ ] Subtasks use `POST /list/{list_id}/task` with `"parent"` field — NOT `/task/{id}/subtask`
- [ ] Due dates use the `ms(yyyy, mm, dd)` helper (18:00 local time) with `"due_date_time": False`
- [ ] Status string matches the exact status name from the list (fetched via GET `/list/{id}`)
- [ ] Assignees are being set via POST (creation), not PUT (update)
