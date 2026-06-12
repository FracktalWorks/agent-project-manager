# Agent Project Manager — Repository Custom Instructions for GitHub Copilot

> Auto-discovered by GitHub Copilot (cloud agent, code review, and chat on github.com).
> Keep this file concise — 2 pages max. Task-specific instructions go in `.github/instructions/`.
> Full agent documentation: `AGENTS.md`

## What This Repo Does

A **project management and HR delegation agent** for Fracktal Works. It plans projects,
breaks down technical work (WBS, Gantt, risk registers), delegates to the right people
based on resume-inferred skills and live ClickUp workload, tracks risks and follow-ups,
generates daily morning reports, and keeps everything synchronised in ClickUp.

## High-Level Architecture

- **Type:** Python 3.12+ agent (MAF framework: `agents.py` exports `build_agents()`)
- **Dual-mode** — same codebase serves both VS Code Copilot Chat
  (`.github/agents/agent-project-manager.agent.md`) and the CommandCenter orchestrator
  (`agents.py` + `config.json`)
- **13 skill domains** in `.github/skills/`, each with a SKILL.md + optional scripts/
- **Shared utilities** in `scripts/` (diagnostics, memory search, workload analysis, integrations)
- **No LangGraph** — `graph.py` is retained for reference only; the executor calls `build_agents()` exclusively

## Key Files

| File | Purpose |
|---|---|
| `agents.py` | MAF entry point — `build_agents()` returns agents with async tool functions |
| `config.json` | CommandCenter contract (name, integrations, authority, `max_mutation_attempts: 1`) |
| `AGENTS.md` | AI coding agent instructions (persona, skills map, ClickUp API rules, user IDs) |
| `.github/agents/agent-project-manager.agent.md` | VS Code Copilot Chat custom agent definition |
| `.github/prompts/system.md` | Primary system prompt (loaded by `agents.py`) |
| `.github/skills/*/SKILL.md` | Per-skill instructions (13 skills) |
| `.github/skills/*/scripts/` | Python scripts that do the actual work for each skill |
| `data/hr_structure.json` | Org chart — the HR source of truth |
| `outputs/_memory/` | Persistent memory (risk log, decisions, follow-ups, project registry) |

## Build, Test, Validate

**Bootstrap:**
```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

**Run tests:**
```bash
python -m pytest tests/ -v
```
Minimum: `test_build_agents_importable`, `test_agent_has_name_and_instructions`,
`test_system_prompt_includes_all_skills`, `test_tools_are_async`.

**Health check:**
```bash
python scripts/self_anneal_diagnostics.py
```

## Project Layout (Non-Obvious Dependencies)

```
agent-project-manager/
├── agents.py               ← Entry point (must export build_agents() -> list[BaseAgent])
├── config.json             ← CommandCenter contract
├── .github/
│   ├── copilot-instructions.md   ← THIS FILE
│   ├── agents/             ← VS Code custom agents
│   ├── skills/             ← 13 skill domains, each with SKILL.md + scripts/
│   ├── prompts/            ← system.md + reusable .prompt.md task prompts
│   └── instructions/       ← Path-scoped instructions (outputs/, .tmp/, scripts/, skills)
├── scripts/                ← Shared utilities (on sys.path at runtime)
├── data/                   ← HR structure, project priorities, resumes
├── outputs/                ← Per-project artifacts + _memory/ (JSON + FTS5 SQLite)
├── .tmp/                   ← Caches + short-lived intermediates (see tmp-folder instructions)
├── tests/                  ← pytest suite (imports agents.py, calls build_agents())
└── .env                    ← API keys (local only, never commit)
```

**Critical patterns:**
- Skill scripts resolve the repo root via `Path(__file__).resolve().parents[4]` — moving a
  script changes this count
- Credentials: `os.getenv(...)` works in both modes (`.env` for local, env injection for CommandCenter)
- `max_mutation_attempts: 1` — never retry a failed ClickUp write automatically
- Always confirm with the user before writing to ClickUp
- ClickUp API has 6 silent-failure rules — see the table in `AGENTS.md` before touching any ClickUp code
- `data/hr_structure.json` is the HR record; `outputs/_memory/project_registry.json` is the project record

## Checks Run Before Commit/PR

- `tests/test_agents.py` must pass (build_agents importable, agents have name + instructions + tools)
- `config.json`: `max_mutation_attempts` must be 1
- Agent must not instantiate at module import time — `build_agents()` is the single entry point
- No hardcoded credentials in any committed file

## Dependencies That Aren't Obvious

- `agent_framework_github_copilot` — MAF base class for `GitHubCopilotAgent`. Not in
  `pyproject.toml`; injected by the CommandCenter runtime. Tests skip gracefully when absent.
- ClickUp user IDs are hardcoded in `AGENTS.md` (sourced from `data/hr_structure.json`).

