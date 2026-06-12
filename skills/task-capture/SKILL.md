---
name: task-capture
description: 'Quickly capture and organize tasks for a specific person. Understands ClickUp project structure (spaces, lists, tasks, subtasks), auto-detects where tasks belong based on project context, and asks clarifying questions when ambiguous. Trigger keywords: add task, create task, new task, todo, my tasks, assign to me, capture.'
argument-hint: 'Describe the task you want to add (what to do, for which project if known).'
user-invocable: true
disable-model-invocation: false
---

# Task Capture

Quickly add tasks to ClickUp under the right project, list, and subtask hierarchy without manual navigation. The skill understands your project structure and places tasks intelligently.

---

## ⚡ Quick Command Reference (copy-paste these)

### Add a task — you know the exact list ID
```bash
# Use --list-id to skip placement scoring (fastest, most reliable for agents)
python .github/skills/task-capture/scripts/capture_task.py \
    "Procure additional dial gauge" \
    --assignee "Kiran" \
    --list-id 901613553036 \
    --due 2026-06-10 \
    --yes
```

### Add a task — you know the project name but not the list ID
```bash
python .github/skills/task-capture/scripts/capture_task.py \
    "Complete manufacturing drawings" \
    --assignee "Suryansh" \
    --project "MDS" \
    --due 2026-06-15 \
    --yes
```

### Add multiple tasks from a JSON file
```bash
# tasks.json format: [{"task": "...", "assignee": "...", "project": "...", "due": "..."}]
python .github/skills/task-capture/scripts/capture_task.py \
    --batch tasks.json --due tomorrow --yes
```

### Find a list ID before creating a task
```bash
# Look up 'Quality Control' list ID
python .github/skills/clickup-ops/scripts/list_workspace.py --filter "quality control" --id-only

# See full workspace list map (cache it for future use)
python .github/skills/clickup-ops/scripts/list_workspace.py --save-cache
python .github/skills/clickup-ops/scripts/list_workspace.py --from-cache --filter "mds"
```

### Key flags summary
| Flag | Required? | Purpose |
|------|-----------|----------|
| `"<task>"` | Yes | Task description (verb + object) |
| `--assignee` | Yes (with --yes) | Person name from hr_structure.json |
| `--list-id` | Recommended | Exact ClickUp list ID — skips scoring |
| `--project` | Optional | Boosts keyword scoring toward a project |
| `--due` | Optional | ISO date, 'tomorrow', 'next week', '3 days' |
| `--yes` | Required for agents | Non-interactive: auto-confirm, no prompts |
| `--batch` | Batch mode | Path to JSON file with multiple tasks |

---

## When to Use
- You want to quickly add a new task to your queue
- You have work that needs to be tracked but don't know which project list it belongs under
- You need to create a subtask under an existing parent task
- You want to capture a task without thinking about ClickUp hierarchy details

## How It Works

1. **You describe the task** — what needs to be done, any project context, and optionally who it's for
2. **The skill resolves the assignee** — if a person is named, it looks up their ClickUp user ID from `data/hr_structure.json`. If no one is mentioned, it asks: "Who should this be assigned to?"
3. **The skill reads your project structure** — loads active projects, lists, and parent tasks from ClickUp
4. **The skill decides or asks** — if the destination is clear (e.g., "add a design review task to the MDS project"), it creates the task directly. If ambiguous (e.g., "fix the wiring"), it asks which project/list you mean
5. **Task is created** — assigned to the chosen person with tomorrow as the default due date (can be adjusted)

## Task Placement Logic

The skill uses keyword scoring to auto-suggest placement, not blind prompting:

```
Is an assignee named?
  YES → Look up their ClickUp user ID in hr_structure.json
  NO  → Ask: "Who should this be assigned to?"

Score every active project + list against the task description:
  - Project name word overlap  (+2 per word)
  - List name word overlap      (+2 per word)
  - Explicit project mention    (+5 bonus)

Top-scoring candidate:
  Score clearly higher than runner-up (gap ≥ 3)?
    YES → Suggest it: "I'd place this under [Project] → [List]. Confirm? (y/n)"
    NO  → Show top 3 candidates ranked and ask user to pick

Should it be a subtask?
  Task description shares ≥ 2 keywords with a parent task in that list?
    YES → Suggest: "Should this be a subtask of '[Parent Task]'? (y/n)"
    NO  → Create as parent task
```

