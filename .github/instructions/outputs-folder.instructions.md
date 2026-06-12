---
applyTo: "outputs/**"
description: "Organisation and structure rules for the outputs/ folder. Enforced when the agent creates or modifies project output directories."
---

# outputs/ Folder Organisation

## Standard Project Structure

Every project folder in outputs/ MUST follow this layout:

```
outputs/{project-slug}/
├── tasks.json                    # ClickUp task plan (input to create_tasks_with_subtasks.py)
├── project-plan/                 # Technical plan artifacts
│   ├── project_plan.md           # Source of truth (Markdown)
│   ├── project_plan.docx         # Rendered export (only when exported)
│   ├── project_plan.pdf          # Rendered export (only when exported)
│   ├── spec.json                 # Plan spec used to generate the MD
│   └── metadata.json             # Slug, dates, ClickUp IDs
├── project-docs/                 # ClickUp Doc specs
│   ├── spec.json                 # Doc content spec
│   └── doc_ids.json              # Created ClickUp doc/page IDs
├── step_*.json                   # Planning pipeline step outputs
└── research/                     # Research artifacts (papers, extracted text)
```

Reports are stored separately:

```
outputs/morning_reports/morning_report_YYYY-MM-DD.md
```

## Rules

### DO

- Store ALL pipeline step outputs as JSON in the project folder
- Keep `project_plan.md` as the single source of truth; exports are derived
- Store project-specific research artifacts in `research/`
- Use kebab-case for project slugs (e.g. `julia-series`, `penrose-pellet-extruder`)
- Register every project in `outputs/_memory/project_registry.json` with its ClickUp IDs

### DO NOT

- Put Python scripts in outputs/ — one-off scripts go in `.tmp/`, reusable ones in `scripts/`
- Put `.tmp/` subdirectories inside project folders — intermediates go in repo root `.tmp/`
- Keep old versioned files (`_v2_FINAL` etc.) — archive superseded versions or delete them
- Duplicate files across project folders — each project is self-contained
- Duplicate reports — morning reports live ONLY in `outputs/morning_reports/`

### Versioning

- Keep only the LATEST version of each deliverable in the project folder
- If version history is needed, move old versions to an `archive/` subdirectory
- Never name files `_FINAL` — the latest is always the final

### The _memory/ Directory

`outputs/_memory/` is the long-term memory store and is structured differently:

| File | Purpose |
|---|---|
| `company_context.json` | Company stage, active projects, priorities |
| `project_registry.json` | All projects with ClickUp IDs, Doc IDs, external links |
| `risk_log.json` | Active and closed risks with scores, owners, review dates |
| `decision_journal.json` | Key decisions with date, rationale, outcome |
| `follow_ups.json` | Open follow-ups with assignees and due dates |
| `open_questions.json` | Unresolved questions blocking plans or decisions |
| `lessons_learned.json` | Failure patterns and their fixes |
| `interaction_log.json` | Session summaries (last 20, compressed) |
| `workspace_lists.json` | Cached ClickUp workspace list map |
| `project_memory.db` | SQLite FTS5 — Tier 2 deep history search |

Do not put project-specific deliverables directly in `_memory/` — they belong in the project folder.
