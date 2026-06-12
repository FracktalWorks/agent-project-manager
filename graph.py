"""agent-project-manager — LangGraph StateGraph."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

AGENT_DIR   = Path(__file__).parent.resolve()
INSTRUCTIONS_FILE = AGENT_DIR / "instructions.md"
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
    "clickup": {
        "CLICKUP_API_TOKEN": "api_token",
        "CLICKUP_TEAM_ID":   "team_id",
    },
}


def _inject_credentials(integrations: dict[str, Any]) -> None:
    for name, field_map in _INTEGRATION_ENV_MAP.items():
        ctx = integrations.get(name, {})
        for env_var, ctx_key in field_map.items():
            value = ctx.get(ctx_key)
            if value:
                os.environ[env_var] = value


# Skills are loaded in priority order so critical rules appear early in context.
_SKILL_LOAD_ORDER = [
    "clickup-ops",
    "hr-structure",
    "task-capture",
    "project-planning",
    "project-tracking",
    "project-breakdown",
    "project-memory",
    "agent-memory",
    "clickup-docs",
    "external-integrations",
    "self-annealing",
    "technical-planning",
]


def _build_system_prompt() -> str:
    parts: list[str] = []
    if INSTRUCTIONS_FILE.exists():
        parts.append(INSTRUCTIONS_FILE.read_text(encoding="utf-8"))
        if SKILLS_DIR.exists():
            parts.append("\n\n---\n\n## Skill Reference Library\n")
            loaded: set[str] = set()
            for skill_name in _SKILL_LOAD_ORDER:
                skill_md = SKILLS_DIR / skill_name / "SKILL.md"
                if skill_md.exists():
                    parts.append(
                        f"\n### Skill: {skill_name}\n\n"
                        f"{skill_md.read_text(encoding='utf-8')}"
                    )
                    loaded.add(skill_name)
            for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
                if skill_md.parent.name not in loaded:
                    parts.append(
                        f"\n### Skill: {skill_md.parent.name}\n\n"
                        f"{skill_md.read_text(encoding='utf-8')}"
                    )
    else:
        agents_md = AGENT_DIR / "AGENTS.md"
        if agents_md.exists():
            parts.append(agents_md.read_text(encoding="utf-8"))
        if SKILLS_DIR.exists():
            loaded_: set[str] = set()
            for skill_name in _SKILL_LOAD_ORDER:
                skill_md = SKILLS_DIR / skill_name / "SKILL.md"
                if skill_md.exists():
                    parts.append(f"\n\n{skill_md.read_text(encoding='utf-8')}")
                    loaded_.add(skill_name)
            for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
                if skill_md.parent.name not in loaded_:
                    parts.append(f"\n\n{skill_md.read_text(encoding='utf-8')}")
    return "\n".join(parts)


async def chat_node(state: AgentState) -> dict[str, Any]:
    from acb_llm import LLMTier, complete

    _inject_credentials(state.get("integrations") or {})

    payload  = state.get("event_payload") or {}
    history  = list(payload.get("messages") or state.get("messages") or [])
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
        facts      = memory.get("user_facts", []) + memory.get("session_facts", [])
        graph_ctx  = memory.get("graph_context", [])
        if facts or graph_ctx:
            system += "\n\n# Memory from previous sessions\n"
            for f in facts:
                system += f"\n- {f}"
            for g in graph_ctx:
                system += f"\n- [{g.get('entity','')}] {g.get('summary','')}"

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

    # Extract <mem>...</mem> tags (stateless memory pattern)
    memories_to_save = [
        {"text": m.group(1).strip(), "category": "fact", "confidence": 0.85}
        for m in re.finditer(r"<mem>(.*?)</mem>", response, re.DOTALL)
    ]
    response_clean = re.sub(r"<mem>.*?</mem>", "", response, flags=re.DOTALL).strip()

    return {
        "result":           {"role": "assistant", "content": response_clean},
        "messages":         messages_for_llm + [{"role": "assistant", "content": response_clean}],
        "memories_to_save": memories_to_save,
    }


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("chat", chat_node)
    g.add_edge(START, "chat")
    g.add_edge("chat", END)
    return g
