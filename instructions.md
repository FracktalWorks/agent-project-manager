# Agent Builder Guide — Skills + Scripts + CommandCenter Framework

> ⚠️ **DEPRECATED (v2.0, 2026-06-03).** This document describes the old `skills/ + prompts/ +
> graph.py` layout. The repo now uses the v2.2 layout: `.github/skills/`, `.github/prompts/`,
> `agents.py` (MAF `build_agents()`). See `agent_repo_compatibility.md` for the current
> quick reference and `.github/copilot-instructions.md` for the authoritative layout.

> **Audience:** anyone building a new agent using this workspace as a template, or migrating an existing agent to the `skills/ + scripts/ + prompts/` pattern.
> **Framework:** DOE v2 — Skills / Orchestration / Execution.
> **CommandCenter contract source of truth:** `config.json` schema (§5), `graph.py` contract (§6). If this doc and the code disagree, the code wins — update this doc.
> **Date:** 2026-06-03 · **Version:** 2.0

---

## 0. TL;DR — the framework in one table

| Artefact | Must-have | Purpose |
|---|---|---|
| `config.json` | Yes | Declares agent name, skills, integrations, model tier. |
| `graph.py` | Yes | LangGraph `build_graph()` shim — loads system prompt, bridges credentials, calls LLM. |
| `prompts/system.md` | Yes | Primary system prompt (agent identity, pipeline overview, communication rules). |
| `skills/<name>/SKILL.md` | Per skill | Instructions for a skill domain: when to use, what scripts to call, expected outputs. |
| `skills/<name>/scripts/` | Per skill | Python scripts that do the actual work for that skill. |
| `scripts/` | Yes | Shared utilities (Google Sheets sync, diagnostics, memory manager, product catalog). |
| `AGENTS.md` | Yes | Pointer file for AI coding agents — persona summary + skill/script map. |
| `data/` | Recommended | Product catalogs, templates, reference PDFs, images. See `data/INDEX.md`. |
| `outputs/{slug}/` | At runtime | Per-campaign persistent JSON files written by scripts. |
| `memories/repo/` | Recommended | Repository-scoped facts for AI coding agents working on this repo. |
| `.env` | Local only | API keys for local / VS Code Copilot Chat mode. Never committed. |
| `tests/` | Recommended | pytest suite; at minimum imports `graph.py` and calls `build_graph()`. |

This repo runs in **two modes simultaneously** with no conflicts:

| Mode | Entry point | When to use |
|---|---|---|
| **VS Code Copilot Chat** | `.github/agents/<name>.agent.md` | Local dev, rapid iteration, manually triggering pipeline steps |
| **CommandCenter orchestrator** | `graph.py` + `config.json` | Production runs, event-driven triggers, Control Plane chat, Langfuse observability |

---

## 1. Workspace folder structure

```
agent-<name>/
├── config.json               # CommandCenter agent contract
├── graph.py                  # LangGraph build_graph() shim
├── pyproject.toml            # Pip-installable package (deps)
├── AGENTS.md                 # AI coding agent instructions
├── README.md
├── compatibility.md          # This file
│
├── prompts/
│   └── system.md             # PRIMARY system prompt for CommandCenter / Anthropic mode
│
├── skills/
│   ├── <skill-name>/
│   │   ├── SKILL.md          # Instructions + frontmatter (when to use, what to call)
│   │   └── scripts/          # Python scripts for this skill
│   └── ...
│
├── scripts/                  # Shared utility scripts (not skill-specific)
│   ├── append_to_sheet.py
│   ├── campaign_data_manager.py
│   ├── self_anneal_diagnostics.py
│   └── ...
│
├── data/
│   ├── INDEX.md              # Agent-readable manifest of data/ contents
│   ├── products_catalog.json
│   └── ...
│
├── outputs/
│   ├── _memory/              # Long-term memory store (JSON + FTS5)
│   └── {campaign-slug}/      # Per-campaign step JSONs
│
├── memories/
│   └── repo/                 # Repo-scoped facts for AI coding agents
│
├── tests/
│   └── test_graph.py
│
└── .env                      # Local only — never commit
```

