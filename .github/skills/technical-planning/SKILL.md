---
name: technical-planning
description: 'Create a single, ClickUp-ready technical project plan covering project summary, work streams, tasks, subtasks, and timeline. Outputs a source Markdown file plus DOCX and PDF exports. Trigger keywords: project plan, technical plan, plan project, work streams, tasks, subtasks, timeline, deliverables, milestones, resource plan.'
argument-hint: 'Describe the project: name, domain, objectives, constraints (budget, timeline, team size). Include start/end date if known.'
user-invocable: true
disable-model-invocation: false
---

# Technical Project Planning

Generate a single, actionable project plan for any Fracktal Works initiative. The output is a clean Markdown document plus DOCX and PDF exports — structured for direct use by ClickUp and the team.

## When to Use
- User wants to plan a new product, engineering initiative, or internal project
- User needs work streams, tasks, and subtasks laid out with owners and timelines
- User needs a document they can share with stakeholders or push into ClickUp
- User wants to re-export a previously written plan to DOCX or PDF after editing

## Output Folder Structure

```
outputs/
  {project-slug}/
    project-plan/
      project_plan.md      ← source of truth — edit this
      project_plan.docx    ← generated from MD
      project_plan.pdf     ← generated from MD
      metadata.json        ← slug, name, dates, version, ClickUp IDs
```

- **Always edit `project_plan.md`** — never manually edit the DOCX or PDF.
- To re-export after edits: run `render_plan.py` against the MD file.
- `metadata.json` tracks ClickUp space/list IDs so the agent can link back.

## Scripts

| Script | Purpose |
|---|---|
| `.github/skills/technical-planning/scripts/generate_project_plan.py` | Generate `project_plan.md` from user inputs |
| `.github/skills/technical-planning/scripts/render_plan.py` | Convert an existing `project_plan.md` → DOCX + PDF |

Research scripts (optional — use when deeper background is needed):

| Script | Purpose |
|---|---|
| `.github/skills/technical-planning/scripts/web_research.py` | Web search: industry practices, tech comparisons |
| `.github/skills/technical-planning/scripts/search_papers.py` | Academic paper search |
| `.github/skills/technical-planning/scripts/fetch_paper.py` | Download open-access papers |
| `.github/skills/technical-planning/scripts/pdf_to_markdown.py` | Convert PDFs to Markdown for reading |

## Environment Variables Required

| Variable | Purpose |
|---|---|
| `CLICKUP_API_TOKEN` | Needed only if syncing plan into ClickUp |
| `SERPAPI_API_KEY` | Only if running web research scripts |

---

## Workflow

### Step 1 — Gather Inputs

Collect from the user:
- **Project name** (required)
- **Project description / objectives** (required)
- **Start date** and **target end date** (required)
- **Work streams** — top-level areas of work (e.g. Hardware, Software, Operations). If not provided, infer from the domain.
- **Team members** — read `data/hr_structure.json` and match skills to work streams.
- **Key constraints** — budget, regulatory, dependencies on other projects.

### Step 2 — Generate the Plan

```bash
python .github/skills/technical-planning/scripts/generate_project_plan.py \
  --project-name "Penrose V2" \
  --description "Develop and launch the Penrose V2 filament dryer with active drying..." \
  --start-date 2026-06-01 \
  --end-date 2026-09-30 \
  --workstreams "Hardware Design,Firmware,Testing & QC,Procurement,Documentation" \
  --output "outputs/penrose-v2/project-plan/"
```

This creates `outputs/{slug}/project-plan/project_plan.md`.

### Step 3 — Export to DOCX + PDF

```bash
python .github/skills/technical-planning/scripts/render_plan.py \
  --input "outputs/penrose-v2/project-plan/project_plan.md"
```

Writes `project_plan.docx` and `project_plan.pdf` alongside the MD.

### Step 4 — Re-render After Edits

If the user edits `project_plan.md` and wants fresh exports:

```bash
python .github/skills/technical-planning/scripts/render_plan.py \
  --input "outputs/{slug}/project-plan/project_plan.md"
```

Never re-run `generate_project_plan.py` after the MD has been manually edited — that would overwrite changes.

---

## Project Plan Document Structure

The generated `project_plan.md` always contains these sections:

1. **Project Summary** — one-paragraph description, objectives, scope, out-of-scope
2. **Team & Roles** — table: Name | Role | Work Stream | Capacity
3. **Work Streams & Tasks** — one `###` section per work stream, each containing:
   - Work stream owner and timeline
   - Task table: Task | Subtask | Owner | Duration | Start | End | Status
4. **Milestone Timeline** — table: Milestone | Date | Owner | Status
5. **Risks & Mitigations** — table: Risk | Likelihood (H/M/L) | Impact (H/M/L) | Mitigation | Owner
6. **Open Questions** — bulleted list of unresolved decisions blocking the plan

---

## ClickUp Sync (after plan is confirmed)

After the user approves the plan, use `clickup-ops` skill to push it:
- One **List** per work stream
- One **Task** per task row
- **Subtasks** linked to their parent tasks
- Assignees and due dates from the plan tables

Save the resulting ClickUp IDs back to `outputs/{slug}/project-plan/metadata.json`.

---

## HR Integration

Before finalising owners in the plan:
1. Read `data/hr_structure.json` — match task skill requirements to member `skills` arrays.
2. Check `available_hours_per_week` — do not over-assign.
3. Prefer people already working on related projects (context continuity).
4. Flag any tasks with no suitable assignee as an open question.
3. Run `python scripts/workload_analysis.py --suggest {skills} --effort {hours}` to find best-fit candidates.
4. Assign specific people to WBS work packages and reflect in the Gantt resource column.
5. Flag over-capacity risks in the risk register.

## Delegation Rules for Technical Tasks

| Task Type | Preferred Assignee Pool |
|---|---|
| Firmware / embedded | Ayush Sarkar, Pavan Siddapuram, interns with arduino/raspberry pi skills |
| Mechanical CAD / DFM | Suryansh Lal, Ayush Sarkar, interns with solidworks/fusion360 skills |
| Software / web / API | Pavan Siddapuram, Raja Sohal, interns with python/react skills |
| 3D printing / production | SOUGATA MAJI, Kallesha (Fracktory team) |
| Research & documentation | Any intern with domain-matching skills |

## Edge Cases
- If SERPAPI_API_KEY is missing, skip web research and note it in the plan; proceed with architecture and WBS from requirements alone.
- If no start date given, use today's date.
- If team size is unknown, pull from `data/hr_structure.json` and the relevant department.
- For safety-critical projects (medical, automotive, aerospace), explicitly flag applicable standards (IEC 61508, ISO 26262, DO-178C) in the risk register.
