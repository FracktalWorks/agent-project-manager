---
name: daily-morning-report
description: >
  Generate a daily morning report showing only tasks that are overdue, due today,
  due tomorrow, or actively in-process. Includes department-wise breakup, people
  workload rollup, and AI-suggested assignments for idle/light-load team members
  based on skill matching. Trigger keywords: morning report, daily report,
  work report, project overview, team status, who is doing what, workload summary,
  what should I assign today.
argument-hint: 'Optional: specify a department name to scope the report, or leave blank for all departments.'
user-invocable: true
disable-model-invocation: false
---

# Morning Report Skill

## Agent instructions — run this, present the output, done

When the user asks for a morning report / daily report / work overview / who is doing what:

1. **Run the script — no decisions needed:**
   ```bash
   python .github/skills/daily-morning-report/scripts/generate_morning_report.py
   ```
   The script handles everything programmatically:
   - Fetches all tasks from ClickUp
   - Filters to active lists only (green = active, yellow = paused, red = stopped)
   - Excludes backlog, done, closed, cancelled tasks
   - Maps people to departments via `hr_structure.json`
   - Classifies workload status per person
   - Writes the report to `outputs/morning_reports/morning_report_YYYY-MM-DD.md`

2. **Read the saved file** and present it to the user.

3. **Add a 2-line top summary** (most urgent concern + top idle people), then stop.

4. Do NOT re-run, re-interpret, or second-guess the output. The script is the source of truth.

---

## What the script decides automatically

| Decision | Rule (hardcoded in script) |
|---|---|
| Which lists to include | `green` color only — set in ClickUp list settings |
| Which tasks to show | Excludes: `backlog`, `done`, `closed`, `complete`, `completed`, `cancelled`, `canceled` |
| Workload status | OVERLOADED: est. hours > 48h capacity |
| | BEHIND: ≥1 overdue task (due date < today, not closed) |
| | LIGHT_LOAD: <2 tasks OR est. hours < 25% capacity |
| | IDLE: 0 tasks |
| | ON_TRACK: everything else |
| Hour estimate per task | urgent=8h, high=6h, normal=4h, low=2h |
| Department placement | `data/hr_structure.json` + `dept_mapping.json` |
| Report output path | `outputs/morning_reports/morning_report_YYYY-MM-DD.md` |
| Cross-dept task flag | ⚡ shown when list's owning dept ≠ person's dept |

---

## List color convention (workspace-wide)

> Defined in `AGENTS.md` and `.github/skills/daily-morning-report/scripts/dept_mapping.json`

| Color | Meaning | In report |
|---|---|---|
| 🟢 green | Active — being worked on | ✅ Included |
| 🟡 yellow | Paused / on hold | ❌ Skipped |
| 🔴 red | Stopped / inactive | ❌ Skipped |
| *(none)* | No color set | ✅ Included |

To change a project's state: update its list color in ClickUp. The report picks it up automatically next run.

---

## Configuration files (edit these, not the script)

| File | What to change |
|---|---|
| `data/hr_structure.json` | Add/remove people, update ClickUp IDs, change `_report_dept` overrides |
| `.github/skills/daily-morning-report/scripts/dept_mapping.json` | Department→report-section mapping, list→department mapping, skip_list_ids |
| `data/hr_structure.json` `_report_dept` field | Override a person's report section (e.g. Kiran → Founders Office) |

---

## Optional flags

```bash
# Scope to one department only
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --department "R&D"

# Custom output path
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --output path/to/file.md

# Machine-readable JSON
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --format json
```

---

## Department → Report section mapping (current)

| hr_structure.json dept | Report section |
|---|---|
| Leadership | Founders Office |
| HR & Operations (Kiran) | Founders Office *(override)* |
| Engineering | R&D |
| Interns | R&D |
| Manufacturing | Manufacturing |
| Operations → Manufacturing | Manufacturing *(override)* |
| Fracktory | Fracktory |
| Design & Marketing | Marketing |
| Sales | Sales |
| After Sales | Aftersales / Fracktal Care |
| HR & Operations (Pooja) | HR |
| HR & Operations (Divya, Lakshmipathi) | Admin *(override)* |
| Finance | Finance |
| Unassigned | *(skipped)* |

---

## List → Department mapping (mixed spaces only)

