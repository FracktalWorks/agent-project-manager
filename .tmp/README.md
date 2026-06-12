# .tmp/ — Temporary Files

Rules: `.github/instructions/tmp-folder.instructions.md`

| Allowed | Examples |
|---|---|
| Reusable fix-up utilities | small scripts used across projects (promote to `scripts/` after 3+ uses) |
| API response caches | `search_cache/`, `web_cache/` subdirs (each needs its own README; 48 h TTL) |
| Short-lived intermediates | deleted by the script that created them, same agent turn |

| Forbidden | Where it belongs |
|---|---|
| One-off debug scripts (`check_*.py`, `verify_*.py`) | delete after use |
| ClickUp data dumps | `outputs/_memory/` or `outputs/{slug}/` |
| Project-specific artifacts | `outputs/{slug}/` |
| Duplicates of skill scripts | use the skill script with args |

Cache data is gitignored; utilities and READMEs are tracked.
