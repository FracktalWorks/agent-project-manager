"""
update_list_colors.py — Scan task/subtask due dates in a ClickUp List and
set the list's status color according to the Fracktal project health convention:

  🟢 green  — all tasks on schedule (no overdue, nothing due today)
  🟡 yellow — at least one task/subtask is due today or tomorrow (warn)
  🔴 red    — at least one task/subtask is overdue (past due, not closed)

The play/pause/stop icon is set manually in ClickUp. This script only
manages the color.

Usage:
  # Check and update a single list
  python scripts/update_list_colors.py --list-id 901612525485

  # Check and update ALL hardware project lists
  python scripts/update_list_colors.py --folder-id 90166940853

  # Dry-run (report only, no writes)
  python scripts/update_list_colors.py --folder-id 90166940853 --dry-run

Environment:
  CLICKUP_API_TOKEN, CLICKUP_TEAM_ID
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}
BASE = "https://api.clickup.com/api/v2"

# ── Thresholds ───────────────────────────────────────────────────────────────
WARN_DAYS = 1   # tasks due within this many days → yellow
# Anything overdue (due_date < now, not closed) → red immediately

# ── Closed status types (ClickUp) ────────────────────────────────────────────
CLOSED_TYPES = {"closed", "done"}


def _get(path: str, params: dict | None = None) -> dict | list:
    r = httpx.get(f"{BASE}{path}", headers=H, params=params, timeout=20)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.get(f"{BASE}{path}", headers=H, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> dict:
    r = httpx.put(f"{BASE}{path}", headers=H, json=body, timeout=20)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.put(f"{BASE}{path}", headers=H, json=body, timeout=20)
    r.raise_for_status()
    return r.json()


def get_list(list_id: str) -> dict:
    return _get(f"/list/{list_id}")


def get_tasks(list_id: str) -> list[dict]:
    """Return all open tasks AND their subtasks for a list."""
    data = _get(
        f"/list/{list_id}/task",
        params={"include_closed": "false", "subtasks": "true"},
    )
    return data.get("tasks", data) if isinstance(data, dict) else data


def compute_color(tasks: list[dict]) -> tuple[str, list[str]]:
    """
    Returns (color, reasons) where color is 'red', 'yellow', or 'green'.
    reasons is a list of human-readable strings explaining why.

    Comparison is by CALENDAR DATE (not by millisecond) so that a task whose
    due date is today is never treated as overdue — ClickUp stores due dates as
    04:00 IST which is earlier in the day than the script runs.

    Rules:
      red    — due_date < today   (past calendar day, not closed)
      yellow — due_date == today OR due_date <= today + WARN_DAYS
      green  — everything else on schedule
    """
    today = datetime.date.today()
    warn_cutoff = today + datetime.timedelta(days=WARN_DAYS)

    overdue: list[str] = []
    due_soon: list[str] = []

    for task in tasks:
        status_type = task.get("status", {}).get("type", "")
        if status_type in CLOSED_TYPES:
            continue

        due = task.get("due_date")
        if due is None:
            continue
        due_date = datetime.datetime.fromtimestamp(int(due) / 1000).date()
        name = task.get("name", task.get("id", "?"))

        if due_date < today:
            overdue.append(f"OVERDUE: '{name}' (was due {due_date})")
        elif due_date <= warn_cutoff:
            due_soon.append(f"DUE SOON: '{name}' (due {due_date})")

    if overdue:
        return "red", overdue + due_soon
    if due_soon:
        return "yellow", due_soon
    return "green", []


def _fmt(ms: int) -> str:
    return datetime.datetime.fromtimestamp(ms / 1000).date().isoformat()


def set_list_color(list_id: str, list_name: str, color: str) -> None:
    _put(f"/list/{list_id}", {"name": list_name, "status": color})


def process_list(list_id: str, dry_run: bool = False) -> dict:
    lst = get_list(list_id)
    name = lst["name"]
    current_status = lst.get("status", {}).get("status", "unknown")

    tasks = get_tasks(list_id)
    color, reasons = compute_color(tasks)

    icon = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(color, "⚪")
    print(f"\n  {icon} {name}  (was: {current_status} → now: {color})")
    for r in reasons:
        print(f"      • {r}")
    if not reasons:
        print("      • All tasks on schedule")

    if color != current_status:
        if dry_run:
            print(f"      [dry-run] would update to {color}")
        else:
            set_list_color(list_id, name, color)
            print(f"      ✅ Updated to {color}")
    else:
        print(f"      ✓ No change needed")

    return {"list_id": list_id, "name": name, "color": color, "reasons": reasons}


def process_folder(folder_id: str, dry_run: bool = False) -> list[dict]:
    data = _get(f"/folder/{folder_id}")
    lists = data.get("lists", [])
    results = []
    for lst in lists:
        results.append(process_list(lst["id"], dry_run=dry_run))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Update ClickUp list status colors.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list-id",   help="Single list ID to update")
    group.add_argument("--folder-id", help="Folder ID — update all lists in folder")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report colors without writing to ClickUp")
    args = parser.parse_args()

    print("=" * 60)
    print("  ClickUp List Color Update")
    if args.dry_run:
        print("  (DRY RUN — no changes will be written)")
    print("=" * 60)
    print()
    print("  Convention:")
    print("  🟢 green  — all tasks on schedule")
    print(f"  🟡 yellow — task/subtask due within {WARN_DAYS} day(s)")
    print("  🔴 red    — at least one task/subtask is overdue")
    print()
    print("  Play/Pause/Stop icon is set manually in ClickUp UI.")
    print()

    if args.list_id:
        process_list(args.list_id, dry_run=args.dry_run)
    else:
        results = process_folder(args.folder_id, dry_run=args.dry_run)
        print(f"\n  Done — processed {len(results)} lists.")


if __name__ == "__main__":
    main()
