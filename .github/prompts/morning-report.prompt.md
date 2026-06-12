---
description: "Generate the daily morning report — department-wise project breakdown + people workload rollup."
argument-hint: "[department]"
---

# Morning Report

Generate the daily bird's-eye morning report.

## Steps

1. **Run the script (no decisions needed):**
   ```bash
   python .github/skills/daily-morning-report/scripts/generate_morning_report.py
   ```
   If a department is specified, add `--department "NAME"`.

2. **Read the saved file** at `outputs/morning_reports/morning_report_YYYY-MM-DD.md` and present it.

3. **Add a 2-line top summary**: most urgent concern + top idle people.

4. Do NOT re-run, re-interpret, or second-guess the output. The script is the source of truth.

Full skill: `.github/skills/daily-morning-report/SKILL.md`