## Batch Mode

When multiple tasks are provided at once (via `--batch tasks.json`), the skill:
1. Scores and suggests placement for every task upfront
2. Prints a summary table: task | suggested space → list | assignee | confidence
3. Flags any task where confidence is LOW with `[?]`
4. Asks once: "Confirm all suggestions? Or enter task numbers to change (e.g. 2,4):"
5. For flagged/selected tasks, asks clarifying questions one by one
6. Creates all tasks only after final confirmation

Example batch summary:
```
  #  Task                              Assignee  Space → List                     Conf
  1  Review vendor quotations          Vijay     Photo Booth → Quotation Package   HIGH
  2  Fix wiring issue                  Sridhar   [?] Photo Booth / MDS             LOW
  3  Update Gantt chart                Ayush     MDS → Planning                    HIGH

Tasks marked [?] need clarification. Confirm rest and fix #2? (y/n):
```

## Scripts

| Script | Purpose |
|---|---|
| `.github/skills/task-capture/scripts/capture_task.py` | Main task capture logic: understand structure, decide placement, create task |
| `.github/skills/clickup-ops/scripts/clickup_client.py` | Low-level API access (reused) |

## Steps — Capture a Task

1. User provides: task description, optional project/list context, optional due date.
2. Script loads `outputs/_memory/project_registry.json` and fetches live ClickUp structure.
3. Script applies placement logic:
   - If project is ambiguous → ask user "Which project?"
   - If list is ambiguous → ask user "Which list in [project]?"
   - If should be subtask → ask user "Should this be under [parent task name]?"
4. Script creates task with:
   - Title: `[Verb] + [Object]` (e.g., "Review design drawings")
   - Assignee: the target person (e.g., Vijay, Ayush, Sridhar)
   - Due date: user-provided or today + 1 day
   - Status: `to do` (assuming assignee + due date will be set)
   - Description: full task description
5. Task appears in ClickUp with correct parent/list hierarchy.

## Task Creation Rules

Every task created via task-capture MUST have:
- **Title**: `[Verb] + [Object]` — actionable verb first
  - ✅ "Review design drawings", "Order motor couplers", "Fix wiring issue"
  - ❌ "Design review", "Motor couplers", "Wiring"
- **Assignee**: a named person resolved from `data/hr_structure.json`. If not provided, ask: "Who should this task be assigned to?"
- **Due date**: specific date (today + 1, today + 3, etc.)
- **Description**: brief summary of what "done" looks like (1-3 sentences)
- **List/Parent**: correct location in ClickUp hierarchy

## Examples

### Example 1: Assignee provided, clear project
```
User: "Assign Ayush a task: Review vendor quotations. Photo Booth."
→ Resolves Ayush → clickup_user_id: 100842373
→ Finds Photo Booth → "Prepare & Send Quotation Package to Vendor" list
→ Creates task assigned to Ayush, due tomorrow
```

### Example 2: No assignee — skill asks
```
User: "Add a task: Fix electrical connection issue."
→ No assignee mentioned → asks: "Who should this be assigned to? (Vijay, Ayush, Sridhar, Suryansh, ...)"
→ User says "Sridhar"
→ Script scans active projects (ambiguous) → asks which project
→ Creates task assigned to Sridhar
```

### Example 3: Belongs as a subtask
```
User: "Add a task for Vijay: Test acrylic durability. Photo Booth."
→ Resolves Vijay → 236494607
→ Finds Photo Booth → sees parent task "Final QA & Performance Testing"
→ Asks: "Should this be a subtask of 'Final QA & Performance Testing'? (y/n)"
→ User confirms → creates subtask
```

## Data Sources

| File | Use |
|---|---|
| `outputs/_memory/project_registry.json` | Map of all projects with ClickUp space/folder/list IDs |
| `data/project_priorities.json` | Which projects are active |
| ClickUp API (live query) | Current lists and parent tasks in each project |
| `data/hr_structure.json` | Get assignee user IDs by name |

## Edge Cases
- If the user says "add to MDS", the script finds the MDS project and lists all its lists, then asks which list
- If the user says "add this as a subtask of [task name]", the script finds that parent task and creates the subtask
- If the project doesn't exist or is archived, the script says "I don't find that project. Active projects are: [list]. Which one?" and waits
- If the due date is ambiguous (user says "next week"), the script interprets it as today + 5 days
