#!/usr/bin/env python3
"""
discover_review_status.py — Find all ClickUp lists that have a 'review' status.

Outputs JSON: list of {space_name, folder_name, list_id, list_name, statuses}
so you can see exactly what will be changed before executing the rename.

Usage:
    python scripts/discover_review_status.py
    python scripts/discover_review_status.py --execute   # renames 'review' -> 'on hold'
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(AGENT_DIR / "skills" / "clickup-ops" / "scripts"))

env_path = AGENT_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import httpx
from clickup_client import ClickUpClient

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}


def get_list_detail(list_id: str) -> dict:
    r = httpx.get(f"https://api.clickup.com/api/v2/list/{list_id}", headers=H, timeout=20)
    r.raise_for_status()
    return r.json()


def update_list_statuses(list_id: str, statuses: list[dict]) -> dict:
    """Update statuses on a list. Sends only the statuses field."""
    r = httpx.put(
        f"https://api.clickup.com/api/v2/list/{list_id}",
        headers=H,
        json={"statuses": statuses},
        timeout=20,
    )
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.put(
            f"https://api.clickup.com/api/v2/list/{list_id}",
            headers=H,
            json={"statuses": statuses},
            timeout=20,
        )
    r.raise_for_status()
    return r.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually rename 'review' -> 'on hold' on all matching lists")
    args = parser.parse_args()

    client = ClickUpClient()

    # Load workspace lists from cache if available, else fetch live
    cache_file = AGENT_DIR / "outputs" / "_memory" / "workspace_lists.json"
    if cache_file.exists():
        all_lists = json.loads(cache_file.read_text())["lists"]
        print(f"Using cached workspace map ({len(all_lists)} lists)", file=sys.stderr)
    else:
        print("Cache not found, fetching from ClickUp...", file=sys.stderr)
        from list_workspace import fetch_workspace_lists
        all_lists = fetch_workspace_lists(client)

    print(f"\nScanning {len(all_lists)} lists for 'review' status...\n", file=sys.stderr)

    matches = []
    for entry in all_lists:
        list_id = entry["list_id"]
        try:
            detail = get_list_detail(list_id)
        except Exception as e:
            print(f"  [skip] {entry['list_name']} ({list_id}): {e}", file=sys.stderr)
            continue

        statuses = detail.get("statuses", [])
        review_statuses = [s for s in statuses if s.get("status", "").lower() == "review"]
        if review_statuses:
            matches.append({
                "space_name": entry["space_name"],
                "folder_name": entry["folder_name"],
                "list_id": list_id,
                "list_name": entry["list_name"],
                "review_status": review_statuses[0],
                "all_statuses": statuses,
            })

    if not matches:
        print("No lists found with a 'review' status.")
        return

    print(f"Found {len(matches)} list(s) with 'review' status:\n")
    for m in matches:
        folder = f" / {m['folder_name']}" if m['folder_name'] else ""
        rs = m['review_status']
        print(f"  [{m['list_id']}] {m['space_name']}{folder} -> {m['list_name']}")
        print(f"    Status: \"{rs['status']}\" | color: {rs.get('color')} | orderindex: {rs.get('orderindex')}")

    if not args.execute:
        print(f"\nDry run complete. Add --execute to rename 'review' -> 'on hold' on all {len(matches)} lists.")
        return

    # Execute the rename
    print(f"\nRenaming 'review' -> 'on hold' on {len(matches)} lists...\n")
    success, failed = 0, 0
    for m in matches:
        updated_statuses = []
        for s in m["all_statuses"]:
            if s.get("status", "").lower() == "review":
                updated_statuses.append({
                    "status": "on hold",
                    "color": s.get("color", "#d3d3d3"),
                    "orderindex": s.get("orderindex", 0),
                })
            else:
                updated_statuses.append({
                    "status": s["status"],
                    "color": s.get("color", "#d3d3d3"),
                    "orderindex": s.get("orderindex", 0),
                })
        try:
            update_list_statuses(m["list_id"], updated_statuses)
            print(f"  ✅ {m['list_name']} ({m['list_id']})")
            success += 1
        except Exception as e:
            print(f"  ❌ {m['list_name']} ({m['list_id']}): {e}")
            failed += 1

    print(f"\nDone: {success} updated, {failed} failed.")


if __name__ == "__main__":
    main()