| ClickUp List | Department |
|---|---|
| Sales Operations | Sales |
| Marketing Operations | Marketing |
| Video Content | Marketing |
| Social Media Content | Marketing |
| 3D Printing Course | Marketing |
| Website_Fracktal | Marketing |
| SEO & Blogs | Marketing |
| HR | HR |
| Finance & Accounting | Finance |
| Manufacturing | Manufacturing |
| Founders Office | Founders Office |

All other lists (R&D, Fracktal Care, Fracktory) map 1:1 to their space/department.


# Morning Report Skill

Generate a comprehensive morning status report for Fracktal Works covering all active projects
and every team member's workload.

---

## What the report contains

### Section 1 — Department-wise Breakup
For each department (Sales, Marketing, Aftersales/Fracktal Care, R&D, HR, Admin, Finance,
Manufacturing, Founders Office):
- Lists every person in that department
- For each person: their active ClickUp tasks, grouped by project/sub-project (ClickUp list)
- Highlights any overdue or at-risk tasks inline

### Section 2 — People-wise Rollup
A consolidated view of every person in the company with their workload status:

| Status | Meaning |
|---|---|
| 🔴 OVERLOADED | Estimated task hours > weekly capacity (default 48h) |
| 🟠 BEHIND | Has ≥ 1 overdue task (due date passed, not closed) |
| 🟢 ON TRACK | Tasks assigned, none overdue, within capacity |
| 🟡 LIGHT LOAD | Fewer than 2 open tasks OR estimated hours < 25% of capacity |
| ⚪ IDLE | No open tasks assigned in ClickUp |

---

## Quick command

```bash
# Full morning report (all departments, all people)
python .github/skills/daily-morning-report/scripts/generate_morning_report.py

# Scope to one department
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --department "R&D"

# Save to file
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --output outputs/morning_report_$(date +%Y-%m-%d).md

# JSON output (machine-readable)
python .github/skills/daily-morning-report/scripts/generate_morning_report.py --format json
```

---

## Department → HR mapping

The script uses the mapping in `.github/skills/daily-morning-report/scripts/dept_mapping.json` to translate
the department names in `hr_structure.json` into the report's department categories.

**Current mapping (edit `dept_mapping.json` to update):**

| Report Department | hr_structure.json department |
|---|---|
| Founders Office | Leadership |
| R&D | Engineering |
| Manufacturing | Operations |
| Marketing | Design & Marketing |
| Sales | Sales |
| Aftersales / Fracktal Care | After Sales |
| HR | HR |
| Admin | Admin |
| Finance | Finance |

> **NOTE:** If a person's department is missing from `hr_structure.json` (e.g. HR, Admin, Finance
> staff not yet added), they will not appear. Add them to `data/hr_structure.json` with a
> matching department name to include them in the report.

---

## Workload thresholds (tunable)

| Parameter | Default | Location |
|---|---|---|
| Hours per normal-priority task | 4h | `generate_morning_report.py` → `TASK_EFFORT_BY_PRIORITY` |
| Overloaded threshold | > weekly capacity | same file |
| Light load threshold | < 25% of capacity | same file |
| "Behind" = overdue by N days | ≥ 0 days (any overdue task) | same file |

---

## Agent invocation steps

When the user asks for a morning report / daily report / work overview:

1. Run the script:
   ```bash
   python .github/skills/daily-morning-report/scripts/generate_morning_report.py
   ```
2. Read the output (stdout is Markdown, already formatted for display).
3. Present the report to the user. Add a 1-line summary of the biggest concerns at the top
   (most overloaded person, most behind project).
4. Optionally ask if the user wants to push it to a ClickUp Doc.

---

## Output format (Markdown)

```
# 🌅 Morning Report — Fracktal Works
**Generated:** 2026-06-08 09:00 IST

---

## Department Breakdown

### 🏢 R&D
#### Ayush Sarkar — Mechatronics Engineer
| Project | Task | Status | Due | Flag |
|---------|------|--------|-----|------|
| Julia Series | Design extruder head v2 | in process | 2026-06-10 | 🟢 |
| MDS | Wire harness layout | to do | 2026-06-15 | 🟢 |

...

---

## People Rollup

| Person | Dept | Tasks | Est. Hours | Capacity | Status |
|--------|------|-------|------------|----------|--------|
| Ayush Sarkar | R&D | 5 | 22h | 48h | 🟢 ON TRACK |
| Suryansh Lal | R&D | 0 | 0h | 48h | ⚪ IDLE |
...
```
