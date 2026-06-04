# agent-project-manager

HR project management agent — plans, prioritises, delegates and tracks company projects via ClickUp.

Built on the **DOE v2** (Skills / Orchestration / Execution) framework.

---

## What it does

- **Plans projects** — breaks goals into phases, tasks, and milestones with priority scoring
- **Understands HR structure** — knows your org chart, roles, skills, and capacity (`data/hr_structure.json`)
- **Delegates intelligently** — matches tasks to the right people based on skills and available hours
- **Tracks progress** — weekly status reports with ✅ on track · ⚠️ at risk · ❌ blocked flagging
- **Syncs to ClickUp** — creates Spaces, Folders, Lists, Tasks, assignees, deadlines, and follow-up comments
- **Remembers context** — persists decisions and project history across sessions

---

## Quick Start

### 1. Install dependencies
```bash
pip install -e .
```

### 2. Configure credentials
```bash
cp .env.example .env
# Edit .env with your actual keys
```

Get your ClickUp API token from: **ClickUp Settings → Apps → API Token**  
Your Team ID is in the ClickUp URL: `app.clickup.com/{TEAM_ID}/...`

### 3. Populate your HR structure
Edit `data/hr_structure.json` with your actual team members, roles, skills, and capacity.

### 4. Smoke test
```bash
python -c "from graph import build_graph; print(build_graph())"
python scripts/self_anneal_diagnostics.py --check all
```

### 5. Run tests
```bash
pytest tests/
```

---

## Usage — VS Code Copilot Chat

Open this workspace in VS Code and chat:

> "Plan a new project: migrate our database to PostgreSQL, deadline end of August."

> "Who should handle frontend work this sprint? We need 15 hours of React work."

> "Create all the ClickUp tasks for the DB migration project."

> "Give me a status report on all active projects."

> "Alice is on leave until August 15 — update her capacity."

---

## Project Structure

```
agent-project-manager/
├── config.json                   # CommandCenter agent contract
├── graph.py                      # LangGraph build_graph() entry point
├── pyproject.toml
├── AGENTS.md                     # AI coding agent instructions
├── prompts/system.md             # Primary system prompt
├── skills/
│   ├── project-planning/         # Plan projects, score priorities
│   ├── hr-structure/             # Query org chart, find owners
│   ├── project-tracking/         # Status reports, follow-ups
│   ├── clickup-ops/              # ClickUp API integration
│   ├── agent-memory/             # Persist facts across sessions
│   └── self-annealing/           # Error recovery
├── scripts/
│   ├── project_data_manager.py   # Load/save project JSON files
│   └── self_anneal_diagnostics.py
├── data/
│   ├── hr_structure.json         # ← FILL THIS IN with your team
│   ├── project_priorities.json   # Auto-updated by agent
│   └── INDEX.md
├── outputs/                      # Per-project step JSONs (auto-created)
└── tests/
```

---

## ClickUp Setup

1. Add your `CLICKUP_API_TOKEN` and `CLICKUP_TEAM_ID` to `.env`.
2. Ask the agent to list your ClickUp members:
   ```bash
   python skills/clickup-ops/scripts/clickup_client.py --list-members
   ```
3. Copy the `clickup_user_id` values into `data/hr_structure.json` for each person.

---

## Credentials

| Key | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `CLICKUP_API_TOKEN` | ClickUp → Settings → Apps → API Token |
| `CLICKUP_TEAM_ID` | Visible in ClickUp URL |

Never commit `.env` — add it to `.gitignore`.