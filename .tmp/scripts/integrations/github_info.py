"""
github_info.py — Fetch GitHub repository metadata and open issues.

Usage:
    python scripts/integrations/github_info.py --repo "owner/repo"
    python scripts/integrations/github_info.py --repo "owner/repo" --mode issues --state open --limit 10
    python scripts/integrations/github_info.py --repo "owner/repo" --output .tmp/project/github_info.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
API_BASE = "https://api.github.com"


def headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def get_repo(repo: str) -> dict:
    r = httpx.get(f"{API_BASE}/repos/{repo}", headers=headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    return {
        "repo": repo,
        "description": data.get("description"),
        "url": data.get("html_url"),
        "language": data.get("language"),
        "default_branch": data.get("default_branch"),
        "open_issues_count": data.get("open_issues_count"),
        "last_push": data.get("pushed_at"),
        "latest_release": None,
    }


def get_latest_release(repo: str) -> str | None:
    try:
        r = httpx.get(f"{API_BASE}/repos/{repo}/releases/latest", headers=headers(), timeout=15)
        if r.status_code == 200:
            return r.json().get("tag_name")
    except Exception:
        pass
    return None


def get_issues(repo: str, state: str, limit: int) -> list[dict]:
    r = httpx.get(
        f"{API_BASE}/repos/{repo}/issues",
        headers=headers(),
        params={"state": state, "per_page": min(limit, 100)},
        timeout=15,
    )
    r.raise_for_status()
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "url": i["html_url"],
            "assignee": i["assignee"]["login"] if i.get("assignee") else None,
            "labels": [lbl["name"] for lbl in i.get("labels", [])],
            "created_at": i["created_at"],
        }
        for i in r.json()
        if "pull_request" not in i  # exclude PRs
    ][:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub repo info")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--mode", choices=["info", "issues"], default="info")
    parser.add_argument("--state", choices=["open", "closed", "all"], default="open")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default=None, help="Path to save JSON output")
    args = parser.parse_args()

    if args.mode == "info":
        result = get_repo(args.repo)
        result["latest_release"] = get_latest_release(args.repo)
    else:
        result = {"repo": args.repo, "issues": get_issues(args.repo, args.state, args.limit)}

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
