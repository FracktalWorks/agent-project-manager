"""
notion_info.py — Fetch Notion page metadata.

Usage:
    python scripts/integrations/notion_info.py --page-id "abc123def456"
    python scripts/integrations/notion_info.py --page-id "abc123def456" --output .tmp/project/notion_info.json

Requires NOTION_API_TOKEN in .env (Internal Integration token with page access).
"""

import argparse
import json
import os
from pathlib import Path

import httpx
from load_env import load_env; load_env()
NOTION_TOKEN = os.getenv("NOTION_API_TOKEN")
API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def headers() -> dict:
    if not NOTION_TOKEN:
        raise EnvironmentError("NOTION_API_TOKEN not set in .env")
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def clean_page_id(page_id: str) -> str:
    """Accept both hyphenated UUID and raw 32-char ID."""
    return page_id.replace("-", "")


def get_page(page_id: str) -> dict:
    pid = clean_page_id(page_id)
    r = httpx.get(f"{API_BASE}/pages/{pid}", headers=headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    # Extract plain-text title from properties
    title = ""
    for prop in data.get("properties", {}).values():
        if prop.get("type") == "title":
            parts = prop.get("title", [])
            title = "".join(p.get("plain_text", "") for p in parts)
            break

    return {
        "page_id": page_id,
        "title": title,
        "url": data.get("url"),
        "created_time": data.get("created_time"),
        "last_edited_time": data.get("last_edited_time"),
        "parent_type": data.get("parent", {}).get("type"),
        "archived": data.get("archived", False),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Notion page metadata")
    parser.add_argument("--page-id", required=True, help="Notion page ID (UUID or raw 32-char)")
    parser.add_argument("--output", default=None, help="Path to save JSON output")
    args = parser.parse_args()

    result = get_page(args.page_id)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
