---
name: project-memory
description: 'Dual-tier persistent memory for projects, decisions, risks, and company context. Tier 1 is JSON working memory loaded at session start. Tier 2 is SQLite FTS5 for deep historical search. Stores risks, open questions, follow-ups, and lessons learned. Trigger keywords: remember, recall, save, what did we decide, risks, follow-up, what did we say about, past context, open questions, history.'
argument-hint: 'What do you want to store or retrieve?'
user-invocable: true
disable-model-invocation: false
---

# Project Memory

The agent's institutional knowledge base. Every decision, risk, open question, and lesson learned is persisted here so nothing is lost between sessions.

## Memory Architecture

> **Quick rule for simple agents:** Always try Tier 1 JSON files first — they load instantly. Only call `memory_search.py` (Tier 2) if the answer cannot be found in the JSON files or if explicitly asked about history/past decisions.

### Tier 1 — Working Memory (JSON files, loaded at session start)

| File | Contents |
|---|---|
| `outputs/_memory/company_context.json` | Company stage, active projects, priorities, key relationships |
| `outputs/_memory/project_registry.json` | All projects with slug, status, ClickUp IDs, owners, key dates |
| `outputs/_memory/open_questions.json` | Outstanding unknowns that need answers before plans can close |
| `outputs/_memory/risk_log.json` | Active and closed risks across all projects |
| `outputs/_memory/decision_journal.json` | Key decisions with date, rationale, owner, outcome |
| `outputs/_memory/follow_ups.json` | Tasks flagged for follow-up with due dates and assignees |
| `outputs/_memory/lessons_learned.json` | Post-mortem findings, recurring failure patterns |
| `outputs/_memory/interaction_log.json` | Summary of past agent sessions (last 20, compressed) |

### Tier 2 — Long-Term Search (SQLite FTS5)

File: `outputs/_memory/project_memory.db`

| Table | Indexed Fields | Use |
|---|---|---|
| `facts` | entity, content, tags | Atomic searchable facts |
| `decisions` | project, decision, context, outcome | Decision history |
| `risks` | project, risk, category, status | Risk history |
| `interactions` | summary, topics, date | Session history |
| `entities` | name, type, description | People, vendors, tools, repos |
| `lessons` | title, pattern, fix | Recurring failure patterns |

**Query:** `python scripts/memory_search.py --query "<text>" [--project <slug>] [--type facts|decisions|risks]`

---

## Memory Retrieval Routing

Use this tree before every substantive response:

```
Is the topic about CURRENT PROJECT STATE?
  (active tasks, current blockers, who owns what)
  → Tier 1 — project_registry.json + follow_ups.json

Is the answer clearly visible in loaded JSON files?
  → Tier 1. Don't search if you already have it.

Does the question reference a SPECIFIC PAST DECISION or EVENT?
  ("what did we decide about X?", "when did we approve Y?")
  → Tier 2 via memory_search.py --type decisions

Does it mention a PERSON, VENDOR, or TOOL not in current JSON?
  → Tier 2 via memory_search.py --type entities

Is this a question about PATTERNS or RECURRING PROBLEMS?
  ("have we seen this before?", "why does X keep failing?")
  → Tier 2 via memory_search.py --type lessons

Is the agent about to give advice on a MAJOR DECISION?
  → Use BOTH tiers. Pull full project history before recommending.

DEFAULT: Tier 1.
```

---

## What to Persist and When

### After every session, save:
- Any new decision made → `decision_journal.json` + Tier 2 `decisions` table
- Any new risk identified → `risk_log.json` + Tier 2 `risks` table
- Any open question raised → `open_questions.json`
- Any follow-up promised → `follow_ups.json`
- Any new person/vendor/tool mentioned → Tier 2 `entities` table
- Session summary → `interaction_log.json` (compressed, ≤ 5 sentences)

### Trigger: "What are our open risks?"
→ Load `risk_log.json`, filter status=open, sort by score descending, present.

### Trigger: "What did we decide about X?"
→ Search `decision_journal.json` first. If not found → Tier 2 `decisions` search.

### Trigger: "Any follow-ups due this week?"
→ Load `follow_ups.json`, filter due_date ≤ today+7, present sorted by due date.

### Trigger: "Lessons learned from project Y?"
→ Filter `lessons_learned.json` by project. Augment with Tier 2 search.

---

## Risk Log Schema

```json
{
  "id": "R-2026-031",
  "project": "penrose-pellet-extruder",
  "title": "Auger lead time > 2 weeks",
  "category": "supply_chain",
  "probability": "medium",
  "impact": "high",
  "score": 6,
  "mitigation": "Order from 2 vendors in parallel",
  "owner": "Ayush Sarkar",
  "status": "open",
  "created": "2026-06-04",
  "updated": "2026-06-04",
  "review_due": "2026-06-11"
}
```

---

## Decision Journal Schema

```json
{
  "id": "D-2026-018",
  "project": "penrose-pellet-extruder",
  "decision": "Use Word doc format for user manual (not LaTeX)",
  "rationale": "Faster iteration, existing team knows Word, customer expects editable format",
  "owner": "Kiran Kumar",
  "date": "2026-06-03",
  "outcome": null,
  "review_date": null
}
```

---

## Follow-Up Schema

```json
{
  "id": "FU-2026-047",
  "project": "penrose-pellet-extruder",
  "task": "Confirm barrel dimensions with machinist before EDM grooving",
  "assignee": "Suryansh Lal",
  "due_date": "2026-06-05",
  "status": "open",
  "created": "2026-06-04",
  "note": "Dimensions must match CAD rev C"
}
```

---

## Memory Update Rules

1. **Update in real time during conversation** — do not wait until the end of a session.
2. Never lose a decision. If it was made, log it, even if it feels minor.
3. When a risk is mitigated or closed, update its status and log the outcome.
4. When a follow-up is resolved, mark it closed with the resolution note.
5. Keep `interaction_log.json` capped at 20 entries (drop oldest, keep summaries).
6. Never store secrets (API keys, passwords) in any memory file.
7. When the same failure pattern appears twice, write a `lessons_learned.json` entry.

---

## Pre-Response Memory Check

Before every substantive response, ask internally:

1. **Do I have enough Tier 1 context to answer this well?** If NO → query Tier 2.
2. **Am I about to ask something already answered in memory?** Search before asking.
3. **Did the user share new facts?** Update memory files as part of this response.
4. **Are there open risks or follow-ups relevant to this topic?** Surface them proactively.

A project manager who doesn't remember last week's decisions is a liability. This memory system is the agent's institutional trust.