**Rules:**
- `config.json` and `graph.py` MUST be at the repo root.
- `prompts/system.md` is the single source of truth for the agent system prompt. Do not duplicate it in `AGENTS.md`.
- Skill instructions live in `skills/*/SKILL.md` only. Shared knowledge between skills goes in `AGENTS.md` or `prompts/system.md`.
- No credentials in the repo. Ever. Local mode reads `.env`; CommandCenter mode reads `state["integrations"]` (§8).

---

## 2. `SKILL.md` — anatomy and frontmatter

Every `skills/<name>/SKILL.md` requires YAML frontmatter:

```yaml
---
name: skill-name              # Required. Lowercase + hyphens. Must match folder name.
description: 'What this skill does and WHEN to use it. Max 1024 chars. This is the discovery surface — include trigger keywords.'
argument-hint: 'Optional hint shown when invoked as slash command'
user-invocable: true          # Default true. Set false to suppress slash-command listing.
disable-model-invocation: false # Default false. Set true to require explicit slash invocation only.
---
```

Required: `name` + `description`. Everything else is optional.

### Body structure (recommended)

```markdown
# Skill Name

One-line summary of what this skill accomplishes.

## When to Use
- Trigger condition A
- Trigger condition B

## Scripts
| Script | Purpose |
|--------|---------|
| `scripts/main_script.py` | Does the heavy lifting |
| `scripts/helper.py` | Utility used by main |

## Steps
1. Run `python skills/<name>/scripts/main_script.py --help` to confirm options.
2. ...

## Outputs
- `outputs/{slug}/step_N_<name>.json` — key fields: ...

## Edge Cases
- What to do when X fails
```

### Skill loading in `graph.py`

`graph.py` builds the system prompt by concatenating:
1. `prompts/system.md` — agent identity and pipeline overview (~6 k tokens)
2. Each `skills/*/SKILL.md` — appended as a "Tool: `<name>`" block

Updating a `SKILL.md` is immediately reflected in the next CommandCenter run without touching `graph.py`.

---

## 3. `prompts/system.md` — the primary system prompt

- Concise agent identity (who the agent is, what it does)
- Pipeline overview (numbered steps, which skill to use at each step)
- Self-annealing rules and communication rules
- References to individual `skills/*/SKILL.md` files for deep detail

**Keep it under ~400 lines.** The `graph.py` loader appends all SKILL.md files after it; a bloated `system.md` pushes skills out of context.

**Do not duplicate** skill-level detail here. Write "See `skills/research/SKILL.md`" and put the detail there.

---

## 4. `scripts/` — shared utilities

Scripts in `scripts/` are added to `sys.path` by `graph.py` at run-start, making them importable from any skill script:

```python
from self_anneal_diagnostics import run_check
from campaign_data_manager import load_step, save_step
```

Use `scripts/` for:
- Google Sheets sync (`append_to_sheet.py`, `update_sheet.py`, etc.)
- Campaign data I/O (`campaign_data_manager.py`)
- Diagnostics (`self_anneal_diagnostics.py`)

Do **not** put API-calling scripts in `scripts/` if they belong to a specific skill domain — those go in `skills/<name>/scripts/`.

---

## 5. `config.json` — canonical schema

Minimal:

```json
{
  "name": "my-agent",
  "description": "One-line description shown in the Control Plane picker.",
  "version": "0.1.0",
  "skill_repos": [],
  "max_mutation_attempts": 1
}
```

Full (all fields CommandCenter reads):

