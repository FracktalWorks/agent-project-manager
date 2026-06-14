---
applyTo: ".github/skills/**/scripts/**/*.py"
description: "Coding standards for Python scripts in skill directories. Enforced when agent creates or edits any skill script."
---

# Python Script Standards

## Credential Handling

- Always use `os.getenv("VAR_NAME")` — never hardcode credentials
- Load `.env` from the repo root (python-dotenv or a manual parser) at module top
- If a required env var is missing, print a clear error and `sys.exit(1)`
- Never log or print API keys, tokens, or secrets

## ClickUp API (Mandatory — violations cause silent failures)

- Assignees: flat int list only (`"assignees": [100842373]`), set at creation via POST
- Subtasks: POST to `/list/{id}/task` with `"parent": pid` — never `/task/{id}/subtask`
- Always send `Content-Type: application/json` alongside `Authorization`
- Due dates: 18:00 local (or noon UTC), never midnight — avoids IST off-by-one
- Status: use exact strings fetched from the list, never guess
- On 429: sleep 62s and retry ONCE; `max_mutation_attempts = 1` for all other failures

## Error Handling

- Wrap API calls in try/except with specific exception types (not bare except)
- On final failure: print clear error with failing URL/endpoint, then `sys.exit(1)`
- Scripts must return non-zero exit codes on failure

## CLI Conventions

- Use argparse for all CLI scripts; always support `--help`
- Support `--dry-run` for any script that writes to ClickUp
- Output JSON to stdout for structured data; `print()` for human summaries

## Imports and Paths

- Use `pathlib.Path` for file paths, never string concatenation
- Repo root from a skill script is `Path(__file__).resolve().parents[4]`
  (script → scripts/ → skill/ → skills/ → .github/ → root) ← outdated after skills/ moved into .github/skills/; now 5 levels: script → scripts/ → skill/ → skills/ → .github/ → root
- Add `scripts/` to sys.path when importing shared utilities
- List new dependencies in `pyproject.toml`

## File I/O

- Use `Path.read_text()` / `Path.write_text()` with `encoding='utf-8'`
- JSON: `json.dump(data, f, indent=2, ensure_ascii=False)`
- Never overwrite files without confirmation; use `.tmp/` for intermediates

## Naming Conventions

- Script files: `snake_case.py`
- Functions: `snake_case()`
- Constants: `UPPER_SNAKE_CASE`
