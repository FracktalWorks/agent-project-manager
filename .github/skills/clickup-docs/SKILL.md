---
name: clickup-docs
description: 'Create and maintain structured multi-page ClickUp Docs inside a List Doc view. Every project gets a 6-page doc: Overview (index with links), Project Plan, Product Requirements, Product Documentation, Subsystems, and Open Questions & Risks. Use create_project_docs.py to build or rebuild the full doc from a spec.json. Use publish_plan_to_list.py for lightweight plan-only publishing. Trigger keywords: create doc, project documentation, publish docs, doc view, list doc, product requirements, subsystems, project plan, architecture, open questions, risks.'
argument-hint: 'Specify the project slug or the path to outputs/{slug}/project-docs/spec.json.'
user-invocable: true
disable-model-invocation: false
---

# ClickUp Project Documentation

Every project gets a structured multi-page Doc inside its ClickUp List. The doc appears as a view in the list's view bar — visible to all team members alongside the task board.

## Page Structure (6 pages, always this order)

```
📋 Overview          — index page: one-para summary, status, team, milestone table, top risks,
                       and links to every other page. Created LAST so links are accurate.
🗺 Project Plan      — objectives, scope in/out, timeline, milestone table, dependencies
📄 Product Requirements — functional requirements, non-functional requirements, constraints, personas
📐 Product Documentation — system architecture, how it works, key design decisions (ADRs), file links
⚙️ Subsystems        — one ## section per major subsystem (description, specs, known issues)
❓ Open Questions & Risks — unresolved decisions blocking the project, risk register
```

**What goes in docs vs tasks:**
- Docs = understanding — architecture, requirements, design decisions, subsystem breakdown, open questions
- Tasks = doing — sprint items, assignments, deadlines. Do NOT duplicate task lists in docs.

## File Structure Per Project

```
outputs/{slug}/
  project-docs/
    spec.json     ← source of truth — edit this to update docs
    doc_ids.json  ← auto-written: doc_view_id + all page IDs
```

## Scripts

| Script | Purpose |
|--------|---------|
| `.github/skills/clickup-docs/scripts/create_project_docs.py` | Build or rebuild the full 6-page doc from `spec.json` |
| `.github/skills/clickup-docs/scripts/publish_plan_to_list.py` | Lightweight: publish a single `project_plan.md` as a doc view |

---

## Workflow — Create Docs for a New Project

### Step 1: Create the spec file

Save to `outputs/{slug}/project-docs/spec.json`. Required fields:

```json
{
  "name": "Project Name",
  "slug": "project-slug",
  "list_id": "901611xxxxxx",
  "clickup_list_url": "https://app.clickup.com/...",
  "doc_view_name": "Project Name — Documentation",
  "status": "Active",
  "phase": "Design",
  "last_updated": "YYYY-MM-DD",
  "description": "One paragraph about what this project is and why.",
  "team": [{"name": "...", "role": "..."}],
  "objectives": ["..."],
  "scope_in": ["..."],
  "scope_out": ["..."],
  "timeline": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "milestones": [{"milestone": "...", "date": "...", "owner": "...", "status": "Upcoming"}],
  "dependencies": ["..."],
  "functional_requirements": [{"req": "...", "priority": "H/M/L", "status": "Open"}],
  "nonfunctional_requirements": [{"req": "...", "target": "...", "status": "Open"}],
  "constraints": ["..."],
  "personas": [{"name": "...", "description": "..."}],
  "architecture": "Narrative describing system architecture.",
  "how_it_works": "Narrative describing operation.",
  "design_decisions": [{"title": "...", "context": "...", "decision": "...", "rationale": "...", "consequences": "..."}],
  "subsystems": [{"name": "...", "status": "...", "owner": "...", "description": "...", "specs": ["..."], "known_issues": ["..."]}],
  "open_questions": [{"question": "...", "owner": "...", "status": "Open"}],
  "risks": [{"risk": "...", "likelihood": "H/M/L", "impact": "H/M/L", "mitigation": "...", "owner": "..."}],
  "external_links": {"Resource Name": "URL"}
}
```

The agent should populate this spec from conversation with the user and available project context before running the script.

### Step 2: Build and publish

```bash
# Create fresh docs (first time)
python .github/skills/clickup-docs/scripts/create_project_docs.py \
  --spec outputs/{slug}/project-docs/spec.json

# Rebuild from scratch (wipes existing doc view, recreates all pages)
python .github/skills/clickup-docs/scripts/create_project_docs.py \
  --spec outputs/{slug}/project-docs/spec.json --rebuild
```

### Step 3: Update docs after changes

1. Edit `spec.json` (the source of truth)
2. Re-run without `--rebuild` — the script updates existing pages in place
3. The Overview page is always re-written last so navigation links stay accurate

---

## Workflow — Update a Single Page

If only one section has changed (e.g. a new design decision was made):
1. Edit the relevant field in `spec.json`
2. Re-run `create_project_docs.py` (no `--rebuild`) — it detects existing pages and updates them

---

## ClickUp API — Confirmed Working Endpoints

| Action | Method | Endpoint | API version |
|--------|--------|----------|-------------|
| Create doc-type view on list | POST | `/list/{list_id}/view` body `{"type":"doc"}` | v2 |
| Add page to doc/view | POST | `/workspaces/{ws}/docs/{doc_id}/pages` | v3 |
| Update page | PUT | `/workspaces/{ws}/docs/{doc_id}/pages/{page_id}` | v3 |
| List pages | GET | `/workspaces/{ws}/docs/{doc_id}/pages` | v3 |
| Delete view | DELETE | `/view/{view_id}` | v2 |

> **Important:** ClickUp v3 `POST /docs` does NOT accept `list`, `folder`, `space`, or `workspace` as parent types. The only working pattern for list-scoped docs is the v2 view API above.

---

## Improvements Implemented (2026-06-06)

1. **No task lists in docs** — sprint tasks belong in ClickUp lists, not documentation pages
2. **Multi-page navigation** — Overview page links to every section page by URL
3. **spec.json as single source of truth** — edit once, republish anywhere (ClickUp, DOCX, PDF)
4. **Design decisions documented (ADRs)** — context, decision, rationale, consequences per decision
5. **Subsystems as first-class content** — each subsystem gets its own entry with owner, specs, and known issues
6. **Open questions separated from risks** — blocking decisions tracked separately from probability/impact risks
7. **No fabricated task content** — docs describe what and why; ClickUp tasks track who does what by when

```
Space
└── Folder
    └── Doc: "[Folder Name] — Project Reference"
        ├── Page: Overview & Index  (what's in this folder, color coding meaning, links)
        ├── Page: [Project A Name]  (PRD, status, team, links)
        ├── Page: [Project B Name]
        └── ...
```

