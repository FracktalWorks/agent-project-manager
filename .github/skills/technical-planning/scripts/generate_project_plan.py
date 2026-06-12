#!/usr/bin/env python3
"""
generate_project_plan.py — Generate a single, ClickUp-ready project plan.

Produces:
  outputs/{slug}/project-plan/project_plan.md   (source of truth)
  outputs/{slug}/project-plan/metadata.json     (slug, dates, ClickUp IDs)

Then call render_plan.py to export to DOCX + PDF.

Usage:
  # Generate plan from CLI args
  python .github/skills/technical-planning/scripts/generate_project_plan.py \\
    --project-name "Penrose V2" \\
    --description "Develop and launch the Penrose V2 filament dryer..." \\
    --start-date 2026-06-01 \\
    --end-date 2026-09-30 \\
    --workstreams "Hardware Design,Firmware,Testing & QC,Procurement,Documentation"

  # Generate plan from a full JSON spec (richer — agent builds the spec first)
  python .github/skills/technical-planning/scripts/generate_project_plan.py \\
    --spec outputs/penrose-v2/project-plan/spec.json

  # Skip DOCX/PDF rendering (generate MD only)
  python .github/skills/technical-planning/scripts/generate_project_plan.py \\
    --project-name "..." --no-render

  # Re-render an existing MD to DOCX + PDF without regenerating content:
  python .github/skills/technical-planning/scripts/render_plan.py \\
    --input outputs/penrose-v2/project-plan/project_plan.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

HR_FILE = REPO_ROOT / "data" / "hr_structure.json"
OUTPUTS_DIR = REPO_ROOT / "outputs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def today_str() -> str:
    return datetime.now().strftime("%B %d, %Y")


def fmt_date(d: str | None) -> str:
    """Format a YYYY-MM-DD string to 'Jun 01, 2026'."""
    if not d:
        return "TBD"
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return d


def load_hr() -> list[dict]:
    """Return flat list of all members from hr_structure.json."""
    if not HR_FILE.exists():
        return []
    data = json.loads(HR_FILE.read_text(encoding="utf-8"))
    members = []
    for dept in data.get("departments", []):
        for team in dept.get("teams", []):
            for m in team.get("members", []):
                members.append({
                    "name": m.get("name", ""),
                    "role": m.get("role", ""),
                    "department": dept.get("name", ""),
                    "skills": m.get("skills", []),
                    "available_hours_per_week": m.get("available_hours_per_week", 40),
                    "clickup_user_id": m.get("clickup_user_id"),
                })
    return members


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  Saved: {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Default structure builders
# ---------------------------------------------------------------------------

def build_default_workstreams(
    names: list[str],
    start_date: str,
    end_date: str,
) -> list[dict]:
    """
    Build placeholder work streams with skeleton tasks.
    The agent enriches these before writing the final plan.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        total_days = max((end - start).days, 7)
    except ValueError:
        start = datetime.now()
        total_days = 90

    streams = []
    for i, name in enumerate(names):
        ws_start = start + timedelta(days=i * 3)
        ws_end = start + timedelta(days=total_days - i * 2)
        streams.append({
            "name": name,
            "owner": "TBD",
            "start": ws_start.strftime("%Y-%m-%d"),
            "end": ws_end.strftime("%Y-%m-%d"),
            "tasks": [
                {
                    "task": f"{name} — Planning & Scope",
                    "subtask": "Define deliverables and success criteria",
                    "owner": "TBD",
                    "duration": "1 week",
                    "start": ws_start.strftime("%Y-%m-%d"),
                    "end": (ws_start + timedelta(weeks=1)).strftime("%Y-%m-%d"),
                    "status": "To Do",
                },
                {
                    "task": f"{name} — Execution",
                    "subtask": "Core work for this stream",
                    "owner": "TBD",
                    "duration": "TBD",
                    "start": (ws_start + timedelta(weeks=1)).strftime("%Y-%m-%d"),
                    "end": (ws_end - timedelta(weeks=1)).strftime("%Y-%m-%d"),
                    "status": "To Do",
                },
                {
                    "task": f"{name} — Review & Sign-off",
                    "subtask": "Quality check and stakeholder review",
                    "owner": "TBD",
                    "duration": "1 week",
                    "start": (ws_end - timedelta(weeks=1)).strftime("%Y-%m-%d"),
                    "end": ws_end.strftime("%Y-%m-%d"),
                    "status": "To Do",
                },
            ],
        })
    return streams


