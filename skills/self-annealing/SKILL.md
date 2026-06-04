---
name: self-annealing
description: 'Detect, diagnose, and recover from errors during agent operation. Runs health checks, validates API connectivity, records learnings, and updates the agent to handle similar failures in future. Trigger keywords: error, failed, broken, fix, debug, health check, retry, diagnostic, not working.'
argument-hint: 'Describe the error or run --check all for a full diagnostic.'
user-invocable: true
disable-model-invocation: false
---

# Self-Annealing

DETECT → DIAGNOSE → FIX → TEST → RECORD → UPDATE → STRONGER

## When to Use
- Any script raises an unexpected error
- ClickUp API calls fail or return unexpected data
- User reports something is not working
- Before any major operation (run `--check api_health` first)
- After a fix — verify with `--check all`

## Health Checks

| When | Command |
|---|---|
| Before any project operation | `python scripts/self_anneal_diagnostics.py --check api_health` |
| After task creation | `python scripts/self_anneal_diagnostics.py --check clickup_connectivity` |
| After data changes | `python scripts/self_anneal_diagnostics.py --check data_integrity` |
| Full diagnostic | `python scripts/self_anneal_diagnostics.py --check all` |

## Recovery Steps

1. **Detect** — error is raised, agent captures the full traceback.
2. **Diagnose** — classify: API error (auth, rate limit, not found), data error (missing field, bad JSON), logic error.
3. **Fix** — apply the smallest possible fix (do NOT change unrelated code).
4. **Test** — re-run the failed step with `--dry-run` if available.
5. **Record** — append to `outputs/_memory/learnings_log.json`:
   ```json
   {"date": "...", "error": "...", "fix": "...", "prevention": "..."}
   ```
6. **Update** — if the fix is a pattern, update the relevant SKILL.md Edge Cases section.

## Common Fixes

| Error | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` | Invalid/expired CLICKUP_API_TOKEN | Re-generate token in ClickUp settings |
| `404 Not Found` on task | Task ID stale (was deleted) | Re-fetch IDs via `clickup_client.py --list-tasks` |
| `429 Rate Limit` | Too many requests | Wait 62 s, retry once |
| `FileNotFoundError: hr_structure.json` | Data file not populated | Ask user to fill `data/hr_structure.json` |
| `KeyError: 'slug'` in plan JSON | Plan not fully generated | Re-run `plan_project.py` |
