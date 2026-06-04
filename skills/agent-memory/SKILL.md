---
name: agent-memory
description: 'Dual-tier persistent memory for project facts, decisions, risks, open questions, and follow-ups. Tier 1 is JSON (loaded at session start). Tier 2 is SQLite FTS5 (queried on demand). Stores HR decisions, project history, delegation context, risk log, and lessons learned. Trigger keywords: remember, recall, save fact, look up, past context, what did we decide, history, risks, follow-ups, open questions.'
argument-hint: 'What do you want to remember or recall?'
user-invocable: true
disable-model-invocation: false
---

# Agent Memory

Store and retrieve durable facts about projects, people, risks, decisions, and follow-ups so they are available in every future session.

> **This skill is the lightweight session interface.** For the full dual-tier architecture, risk log, decision journal, and follow-up schemas, see `skills/project-memory/SKILL.md`.

## When to Use
- After a key decision is made (e.g., "we decided to delay Phase 2 by 2 weeks")
- When a user asks "what did we decide about X?"
- To recall project history or past delegation choices
- To store HR-related facts (e.g., "Suryansh is on site in Hisar until June 10")
- When a new risk is identified during planning or tracking
- When a follow-up is promised during a conversation

## Memory Tiers

| Tier | Location | Lifetime | What to store |
|---|---|---|---|
| **Stateless** | `<mem>` tags in response | Session | Quick facts, ≤ 200 chars |
| **Tier 1 JSON** | `outputs/_memory/*.json` | Permanent | Structured facts — projects, risks, decisions, follow-ups |
| **Tier 2 SQLite** | `outputs/_memory/project_memory.db` | Permanent | Full-text search across all history |

## `<mem>` Tag Rules

- Emit ≤ 2 `<mem>` tags per turn.
- Each ≤ 200 chars.
- Categories: `fact`, `preference`, `decision`, `open_question`, `risk`, `follow_up`.

Examples:
```
We confirmed IST semantics for ClickUp due dates. <mem>ClickUp due dates set to IST show as previous day UTC — this is correct, do not shift</mem>
Penrose auger is on order from two vendors. <mem>Penrose risk R-001 mitigated: auger ordered from 2 vendors in parallel</mem>
```

## Key Memory Files (Tier 1)

| File | Contents |
|---|---|
| `outputs/_memory/company_context.json` | Company stage, active projects, priorities |
| `outputs/_memory/project_registry.json` | All projects with ClickUp IDs, Doc IDs, external links |
| `outputs/_memory/risk_log.json` | Active and closed risks with scores and owners |
| `outputs/_memory/decision_journal.json` | Key decisions with date, rationale, outcome |
| `outputs/_memory/follow_ups.json` | Open follow-ups with assignees and due dates |
| `outputs/_memory/open_questions.json` | Unresolved questions blocking a plan or decision |
| `outputs/_memory/lessons_learned.json` | Failure patterns and their fixes |
| `outputs/_memory/interaction_log.json` | Past session summaries (last 20, compressed) |
| `outputs/_memory/agent_long_term_memory.json` | Legacy catch-all facts store (kept for backward compat) |

## Quick Reference: What to Persist When

| Event | File to Update |
|---|---|
| Decision made | `decision_journal.json` |
| Risk identified | `risk_log.json` |
| Follow-up promised | `follow_ups.json` |
| Unresolved question | `open_questions.json` |
| New external link (GitHub, Notion, etc.) | `project_registry.json` |
| Lesson from a failure | `lessons_learned.json` |
| New session summary | `interaction_log.json` |

## Proactive Surfacing Rules

At the start of any project-related conversation, check and surface:
- **Open risks** with score ≥ 6 for the relevant project.
- **Follow-ups** due within 7 days for the relevant project.
- **Open questions** that block the current conversation topic.

Do not wait for the user to ask about these. If they exist, mention them briefly at the top of the response.
