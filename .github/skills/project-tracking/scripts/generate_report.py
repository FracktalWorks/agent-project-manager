"""
generate_report.py — Format a human-readable status report from a fetch_status JSON.

Usage:
    # From a pre-fetched JSON file
    python .github/skills/project-tracking/scripts/generate_report.py \
        --input outputs/my-project/tasks.json \
        --project-name "My Project"

    # Directly by project slug (fetches from ClickUp first)
    python .github/skills/project-tracking/scripts/generate_report.py \
        --slug my-project \
        --project-name "My Project"

    # All projects at once
    python .github/skills/project-tracking/scripts/generate_report.py \
        --slug "" \
        --project-name "Fracktal Works"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(AGENT_DIR / ".github" / "skills" / "clickup-ops" / "scripts"))

from clickup_client import ClickUpClient  # noqa: E402


FLAG_ICONS = {
    "on_track": "✅",
    "at_risk":  "⚠️",
    "blocked":  "❌",
}


def _load_env() -> None:
    env_path = AGENT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _load_project_registry() -> list[dict]:
    path = AGENT_DIR / "outputs" / "_memory" / "project_registry.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("projects", [])


def _fetch_tasks_for_list(client: ClickUpClient, list_id: str, assignee_filter: str = "") -> list[dict]:
    from datetime import date, datetime, timezone

    def _days_until(due_ms):
        if due_ms is None:
            return None
        due_dt = datetime.fromtimestamp(due_ms / 1000, tz=timezone.utc).date()
        return (due_dt - date.today()).days

    tasks = client.get_tasks(list_id)
    result = []
    for t in tasks:
        assignees = [a.get("username", "") for a in (t.get("assignees") or []) if a]
        assignee_str = ", ".join(assignees)
        if assignee_filter and assignee_filter.lower() not in assignee_str.lower():
            continue
        status = (t.get("status", {}).get("status") or "").lower()
        if "block" in status:
            flag = "blocked"
        else:
            days = _days_until(t.get("due_date") and int(t["due_date"]))
            flag = "at_risk" if (days is not None and days <= 3) else "on_track"
        due_raw = t.get("due_date")
        result.append({
            "id": t["id"],
            "title": t["name"],
            "assignee": assignee_str,
            "due_date": datetime.fromtimestamp(int(due_raw) / 1000, tz=timezone.utc).date().isoformat()
                        if due_raw else None,
            "status": (t.get("status", {}).get("status") or "unknown"),
            "flag": flag,
        })
    return result


def _fetch_data(slug: str) -> dict:
    """Fetch task data from ClickUp. If slug is empty, fetch all projects."""
    from datetime import datetime, timezone
    _load_env()
    token = os.environ.get("CLICKUP_API_TOKEN") or ""
    team_id = os.environ.get("CLICKUP_TEAM_ID") or ""
    client = ClickUpClient(token=token, team_id=team_id)
    now = datetime.now(timezone.utc).isoformat()

    if slug:
        projects = _load_project_registry()
        target = next((p for p in projects if p.get("slug") == slug), None)
        if not target:
            print(f"Project '{slug}' not found in project_registry.json", file=sys.stderr)
            sys.exit(1)
        list_id = target.get("clickup_list_id")
        if not list_id:
            print(f"Project '{slug}' has no clickup_list_id", file=sys.stderr)
            sys.exit(1)
        return {
            "fetched_at": now,
            "tasks": _fetch_tasks_for_list(client, list_id),
        }

    # All projects
    projects = _load_project_registry()
    if not projects:
        print("No projects found in project_registry.json", file=sys.stderr)
        sys.exit(1)
    project_reports = []
    for proj in projects:
        list_id = proj.get("clickup_list_id")
        if not list_id:
            continue
        project_reports.append({
            "project_name": proj.get("name", proj.get("slug", list_id)),
            "list_id": list_id,
            "tasks": _fetch_tasks_for_list(client, list_id),
        })
    return {"fetched_at": now, "projects": project_reports}


def render_report(data: dict, project_name: str) -> str:
    tasks     = data.get("tasks", [])
    at_risk   = [t for t in tasks if t["flag"] == "at_risk"]
    blocked   = [t for t in tasks if t["flag"] == "blocked"]
    on_track  = [t for t in tasks if t["flag"] == "on_track"]

    if blocked:
        overall = "❌ BLOCKED"
    elif at_risk:
        overall = "⚠️  AT RISK"
    else:
        overall = "✅ ON TRACK"

    lines = [
        f"# Status Report — {project_name}",
        f"**Fetched:** {data.get('fetched_at', 'unknown')}",
        f"**Overall:** {overall}",
        "",
    ]

    def render_group(title: str, group: list[dict]) -> None:
        if not group:
            return
        lines.append(f"## {title}")
        for t in group:
            icon = FLAG_ICONS.get(t["flag"], "•")
            due  = t.get("due_date") or "no deadline"
            assignee = t.get("assignee") or "unassigned"
            lines.append(f"- {icon} **{t['title']}** — {assignee} · due {due}")
        lines.append("")

    render_group("❌ Blocked", blocked)
    render_group("⚠️  At Risk", at_risk)
    render_group("✅ On Track", on_track)

    return "\n".join(lines)


def render_full_portfolio_report(data: dict) -> str:
    """Render a multi-project portfolio report."""
    projects = data.get("projects", [])
    now = data.get("fetched_at", "unknown")
    lines = [
        f"# 📊 Portfolio Status Report — Fracktal Works",
        f"**Fetched:** {now}",
        "",
    ]

    total_tasks = sum(len(p.get("tasks", [])) for p in projects)
    total_blocked = sum(1 for p in projects for t in p.get("tasks", []) if t["flag"] == "blocked")
    total_at_risk = sum(1 for p in projects for t in p.get("tasks", []) if t["flag"] == "at_risk")
    lines.append(f"**{len(projects)} projects · {total_tasks} tasks · {total_blocked} blocked · {total_at_risk} at risk**")
    lines.append("")

    for proj in projects:
        proj_name = proj.get("project_name", "Unknown")
        tasks = proj.get("tasks", [])
        blocked = [t for t in tasks if t["flag"] == "blocked"]
        at_risk = [t for t in tasks if t["flag"] == "at_risk"]

        if blocked:
            status = "❌ BLOCKED"
        elif at_risk:
            status = "⚠️  AT RISK"
        else:
            status = "✅ OK"

        lines.append(f"## {proj_name} — {status}")
        for t in blocked + at_risk:
            icon = FLAG_ICONS.get(t["flag"], "•")
            due = t.get("due_date") or "no deadline"
            lines.append(f"  - {icon} **{t['title']}** — {t.get('assignee') or 'unassigned'} · due {due}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a status report.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input", help="Path to fetch_status JSON output (skip ClickUp fetch)")
    group.add_argument("--slug", help="Project slug to fetch from ClickUp (empty string = all projects)")
    parser.add_argument("--project-name", default="Project", help="Display name for the project")
    args = parser.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        report = render_report(data, args.project_name)
    elif args.slug is not None:
        data = _fetch_data(args.slug)
        if "projects" in data:
            report = render_full_portfolio_report(data)
        else:
            report = render_report(data, args.project_name)
    else:
        parser.error("Either --input or --slug is required")

    print(report)


if __name__ == "__main__":
    main()
