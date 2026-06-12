"""
query_hr.py — Query the company HR structure.

Usage:
    python .github/skills/hr-structure/scripts/query_hr.py --skill Python
    python .github/skills/hr-structure/scripts/query_hr.py --role "Senior Engineer"
    python .github/skills/hr-structure/scripts/query_hr.py --available-hours 8
    python .github/skills/hr-structure/scripts/query_hr.py --list-all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[4]
HR_FILE   = AGENT_DIR / "data" / "hr_structure.json"


def load_hr() -> dict:
    if not HR_FILE.exists():
        raise FileNotFoundError(
            f"HR structure file not found: {HR_FILE}\n"
            "Please populate data/hr_structure.json first."
        )
    return json.loads(HR_FILE.read_text(encoding="utf-8"))


def all_members(hr: dict) -> list[dict]:
    members = []
    for dept in hr.get("departments", []):
        for team in dept.get("teams", []):
            for m in team.get("members", []):
                members.append({
                    "department": dept["name"],
                    "team": team["name"],
                    **m,
                })
    return members


def filter_members(
    members: list[dict],
    skill: str | None = None,
    role: str | None = None,
    min_hours: float = 0,
) -> list[dict]:
    results = []
    for m in members:
        if m.get("status", "active") != "active":
            continue
        if skill and skill.lower() not in [s.lower() for s in m.get("skills", [])]:
            continue
        if role and role.lower() not in m.get("role", "").lower():
            continue
        if m.get("available_hours_per_week", 0) < min_hours:
            continue
        results.append(m)
    return sorted(results, key=lambda x: x.get("available_hours_per_week", 0), reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query HR structure.")
    parser.add_argument("--skill", default=None, help="Filter by skill (e.g. Python)")
    parser.add_argument("--role", default=None, help="Filter by role keyword")
    parser.add_argument("--available-hours", type=float, default=0,
                        help="Minimum available hours per week")
    parser.add_argument("--list-all", action="store_true", help="List all active members")
    args = parser.parse_args()

    hr      = load_hr()
    members = all_members(hr)

    if args.list_all:
        print(json.dumps(members, indent=2))
        return

    results = filter_members(
        members,
        skill=args.skill,
        role=args.role,
        min_hours=args.available_hours,
    )

    if not results:
        print("No matching members found. Consider re-prioritising or checking capacity.")
    else:
        print(f"Found {len(results)} candidate(s):\n")
        for m in results[:5]:
            print(
                f"  {m['name']} — {m['role']} ({m['department']} / {m['team']})\n"
                f"    Skills: {', '.join(m.get('skills', []))}\n"
                f"    Available: {m.get('available_hours_per_week', 0)}h/week\n"
            )


if __name__ == "__main__":
    main()
