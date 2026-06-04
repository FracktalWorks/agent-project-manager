"""
generate_report.py — Format a human-readable status report from a fetch_status JSON.

Usage:
    python skills/project-tracking/scripts/generate_report.py \
        --input outputs/my-project/tasks.json \
        --project-name "My Project"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


FLAG_ICONS = {
    "on_track": "✅",
    "at_risk":  "⚠️",
    "blocked":  "❌",
}


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a status report.")
    parser.add_argument("--input", required=True, help="Path to fetch_status JSON output")
    parser.add_argument("--project-name", default="Project", help="Display name for the project")
    args = parser.parse_args()

    data   = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = render_report(data, args.project_name)
    print(report)


if __name__ == "__main__":
    main()
