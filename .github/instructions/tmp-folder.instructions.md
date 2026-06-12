---
applyTo: ".tmp/**"
description: "Organisation and cleanup rules for the .tmp/ folder. Enforced whenever the agent creates, modifies, or cleans up temporary files."
---

# .tmp/ Folder Organisation

## What .tmp/ IS For

Only these categories of files may be placed in `.tmp/`:

### 1. Reusable Utility Scripts
Small Python scripts that perform a specific, repeatable fix-up task used across projects.
- Must have a clear docstring explaining what they fix and when to use them
- Must be runnable standalone with `--help`
- If a utility proves valuable across 3+ projects, promote it to `scripts/` at repo root

### 2. API Response Caches
Subdirectories that cache paid or rate-limited API responses (e.g. SerpAPI, web scraping).
- Each cache directory must have a README.md explaining the cache format and TTL
- Cache entries older than 48 hours should be considered stale
- Never commit cache directories that contain API keys or PII

### 3. Short-Lived Intermediate Files
Files generated during a multi-step operation that are consumed by the next step and then deleted.
- MUST be deleted by the script that created them once consumed
- If a script crashes, clean up its intermediate files on the next run
- Maximum lifetime: duration of the current agent turn

## What .tmp/ is NOT For

### FORBIDDEN: One-Off Debug Scripts
Scripts like `check_*.py`, `verify_*.py`, `test_*.py`, `find_*.py` written to diagnose a single issue.
- Delete these immediately after the issue is resolved
- If the logic is reusable, extract it into the appropriate skill's `scripts/` directory

### FORBIDDEN: ClickUp Data Dumps
JSON files containing raw ClickUp API responses (tasks, lists, members).
- ClickUp caches belong in `outputs/_memory/` (e.g. `workspace_lists.json`)
- If you need a snapshot for debugging, write it to the project directory, not `.tmp/`

### FORBIDDEN: Project-Specific Artifacts
Files tied to a single project (e.g. `julia_*.py`, one-shot task-creation scripts).
- These belong in `outputs/{slug}/` for that project, or should be deleted after use
- Use `.github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py --plan` with a
  `tasks.json` plan instead of writing one-off creation scripts

### FORBIDDEN: Duplicate Functionality
Scripts that duplicate what an existing skill script already does.
- Always check `.github/skills/*/scripts/` and `scripts/` before writing a throwaway script
- Use the skill script with the right arguments instead

## Self-Cleaning Rules

After EVERY agent turn that creates files in `.tmp/`:
1. Delete any intermediate files created during that turn that are no longer needed
2. If `.tmp/` has more than 20 files (excluding caches), prompt the user: ".tmp/ has N files. Clean up?"
3. Never leave behind scripts named `check_*.py`, `verify_*.py`, `test_*.py`, or `find_*.py`
