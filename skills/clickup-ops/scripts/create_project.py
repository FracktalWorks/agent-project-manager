"""
create_project.py — Create a ClickUp Space + Folder + Lists from a plan JSON.

Usage:
    python skills/clickup-ops/scripts/create_project.py \
        --plan outputs/website-redesign/step_1_project_plan.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR  = AGENT_DIR / "data"
sys.path.insert(0, str(Path(__file__).parent))

from clickup_client import ClickUpClient


def date_to_ms(d: str | None) -> int | None:
    if not d or d == "TBD":
        return None
    try:
        dt = date.fromisoformat(d)
        from datetime import datetime, timezone
        return int(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Create ClickUp project from plan JSON.")
    parser.add_argument("--plan", required=True, help="Path to step_1_project_plan.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without calling the API")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    name = plan["project_name"]
    slug = plan.get("slug", name.lower().replace(" ", "-"))

    client = ClickUpClient()

    print(f"\n[create_project] Creating project: {name}")
    print(f"  Phases: {len(plan.get('phases', []))}")

    # 1. Create Space
    if args.dry_run:
        space_id = "DRY_SPACE"
        print(f"  [dry-run] Would create Space: {name}")
    else:
        space = client.create_space(name)
        space_id = space["id"]
        print(f"  ✅ Space created: {space_id}")

    # 2. Create Folder
    if args.dry_run:
        folder_id = "DRY_FOLDER"
        print(f"  [dry-run] Would create Folder: {name}")
    else:
        folder = client.create_folder(space_id, name)
        folder_id = folder["id"]
        print(f"  ✅ Folder created: {folder_id}")

    # 3. Create a List per phase
    list_ids: dict[str, str] = {}
    for phase in plan.get("phases", []):
        phase_name = phase["name"]
        due_ms     = date_to_ms(phase.get("due_date"))
        if args.dry_run:
            list_ids[phase_name] = "DRY_LIST"
            print(f"  [dry-run] Would create List: {phase_name}")
        else:
            lst = client.create_list(folder_id, phase_name, due_date_ms=due_ms)
            list_ids[phase_name] = lst["id"]
            print(f"  ✅ List created: {phase_name} → {lst['id']}")

    # 4. Persist IDs back to project_priorities.json
    priorities_path = DATA_DIR / "project_priorities.json"
    if priorities_path.exists():
        priorities = json.loads(priorities_path.read_text(encoding="utf-8"))
    else:
        priorities = {"projects": []}

    # Upsert project entry
    existing = next((p for p in priorities["projects"] if p.get("slug") == slug), None)
    clickup_data = {
        "clickup_space_id":  space_id,
        "clickup_folder_id": folder_id,
        "clickup_list_ids":  list_ids,
    }
    if existing:
        existing.update(clickup_data)
    else:
        priorities["projects"].append({
            "name": name,
            "slug": slug,
            **clickup_data,
        })

    if not args.dry_run:
        priorities_path.write_text(json.dumps(priorities, indent=2), encoding="utf-8")
        print(f"\n  IDs saved to {priorities_path}")

    print(f"\n[create_project] Done — {name}")
    print(json.dumps(clickup_data, indent=2))


if __name__ == "__main__":
    main()
