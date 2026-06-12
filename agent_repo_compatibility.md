# Agent Builder Guide - Skills + Scripts + CommandCenter Framework

> **Audience:** anyone building a new agent using this workspace as a template.
> **Framework:** DOE v2 - Skills / Orchestration / Execution.
> **Date:** 2026-06-12 **Version:** 2.2

## Quick Reference (v2.2 changes from v2.1)

- Skills moved from skills/ to .github/skills/ (GitHub Copilot convention)
- Prompts moved from prompts/ to .github/prompts/
- Rewrote .github/copilot-instructions.md (repo-wide Copilot context: architecture, build/test, layout)
- Added 5 path-scoped instructions in .github/instructions/ (outputs, .tmp, scripts, python standards, skill authoring)
- Added 4 reusable prompt files (morning-report, diagnose, plan-project, project-status)
- Added .tmp/ convention: utilities + cache READMEs tracked; cache data gitignored
- Added outputs/README.md manifest; outputs/ organised per outputs-folder.instructions.md
- Path resolution fixed in all skill scripts after .github/ restructure (repo root = parents[4])
- agents.py loads .github/prompts/system.md + .github/skills/*/SKILL.md
- graph.py retained for reference only; LangGraph removed from stack

## Core Contract (unchanged)

| Artefact | Purpose |
|---|---|
| config.json | CommandCenter agent contract (name, integrations, model tier, authority, max_mutation_attempts: 1) |
| agents.py | MAF entry point - build_agents() -> list[BaseAgent]; synchronous, zero-argument, no I/O at import time |
| .github/prompts/system.md | Primary system prompt; skills appended automatically by _build_system_prompt() |
| .github/skills/*/SKILL.md | Per-skill instructions (frontmatter: name, description, argument-hint, user-invocable) |
| scripts/ | Shared utilities, added to sys.path at runtime |

Dual-mode: VS Code Copilot Chat (.github/agents/agent-project-manager.agent.md) +
CommandCenter (agents.py / config.json) - both read the same .github/prompts/system.md +
.github/skills/*/SKILL.md source of truth.

Credentials: os.getenv(...) in scripts works in both modes (.env locally; injected by the
Dynamic Agent Loader from the Integration Registry in CommandCenter).

For full details, read the source files:

- .github/copilot-instructions.md
- .github/instructions/*.instructions.md (5 files)
- .github/prompts/*.prompt.md (4 files)
- .github/skills/*/SKILL.md (13 skills)
- AGENTS.md
- tests/
- outputs/README.md