def build_default_milestones(start_date: str, end_date: str) -> list[dict]:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        total = max((end - start).days, 7)
        q1 = start + timedelta(days=total // 4)
        mid = start + timedelta(days=total // 2)
        q3 = start + timedelta(days=3 * total // 4)
    except ValueError:
        now = datetime.now()
        start, q1, mid, q3, end = now, now, now, now, now

    return [
        {"milestone": "Kick-off", "date": start.strftime("%Y-%m-%d"), "owner": "TBD", "status": "Upcoming"},
        {"milestone": "Phase 1 Complete", "date": q1.strftime("%Y-%m-%d"), "owner": "TBD", "status": "Upcoming"},
        {"milestone": "Mid-point Review", "date": mid.strftime("%Y-%m-%d"), "owner": "TBD", "status": "Upcoming"},
        {"milestone": "Phase 2 Complete", "date": q3.strftime("%Y-%m-%d"), "owner": "TBD", "status": "Upcoming"},
        {"milestone": "Project Delivery", "date": end.strftime("%Y-%m-%d"), "owner": "TBD", "status": "Upcoming"},
    ]


def build_default_risks() -> list[dict]:
    return [
        {
            "risk": "Key team member unavailable",
            "likelihood": "M",
            "impact": "H",
            "mitigation": "Cross-train a backup; document all work",
            "owner": "TBD",
        },
        {
            "risk": "Supplier / component delays",
            "likelihood": "M",
            "impact": "H",
            "mitigation": "Source 2 suppliers per critical component; order early",
            "owner": "TBD",
        },
        {
            "risk": "Scope creep",
            "likelihood": "H",
            "impact": "M",
            "mitigation": "Lock scope at kick-off; change requests require PM approval",
            "owner": "TBD",
        },
        {
            "risk": "Technical integration failures",
            "likelihood": "M",
            "impact": "H",
            "mitigation": "Schedule integration milestones early; run parallel tracks",
            "owner": "TBD",
        },
    ]


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_md(
    project_name: str,
    description: str,
    objectives: list[str],
    scope_in: list[str],
    scope_out: list[str],
    workstreams: list[dict],
    milestones: list[dict],
    risks: list[dict],
    team: list[dict],
    open_questions: list[str],
    start_date: str,
    end_date: str,
    version: str = "1.0",
) -> str:
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines += [
        f"# Project Plan — {project_name}",
        "",
        f"**Version:** {version}  ",
        f"**Date:** {today_str()}  ",
        f"**Period:** {fmt_date(start_date)} → {fmt_date(end_date)}  ",
        "",
        "---",
        "",
    ]

    # ── 1. Project Summary ──────────────────────────────────────────────────
    lines += [
        "## 1. Project Summary",
        "",
        description,
        "",
    ]
    if objectives:
        lines.append("**Objectives:**")
        lines += [f"- {o}" for o in objectives]
        lines.append("")
    if scope_in:
        lines.append("**In Scope:**")
        lines += [f"- {s}" for s in scope_in]
        lines.append("")
    if scope_out:
        lines.append("**Out of Scope:**")
        lines += [f"- {s}" for s in scope_out]
        lines.append("")
    lines += ["---", ""]

    # ── 2. Team & Roles ─────────────────────────────────────────────────────
    lines += [
        "## 2. Team & Roles",
        "",
        "| Name | Role | Work Stream | Avail. h/wk |",
        "|------|------|-------------|-------------|",
    ]
    for m in team:
        avail = m.get("available_hours_per_week", "—")
        lines.append(
            f"| {m['name']} | {m['role']} | {m.get('work_stream', 'TBD')} | {avail} |"
        )
    lines += ["", "---", ""]

    # ── 3. Work Streams & Tasks ─────────────────────────────────────────────
    lines += [
        "## 3. Work Streams & Tasks",
        "",
        "> Each work stream maps to a ClickUp List. Tasks → ClickUp Tasks; subtasks → ClickUp Subtasks.",
        "",
    ]
    for ws in workstreams:
        lines += [
            f"### {ws['name']}",
            "",
            f"**Owner:** {ws.get('owner', 'TBD')}  ",
            f"**Timeline:** {fmt_date(ws.get('start'))} → {fmt_date(ws.get('end'))}  ",
            "",
            "| Task | Subtask | Owner | Duration | Start | End | Status |",
            "|------|---------|-------|----------|-------|-----|--------|",
        ]
        for t in ws.get("tasks", []):
            lines.append(
                f"| {t.get('task', '')} "
                f"| {t.get('subtask', '')} "
                f"| {t.get('owner', 'TBD')} "
                f"| {t.get('duration', 'TBD')} "
                f"| {fmt_date(t.get('start'))} "
                f"| {fmt_date(t.get('end'))} "
                f"| {t.get('status', 'To Do')} |"
            )
        lines += ["", ""]
    lines += ["---", ""]

    # ── 4. Milestone Timeline ───────────────────────────────────────────────
    lines += [
        "## 4. Milestone Timeline",
        "",
        "| Milestone | Target Date | Owner | Status |",
        "|-----------|-------------|-------|--------|",
    ]
    for m in milestones:
        lines.append(
            f"| {m['milestone']} | {fmt_date(m['date'])} | {m.get('owner', 'TBD')} | {m.get('status', 'Upcoming')} |"
        )
    lines += ["", "---", ""]

    # ── 5. Risks & Mitigations ──────────────────────────────────────────────
    lines += [
        "## 5. Risks & Mitigations",
        "",
        "| Risk | Likelihood | Impact | Mitigation | Owner |",
        "|------|-----------|--------|------------|-------|",
    ]
    for r in risks:
        lines.append(
            f"| {r['risk']} | {r.get('likelihood', 'M')} | {r.get('impact', 'M')} "
            f"| {r.get('mitigation', '')} | {r.get('owner', 'TBD')} |"
        )
    lines += ["", "---", ""]

    # ── 6. Open Questions ───────────────────────────────────────────────────
    lines += ["## 6. Open Questions", ""]
    if open_questions:
        lines += [f"- [ ] {q}" for q in open_questions]
    else:
        lines.append("- [ ] *(none yet — add blockers or unresolved decisions here)*")
    lines += ["", "---", ""]

    # ── Footer ───────────────────────────────────────────────────────────────
    lines += [
        f"*Generated by Agent-Project-Manager on {today_str()}.*  ",
        f"*Edit `project_plan.md` then run `render_plan.py` to re-export to DOCX and PDF.*",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a ClickUp-ready project plan")
    p.add_argument("--project-name", default="New Project")
    p.add_argument("--description", default="")
    p.add_argument("--start-date", default=date.today().isoformat())
    p.add_argument("--end-date", default=(date.today() + timedelta(days=90)).isoformat())
    p.add_argument(
        "--workstreams",
        default="",
        help="Comma-separated work stream names, e.g. 'Hardware,Firmware,Testing'",
    )
    p.add_argument(
        "--spec",
        default=None,
        help="Path to a JSON spec file with full plan details (overrides other args)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output directory (default: outputs/{slug}/project-plan/)",
    )
    p.add_argument(
        "--no-render",
        action="store_true",
        help="Skip DOCX/PDF rendering — generate MD only",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load spec JSON if provided ──────────────────────────────────────────
    spec: dict[str, Any] = {}
    if args.spec:
        spec_path = Path(args.spec)
        if not spec_path.exists():
            print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
            sys.exit(1)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

    project_name: str = spec.get("project_name") or args.project_name
    description: str = spec.get("description") or args.description or f"{project_name} project plan."
    start_date: str = spec.get("start_date") or args.start_date
    end_date: str = spec.get("end_date") or args.end_date
    version: str = spec.get("version", "1.0")

    objectives: list[str] = spec.get("objectives", [])
    scope_in: list[str] = spec.get("scope_in", [])
    scope_out: list[str] = spec.get("scope_out", [])
    open_questions: list[str] = spec.get("open_questions", [])

    # Work streams: spec > --workstreams arg > generic defaults
    if spec.get("workstreams"):
        workstreams = spec["workstreams"]
    elif args.workstreams:
        ws_names = [w.strip() for w in args.workstreams.split(",") if w.strip()]
        workstreams = build_default_workstreams(ws_names, start_date, end_date)
    else:
        workstreams = build_default_workstreams(
            ["Planning", "Execution", "Testing & QC", "Documentation"],
            start_date,
            end_date,
        )

    milestones = spec.get("milestones") or build_default_milestones(start_date, end_date)
    risks = spec.get("risks") or build_default_risks()

    # Team: from spec, or pull all active HR members
    if spec.get("team"):
        team = spec["team"]
    else:
        hr = load_hr()
        team = [
            {
                "name": m["name"],
                "role": m["role"],
                "work_stream": "TBD",
                "available_hours_per_week": m["available_hours_per_week"],
            }
            for m in hr
            if m.get("name")
        ]

    # ── Output directory ────────────────────────────────────────────────────
    slug = slugify(project_name)
    out_dir = Path(args.output) if args.output else (OUTPUTS_DIR / slug / "project-plan")

    # ── Render Markdown ─────────────────────────────────────────────────────
    md_content = render_md(
        project_name=project_name,
        description=description,
        objectives=objectives,
        scope_in=scope_in,
        scope_out=scope_out,
        workstreams=workstreams,
        milestones=milestones,
        risks=risks,
        team=team,
        open_questions=open_questions,
        start_date=start_date,
        end_date=end_date,
        version=version,
    )

    md_path = out_dir / "project_plan.md"
    write_file(md_path, md_content)

    # ── Write metadata ──────────────────────────────────────────────────────
    metadata = {
        "project_name": project_name,
        "slug": slug,
        "version": version,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.now().isoformat(),
        "plan_md": str(md_path.relative_to(REPO_ROOT)),
        "plan_docx": str((out_dir / "project_plan.docx").relative_to(REPO_ROOT)),
        "plan_pdf": str((out_dir / "project_plan.pdf").relative_to(REPO_ROOT)),
        "clickup_space_id": None,
        "clickup_list_ids": {},
    }
    write_file(out_dir / "metadata.json", json.dumps(metadata, indent=2))

    print(f"\n  Plan:     {md_path}")
    print(f"  Metadata: {out_dir / 'metadata.json'}")

    # ── Auto-render to DOCX + PDF ───────────────────────────────────────────
    if not args.no_render:
        render_script = Path(__file__).parent / "render_plan.py"
        if render_script.exists():
            print("\n  Rendering to DOCX + PDF...")
            result = subprocess.run(
                [sys.executable, str(render_script), "--input", str(md_path)],
                capture_output=False,
            )
            if result.returncode != 0:
                print("  WARNING: render_plan.py returned a non-zero exit code.")
        else:
            print("\n  NOTE: render_plan.py not found — run it manually to export DOCX/PDF.")


if __name__ == "__main__":
    main()

