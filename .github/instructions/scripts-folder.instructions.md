---
applyTo: "scripts/**/*.py"
description: "Rules for creating, organising, and promoting scripts in the shared scripts/ directory. Enforced when the agent creates or modifies any shared utility script."
---

# scripts/ Folder — Shared Utilities

## What scripts/ IS For

scripts/ is the shared infrastructure layer. Every file here must be importable by skill
scripts via `from script_name import ...`. The agent adds scripts/ to sys.path at startup
(`agents.py`).

### Categories (ranked by priority)

1. **Project Lifecycle** — `project_data_manager.py` (load/save project step JSONs, slugify)
2. **Diagnostics** — `self_anneal_diagnostics.py` (health checks, learnings log)
3. **Memory** — `memory_search.py` (FTS5 search across Tier 2 SQLite project memory)
4. **Workload** — `workload_analysis.py`, `quick_workload.py` (live ClickUp workload rollups)
5. **HR Data** — `ingest_resumes.py` (PDF resumes → hr_structure.json skills)
6. **ClickUp Maintenance** — `update_list_colors.py`, `discover_review_status.py`
7. **External Integrations** — `integrations/github_info.py`, `integrations/notion_info.py`, `integrations/google_info.py`

## Creating a New Script

1. **Check first** — Is there already a script in `scripts/` or `.github/skills/*/scripts/` that does this?
2. **Determine location:**
   - Domain-specific (e.g. ClickUp task creation) → `.github/skills/<skill>/scripts/`
   - Shared infrastructure used by 2+ skills → `scripts/`
   - One-off fix-up → `.tmp/` (delete after use)
3. **Follow standards** — Use the conventions in `.github/instructions/python-scripts.instructions.md`
4. **Test it** — Run `python scripts/new_script.py --help` to verify it works
5. **Document it** — Add a module docstring with Usage examples and register it in `AGENTS.md`

## Deciding: Script vs Skill

| Question | Script | Skill |
|---|---|---|
| Does it do ONE specific thing? | Yes — put in scripts/ | No — needs multi-step orchestration |
| Is it domain-agnostic? | Yes — put in scripts/ | No — belongs to a specific domain |
| Does it need SKILL.md instructions? | No | Yes — create .github/skills/<name>/SKILL.md |
| Is it called by 2+ different skills? | Yes — put in scripts/ | Possibly — consider promoting to a skill |

### Promotion Path

```
One-off temp script (.tmp/)
    │  Used successfully 2+ times
    ▼
Shared script (scripts/)
    │  Grows to multi-step workflow with domain knowledge
    ▼
Skill (.github/skills/<name>/SKILL.md + scripts/)
```

## One-Off vs Reusable

### ONE-OFF (Delete after use — location: .tmp/)
- ClickUp data dumps, date fixers, field checkers
- Project-specific data transforms (e.g. `fix_julia_dates.py`-style scripts)
- Debug scripts to diagnose a single issue
- Scripts that duplicate what an existing skill already does

### REUSABLE (Keep permanently — location: scripts/)
- Diagnostics and health-check tools
- Memory and data managers used by multiple skills
- Integration helpers (GitHub, Notion, Google)
