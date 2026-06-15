#!/usr/bin/env python3
"""
workload_analysis.py — Fetch every ClickUp member's assigned tasks across the
entire workspace, compute actual workload, compare against hr_structure.json
capacity, and identify underloaded people (available for new tasks).

Outputs:
  outputs/workload_report.json   — full machine-readable report
  stdout                         — human-friendly summary table

Usage:
  python scripts/workload_analysis.py
  python scripts/workload_analysis.py --update-hr        # write load back to hr_structure.json
  python scripts/workload_analysis.py --person "Pavan"   # filter to one person
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

HR_FILE = REPO_ROOT / "agent-data" / "hr_structure.json"
RESUME_PROFILES_FILE = REPO_ROOT / "agent-data" / "resume_profiles.json"
REPORT_FILE = REPO_ROOT / "outputs" / "workload_report.json"

HOURS_PER_TASK_ESTIMATE = 4.0   # default hours assumed per open task
TASK_EFFORT_BY_PRIORITY = {     # ClickUp priority ids → estimated hours
    1: 8.0,   # urgent
    2: 6.0,   # high
    3: 4.0,   # normal
    4: 2.0,   # low
}

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------

def load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ---------------------------------------------------------------------------
# ClickUp helpers
# ---------------------------------------------------------------------------

def get_client():
    sys.path.insert(0, str(REPO_ROOT / ".github" / "skills" / "clickup-ops" / "scripts"))
    from clickup_client import ClickUpClient
    return ClickUpClient()


def fetch_all_tasks(client) -> list[dict[str, Any]]:
    """
    Walk the full workspace hierarchy and collect every task.
    Returns a flat list of task dicts, each enriched with list/space context.
    """
    all_tasks: list[dict[str, Any]] = []

    spaces = client.get_spaces()
    print(f"  Fetching {len(spaces)} space(s)...")

    for space in spaces:
        space_id = space["id"]
        space_name = space.get("name", space_id)

        # Foldered lists
        try:
            folders = client.get_folders(space_id)
        except Exception as e:
            print(f"    [WARN] Could not fetch folders for space '{space_name}': {e}")
            folders = []

        for folder in folders:
            folder_id = folder["id"]
            try:
                lists = client.get_lists(folder_id)
            except Exception as e:
                print(f"    [WARN] Could not fetch lists for folder '{folder.get('name')}': {e}")
                lists = []
            for lst in lists:
                _collect_tasks(client, lst, space_name, all_tasks)

        # Folder-less lists
        try:
            folderless = client.get_folderless_lists(space_id)
        except Exception as e:
            print(f"    [WARN] Could not fetch folderless lists for '{space_name}': {e}")
            folderless = []
        for lst in folderless:
            _collect_tasks(client, lst, space_name, all_tasks)

    return all_tasks


def _collect_tasks(client, lst: dict, space_name: str, target: list) -> None:
    list_id = lst["id"]
    list_name = lst.get("name", list_id)
    try:
        tasks = client.get_tasks(list_id, include_closed=False)
        for task in tasks:
            task["_space_name"] = space_name
            task["_list_name"] = list_name
        target.extend(tasks)
    except Exception as e:
        print(f"    [WARN] Could not fetch tasks for list '{list_name}': {e}")


# ---------------------------------------------------------------------------
# Workload computation
# ---------------------------------------------------------------------------

def estimate_hours(task: dict) -> float:
    """Estimate effort for a single task based on priority."""
    priority = task.get("priority")
    if isinstance(priority, dict):
        priority = int(priority.get("id", 3))
    elif priority is not None:
        try:
            priority = int(priority)
        except (ValueError, TypeError):
            priority = 3
    else:
        priority = 3
    return TASK_EFFORT_BY_PRIORITY.get(priority, HOURS_PER_TASK_ESTIMATE)


def build_member_workload(tasks: list[dict]) -> dict[int, dict[str, Any]]:
    """
    Returns a dict keyed by ClickUp user_id:
      {
        "name": str,
        "tasks": [task, ...],
        "estimated_hours": float,
        "task_count": int,
      }
    """
    workload: dict[int, dict[str, Any]] = {}

    for task in tasks:
        assignees = task.get("assignees", [])
        hours = estimate_hours(task)
        for assignee in assignees:
            uid = assignee.get("id")
            if uid is None:
                continue
            if uid not in workload:
                workload[uid] = {
                    "name": assignee.get("username", str(uid)),
                    "email": assignee.get("email", ""),
                    "tasks": [],
                    "estimated_hours": 0.0,
                    "task_count": 0,
                }
            workload[uid]["tasks"].append({
                "id": task.get("id"),
                "name": task.get("name"),
                "status": task.get("status", {}).get("status") if isinstance(task.get("status"), dict) else task.get("status"),
                "space": task.get("_space_name"),
                "list": task.get("_list_name"),
                "priority": task.get("priority"),
                "estimated_hours": hours,
            })
            workload[uid]["estimated_hours"] += hours
            workload[uid]["task_count"] += 1

    return workload


# ---------------------------------------------------------------------------
# Map ClickUp workload to HR structure
# ---------------------------------------------------------------------------

def load_hr() -> dict:
    with open(HR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def enrich_with_hr(workload: dict[int, dict], hr_data: dict) -> list[dict[str, Any]]:
    """
    For each HR member, merge ClickUp workload data.
    Returns a flat list of person records, sorted by available_hours descending.
    """
    records = []

    for dept in hr_data.get("departments", []):
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                uid = member.get("clickup_user_id")
                cu_data = workload.get(uid, {}) if uid else {}

                capacity = member.get("capacity_hours_per_week", 40)
                cu_hours = cu_data.get("estimated_hours", 0.0)
                # Clamp to capacity
                load = min(cu_hours, capacity)
                available = max(0.0, capacity - load)

                record = {
                    "name": member.get("name"),
                    "email": member.get("email"),
                    "role": member.get("role"),
                    "department": dept["name"],
                    "team": team["name"],
                    "clickup_user_id": uid,
                    "status": member.get("status", "active"),
                    "capacity_hours_per_week": capacity,
                    "clickup_task_count": cu_data.get("task_count", 0),
                    "estimated_load_hours": round(load, 1),
                    "available_hours_per_week": round(available, 1),
                    "skills": member.get("skills", []),
                    "resume_profile": member.get("resume_profile"),
                    "tasks": cu_data.get("tasks", []),
                }
                records.append(record)

    # Sort: most available first
    records.sort(key=lambda r: r["available_hours_per_week"], reverse=True)
    return records


def update_hr_loads(hr_data: dict, records: list[dict]) -> None:
    """Write computed load back into hr_structure.json member objects."""
    lookup = {r["clickup_user_id"]: r for r in records if r["clickup_user_id"]}
    for dept in hr_data.get("departments", []):
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                uid = member.get("clickup_user_id")
                if uid and uid in lookup:
                    r = lookup[uid]
                    member["current_load_hours_per_week"] = r["estimated_load_hours"]
                    member["available_hours_per_week"] = r["available_hours_per_week"]


# ---------------------------------------------------------------------------
# Scheduling helper
# ---------------------------------------------------------------------------

def suggest_assignee(required_skills: list[str], effort_hours: float,
                     records: list[dict]) -> list[dict]:
    """
    Return up to 3 ranked candidates for a task.
    Ranking: skill match score (desc) → available hours (desc).
    """
    req = set(s.lower() for s in required_skills)
    scored = []
    for r in records:
        if r["status"] != "active":
            continue
        if r["available_hours_per_week"] < effort_hours:
            continue
        member_skills = set(s.lower() for s in r.get("skills", []))
        match_score = len(req & member_skills)
        scored.append({**r, "_match_score": match_score})
    scored.sort(key=lambda x: (-x["_match_score"], -x["available_hours_per_week"]))
    return scored[:3]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_report(records: list[dict], filter_name: str | None = None) -> None:
    print("\n" + "=" * 80)
    print(f"  WORKLOAD REPORT  —  generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 80)
    print(f"{'Name':<28} {'Role':<26} {'Load h/wk':>9} {'Avail h/wk':>10} {'Tasks':>6}")
    print("-" * 80)

    for r in records:
        if filter_name and filter_name.lower() not in r["name"].lower():
            continue
        load_bar = "█" * min(int(r["estimated_load_hours"] / 5), 8)
        avail_indicator = "✓ AVAILABLE" if r["available_hours_per_week"] >= 8 else ""
        print(
            f"{r['name']:<28} {r['role']:<26} "
            f"{r['estimated_load_hours']:>9.1f} {r['available_hours_per_week']:>10.1f} "
            f"{r['clickup_task_count']:>6}  {avail_indicator}"
        )

    print("-" * 80)

    underloaded = [r for r in records if r["available_hours_per_week"] >= 10 and r["status"] == "active"]
    print(f"\n🟢 {len(underloaded)} people with 10+ available hours/week:")
    for r in underloaded:
        skills_preview = ", ".join(r["skills"][:5])
        print(f"   • {r['name']} ({r['role']}) — {r['available_hours_per_week']}h free | skills: {skills_preview}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ClickUp workload analysis")
    parser.add_argument("--update-hr", action="store_true",
                        help="Write computed load values back to hr_structure.json")
    parser.add_argument("--person", metavar="NAME",
                        help="Filter report to a single person (partial name match)")
    parser.add_argument("--suggest", metavar="SKILLS", nargs="+",
                        help="Suggest best assignee for a task (provide skill keywords)")
    parser.add_argument("--effort", type=float, default=4.0,
                        help="Estimated hours for the task (used with --suggest, default=4)")
    args = parser.parse_args()

    load_env()

    print("Connecting to ClickUp...")
    try:
        client = get_client()
    except Exception as e:
        print(f"[ERROR] Cannot connect to ClickUp: {e}")
        sys.exit(1)

    print("Fetching all workspace tasks (this may take a moment)...")
    tasks = fetch_all_tasks(client)
    print(f"  Total open tasks fetched: {len(tasks)}")

    workload = build_member_workload(tasks)
    hr_data = load_hr()
    records = enrich_with_hr(workload, hr_data)

    if args.update_hr:
        update_hr_loads(hr_data, records)
        with open(HR_FILE, "w", encoding="utf-8") as f:
            json.dump(hr_data, f, indent=2, ensure_ascii=False)
        print(f"\nhr_structure.json updated with current load data.")

    # Save full report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_open_tasks": len(tasks),
        "members": [
            {k: v for k, v in r.items() if k != "tasks"}
            for r in records
        ],
        "members_with_tasks": [r for r in records if r["task_count"] > 0] if False else [
            {**{k: v for k, v in r.items() if k != "tasks"}, "tasks": r["tasks"]}
            for r in records
        ],
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved: {REPORT_FILE.relative_to(REPO_ROOT)}")

    print_report(records, filter_name=args.person)

    if args.suggest:
        print(f"\n🎯 Suggested assignees for task requiring: {args.suggest}")
        candidates = suggest_assignee(args.suggest, args.effort, records)
        if candidates:
            for i, c in enumerate(candidates, 1):
                match = c["_match_score"]
                print(f"  {i}. {c['name']} ({c['role']}) — {c['available_hours_per_week']}h free | "
                      f"{match} skill match(es)")
        else:
            print("  No available candidates found.")


if __name__ == "__main__":
    main()