```json
{
  "name": "my-agent",
  "description": "One-line description.",
  "version": "0.1.0",
  "skill_repos": [],
  "integrations": ["anthropic", "zoho-crm", "apollo"],
  "model_tier": "tier-2",
  "execution_budget": {
    "max_runtime_seconds": 300,
    "max_llm_calls": 20,
    "max_tool_calls": 40
  },
  "triggers": {
    "cron": [],
    "webhooks": [{ "source": "zoho", "event_type": "deal.stageChange" }]
  },
  "authority": "suggest",
  "max_mutation_attempts": 1,
  "tags": ["sales", "outbound"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | str | Yes | Bare agent name, must match `agent-<name>` repo. |
| `description` | str | Yes | One line; shown in the Control Plane picker. |
| `version` | semver str | Yes | Bump on every breaking change. |
| `skill_repos` | `list[str]` | Yes (may be `[]`) | External pip-installable skill packages to inject. |
| `integrations` | `list[str]` | Yes (may be `[]`) | Credential keys from the Integration Registry. |
| `model_tier` | `"tier-1"\|"tier-2"\|"tier-3"` | Recommended | Routing hint. |
| `execution_budget` | object | Recommended | Enforced by the long-run supervisor. |
| `authority` | `"read"\|"suggest"\|"suggest_apply"\|"autonomous"` | Recommended | Default ceiling for writes via the Action Broker. |
| `max_mutation_attempts` | int | Yes | **MUST be `1`.** Constraint C-01. |

---

## 6. `graph.py` — required contract

`build_graph()` must be a **synchronous, zero-argument, pure function** returning an **uncompiled** `StateGraph`. The executor compiles it with a `PostgresSaver` checkpointer.

### Minimal template (new agent)

```python
"""my-agent — LangGraph StateGraph."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

AGENT_DIR   = Path(__file__).parent.resolve()
PROMPTS_DIR = AGENT_DIR / "prompts"
SKILLS_DIR  = AGENT_DIR / "skills"
SCRIPTS_DIR = AGENT_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class AgentState(TypedDict, total=False):
    # Core-injected (read-only)
    agent_name: str
    run_id: str
    thread_id: str
    event_payload: dict[str, Any]
    integrations: dict[str, dict[str, Any]]
    memory: dict[str, Any]
    context: dict[str, Any]
    user: dict[str, Any] | None
    # Agent-managed
    messages: list[dict[str, Any]]
    mutation_attempts: int
    error: str | None
    result: Any | None
    memories_to_save: list[dict[str, Any]]


_INTEGRATION_ENV_MAP: dict[str, dict[str, str]] = {
    "anthropic": {"ANTHROPIC_API_KEY": "api_key"},
    "zoho-crm": {
        "ZOHO_CLIENT_ID":     "client_id",
        "ZOHO_CLIENT_SECRET": "client_secret",
        "ZOHO_REFRESH_TOKEN": "refresh_token",
    },
    # add more integrations here
}

def _inject_credentials(integrations: dict[str, Any]) -> None:
    for name, field_map in _INTEGRATION_ENV_MAP.items():
        ctx = integrations.get(name, {})
        for env_var, ctx_key in field_map.items():
            value = ctx.get(ctx_key)
            if value:
                os.environ[env_var] = value


def _build_system_prompt() -> str:
    parts: list[str] = []
    system_md = PROMPTS_DIR / "system.md"
    if system_md.exists():
        parts.append(system_md.read_text(encoding="utf-8"))
        if SKILLS_DIR.exists():
            parts.append("\n\n---\n\n## Registered Skill Tool Descriptions\n")
            for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
                parts.append(
                    f"\n### Tool: {skill_md.parent.name}\n\n"
                    f"{skill_md.read_text(encoding='utf-8')}"
                )
    else:
        # Fallback: load AGENTS.md + all skills
        agents_md = AGENT_DIR / "AGENTS.md"
        if agents_md.exists():
            parts.append(agents_md.read_text(encoding="utf-8"))
        if SKILLS_DIR.exists():
            for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
                parts.append(f"\n\n{skill_md.read_text(encoding='utf-8')}")
    return "\n".join(parts)


async def chat_node(state: AgentState) -> dict[str, Any]:
    from acb_llm import LLMTier, complete

    _inject_credentials(state.get("integrations") or {})

    payload = state.get("event_payload") or {}
    history = list(payload.get("messages") or state.get("messages") or [])
    latest: str = payload.get("message") or ""
    if not latest and history:
        for m in reversed(history):
            if m.get("role") == "user":
                latest = m.get("content", "")
                break
    if not latest:
        return {"result": {"role": "assistant", "content": "No message received."}}

    system = _build_system_prompt()

    # Inject Core memory context
    memory = state.get("memory") or {}
    if memory:
        facts = memory.get("user_facts", []) + memory.get("session_facts", [])
        graph_ctx = memory.get("graph_context", [])
        if facts or graph_ctx:
            system += "\n\n# Memory from previous sessions\n"
            for f in facts:
                system += f"\n- {f}"
            for g in graph_ctx:
                system += f"\n- [{g.get('entity','')}] {g.get('summary','')}"

    # Inject executor-provided prospect/entity memories
    context_memories = (state.get("context") or {}).get("memories", [])
    if context_memories:
        system += "\n\n# Known facts (from memory)\n"
        for m in context_memories:
            system += f"\n- [{m.get('entity','')}] {m.get('fact','')}"

    messages_for_llm = history + [{"role": "user", "content": latest}]
    response: str = await complete(
        tier=LLMTier.TIER_2,
        messages=[{"role": "system", "content": system}] + messages_for_llm,
    )

    # Extract <mem>...</mem> tags (Anthropic stateless memory pattern)
    memories_to_save = [
        {"text": m.group(1).strip(), "category": "fact", "confidence": 0.85}
        for m in re.finditer(r"<mem>(.*?)</mem>", response, re.DOTALL)
    ]
    response_clean = re.sub(r"<mem>.*?</mem>", "", response, flags=re.DOTALL).strip()

    return {
        "result": {"role": "assistant", "content": response_clean},
        "messages": messages_for_llm + [{"role": "assistant", "content": response_clean}],
        "memories_to_save": memories_to_save,
    }


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("chat", chat_node)
    g.add_edge(START, "chat")
    g.add_edge("chat", END)
    return g
```

### Hard rules

- `build_graph()` is synchronous, zero-argument, pure. No I/O at import time.
- State MUST be a `TypedDict` (or `pydantic.BaseModel` with `arbitrary_types_allowed=True`).
- Nodes SHOULD be `async def`.
- On success, set `state["result"]` to a JSON-serialisable value.
- On failure, **raise** — do not swallow. The executor routes to `Self_Mutation_Node`.
- Never read `os.environ[...]` for secrets inside graph nodes — use `state["integrations"]` + `_inject_credentials`.
- Do not call `.compile()` inside `build_graph()` — the executor adds a checkpointer.

---

## 7. Memory pattern — `memories_to_save` via `<mem>` tag

Agents use the **Anthropic stateless memory pattern**:

1. Executor injects prior memories into the system prompt via `state["context"]["memories"]`.
2. The LLM emits durable facts wrapped in `<mem>...</mem>` tags anywhere in its response.
3. `graph.py` extracts those tags, strips them from the visible reply, and returns them in `state["memories_to_save"]`.
4. The executor persists them; they appear as context in future runs.

```
# Raw LLM output:
"Manu is interested in silicone printing. <mem>Dr Manu Srinivas prefers in-person demos at Fracktal office</mem>"

# After stripping:
result.content  →  "Manu is interested in silicone printing."
memories_to_save → [{"text": "Dr Manu Srinivas prefers in-person demos at Fracktal office", ...}]
```

Rules: ≤ 2 `<mem>` tags per turn · each ≤ 200 chars · `category ∈ {fact, preference, decision, open_question}`.

The `skills/agent-memory/` skill provides a parallel **local** memory store in `outputs/_memory/` (JSON + FTS5 SQLite) for cross-campaign search within this agent.

---

## 8. Integrations — credential flow

**CommandCenter mode:** credentials come from `state["integrations"]`. `_inject_credentials()` bridges them into `os.environ`.

**Local / VS Code mode:** credentials come from `.env` (loaded by `python-dotenv`).

Skill scripts always read `os.getenv(...)` — works in both modes unchanged.

Integration name → `.env` variable mapping for `agent-sales-assistant`:

| Integration key | `.env` variable(s) |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `apollo` | `APOLLO_API_KEY` |
| `serpapi` | `SERPAPI_API_KEY` |
| `apify` | `APIFY_API_TOKEN` |
| `anymailfinder` | `ANYMAILFINDER_API_KEY` |
| `instantly` | `INSTANTLY_API_KEY` |
| `zoho-crm` | `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` |
| `google-sheets` | `GOOGLE_SHEETS_CREDENTIALS_FILE` |

---

## 9. Chat-mode contract (Control Plane chat surface)

`POST /agent/run` per turn:

```json
{
  "agent": "my-agent",
  "payload": {
    "mode": "chat",
    "message": "<latest user message>",
    "messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
    "session_id": "<stable session uuid>"
  },
  "thread_id": "<session uuid>"
}
```

Read `state["event_payload"]["messages"]` + `state["event_payload"]["message"]`. Return:

```python
state["result"] = {"role": "assistant", "content": "<text>"}
```

Stay idempotent on retry — the gateway may replay the same `run_id`.

---

## 10. Dual-mode operation

Both modes share the same source of truth: `prompts/system.md` + `skills/*/SKILL.md`.

| | VS Code Copilot Chat | CommandCenter |
|---|---|---|
| Entry point | `.github/agents/<name>.agent.md` | `graph.py` + `config.json` |
| System prompt | Agent reads files directly via tools | `graph.py` `_build_system_prompt()` |
| Credentials | `.env` / `python-dotenv` | `state["integrations"]` + `_inject_credentials()` |
| Scripts | Run via VS Code terminal tools | Run as subprocess or imported via `sys.path` |
| Outputs | `outputs/{slug}/` (local disk) | `outputs/{slug}/` (persistent clone on executor) |
| Memory | `outputs/_memory/` (local JSON/FTS5) | `state["memories_to_save"]` + `outputs/_memory/` |

**Rule:** Adding `graph.py` and `config.json` does not touch any existing file. VS Code Copilot Chat continues to work exactly as before.

---

## 11. `AGENTS.md` — pointer file for AI coding agents

Template:

```markdown
# Agent Instructions — My Agent

> You are a [brief persona description].

## Architecture (3-layer DOE v2)

**Layer 1: Skills (`skills/*/SKILL.md`)** — instructions for each capability domain.
**Layer 2: Orchestration (YOU)** — read skills, call scripts in the right order, handle errors.
**Layer 3: Execution (`skills/*/scripts/`, `scripts/`)** — Python scripts that do the work.

## Skills

| Skill | SKILL.md | Purpose |
|---|---|---|
| my-skill | `skills/my-skill/SKILL.md` | Does X |

## Shared Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `campaign_data_manager.py` | Load/save step JSON files |
| `self_anneal_diagnostics.py` | Health checks + learnings log |

## File Organisation

- `outputs/{slug}/` — per-campaign step JSONs
- `data/` — product catalogs, templates (see `data/INDEX.md`)
- `.env` — API keys (local only, never commit)
```

---

## 12. `outputs/` — persistent campaign data

```
outputs/
├── _memory/
│   ├── agent_long_term_memory.json
│   ├── agent_memory_index.json
│   └── learnings_log.json
└── {campaign-slug}/
    ├── step_1_product_analysis.json
    ├── step_2_competitive_analysis.json
    ├── step_3_industry_targeting.json
    ├── step_4_company_prospects.json
    ├── step_5_decision_makers.json
    ├── step_6_outreach_sequences.json
    ├── step_7_campaign_tracker.json
    └── campaign_config.json
```

---

## 13. Self-annealing pattern

Every agent built on this framework implements the self-annealing loop via `skills/self-annealing/SKILL.md`:

```
DETECT → DIAGNOSE → FIX → TEST → RECORD → UPDATE → STRONGER
```

Mandatory health checks (via `python scripts/self_anneal_diagnostics.py`):

| When | Check |
|---|---|
| Before any campaign | `--check api_health` |
| Before Step 4 | `--check web_scraping` |
| After each step | `--check step_validation --step N` |
| After Steps 4-5-6 | `--check data_quality` |
| Before user review | `--check all` |

---

## 14. `tests/` — minimum viable test

```python
# tests/test_graph.py

def test_build_graph_importable():
    from graph import build_graph
    from langgraph.graph import StateGraph
    assert isinstance(build_graph(), StateGraph)

def test_graph_has_chat_node():
    from graph import build_graph
    assert "chat" in build_graph().nodes
```

---

## 15. Anti-patterns

- `os.environ["..."]` reads for secrets inside `graph.py` nodes.
- `requests.get(...)` or any I/O at module import time.
- `build_graph()` that takes arguments or performs I/O.
- Calling `.compile()` inside `build_graph()`.
- `max_mutation_attempts > 1` or missing.
- Mutable module-level state used to cache results across runs (use the checkpointer).
- Agent persona duplicated in both `prompts/system.md` AND `AGENTS.md` — one source of truth.
- Skill instructions in `prompts/system.md` — put them in `skills/<name>/SKILL.md`; `graph.py` appends them automatically.
- Catching `Exception` and returning `{"error": ...}` instead of raising.

---

## 16. Building a new agent — checklist

1. Copy this repo as a template. Rename to `agent-<name>`.
2. Edit `config.json` — update `name`, `description`, `integrations`, `tags`.
3. Edit `prompts/system.md` — agent identity, pipeline overview, communication rules.
4. Edit `AGENTS.md` — persona summary + skill/script map for AI coding agents.
5. Create `skills/<name>/` for each capability:
   - `SKILL.md` with frontmatter + body
   - `scripts/` with Python scripts for that skill
6. Edit `graph.py` — update `_INTEGRATION_ENV_MAP` for your integrations.
7. Edit `pyproject.toml` — update `name` and `dependencies`.
8. Add `tests/test_graph.py` with the `build_graph()` import test.
9. Smoke test: `python -c "from graph import build_graph; print(build_graph())"`.
10. Register in CommandCenter: add `"my-agent"` to `_KNOWN_AGENTS` in `apps/gateway/gateway/routes/agent.py`.

---

## 17. This agent (`agent-sales-assistant`) — quick reference

**9 skills:**

| Skill | SKILL.md | Description |
|---|---|---|
| `prospect-pipeline` | `skills/prospect-pipeline/SKILL.md` | 7-step outbound pipeline |
| `research` | `skills/research/SKILL.md` | Web + academic + document research |
| `proposal` | `skills/proposal/SKILL.md` | Proposal authoring and rendering |
| `crm-ops` | `skills/crm-ops/SKILL.md` | Zoho CRM + Instantly integration |
| `lead-scraping` | `skills/lead-scraping/SKILL.md` | Google Maps, SERP, Apify lead discovery |
| `gem-competition` | `skills/gem-competition/SKILL.md` | GeM tender strategy for Indian OEM/MSME |
| `agent-memory` | `skills/agent-memory/SKILL.md` | Two-tier memory (JSON + FTS5) |
| `sales-methodology` | `skills/sales-methodology/SKILL.md` | Tracy, Blount, Cardone, Ross, Weinberg, Rackham |
| `self-annealing` | `skills/self-annealing/SKILL.md` | Error recovery + continuous improvement |

**Integrations:** `anthropic`, `apollo`, `serpapi`, `apify`, `anymailfinder`, `instantly`, `zoho-crm`, `google-sheets`

**Dual-mode:** VS Code Copilot Chat (`.github/agents/agent-sales-assistant.agent.md`) + CommandCenter (`graph.py` / `config.json`) — both read the same `prompts/system.md` + `skills/*/SKILL.md` source of truth.

---

## 18. Versioning

Breaking changes get a version bump in `config.json` and an entry in `CHANGELOG.md`.
For CommandCenter Core questions, open an issue on `CommandCenter-Core` with label `agent-spec`.
