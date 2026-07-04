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

## Known Failure Patterns (Lessons Learned)

| # | Pattern | Symptom | Root Cause | Fix |
|---|---------|---------|------------|-----|
| L-001 | ClickUp assignees not set | Task created (200 OK), assignees empty in UI | `PUT /task/{id}` silently ignores assignees. Wrong format `[{"id":...}]` used. | Set assignees only via POST at creation; use flat int list `[12345]`. See `clickup-ops` API Rules. |
| L-002 | ClickUp status error on task creation | `{"err":"Status not found","ECODE":"CRTSK_001"}` | Status string doesn't match list's exact status names | Fetch list first (`GET /list/{id}`), use exact status string from response |
| L-003 | Due dates off by one day | Task shows as due on wrong date in ClickUp UI | `datetime(yyyy, mm, dd)` converts to midnight UTC, which is previous day in IST | Use `datetime(yyyy, mm, dd, 18, 0)` and set `"due_date_time": False` |
| L-004 | Subtask creation 404 | `/task/{id}/subtask` returns 404 | Endpoint doesn't exist in this workspace's API version | Use `POST /list/{list_id}/task` with `"parent": parent_task_id` |
| L-005 | PDF emojis render as blank boxes | Emojis missing in PDF even though MD shows them correctly | No colour emoji font (Noto Color Emoji) installed on Linux | `sudo apt-get install fonts-noto-color-emoji && fc-cache -fv` |
| L-006 | Chromium fails to launch on Linux | `TargetClosedError: ... libatk-1.0.so.0: cannot open shared object file` | Missing system deps for headless Chromium | Install deps: `sudo apt-get install libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 libnspr4 libnss3` |
| L-007 | WeasyPrint produces emoji-less PDFs | PDF looks structurally correct but emojis are blank squares | WeasyPrint doesn't support coloured emoji glyphs | Always use the Playwright+Chromium pipeline (`convert_md_to_pdf.py`); never fall back to weasyprint for reports with emojis |
| L-008 | `run_diagnostics` MAF tool reports "Tool execution failed" | Tool error even though script works fine when run directly | `_run()` in `agents.py` raises `RuntimeError` on non-zero exit; diagnostics script exits 1 when issues found (which is expected) | Rewrote `run_diagnostics()` to use `subprocess.run` directly, returning stdout/stderr regardless of exit code |

## Common Fixes

| Error | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` | Invalid/expired CLICKUP_API_TOKEN | Re-generate token in ClickUp settings |
| `404 Not Found` on task | Task ID stale (was deleted) | Re-fetch IDs via `clickup_client.py --list-tasks` |
| `429 Rate Limit` | Too many requests | Wait 62 s, retry once |
| `FileNotFoundError: hr_structure.json` | Data file not populated | Ask user to fill `data/hr_structure.json` |
| `KeyError: 'slug'` in plan JSON | Plan not fully generated | Re-run `plan_project.py` |
