"""
create_tasks_with_subtasks.py — Create parent tasks and their subtasks from a JSON plan.

Reads credentials from .env at the repo root, then falls back to environment variables.
Does NOT use dotenv.find_dotenv() (fragile in piped/sub-process contexts).

Usage — from a JSON plan file:
    python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \\
        --plan outputs/control-center/tasks.json

Usage — quick inline (single list, all tasks → one assignee):
    python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \\
        --plan outputs/control-center/tasks.json \\
        --list-id 901611246899 \\
        --assignee-id 101084655 \\
        --due 2026-06-13

Usage — dry run (no API calls, just print what would be created):
    python .github/skills/clickup-ops/scripts/create_tasks_with_subtasks.py \\
        --plan outputs/control-center/tasks.json --dry-run

Plan JSON schema
----------------
{
  "list_id": "901611246899",          # required unless --list-id is passed
  "default_assignees": [101084655],   # optional; can be overridden per task
  "default_due": "2026-06-13",        # optional; can be overridden per task
  "default_priority": 2,              # 1=urgent 2=high 3=normal 4=low
  "tasks": [
    {
      "name": "Parent task title",
      "description": "What it delivers and done-when criterion.",
      "assignees": [101084655],        # optional override
      "due": "2026-06-13",             # optional override
      "priority": 2,                   # optional override
      "status": "to do",               # optional; defaults to "to do"
      "subtasks": [
        {
          "name": "Subtask title",
          "description": "Specific step and acceptance criterion.",
          "assignees": [101084655],    # optional override
          "due": "2026-06-13",
          "priority": 3
        }
      ]
    }
  ]
}

Exit codes
----------
  0  All tasks created successfully
  1  Configuration error (missing token, bad plan file)
  2  API error (at least one task failed)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import datetime as dt
from pathlib import Path

# Add sibling scripts to path for ClickUpClient import
sys.path.insert(0, str(Path(__file__).parent))
from clickup_client import ClickUpClient  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parents[4]


# ─── Env loading ─────────────────────────────────────────────────────────────

def _load_env_file(path: Path) -> None:
    """Parse a .env file and inject into os.environ (setdefault — never overwrite)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ─── Date helpers ─────────────────────────────────────────────────────────────

def _to_ms(date_str: str | None) -> int | None:
    """Convert YYYY-MM-DD to ClickUp millisecond timestamp at 18:00 local."""
    if not date_str or date_str.upper() == "TBD":
        return None
    try:
        d = dt.date.fromisoformat(date_str)
        return int(dt.datetime(d.year, d.month, d.day, 18, 0).timestamp() * 1000)
    except ValueError:
        return None


# ─── Core creation logic ──────────────────────────────────────────────────────

def create_parent_and_subtasks(
    client: ClickUpClient,
    list_id: str,
    task_def: dict,
    default_assignees: list[int],
    default_due_ms: int | None,
    default_priority: int,
    dry_run: bool = False,
) -> tuple[str | None, int]:
    """Create one parent task plus all its subtasks.

    Returns (parent_task_id, error_count).
    """
    errors = 0

    assignees = task_def.get("assignees") or default_assignees
    due_ms = _to_ms(task_def.get("due")) or default_due_ms
    priority = task_def.get("priority") or default_priority
    status = task_def.get("status", "to do")
    name = task_def["name"]
    desc = task_def.get("description", "")

    if dry_run:
        print(f"  [dry-run] Parent: {name!r}")
        parent_id = "DRY_PARENT"
    else:
        try:
            result = client.create_task(
                list_id=list_id,
                name=name,
                description=desc,
                assignees=assignees or None,
                due_date_ms=due_ms,
                priority=priority,
            )
            # set status after creation (create_task doesn't accept status kwarg)
            if status and status != "to do":
                client.update_task(result["id"], status=status)
            parent_id = result["id"]
            print(f"  CREATED {parent_id} :: {name}")
        except Exception as exc:
            print(f"  ERROR creating parent {name!r}: {exc}", file=sys.stderr)
            return None, 1

    for sub in task_def.get("subtasks", []):
        sub_assignees = sub.get("assignees") or assignees
        sub_due_ms = _to_ms(sub.get("due")) or due_ms
        sub_priority = sub.get("priority") or 3  # default subtasks to normal
        sub_name = sub["name"]
        sub_desc = sub.get("description", f"Subtask under: {name}")

        if dry_run:
            print(f"      [dry-run] Subtask: {sub_name!r}")
            continue

        for attempt in range(2):
            try:
                sr = client.create_subtask(
                    list_id=list_id,
                    parent_id=parent_id,
                    name=sub_name,
                    description=sub_desc,
                    assignees=sub_assignees or None,
                    due_date_ms=sub_due_ms,
                    priority=sub_priority,
                )
                print(f"      CREATED {sr['id']} :: {sub_name}")
                break
            except Exception as exc:
                if attempt == 0:
                    time.sleep(62)
                    continue
                print(f"      ERROR creating subtask {sub_name!r}: {exc}", file=sys.stderr)
                errors += 1

    return parent_id, errors


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load .env from repo root before anything else
    _load_env_file(AGENT_DIR / ".env")

    parser = argparse.ArgumentParser(
        description="Create parent tasks + subtasks in ClickUp from a JSON plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--plan", required=True, help="Path to tasks JSON plan file")
    parser.add_argument("--list-id", default=None, help="Override list_id from plan")
    parser.add_argument("--assignee-id", type=int, default=None,
                        help="Override default assignee (ClickUp user int ID)")
    parser.add_argument("--due", default=None, help="Override default due date YYYY-MM-DD")
    parser.add_argument("--priority", type=int, default=None,
                        help="Override default priority (1=urgent 2=high 3=normal 4=low)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without calling the API")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    list_id = args.list_id or plan.get("list_id")
    if not list_id:
        print("ERROR: list_id is required (set in plan JSON or pass --list-id)", file=sys.stderr)
        sys.exit(1)

    default_assignees: list[int] = []
    if args.assignee_id:
        default_assignees = [args.assignee_id]
    elif plan.get("default_assignees"):
        default_assignees = plan["default_assignees"]

    default_due_ms = _to_ms(args.due or plan.get("default_due"))
    default_priority = args.priority or plan.get("default_priority", 2)

    if args.dry_run:
        print(f"[dry-run] List: {list_id}")
        client = None
    else:
        client = ClickUpClient()

    tasks = plan.get("tasks", [])
    print(f"\nCreating {len(tasks)} parent task(s) in list {list_id} ...\n")

    total_errors = 0
    for task_def in tasks:
        _, errs = create_parent_and_subtasks(
            client=client,
            list_id=list_id,
            task_def=task_def,
            default_assignees=default_assignees,
            default_due_ms=default_due_ms,
            default_priority=default_priority,
            dry_run=args.dry_run,
        )
        total_errors += errs

    if total_errors:
        print(f"\nFinished with {total_errors} error(s). Check stderr above.", file=sys.stderr)
        sys.exit(2)

    print(f"\nDone — {len(tasks)} parent task(s) created.")


if __name__ == "__main__":
    main()
