---
description: "Run agent health diagnostics — API connectivity, data files, memory integrity."
---

# Diagnose

Run full agent diagnostics to identify issues before they become problems.

## Steps

1. **Health check:**
   ```bash
   python scripts/self_anneal_diagnostics.py
   ```

2. **Verify ClickUp connectivity:**
   ```bash
   python .github/skills/clickup-ops/scripts/list_workspace.py --from-cache --filter "founders"
   ```
   If the cache is missing, run with `--save-cache` (live API).

3. **Check memory files** in `outputs/_memory/` — flag anything due or high-score in
   `risk_log.json` and `follow_ups.json`.

4. **Run the test suite:**
   ```bash
   python -m pytest tests/ -v
   ```

5. **Summarise:** Flag all warnings and critical issues. Suggest fixes for each.
   Log new learnings per `.github/skills/self-annealing/SKILL.md`.
