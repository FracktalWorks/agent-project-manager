"""
plan_project.py — Generate a structured project plan JSON.

Usage:
    python .github/skills/project-planning/scripts/plan_project.py \
        --name "Website Redesign" \
        --goal "Redesign the company website for Q3 launch" \
        --deadline "2026-09-30" \
        --output outputs/website-redesign/step_1_project_plan.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path

AGENT_DIR   = Path(__file__).resolve().parents[4]
DATA_DIR    = AGENT_DIR / "agent-data"
OUTPUTS_DIR = AGENT_DIR / "outputs"

sys.path.insert(0, str(AGENT_DIR / ".tmp" / "scripts"))
from project_data_manager import save_step, slugify


def score_priority(impact: int, urgency: int, effort_inv: int) -> int:
    return impact * urgency * effort_inv


def load_active_projects() -> list[dict]:
    path = DATA_DIR / "project_priorities.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("projects", [])
    return []


def build_plan(name: str, goal: str, deadline: str | None) -> dict:
    slug = slugify(name)
    today = date.today().isoformat()

    plan = {
        "project_name": name,
        "slug": slug,
        "goal": goal,
        "created_date": today,
        "deadline": deadline or "TBD",
        "priority_score": None,  # filled by agent after scoring
        "phases": [
            {
                "name": "Phase 1 — Discovery & Planning",
                "due_date": deadline or "TBD",
                "tasks": [
                    {
                        "title": "Define project scope and success criteria",
                        "owner_role": "Project Manager",
                        "effort_hours": 4,
                        "due_date": "TBD",
                        "dependencies": [],
                    },
                    {
                        "title": "Identify stakeholders and gather requirements",
                        "owner_role": "Project Manager",
                        "effort_hours": 8,
                        "due_date": "TBD",
                        "dependencies": [],
                    },
                ],
            },
            {
                "name": "Phase 2 — Execution",
                "due_date": deadline or "TBD",
                "tasks": [],
            },
            {
                "name": "Phase 3 — Review & Handoff",
                "due_date": deadline or "TBD",
                "tasks": [
                    {
                        "title": "Final review and sign-off",
                        "owner_role": "Project Manager",
                        "effort_hours": 2,
                        "due_date": "TBD",
                        "dependencies": [],
                    },
                ],
            },
        ],
        "notes": f"Goal: {goal}",
    }
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a structured project plan JSON.")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--goal", required=True, help="Project goal / one-liner")
    parser.add_argument("--deadline", default=None, help="Hard deadline (YYYY-MM-DD)")
    parser.add_argument("--output", default=None, help="Output JSON path (optional)")
    args = parser.parse_args()

    plan = build_plan(args.name, args.goal, args.deadline)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"Plan saved to {out}")
    else:
        # Auto-save using campaign_data_manager
        save_step(plan["slug"], 1, "project_plan", plan)
        print(f"Plan saved to outputs/{plan['slug']}/step_1_project_plan.json")

    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
