"""
self_anneal_diagnostics.py — Health checks and learnings log for agent-project-manager.

Usage:
    python scripts/self_anneal_diagnostics.py --check api_health
    python scripts/self_anneal_diagnostics.py --check clickup_connectivity
    python scripts/self_anneal_diagnostics.py --check data_integrity
    python scripts/self_anneal_diagnostics.py --check all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows consoles default to cp1252 — force UTF-8 so emoji output doesn't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AGENT_DIR   = Path(__file__).resolve().parent.parent.parent
DATA_DIR    = AGENT_DIR / "agent-data"
OUTPUTS_DIR = AGENT_DIR / "outputs"
MEMORY_DIR  = OUTPUTS_DIR / "_memory"


def check_api_health() -> list[str]:
    issues = []
    token = os.environ.get("CLICKUP_API_TOKEN", "")
    if not token:
        issues.append("CLICKUP_API_TOKEN is not set in environment / .env")
    if not os.environ.get("CLICKUP_TEAM_ID", ""):
        issues.append("CLICKUP_TEAM_ID is not set in environment / .env")
    return issues


def check_clickup_connectivity() -> list[str]:
    issues = []
    try:
        sys.path.insert(0, str(AGENT_DIR / ".github" / "skills" / "clickup-ops" / "scripts"))
        from clickup_client import ClickUpClient
        client = ClickUpClient()
        teams = client.get_teams()
        if not teams:
            issues.append("ClickUp API returned no teams — check CLICKUP_TEAM_ID")
    except Exception as e:
        issues.append(f"ClickUp connectivity failed: {e}")
    return issues


def check_data_integrity() -> list[str]:
    issues = []
    hr_path = DATA_DIR / "hr_structure.json"
    if not hr_path.exists():
        issues.append("agent-data/hr_structure.json is missing — populate it before delegating tasks")
    else:
        try:
            hr = json.loads(hr_path.read_text(encoding="utf-8"))
            if not hr.get("departments"):
                issues.append("agent-data/hr_structure.json has no departments")
        except json.JSONDecodeError as e:
            issues.append(f"agent-data/hr_structure.json is invalid JSON: {e}")

    pp_path = DATA_DIR / "project_priorities.json"
    if not pp_path.exists():
        issues.append("agent-data/project_priorities.json is missing — will be created on first project")

    return issues


def record_learning(error: str, fix: str, prevention: str) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    log_path = MEMORY_DIR / "learnings_log.json"
    log: list[dict] = []
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
    log.append({
        "date":       datetime.now(timezone.utc).isoformat(),
        "error":      error,
        "fix":        fix,
        "prevention": prevention,
    })
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Learning recorded to {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent health checks.")
    parser.add_argument(
        "--check",
        choices=["api_health", "clickup_connectivity", "data_integrity", "all"],
        required=True,
    )
    parser.add_argument("--record-learning", nargs=3,
                        metavar=("ERROR", "FIX", "PREVENTION"),
                        help="Record a learning entry")
    args = parser.parse_args()

    if args.record_learning:
        record_learning(*args.record_learning)
        return

    checks = {
        "api_health":           check_api_health,
        "clickup_connectivity": check_clickup_connectivity,
        "data_integrity":       check_data_integrity,
    }

    if args.check == "all":
        to_run = list(checks.values())
    else:
        to_run = [checks[args.check]]

    all_issues: list[str] = []
    for fn in to_run:
        all_issues.extend(fn())

    if all_issues:
        print("❌ Issues found:")
        for issue in all_issues:
            print(f"  • {issue}")
        sys.exit(1)
    else:
        print("✅ All checks passed.")


if __name__ == "__main__":
    main()
