"""
sync_tasks.py — Create or update tasks in ClickUp from a project plan JSON.

Usage:
    # Create all tasks for a project plan:
    python .github/skills/clickup-ops/scripts/sync_tasks.py \
        --plan outputs/website-redesign/step_1_project_plan.json

    # Update a single task:
    python .github/skills/clickup-ops/scripts/sync_tasks.py \
        --task-id abc123 --status "in progress" --assignee "Alice Chen"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[5]
DATA_DIR  = AGENT_DIR / "agent-data"
sys.path.insert(0, str(Path(__file__).parent))

from clickup_client import ClickUpClient


def date_to_ms(d: str | None) -> int | None:
    if not d or d == "TBD":
        return None
    try:
        dt = date.fromisoformat(d)
        return int(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


def load_list_ids(slug: str) -> dict[str, str]:
    path = DATA_DIR / "project_priorities.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    project = next((p for p in data.get("projects", []) if p.get("slug") == slug), None)
    return (project or {}).get("clickup_list_ids", {})


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync tasks to ClickUp.")
    parser.add_argument("--plan", default=None, help="Path to step_1_project_plan.json")
    # Single-task update mode
    parser.add_argument("--task-id", default=None, help="ClickUp task ID to update")
    parser.add_argument("--status",  default=None, help="New status string")
    parser.add_argument("--assignee", default=None, help="Assignee name or email")
    parser.add_argument("--due-date", default=None, help="New due date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = ClickUpClient()

    # ---- Single task update ----
    if args.task_id:
        updates: dict = {}
        if args.status:
            updates["status"] = args.status
        if args.due_date:
            ms = date_to_ms(args.due_date)
            if ms:
                updates["due_date"] = ms
        if args.assignee:
            uid = client.find_member_id(args.assignee)
            if uid is None:
                print(f"ERROR: Member '{args.assignee}' not found in ClickUp workspace.")
                sys.exit(1)
            updates["assignees"] = {"add": [uid], "rem": []}
        if args.dry_run:
            print(f"[dry-run] Would update task {args.task_id}: {json.dumps(updates, indent=2)}")
        else:
            result = client.update_task(args.task_id, **updates)
            print(f"✅ Task updated: {result.get('id')}")
        return

    # ---- Bulk create from plan ----
    if not args.plan:
        print("ERROR: provide --plan or --task-id")
        sys.exit(1)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    slug = plan.get("slug", "")
    list_ids = load_list_ids(slug)

    if not list_ids:
        print(
            f"ERROR: No ClickUp list IDs found for project '{slug}'.\n"
            "Run create_project.py first."
        )
        sys.exit(1)

    # Pre-fetch member IDs for name→id resolution
    members = client.get_members()
    def resolve_member(name: str) -> int | None:
        needle = name.lower()
        for m in members:
            u = m.get("user", {})
            if needle in u.get("username", "").lower() or needle in u.get("email", "").lower():
                return u["id"]
        return None

    created: list[dict] = []

    for phase in plan.get("phases", []):
        phase_name = phase["name"]
        list_id    = list_ids.get(phase_name)
        if not list_id:
            print(f"⚠️  No list ID for phase '{phase_name}' — skipping")
            continue

        for task in phase.get("tasks", []):
            title       = task["title"]
            owner_role  = task.get("owner_role", "")
            due_ms      = date_to_ms(task.get("due_date"))
            description = f"Owner role: {owner_role}"

            assignee_ids: list[int] = []
            if owner_role:
                uid = resolve_member(owner_role)
                if uid:
                    assignee_ids.append(uid)

            if args.dry_run:
                print(f"  [dry-run] Would create task '{title}' in list {list_id}")
                continue

            result = client.create_task(
                list_id=list_id,
                name=title,
                description=description,
                assignees=assignee_ids or None,
                due_date_ms=due_ms,
            )
            print(f"  ✅ Task created: {result['id']} — {title}")
            created.append({"id": result["id"], "title": title, "phase": phase_name})

    print(f"\n[sync_tasks] Created {len(created)} task(s).")


if __name__ == "__main__":
    main()
