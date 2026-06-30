#!/usr/bin/env python3
"""
Bulk task status updater — mass close, move to "to do", or any status transition
for ClickUp tasks matching a filter (assignee, list, status).

Usage:
    python bulk_update_tasks.py --assignee 272439149 --to-status "Closed"
    python bulk_update_tasks.py --list-id 901614456560 --from-status "to do" --to-status "Closed"
    python bulk_update_tasks.py --assignee 272439149 --to-status "done" --dry-run
    python bulk_update_tasks.py --task-ids 86d38tp9v,86d38tm16 --to-status "Closed"
    python bulk_update_tasks.py --plan tasks.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Ensure .github/skills/clickup-ops/scripts/ is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".github" / "skills" / "clickup-ops" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / ".tmp" / "scripts"))
from load_env import load_env; load_env()
from clickup_client import ClickUpClient


class BulkUpdater:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.client = ClickUpClient()
        self.results: list[dict] = []

    def close_assignee_tasks(self, assignee_id: int, list_id: str | None = None,
                              from_status: str = "", to_status: str = "Closed") -> int:
        """Close all tasks assigned to a person, optionally scoped to a list."""
        if list_id:
            lists = {list_id: ""}
        else:
            lists = self._discover_lists()

        closed = 0
        for lid in lists:
            tasks = self.client.get_tasks(lid, subtasks=True)
            for task in tasks:
                if not self._task_assigned_to(task, assignee_id):
                    continue
                if from_status and task.get("status", {}).get("status", "") != from_status:
                    continue
                self._update_task(task["id"], to_status)
                closed += 1
                # Also close subtasks
                for subtask in self._get_all_subtasks(task):
                    if self._task_assigned_to(subtask, assignee_id):
                        self._update_task(subtask["id"], to_status)
                        closed += 1
        return closed

    def close_task_ids(self, task_ids: list[str], to_status: str = "Closed") -> int:
        """Close a specific list of task IDs."""
        for tid in task_ids:
            self._update_task(tid.strip(), to_status)
        return len(task_ids)

    def close_from_plan(self, plan_file: str, to_status: str = "Closed") -> int:
        """Close all tasks listed in a plan JSON file."""
        plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
        task_ids = self._extract_task_ids(plan)
        return self.close_task_ids(task_ids, to_status)

    def _discover_lists(self) -> dict[str, str]:
        """Return {list_id: list_name} for all lists."""
        try:
            spaces = self.client.get_spaces()
        except Exception:
            spaces = []
        lists = {}
        for space in spaces:
            try:
                folders = self.client.get_folders(space["id"])
            except Exception:
                folders = [{"id": None}]
            for folder in folders:
                fid = folder["id"]
                try:
                    ll = self.client.get_lists(fid or space["id"])
                except Exception:
                    continue
                for lst in ll:
                    lists[lst["id"]] = lst.get("name", "")
        return lists

    def _task_assigned_to(self, task: dict, assignee_id: int) -> bool:
        assignees = task.get("assignees", [])
        return any(a.get("id") == assignee_id for a in assignees)

    def _get_all_subtasks(self, task: dict) -> list[dict]:
        """Get direct subtasks from nested responses."""
        return task.get("subtasks", [])

    def _update_task(self, task_id: str, status: str) -> None:
        if self.dry_run:
            print(f"  [DRY RUN] Would set task {task_id} to '{status}'")
            self.results.append({"task_id": task_id, "status": status, "dry": True})
            return
        try:
            self.client.update_task(task_id, {"status": status})
            print(f"  ✓ Task {task_id} → '{status}'")
            self.results.append({"task_id": task_id, "status": status, "success": True})
        except Exception as e:
            print(f"  ✗ Task {task_id} FAILED: {e}")
            self.results.append({"task_id": task_id, "status": status, "error": str(e)})
        time.sleep(0.3)  # rate limit buffer

    @staticmethod
    def _extract_task_ids(plan: dict) -> list[str]:
        """Recursively extract task IDs from a plan JSON."""
        ids: list[str] = []
        if isinstance(plan, dict):
            if "id" in plan and isinstance(plan["id"], str):
                ids.append(plan["id"])
            for v in plan.values():
                ids.extend(BulkUpdater._extract_task_ids(v))
        elif isinstance(plan, list):
            for item in plan:
                ids.extend(BulkUpdater._extract_task_ids(item))
        return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk update ClickUp task statuses")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--assignee", type=int, help="Assignee user ID to filter by")
    g.add_argument("--task-ids", help="Comma-separated task IDs to update")
    g.add_argument("--plan", help="Path to a plan JSON file with task IDs")
    parser.add_argument("--list-id", help="Scope to a specific list ID")
    parser.add_argument("--from-status", default="", help="Only update tasks with this status")
    parser.add_argument("--to-status", default="Closed", help="Target status (default: Closed)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    updater = BulkUpdater(dry_run=args.dry_run)

    if args.task_ids:
        count = updater.close_task_ids(args.task_ids.split(","), args.to_status)
    elif args.plan:
        count = updater.close_from_plan(args.plan, args.to_status)
    else:
        count = updater.close_assignee_tasks(
            args.assignee, args.list_id, args.from_status, args.to_status
        )

    action = "Would update" if args.dry_run else "Updated"
    print(f"\n{action} {count} task(s).")

    if args.dry_run:
        for r in updater.results:
            print(f"  {r['task_id']} → {r['status']}")


if __name__ == "__main__":
    main()
