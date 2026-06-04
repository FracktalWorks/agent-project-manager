"""
fetch_status.py — Pull task status from a ClickUp list.

Usage:
    python skills/project-tracking/scripts/fetch_status.py --list-id <list_id>
    python skills/project-tracking/scripts/fetch_status.py --list-id <list_id> --output outputs/my-project/tasks.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AGENT_DIR / "skills" / "clickup-ops" / "scripts"))

from clickup_client import ClickUpClient  # noqa: E402


def days_until(due_ms: int | None) -> int | None:
    if due_ms is None:
        return None
    due_dt = datetime.fromtimestamp(due_ms / 1000, tz=timezone.utc).date()
    return (due_dt - date.today()).days


def flag_task(task: dict) -> str:
    status = (task.get("status", {}).get("status") or "").lower()
    if "block" in status:
        return "blocked"
    days = days_until(task.get("due_date") and int(task["due_date"]))
    if days is not None and days <= 3:
        return "at_risk"
    return "on_track"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch task status from ClickUp.")
    parser.add_argument("--list-id", required=True, help="ClickUp list ID")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    token   = os.environ.get("CLICKUP_API_TOKEN") or ""
    team_id = os.environ.get("CLICKUP_TEAM_ID")  or ""
    client  = ClickUpClient(token=token, team_id=team_id)

    tasks = client.get_tasks(args.list_id)

    flagged = []
    for t in tasks:
        due_raw = t.get("due_date")
        flagged.append({
            "id":       t["id"],
            "title":    t["name"],
            "assignee": ", ".join(a.get("username", "") for a in t.get("assignees", [])),
            "due_date": datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date().isoformat()
                        if due_raw else None,
            "status":   (t.get("status", {}).get("status") or "unknown"),
            "flag":     flag_task(t),
        })

    report = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "list_id":    args.list_id,
        "tasks":      flagged,
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report saved to {out}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
