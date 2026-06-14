"""
fetch_status.py — Pull task status from a ClickUp list or all registered projects.

Usage:
    # Single list by ID
    python .github/skills/project-tracking/scripts/fetch_status.py --list-id <list_id>

    # All registered projects (reads outputs/_memory/project_registry.json)
    python .github/skills/project-tracking/scripts/fetch_status.py --all-projects

    # Filter by assignee name (case-insensitive substring match)
    python .github/skills/project-tracking/scripts/fetch_status.py --all-projects --assignee "Suryansh"
    python .github/skills/project-tracking/scripts/fetch_status.py --list-id <list_id> --assignee "Kiran"

    # Save output to file
    python .github/skills/project-tracking/scripts/fetch_status.py --all-projects --output outputs/status.json

Output JSON schema:
    {
      "fetched_at": "...",
      "list_id": "...",           # present in single-list mode
      "project_name": "...",      # present in all-projects mode per project
      "tasks": [
        {
          "id": "...",
          "title": "...",
          "assignee": "Alice, Bob",
          "due_date": "2026-06-10",
          "status": "to do",
          "flag": "on_track"      # on_track | at_risk | blocked
        }
      ]
    }

    In --all-projects mode the top-level output is:
    {
      "fetched_at": "...",
      "projects": [ { "project_name": "...", "list_id": "...", "tasks": [...] }, ... ]
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(AGENT_DIR / ".github" / "skills" / "clickup-ops" / "scripts"))

from clickup_client import ClickUpClient  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_env() -> None:
    env_path = AGENT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


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


def serialise_task(t: dict, assignee_filter: str = "") -> dict | None:
    """Convert a raw ClickUp task dict to a clean record. Returns None if filtered out."""
    assignees = [a.get("username", "") for a in (t.get("assignees") or []) if a]
    assignee_str = ", ".join(assignees)

    if assignee_filter and assignee_filter.lower() not in assignee_str.lower():
        return None

    due_raw = t.get("due_date")
    return {
        "id":       t["id"],
        "title":    t["name"],
        "assignee": assignee_str,
        "due_date": datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date().isoformat()
                    if due_raw else None,
        "status":   (t.get("status", {}).get("status") or "unknown"),
        "flag":     flag_task(t),
    }


def fetch_list(client: ClickUpClient, list_id: str, assignee_filter: str = "") -> list[dict]:
    tasks = client.get_tasks(list_id)
    result = []
    for t in tasks:
        record = serialise_task(t, assignee_filter)
        if record is not None:
            result.append(record)
    return result


def load_project_registry() -> list[dict]:
    path = AGENT_DIR / "outputs" / "_memory" / "project_registry.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("projects", [])


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(description="Fetch task status from ClickUp.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-id", help="ClickUp list ID for a single list")
    group.add_argument("--all-projects", action="store_true",
                       help="Query all lists registered in outputs/_memory/project_registry.json")
    parser.add_argument("--assignee", default="",
                        help="Filter tasks by assignee name (case-insensitive substring)")
    parser.add_argument("--output", default=None, help="Save JSON output to this file path")
    args = parser.parse_args()

    token   = os.environ.get("CLICKUP_API_TOKEN") or ""
    team_id = os.environ.get("CLICKUP_TEAM_ID")  or ""
    client  = ClickUpClient(token=token, team_id=team_id)

    now = datetime.now(timezone.utc).isoformat()

    if args.list_id:
        tasks = fetch_list(client, args.list_id, args.assignee)
        report = {
            "fetched_at": now,
            "list_id":    args.list_id,
            "tasks":      tasks,
        }
    else:
        projects = load_project_registry()
        if not projects:
            print("No projects found in outputs/_memory/project_registry.json", file=sys.stderr)
            sys.exit(1)

        project_reports = []
        for proj in projects:
            list_id = proj.get("clickup_list_id")
            if not list_id:
                continue
            tasks = fetch_list(client, list_id, args.assignee)
            project_reports.append({
                "project_name": proj.get("name", proj.get("slug", list_id)),
                "list_id":      list_id,
                "tasks":        tasks,
            })

        report = {
            "fetched_at": now,
            "projects":   project_reports,
        }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report saved to {out}", file=sys.stderr)
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
