"""
list_workspace.py — Enumerate all ClickUp spaces, folders, and lists.

Outputs a structured JSON map of the workspace that agents can reference to find
list IDs without making multiple live API calls. Cache the output in
outputs/_memory/workspace_lists.json so simpler agents can look up IDs offline.

Usage:
    # Dump all lists as JSON
    python .github/skills/clickup-ops/scripts/list_workspace.py

    # Filter by name (case-insensitive substring match)
    python .github/skills/clickup-ops/scripts/list_workspace.py --filter "quality"
    python .github/skills/clickup-ops/scripts/list_workspace.py --filter "mds"

    # Save to cache file (recommended — lets simpler agents skip live API calls)
    python .github/skills/clickup-ops/scripts/list_workspace.py --save-cache

    # Load from cache instead of hitting API
    python .github/skills/clickup-ops/scripts/list_workspace.py --from-cache

    # Find a list and print just its ID (useful for scripting)
    python .github/skills/clickup-ops/scripts/list_workspace.py --filter "quality control" --id-only

Output schema:
    [
      {
        "space_id": "...",
        "space_name": "...",
        "folder_id": "...",       # null for folderless lists
        "folder_name": "...",     # null for folderless lists
        "list_id": "...",
        "list_name": "..."
      },
      ...
    ]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[5]
CACHE_FILE = AGENT_DIR / "outputs" / "_memory" / "workspace_lists.json"
sys.path.insert(0, str(AGENT_DIR / ".github" / "skills" / "clickup-ops" / "scripts"))

from clickup_client import ClickUpClient  # noqa: E402


def fetch_workspace_lists(client: ClickUpClient) -> list[dict]:
    """Walk all spaces → folders → lists and return flat list of records."""
    records: list[dict] = []
    spaces = client.get_spaces()

    for space in spaces:
        sid = space["id"]
        sname = space.get("name", sid)

        # Foldered lists
        try:
            folders = client.get_folders(sid)
        except Exception:
            folders = []

        for folder in folders:
            fid = folder["id"]
            fname = folder.get("name", fid)
            try:
                lists = client.get_lists(fid)
            except Exception:
                lists = []
            for lst in lists:
                records.append({
                    "space_id": sid,
                    "space_name": sname,
                    "folder_id": fid,
                    "folder_name": fname,
                    "list_id": lst["id"],
                    "list_name": lst.get("name", lst["id"]),
                })

        # Folderless lists
        try:
            lists = client.get_folderless_lists(sid)
        except Exception:
            lists = []
        for lst in lists:
            records.append({
                "space_id": sid,
                "space_name": sname,
                "folder_id": None,
                "folder_name": None,
                "list_id": lst["id"],
                "list_name": lst.get("name", lst["id"]),
            })

    return records


def load_cache() -> list[dict] | None:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8")).get("lists")
    return None


def save_cache(records: list[dict]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lists": records,
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Cache saved → {CACHE_FILE}", file=sys.stderr)


def main() -> None:
    # Load .env manually (no dotenv dependency required)
    env_path = AGENT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    parser = argparse.ArgumentParser(description="List all ClickUp spaces/folders/lists.")
    parser.add_argument("--filter", default="", help="Case-insensitive substring filter on list name")
    parser.add_argument("--save-cache", action="store_true", help="Save results to outputs/_memory/workspace_lists.json")
    parser.add_argument("--from-cache", action="store_true", help="Load from cache instead of querying API")
    parser.add_argument("--id-only", action="store_true", help="Print only the list_id(s) of matching lists")
    args = parser.parse_args()

    if args.from_cache:
        records = load_cache()
        if records is None:
            print("No cache found. Run without --from-cache first.", file=sys.stderr)
            sys.exit(1)
    else:
        client = ClickUpClient()
        records = fetch_workspace_lists(client)
        if args.save_cache:
            save_cache(records)

    # Apply filter
    if args.filter:
        needle = args.filter.lower()
        records = [r for r in records if needle in r["list_name"].lower()]

    if args.id_only:
        for r in records:
            print(r["list_id"])
        return

    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
