#!/usr/bin/env python3
"""
generate_morning_report.py — Bird's-eye morning status report for Fracktal Works.

Pulls all open tasks from the entire ClickUp workspace, maps them to people via
hr_structure.json, and renders a structured Markdown report with:
  1. Department-wise breakup  — who is doing what under which sub-project
  2. People-wise rollup       — workload status per person

Usage:
  python .github/skills/daily-morning-report/scripts/generate_morning_report.py
  python .github/skills/daily-morning-report/scripts/generate_morning_report.py --department "R&D"
  python .github/skills/daily-morning-report/scripts/generate_morning_report.py --output outputs/morning_report.md
  python .github/skills/daily-morning-report/scripts/generate_morning_report.py --format json

Workload status flags:
  OVERLOADED  — estimated task hours > weekly capacity
  BEHIND      — has ≥1 overdue task (due date passed, not closed/done)
  ON_TRACK    — tasks assigned, none overdue, within capacity
  LIGHT_LOAD  — < 2 tasks OR estimated hours < 25% of capacity
  IDLE        — no open tasks assigned in ClickUp
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
SKILLS_DIR  = SCRIPT_DIR.parent.parent          # .github/skills/
REPO_ROOT   = SKILLS_DIR.parents[1]              # repo root (above .github/)

HR_FILE     = REPO_ROOT / "data" / "hr_structure.json"
DEPT_MAP    = SCRIPT_DIR / "dept_mapping.json"
OUTPUT_DIR  = REPO_ROOT / "outputs"
REPORT_DIR  = REPO_ROOT / "outputs" / "morning_reports"

# ---------------------------------------------------------------------------
# Thresholds (tune here)
# ---------------------------------------------------------------------------
TASK_EFFORT_BY_PRIORITY: dict[int, float] = {
    1: 8.0,   # urgent
    2: 6.0,   # high
    3: 4.0,   # normal
    4: 2.0,   # low
}
DEFAULT_TASK_HOURS   = 4.0   # fallback when priority unknown
OVERLOADED_FACTOR    = 1.0   # estimated_hours > capacity * factor → overloaded
LIGHT_LOAD_FACTOR    = 0.25  # estimated_hours < capacity * factor → light
LIGHT_LOAD_MIN_TASKS = 2     # fewer than N tasks also counts as light load

CLOSED_STATUSES = {"done", "closed", "complete", "completed", "cancelled", "canceled", "backlog"}

# Status emoji
EMOJI = {
    "OVERLOADED": "🔴",
    "BEHIND":     "🟠",
    "ON_TRACK":   "🟢",
    "LIGHT_LOAD": "🟡",
    "IDLE":       "⚪",
}

# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------

def load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ---------------------------------------------------------------------------
# ClickUp helpers
# ---------------------------------------------------------------------------

def get_client():
    sys.path.insert(0, str(SKILLS_DIR / "clickup-ops" / "scripts"))
    from clickup_client import ClickUpClient  # noqa: E402
    return ClickUpClient()


_skip_ids: set[str] = set()  # populated in main() from dept_mapping config


def fetch_all_tasks(client) -> list[dict[str, Any]]:
    """Walk the entire workspace and return every open task, enriched with space/list names."""
    all_tasks: list[dict[str, Any]] = []

    spaces = client.get_spaces()
    print(f"  Fetching across {len(spaces)} space(s)...", flush=True)

    for space in spaces:
        space_id   = space["id"]
        space_name = space.get("name", space_id)

        # Foldered lists
        try:
            folders = client.get_folders(space_id)
        except Exception as exc:
            print(f"    [WARN] Folders for '{space_name}': {exc}")
            folders = []

        for folder in folders:
            folder_name = folder.get("name", folder["id"])
            try:
                lists = client.get_lists(folder["id"])
            except Exception as exc:
                print(f"    [WARN] Lists in folder '{folder_name}': {exc}")
                lists = []
            for lst in lists:
                _collect(client, lst, space_name, folder_name, all_tasks, _skip_ids)

        # Folder-less lists
        try:
            folderless = client.get_folderless_lists(space_id)
        except Exception as exc:
            print(f"    [WARN] Folderless lists for '{space_name}': {exc}")
            folderless = []
        for lst in folderless:
            _collect(client, lst, space_name, None, all_tasks, _skip_ids)

    return all_tasks


# List colors that indicate an active project (from dept_mapping.json)
# green = active, yellow = paused, red = stopped — populated in main()
_active_colors: set[str] = {"green"}


def _is_list_active(lst: dict, skip_ids: set[str]) -> bool:
    """Return True if this list should be included in the report.

    Convention (set in dept_mapping.json):
      green  = active, being worked on       → include
      yellow = paused / on hold              → exclude
      red    = stopped / inactive            → exclude
      (none) = no color set                  → include (company ops lists etc.)
    """
    list_id = lst.get("id", "")
    if list_id in skip_ids:
        return False
    if lst.get("archived", False):
        return False
    color = (lst.get("status") or {}).get("status", "").lower()
    # If a color is set and it is not in the active set, skip it
    if color and color not in _active_colors:
        return False
    return True


def _collect(client, lst: dict, space_name: str, folder_name: str | None, target: list,
             skip_ids: set[str] | None = None) -> None:
    if not _is_list_active(lst, skip_ids or set()):
        list_name = lst.get("name", lst.get("id", "?"))
        print(f"    [SKIP] '{list_name}' (archived/paused/inactive)", flush=True)
        return
    list_id   = lst["id"]
    list_name = lst.get("name", list_id)
    try:
        tasks = client.get_tasks(list_id, include_closed=False)
        for task in tasks:
            task["_space_name"]  = space_name
            task["_folder_name"] = folder_name
            task["_list_name"]   = list_name
            task["_list_id"]     = list_id
        target.extend(tasks)
    except Exception as exc:
        print(f"    [WARN] Tasks in list '{list_name}': {exc}")


# ---------------------------------------------------------------------------
# Effort estimation
# ---------------------------------------------------------------------------

def estimate_hours(task: dict) -> float:
    priority = task.get("priority")
    if isinstance(priority, dict):
        priority = priority.get("id")
    try:
        priority = int(priority) if priority is not None else 3
    except (ValueError, TypeError):
        priority = 3
    return TASK_EFFORT_BY_PRIORITY.get(priority, DEFAULT_TASK_HOURS)


def is_overdue(task: dict) -> bool:
    status = ""
    raw_status = task.get("status")
    if isinstance(raw_status, dict):
        status = raw_status.get("status", "").lower()
    elif isinstance(raw_status, str):
        status = raw_status.lower()
    if status in CLOSED_STATUSES:
        return False
    due_raw = task.get("due_date")
    if not due_raw:
        return False
    try:
        due_dt = datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date()
        return due_dt < date.today()
    except (ValueError, TypeError):
        return False


def task_due_date_str(task: dict) -> str | None:
    due_raw = task.get("due_date")
    if not due_raw:
        return None
    try:
        return datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError):
        return None


def task_status_str(task: dict) -> str:
    raw = task.get("status")
    if isinstance(raw, dict):
        return raw.get("status", "unknown")
    return str(raw or "unknown")


def task_priority_label(task: dict) -> str:
    priority = task.get("priority")
    if isinstance(priority, dict):
        return priority.get("priority", "normal")
    return {1: "urgent", 2: "high", 3: "normal", 4: "low"}.get(priority, "normal")


# ---------------------------------------------------------------------------
# Daily relevance filter
# ---------------------------------------------------------------------------

def is_daily_relevant(task: dict) -> bool:
    """
    Include a task in the daily morning report if it meets ANY of:
      - Status is 'in process' (active work, regardless of due date)
      - Overdue (due date < today)
      - Due today
      - Due tomorrow
    Tasks due beyond tomorrow are excluded from the daily view.
    """
    status = task_status_str(task).lower()
    if status == "in process":
        return True
    due_raw = task.get("due_date")
    if not due_raw:
        return False
    try:
        due_dt = datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date()
        return due_dt <= date.today() + timedelta(days=1)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Yellow-list backlog pool (available work for assignment suggestions)
# ---------------------------------------------------------------------------

_paused_colors: set[str] = {"yellow"}  # populated in main()


def fetch_suggestion_pool(client, skip_ids: set[str]) -> list[dict[str, Any]]:
    """
    Fetch unassigned / lightly assigned tasks from green + yellow lists that
    are in backlog or to-do status. These form the pool of available work that
    can be suggested for underloaded people.
    """
    pool: list[dict[str, Any]] = []
    candidate_colors = _active_colors | _paused_colors

    spaces = client.get_spaces()
    for space in spaces:
        space_id   = space["id"]
        space_name = space.get("name", space_id)

        all_lists: list[dict] = []
        try:
            for folder in client.get_folders(space_id):
                try:
                    all_lists.extend(client.get_lists(folder["id"]))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            all_lists.extend(client.get_folderless_lists(space_id))
        except Exception:
            pass

        for lst in all_lists:
            lid = lst.get("id", "")
            if lid in skip_ids:
                continue
            if lst.get("archived", False):
                continue
            color = (lst.get("status") or {}).get("status", "").lower()
            if color and color not in candidate_colors:
                continue
            list_name = lst.get("name", lid)
            try:
                tasks = client.get_tasks(lid, include_closed=False)
                for task in tasks:
                    status = task_status_str(task).lower()
                    if status not in ("backlog", "to do", "todo"):
                        continue
                    # Only include unassigned tasks (no assignees)
                    if task.get("assignees"):
                        continue
                    task["_space_name"]  = space_name
                    task["_list_name"]   = list_name
                    task["_list_id"]     = lid
                    task["_list_color"]  = color
                    pool.append(task)
            except Exception:
                pass
    return pool


# ---------------------------------------------------------------------------
# Skill-matching suggestion engine
# ---------------------------------------------------------------------------

def _skill_score(person_skills: list[str], task: dict) -> int:
    """Return count of skill keywords that appear in the task name, list name, folder, or space."""
    haystack = " ".join([
        task.get("name", ""),
        task.get("_list_name", ""),
        task.get("_folder_name", "") or "",
        task.get("_space_name", "") or "",
    ]).lower()
    return sum(1 for s in person_skills if s.lower() in haystack)


def suggest_assignments(
    org: dict[str, list[dict]],
    workload: dict[int, dict],
    pool: list[dict[str, Any]],
    dept_order: list[str],
    list_dept_map: dict[str, str] | None = None,
    max_suggestions_per_person: int = 3,
) -> dict[str, list[dict]]:
    """
    Two-tier suggestion logic for idle/light-load people:

    Tier 1 — ASSIST 🤝
        Source: tasks CURRENTLY ASSIGNED to OVERLOADED/BEHIND colleagues
                that are in an active status (to do / in process / review — NOT backlog).
        Signal: same project = strong match. Skill match required.
        Effect: idle person joins the colleague on their existing work.

    Tier 2 — BACKLOG 📋
        Source: unassigned tasks from active (🟢) + on-hold (🟡) project lists.
        Signal: skill match only (score ≥ 1 with expanded haystack).
        Effect: idle person picks up new work independently.
    """
    if list_dept_map is None:
        list_dept_map = {}

    # ── uid → member lookup ──────────────────────────────────────────────────
    uid_to_member: dict[int, dict] = {}
    ordered_depts = [d for d in dept_order if d in org]
    for d in org:
        if d not in ordered_depts:
            ordered_depts.append(d)
    for dept in ordered_depts:
        for m in org.get(dept, []):
            uid = m.get("clickup_user_id")
            if uid:
                uid_to_member[uid] = m

    # ── classify every person ────────────────────────────────────────────────
    uid_to_status: dict[int, str] = {}
    for uid, m in uid_to_member.items():
        capacity = m.get("capacity_hours_per_week", 40) or 40
        if uid not in workload:
            uid_to_status[uid] = "IDLE"
            continue
        w   = workload[uid]
        est = w["estimated_hours"]
        tc  = len(w["tasks"])
        ov  = w["overdue_count"]
        if est > capacity * OVERLOADED_FACTOR:
            uid_to_status[uid] = "OVERLOADED"
        elif ov > 0:
            uid_to_status[uid] = "BEHIND"
        elif tc < LIGHT_LOAD_MIN_TASKS or est < capacity * LIGHT_LOAD_FACTOR:
            uid_to_status[uid] = "LIGHT_LOAD"
        else:
            uid_to_status[uid] = "ON_TRACK"

    # ── build ASSIST pool from stressed people's active tasks ────────────────
    # Tasks already assigned to overloaded/behind people, in active status.
    # These are exactly what the colleague needs help with.
    assist_tasks: list[dict[str, Any]] = []
    for uid, status in uid_to_status.items():
        if status not in ("OVERLOADED", "BEHIND"):
            continue
        m    = uid_to_member.get(uid, {})
        name = m.get("name", str(uid))
        if uid not in workload:
            continue
        for t in workload[uid]["tasks"]:
            # Already filtered (no backlog/done) by build_workload
            task_copy = dict(t)
            task_copy["_helps"] = [name]
            task_copy["_list_color"] = "green"  # these are from active lists
            task_copy["_tier"] = "assist"
            assist_tasks.append(task_copy)

    # Deduplicate assist tasks by task id
    seen: set[str] = set()
    deduped_assist: list[dict] = []
    for t in assist_tasks:
        tid = t.get("id", "")
        if tid in seen:
            # Merge helps lists
            for existing in deduped_assist:
                if existing.get("id") == tid:
                    existing["_helps"] = list({*existing["_helps"], *t["_helps"]})
            continue
        seen.add(tid)
        deduped_assist.append(t)

    # ── for each idle/light-load person, score and select suggestions ─────────
    suggestions: dict[str, list[dict]] = {}

    for dept_name in ordered_depts:
        for member in org.get(dept_name, []):
            uid      = member.get("clickup_user_id")
            status   = uid_to_status.get(uid, "IDLE") if uid else "IDLE"

            if status in ("OVERLOADED", "BEHIND", "ON_TRACK"):
                continue

            skills      = [s.lower() for s in member.get("skills", [])]
            if not skills:
                continue
            person_dept = member.get("_report_dept", "")

            combined: list[dict] = []
            seen_ids: set[str]   = set()

            # ── Tier 1: ASSIST ────────────────────────────────────────────────
            tier1: list[tuple] = []
            for t in deduped_assist:
                sc = _skill_score(skills, t)
                if sc == 0:
                    continue
                same_dept = any(
                    uid_to_member.get(u2, {}).get("_report_dept") == person_dept
                    for u2, m2 in uid_to_member.items()
                    if m2.get("name") in t["_helps"]
                )
                tier1.append((t, sc, same_dept))
            # same dept first, then score, then priority
            tier1.sort(key=lambda x: (not x[2], -x[1], -estimate_hours(x[0])))

            for t, sc, _ in tier1:
                if len(combined) >= max_suggestions_per_person:
                    break
                tid = t.get("id", "")
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                combined.append({
                    "id":         tid,
                    "name":       t.get("name", "(untitled)"),
                    "project":    t.get("project", "—"),
                    "priority":   t.get("priority", "normal"),
                    "due_date":   t.get("due_date"),
                    "list_color": "green",
                    "helps":      t["_helps"],
                    "tier":       "assist",
                })

            # ── Tier 2: BACKLOG ───────────────────────────────────────────────
            if len(combined) < max_suggestions_per_person:
                tier2: list[tuple] = []
                for t in pool:
                    sc = _skill_score(skills, t)
                    if sc == 0:
                        continue
                    tier2.append((t, sc))
                tier2.sort(key=lambda x: (-x[1], -estimate_hours(x[0])))

                for t, sc in tier2:
                    if len(combined) >= max_suggestions_per_person:
                        break
                    tid = t.get("id", "")
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    combined.append({
                        "id":         tid,
                        "name":       t.get("name", "(untitled)"),
                        "project":    t.get("_list_name", "—"),
                        "priority":   task_priority_label(t),
                        "due_date":   task_due_date_str(t),
                        "list_color": t.get("_list_color", "green"),
                        "helps":      [],
                        "tier":       "backlog",
                    })

            if combined:
                suggestions[member.get("name", str(uid))] = combined

    return suggestions
    """
    Two-tier suggestion logic for idle/light-load people:

    Tier 1 — ASSIST: unassigned tasks from lists where a colleague is
        OVERLOADED or BEHIND, filtered by skill match. Sorted by:
          - same department first
          - then skill score descending
          - then priority (urgent first)

    Tier 2 — BACKLOG: unassigned tasks from paused (yellow) lists matching
        the person's skills. Sorted by skill score then priority.

    Each suggestion carries a 'helps' field naming the relieved colleague(s).
    """
    suggestions: dict[str, list[dict]] = {}
    if not pool:
        return suggestions
    if list_dept_map is None:
        list_dept_map = {}
    # ── Build uid → member lookup ────────────────────────────────────────────
    uid_to_member: dict[int, dict] = {}
    ordered_depts = [d for d in dept_order if d in org]
    for d in org:
        if d not in ordered_depts:
            ordered_depts.append(d)
    for dept in ordered_depts:
        for m in org.get(dept, []):
            uid = m.get("clickup_user_id")
            if uid:
                uid_to_member[uid] = m

    # ── Classify every person's status ───────────────────────────────────────
    uid_to_status: dict[int, str] = {}
    for uid, m in uid_to_member.items():
        capacity = m.get("capacity_hours_per_week", 40) or 40
        if uid not in workload:
            uid_to_status[uid] = "IDLE"
            continue
        w   = workload[uid]
        est = w["estimated_hours"]
        tc  = len(w["tasks"])
        ov  = w["overdue_count"]
        if est > capacity * OVERLOADED_FACTOR:
            uid_to_status[uid] = "OVERLOADED"
        elif ov > 0:
            uid_to_status[uid] = "BEHIND"
        elif tc < LIGHT_LOAD_MIN_TASKS or est < capacity * LIGHT_LOAD_FACTOR:
            uid_to_status[uid] = "LIGHT_LOAD"
        else:
            uid_to_status[uid] = "ON_TRACK"

    # ── Build list_id → overloaded/behind members ────────────────────────────
    list_to_stressed: dict[str, list[str]] = {}
    for uid, status in uid_to_status.items():
        if status not in ("OVERLOADED", "BEHIND"):
            continue
        m    = uid_to_member.get(uid, {})
        name = m.get("name", str(uid))
        if uid in workload:
            for t in workload[uid]["tasks"]:
                lid = t.get("list_id", "")
                if lid:
                    list_to_stressed.setdefault(lid, [])
                    if name not in list_to_stressed[lid]:
                        list_to_stressed[lid].append(name)

    # ── Tag pool tasks ────────────────────────────────────────────────────────
    for task in pool:
        lid = task.get("_list_id", "")
        task["_helps"] = list_to_stressed.get(lid, [])

    # ── For each idle/light-load person, build scored suggestions ────────────
    for dept_name in ordered_depts:
        for member in org.get(dept_name, []):
            uid      = member.get("clickup_user_id")
            capacity = member.get("capacity_hours_per_week", 40) or 40
            status   = uid_to_status.get(uid, "IDLE") if uid else "IDLE"

            if status in ("OVERLOADED", "BEHIND", "ON_TRACK"):
                continue

            skills = [s.lower() for s in member.get("skills", [])]
            if not skills:
                continue

            person_dept = member.get("_report_dept", "")

            tier1: list[tuple] = []  # ASSIST — same project as stressed colleague
            tier2: list[tuple] = []  # BACKLOG — on-hold lists, skill match

            for task in pool:
                skill_sc = _skill_score(skills, task)
                if skill_sc == 0:
                    continue
                helps      = task["_helps"]
                list_color = task.get("_list_color", "green")
                # Tier 1: task is in a list where someone is overloaded/behind
                # Any skill match is sufficient — the project link is the primary signal
                if helps:
                    same_dept = any(
                        uid_to_member.get(u2, {}).get("_report_dept") == person_dept
                        for u2, m2 in uid_to_member.items()
                        if m2.get("name") in helps
                    )
                    tier1.append((task, skill_sc, same_dept, helps))
                else:
                    # Tier 2: only from on-hold (yellow) lists, score >= 1 is sufficient
                    # since the haystack now includes folder + space context
                    if list_color == "yellow":
                        tier2.append((task, skill_sc, helps))

            # Sort tier 1: same-dept first, then skill score, then priority
            tier1.sort(key=lambda x: (not x[2], -x[1], -estimate_hours(x[0])))
            # Sort tier 2: skill score, then priority
            tier2.sort(key=lambda x: (-x[1], -estimate_hours(x[0])))

            combined: list[dict] = []
            seen_ids: set[str] = set()
            for items, is_tier1 in [(tier1, True), (tier2, False)]:
                for entry in items:
                    if len(combined) >= max_suggestions_per_person:
                        break
                    t = entry[0]
                    tid = t.get("id", "")
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    helps_list = entry[3] if is_tier1 else []
                    combined.append({
                        "id":         tid,
                        "name":       t.get("name", "(untitled)"),
                        "project":    t.get("_list_name", "—"),
                        "priority":   task_priority_label(t),
                        "due_date":   task_due_date_str(t),
                        "list_color": t.get("_list_color", "green"),
                        "helps":      helps_list,
                        "tier":       "assist" if is_tier1 else "backlog",
                    })
                if len(combined) >= max_suggestions_per_person:
                    break

            if combined:
                suggestions[member.get("name", str(uid))] = combined

    return suggestions


# ---------------------------------------------------------------------------
# Build person → tasks mapping
# ---------------------------------------------------------------------------

def build_workload(tasks: list[dict], list_dept_map: dict[str, str] | None = None) -> dict[int, dict]:
    workload: dict[int, dict] = {}
    if list_dept_map is None:
        list_dept_map = {}
    for task in tasks:
        # Skip tasks whose status is closed/done/backlog — not actionable
        if task_status_str(task).lower() in CLOSED_STATUSES:
            continue
        # Daily filter: only show overdue, today, tomorrow, or in-process
        if not is_daily_relevant(task):
            continue
        for assignee in (task.get("assignees") or []):
            uid = assignee.get("id")
            if uid is None:
                continue
            if uid not in workload:
                workload[uid] = {
                    "clickup_name": assignee.get("username", str(uid)),
                    "email":        assignee.get("email", ""),
                    "tasks":        [],
                    "estimated_hours": 0.0,
                    "overdue_count":   0,
                }
            h = estimate_hours(task)
            overdue = is_overdue(task)
            list_id = task.get("_list_id", "")
            workload[uid]["tasks"].append({
                "id":        task.get("id"),
                "name":      task.get("name", "(untitled)"),
                "status":    task_status_str(task),
                "priority":  task_priority_label(task),
                "project":   task.get("_list_name", "—"),
                "folder":    task.get("_folder_name"),
                "space":     task.get("_space_name", "—"),
                "list_id":   list_id,
                "task_dept": list_dept_map.get(list_id),
                "due_date":  task_due_date_str(task),
                "overdue":   overdue,
                "est_hours": h,
            })
            workload[uid]["estimated_hours"] += h
            if overdue:
                workload[uid]["overdue_count"] += 1
    return workload


# ---------------------------------------------------------------------------
# Load HR + department mapping
# ---------------------------------------------------------------------------

def load_hr() -> dict:
    with open(HR_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_dept_map() -> tuple[dict[str, str], list[str], str, dict[str, str], set[str], set[str], set[str]]:
    with open(DEPT_MAP, encoding="utf-8") as f:
        cfg = json.load(f)
    active_colors = set(cfg.get("active_colors", ["green"]))
    paused_colors = set(cfg.get("paused_colors", ["yellow"]))
    return (
        cfg["department_map"],
        cfg["report_department_order"],
        cfg.get("skip_marker", "_skip"),
        cfg.get("list_to_department", {}),
        set(cfg.get("skip_list_ids", [])),
        active_colors,
        paused_colors,
    )


def build_org(hr_data: dict, dept_map: dict[str, str], skip_marker: str = "_skip") -> dict[str, list[dict]]:
    """
    Returns: { "Report Department Name" → [person_dict, ...] }
    Members with _report_dept set directly (in hr_structure.json) override the dept-level mapping.
    Departments mapped to skip_marker are excluded.
    """
    org: dict[str, list[dict]] = defaultdict(list)
    for dept in hr_data.get("departments", []):
        hr_dept_name  = dept.get("name", "Unknown")
        dept_report   = dept_map.get(hr_dept_name, hr_dept_name)  # fallback to raw name
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                member = dict(member)
                member["_hr_dept"] = hr_dept_name
                # Member-level override takes priority over dept-level mapping
                report_dept = member.get("_report_dept") or dept_report
                if report_dept == skip_marker:
                    continue
                member["_report_dept"] = report_dept
                org[report_dept].append(member)
    return dict(org)


# ---------------------------------------------------------------------------
# Workload classification
# ---------------------------------------------------------------------------

def classify_person(member: dict, workload: dict[int, dict]) -> dict:
    uid      = member.get("clickup_user_id")
    capacity = member.get("capacity_hours_per_week", 40) or 40

    if uid is None or uid not in workload:
        return {
            "status":           "IDLE",
            "task_count":       0,
            "estimated_hours":  0.0,
            "overdue_count":    0,
            "tasks":            [],
        }

    w = workload[uid]
    est   = w["estimated_hours"]
    tasks = w["tasks"]
    over  = w["overdue_count"]
    tc    = len(tasks)

    if est > capacity * OVERLOADED_FACTOR:
        status = "OVERLOADED"
    elif over > 0:
        status = "BEHIND"
    elif tc < LIGHT_LOAD_MIN_TASKS or est < capacity * LIGHT_LOAD_FACTOR:
        status = "LIGHT_LOAD"
    else:
        status = "ON_TRACK"

    return {
        "status":          status,
        "task_count":      tc,
        "estimated_hours": est,
        "overdue_count":   over,
        "tasks":           tasks,
    }


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_markdown(
    org: dict[str, list[dict]],
    workload: dict[int, dict],
    dept_order: list[str],
    dept_filter: str | None,
    suggestions: dict[str, list[dict]] | None = None,
) -> str:
    today_str    = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# \U0001f305 Morning Report \u2014 Fracktal Works")
    lines.append(f"**Generated:** {now_utc}")
    lines.append(f"**Window:** overdue + due today ({today_str}) + due tomorrow ({tomorrow_str}) + in-process")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Section 1: Department Breakdown ─────────────────────────────────────
    lines.append("## 1. Department Breakdown")
    lines.append("")

    all_people_data: list[tuple[dict, dict]] = []  # (member, classification)

    ordered_depts = [d for d in dept_order if d in org]
    # Append any departments present in org but not in the order list
    for d in org:
        if d not in ordered_depts:
            ordered_depts.append(d)

    for dept_name in ordered_depts:
        if dept_filter and dept_name.lower() != dept_filter.lower():
            continue
        members = org[dept_name]
        lines.append(f"### 🏢 {dept_name}")
        lines.append("")

        for member in members:
            clf   = classify_person(member, workload)
            role  = member.get("role", "—")
            name  = member.get("name", "Unknown")
            emoji = EMOJI[clf["status"]]

            all_people_data.append((member, clf))

            lines.append(f"#### {emoji} {name} — {role}")

            if not clf["tasks"]:
                lines.append("_No open tasks assigned in ClickUp._")
                lines.append("")
                continue

            lines.append("")

            # Decide whether to show a "Task Dept" column for cross-dept work
            person_dept = member.get("_report_dept", "")
            show_task_dept = any(
                t.get("task_dept") and t["task_dept"] != person_dept
                for t in clf["tasks"]
            )

            if show_task_dept:
                lines.append("| Project | Task | Status | Priority | Due | Overdue? | Task Dept |")
                lines.append("|---------|------|--------|----------|-----|----------|-----------|")
            else:
                lines.append("| Project | Task | Status | Priority | Due | Overdue? |")
                lines.append("|---------|------|--------|----------|-----|----------|")

            # Group tasks by project (list name)
            by_project: dict[str, list[dict]] = defaultdict(list)
            for t in clf["tasks"]:
                by_project[t["project"]].append(t)

            for proj, proj_tasks in sorted(by_project.items()):
                for t in proj_tasks:
                    due   = t["due_date"] or "—"
                    over  = "⚠️ YES" if t["overdue"] else "—"
                    if show_task_dept:
                        td = t.get("task_dept") or "—"
                        flag = " ⚡" if t.get("task_dept") and t["task_dept"] != person_dept else ""
                        lines.append(
                            f"| {proj} | {t['name']} | {t['status']} "
                            f"| {t['priority']} | {due} | {over} | {td}{flag} |"
                        )
                    else:
                        lines.append(
                            f"| {proj} | {t['name']} | {t['status']} "
                            f"| {t['priority']} | {due} | {over} |"
                        )
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Section 2: People Rollup ─────────────────────────────────────────────
    if not dept_filter:
        lines.append("## 2. People Rollup")
        lines.append("")

        # Status buckets for summary
        buckets: dict[str, list[str]] = defaultdict(list)

        lines.append("| Person | Department | Role | Tasks | Est. Hours | Capacity | Status |")
        lines.append("|--------|-----------|------|-------|------------|----------|--------|")

        for member, clf in all_people_data:
            name     = member.get("name", "Unknown")
            dept     = member.get("_report_dept", "—")
            role     = member.get("role", "—")
            capacity = member.get("capacity_hours_per_week", 40) or 40
            emoji    = EMOJI[clf["status"]]
            status   = clf["status"].replace("_", " ")

            lines.append(
                f"| {name} | {dept} | {role} "
                f"| {clf['task_count']} | {clf['estimated_hours']:.0f}h "
                f"| {capacity}h | {emoji} {status} |"
            )
            buckets[clf["status"]].append(name)

        lines.append("")

        # Summary callouts
        lines.append("### Attention Needed")
        lines.append("")
        if buckets["OVERLOADED"]:
            lines.append(f"🔴 **Overloaded:** {', '.join(buckets['OVERLOADED'])}")
        if buckets["BEHIND"]:
            lines.append(f"🟠 **Behind (overdue tasks):** {', '.join(buckets['BEHIND'])}")
        if buckets["IDLE"]:
            lines.append(f"⚪ **Idle / No tasks:** {', '.join(buckets['IDLE'])}")
        if buckets["LIGHT_LOAD"]:
            lines.append(f"🟡 **Light load:** {', '.join(buckets['LIGHT_LOAD'])}")
        if buckets["ON_TRACK"]:
            lines.append(f"🟢 **On track:** {', '.join(buckets['ON_TRACK'])}")
        lines.append("")
    # ── Section 3: Assignment Suggestions ──────────────────────────────────────────────
    if not dept_filter and suggestions:
        lines.append("## 3. Suggested Assignments for Today & Tomorrow")
        lines.append("")
        lines.append("> **🤝 Assist:** unassigned tasks from a project where a colleague is overloaded/behind — skill match required.  ")
        lines.append("> **📋 Backlog:** unassigned tasks from on-hold (🟡) projects matching the person's skills.")
        lines.append("")
        for person_name, tasks in suggestions.items():
            lines.append(f"### 📌 {person_name}")
            lines.append("")
            lines.append("| Type | Project | Task | Priority | Due | Helps |")
            lines.append("|------|---------|------|----------|-----|-------|")
            for t in tasks:
                due   = t["due_date"] or "—"
                tier  = "🤝 Assist" if t["tier"] == "assist" else "📋 Backlog"
                helps = ", ".join(t["helps"]) if t["helps"] else ("🟡 on hold" if t["list_color"] == "yellow" else "🟢 active")
                lines.append(
                    f"| {tier} | {t['project']} | {t['name']} "
                    f"| {t['priority']} | {due} | {helps} |"
                )
            lines.append("")
        lines.append("---")
        lines.append("")
    elif not dept_filter:
        lines.append("## 3. Suggested Assignments for Today & Tomorrow")
        lines.append("")
        lines.append("_No unassigned tasks found matching idle/light-load team members' skills._")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------

def render_json(
    org: dict[str, list[dict]],
    workload: dict[int, dict],
    dept_order: list[str],
) -> str:
    output: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "departments":  [],
        "people":       [],
    }

    all_people_data: list[tuple[dict, dict]] = []

    ordered_depts = [d for d in dept_order if d in org]
    for d in org:
        if d not in ordered_depts:
            ordered_depts.append(d)

    for dept_name in ordered_depts:
        members = org.get(dept_name, [])
        dept_out: dict[str, Any] = {"department": dept_name, "members": []}

        for member in members:
            clf = classify_person(member, workload)
            all_people_data.append((member, clf))
            dept_out["members"].append({
                "name":             member.get("name"),
                "role":             member.get("role"),
                "status":           clf["status"],
                "task_count":       clf["task_count"],
                "estimated_hours":  clf["estimated_hours"],
                "overdue_count":    clf["overdue_count"],
                "tasks":            clf["tasks"],
            })
        output["departments"].append(dept_out)

    for member, clf in all_people_data:
        output["people"].append({
            "name":             member.get("name"),
            "department":       member.get("_report_dept"),
            "role":             member.get("role"),
            "status":           clf["status"],
            "task_count":       clf["task_count"],
            "estimated_hours":  clf["estimated_hours"],
            "capacity_hours":   member.get("capacity_hours_per_week", 40),
            "overdue_count":    clf["overdue_count"],
        })

    return json.dumps(output, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate morning work report.")
    parser.add_argument("--department", default=None, help="Scope to one department (case-insensitive)")
    today = datetime.now().strftime("%Y-%m-%d")
    default_out = str(REPORT_DIR / f"morning_report_{today}.md")
    parser.add_argument("--output",  default=default_out, help="Write output to this file path")
    parser.add_argument("--format",  choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    load_env()

    print("Connecting to ClickUp...", flush=True)
    try:
        client = get_client()
    except Exception as exc:
        print(f"[ERROR] Cannot connect to ClickUp: {exc}")
        sys.exit(1)

    print("Fetching all workspace tasks (this may take ~30s)...", flush=True)
    tasks = fetch_all_tasks(client)
    print(f"  Found {len(tasks)} open task(s) across the workspace.", flush=True)

    hr_data   = load_hr()
    dept_map, dept_order, skip_marker, list_dept_map, skip_list_ids, active_colors, paused_colors = load_dept_map()
    # Populate module-level sets used by _collect / _is_list_active
    global _skip_ids, _active_colors, _paused_colors
    _skip_ids     = skip_list_ids
    _active_colors  = active_colors
    _paused_colors  = paused_colors
    workload  = build_workload(tasks, list_dept_map)
    org       = build_org(hr_data, dept_map, skip_marker)

    print("Fetching suggestion pool (yellow + green unassigned backlogs)...", flush=True)
    pool = fetch_suggestion_pool(client, skip_list_ids)
    print(f"  Found {len(pool)} unassigned task(s) available for assignment.", flush=True)
    suggestions = suggest_assignments(org, workload, pool, dept_order, list_dept_map)

    if args.format == "json":
        report = render_json(org, workload, dept_order)
    else:
        report = render_markdown(org, workload, dept_order,
                                  dept_filter=args.department,
                                  suggestions=suggestions)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
