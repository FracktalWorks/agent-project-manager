#!/usr/bin/env python3
"""
Find unassigned ClickUp tasks across all workspace lists, optionally filtered
by skill keywords to match a person's expertise.

Usage:
    python find_unassigned_tasks.py
    python find_unassigned_tasks.py --skills "Python,Django,Flask,Electron,web dev"
    python find_unassigned_tasks.py --space-id 90160576626 --skills "data science"
    python find_unassigned_tasks.py --skip-status "Closed,done"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Ensure load_env + clickup_client are importable
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".github" / "skills" / "clickup-ops" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / ".tmp" / "scripts"))
from load_env import load_env; load_env()
from clickup_client import ClickUpClient

SKILL_KEYWORD_MAP: dict[str, list[str]] = {
    "python": ["python", "flask", "django", "fastapi", "backend", "api", "script"],
    "django": ["django", "web", "backend", "app", "api"],
    "flask": ["flask", "web", "api", "service"],
    "electron": ["electron", "desktop", "app", "gui", "frontend"],
    "java": ["java", "spring", "android", "backend"],
    "web dev": ["web", "frontend", "ui", "react", "dashboard", "app"],
    "data science": ["data", "ml", "ai", "analytics", "model", "training"],
    "devops": ["deploy", "docker", "cloud", "ci", "cd", "pipeline", "infra"],
    "testing": ["test", "qa", "automation", "selenium", "unit"],
    "embedded": ["embedded", "firmware", "c", "c++", "mcu", "iot"],
    "mechanical": ["cad", "mechanical", "solidworks", "fusion", "design", "fea"],
    "electronics": ["pcb", "circuit", "schematic", "altium", "kicad"],
}


def _skill_matches(task_name: str, task_desc: str, skills: list[str]) -> bool:
    """Check if a task matches any of the given skill keywords."""
    text = f"{task_name} {task_desc}".lower()
    for skill in skills:
        keywords = SKILL_KEYWORD_MAP.get(skill.lower(), [skill.lower()])
        if any(kw in text for kw in keywords):
            return True
    return False


def _is_unassigned(task: dict) -> bool:
    return not task.get("assignees") or len(task["assignees"]) == 0


def _should_skip_status(task: dict, skip_statuses: list[str]) -> bool:
    status = task.get("status", {}).get("status", "").lower()
    for s in skip_statuses:
        if s.strip().lower() == status:
            return True
    return False


def find_unassigned(skills: list[str] | None = None,
                    space_id: str | None = None,
                    skip_statuses: list[str] | None = None) -> list[dict]:
    """Find unassigned tasks, optionally matching skills."""
    if skip_statuses is None:
        skip_statuses = ["closed", "done"]

    client = ClickUpClient()
    results: list[dict] = []

    try:
        spaces = client.get_spaces()
    except Exception as e:
        print(f"Error fetching spaces: {e}", file=sys.stderr)
        return []

    for space in spaces:
        if space_id and space["id"] != space_id:
            continue

        try:
            folders = client.get_folders(space["id"])
        except Exception:
            folders = [{"id": None}]

        for folder in folders:
            fid = folder["id"]
            try:
                lists = client.get_lists(fid or space["id"]) if fid else client.get_folderless_lists(space["id"])
            except Exception:
                continue

            for lst in lists:
                try:
                    tasks = client.get_tasks(lst["id"], subtasks=True)
                except Exception:
                    continue

                for task in tasks:
                    # Check parent task
                    if _is_unassigned(task) and not _should_skip_status(task, skip_statuses):
                        name = task.get("name", "")
                        desc = task.get("description", "") or ""
                        if skills is None or _skill_matches(name, desc, skills):
                            results.append({
                                "id": task["id"],
                                "name": name,
                                "list_id": lst["id"],
                                "list_name": lst.get("name", ""),
                                "space_name": space.get("name", ""),
                                "status": task.get("status", {}).get("status", ""),
                                "priority": task.get("priority"),
                                "due_date": task.get("due_date"),
                            })

                    # Check subtasks
                    for subtask in task.get("subtasks", []):
                        if _is_unassigned(subtask) and not _should_skip_status(subtask, skip_statuses):
                            name = subtask.get("name", "")
                            desc = subtask.get("description", "") or ""
                            if skills is None or _skill_matches(name, desc, skills):
                                results.append({
                                    "id": subtask["id"],
                                    "name": name,
                                    "parent_name": task.get("name", ""),
                                    "list_id": lst["id"],
                                    "list_name": lst.get("name", ""),
                                    "space_name": space.get("name", ""),
                                    "status": subtask.get("status", {}).get("status", ""),
                                    "priority": subtask.get("priority"),
                                    "due_date": subtask.get("due_date"),
                                })

                time.sleep(0.2)  # rate limit buffer per list

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find unassigned ClickUp tasks across all workspace lists"
    )
    parser.add_argument("--skills", default="",
                        help="Comma-separated skill keywords to filter matching tasks")
    parser.add_argument("--space-id", default="",
                        help="ClickUp space ID to scope search")
    parser.add_argument("--skip-status", default="Closed,done",
                        help="Comma-separated statuses to skip (default: Closed,done)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else None
    skip_statuses = [s.strip() for s in args.skip_status.split(",") if s.strip()]

    results = find_unassigned(skills=skills, space_id=args.space_id or None,
                              skip_statuses=skip_statuses)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not results:
            print("No unassigned tasks found.")
            return
        print(f"\nFound {len(results)} unassigned task(s):\n")
        for i, t in enumerate(results, 1):
            parent = f"  (subtask of: {t.get('parent_name', '')})" if t.get("parent_name") else ""
            print(f"{i}. [{t['space_name']} / {t['list_name']}] {t['name']}{parent}")
            print(f"   Status: {t['status']} | Priority: {t['priority']} | "
                  f"Due: {t.get('due_date', 'none')} | ID: {t['id']}")
            print()


if __name__ == "__main__":
    main()
