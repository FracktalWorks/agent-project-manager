"""Task capture: intelligently add tasks to ClickUp under the right project/list/subtask.

Supports single-task and batch (--batch tasks.json) modes.
Scores placement automatically and suggests; only asks when confidence is LOW.

For non-interactive (agent/CI) use, pass --yes to auto-confirm all HIGH-confidence
placements and skip all prompts. Combine with --list-id to bypass placement scoring.

Usage (single task):
    python .github/skills/task-capture/scripts/capture_task.py "<task>" \\
        --assignee "Kiran" \\
        --list-id 901613553036 \\
        --due 2026-06-10 \\
        --yes

    python .github/skills/task-capture/scripts/capture_task.py "<task>" \\
        --assignee "Suryansh" \\
        --project "MDS" \\
        --due tomorrow \\
        --yes

Usage (batch):
    python .github/skills/task-capture/scripts/capture_task.py \\
        --batch tasks.json --due tomorrow --yes

Flags:
    --assignee <name>    Person's name (matched against hr_structure.json, fuzzy)
    --list-id <id>       ClickUp list ID — skips placement scoring entirely
    --project <name>     Hint to boost project scoring (substring match)
    --due <date>         Due date: ISO date, 'tomorrow', 'next week', '3 days'
    --yes                Auto-confirm HIGH-confidence suggestions; skip LOW prompts
    --batch <file>       JSON file with multiple tasks (see schema in SKILL.md)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

AGENT_DIR = Path(__file__).resolve().parents[5]

# Load .env from repo root without dotenv.find_dotenv() (safe in piped/subprocess contexts)
_env_path = AGENT_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}
DATA_DIR = AGENT_DIR / "agent-data"
OUTPUT_DIR = AGENT_DIR / "outputs"

STOPWORDS = {"a", "an", "the", "to", "for", "of", "in", "on", "at", "and", "or", "is", "it"}


# ─── HR & Assignee ────────────────────────────────────────────────────────────

def load_hr_ids() -> dict:
    hr_file = DATA_DIR / "hr_structure.json"
    if not hr_file.exists():
        return {}
    data = json.loads(hr_file.read_text(encoding="utf-8"))
    ids = {}
    for dept in data.get("departments", []):
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                name = member.get("name", "")
                uid = member.get("clickup_user_id")
                if uid:
                    ids[name.lower()] = (uid, name)
                    parts = name.split()
                    if parts:
                        ids[parts[0].lower()] = (uid, name)
                    if len(parts) > 1:
                        ids[parts[-1].lower()] = (uid, name)
    return ids


def resolve_assignee(name_hint: str, hr_ids: dict):
    return hr_ids.get(name_hint.strip().lower())


def prompt_assignee(hr_ids: dict):
    all_names = sorted(set(v[1] for v in hr_ids.values()))
    print("\nWho should this task be assigned to?")
    for i, n in enumerate(all_names, 1):
        print(f"  ({i}) {n}")
    try:
        choice = input("\nYour choice (number or name): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_names):
                return resolve_assignee(all_names[idx], hr_ids)
        except ValueError:
            return resolve_assignee(choice, hr_ids)
    except EOFError:
        pass
    return None


# ─── Project Data ─────────────────────────────────────────────────────────────

def load_project_registry() -> dict:
    proj_file = OUTPUT_DIR / "_memory" / "project_registry.json"
    if not proj_file.exists():
        return {}
    return json.loads(proj_file.read_text(encoding="utf-8"))


def fetch_space_lists(space_id: str) -> list:
    """Fetch all lists within a space (across folders and folderless)."""
    try:
        r = httpx.get(f"https://api.clickup.com/api/v2/space/{space_id}/folder",
                      headers=H, timeout=20)
        r.raise_for_status()
        lists = []
        for folder in r.json().get("folders", []):
            for lst in folder.get("lists", []):
                lists.append(lst)
        r2 = httpx.get(f"https://api.clickup.com/api/v2/space/{space_id}/list",
                       headers=H, timeout=20)
        r2.raise_for_status()
        for lst in r2.json().get("lists", []):
            lists.append(lst)
        return lists
    except Exception as e:
        print(f"  [warn] Could not fetch lists for space {space_id}: {e}")
        return []


def fetch_tasks_in_list(list_id: str) -> list:
    try:
        r = httpx.get(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                      headers=H, params={"include_closed": "false", "subtasks": "false"},
                      timeout=20)
        r.raise_for_status()
        return r.json().get("tasks", [])
    except Exception as e:
        print(f"  [warn] Could not fetch tasks: {e}")
        return []


# ─── Scoring ──────────────────────────────────────────────────────────────────

def _keywords(text: str) -> set:
    return {w.lower() for w in text.replace("-", " ").split()
            if w.lower() not in STOPWORDS and len(w) > 2}


def score_all_projects(task_desc: str, active_projects: list, project_hint: str = "") -> list:
    """Score every project+list against task_desc. Returns sorted list of candidates."""
    task_kw = _keywords(task_desc)
    all_candidates = []
    for proj in active_projects:
        space_id = proj.get("clickup_space_id") or proj.get("space_id")
        if not space_id:
            continue
        proj_kw = _keywords(proj.get("name", ""))
        lists = fetch_space_lists(space_id)
        for lst in lists:
            list_kw = _keywords(lst.get("name", ""))
            score = len(task_kw & proj_kw) * 2 + len(task_kw & list_kw) * 2
            if project_hint and project_hint.lower() in proj.get("name", "").lower():
                score += 5
            all_candidates.append({"project": proj, "list": lst, "score": score})
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    if all_candidates:
        top = all_candidates[0]["score"]
        second = all_candidates[1]["score"] if len(all_candidates) > 1 else 0
        all_candidates[0]["confidence"] = "HIGH" if top - second >= 3 and top > 0 else "LOW"
        for c in all_candidates[1:]:
            c["confidence"] = "LOW"
    return all_candidates


def find_subtask_parent(task_desc: str, list_id: str):
    """Return best matching parent task if keyword overlap >= 2, else None."""
    tasks = fetch_tasks_in_list(list_id)
    task_kw = _keywords(task_desc)
    best, best_overlap = None, 1
    for t in tasks:
        if t.get("parent"):
            continue
        overlap = len(task_kw & _keywords(t.get("name", "")))
        if overlap > best_overlap:
            best_overlap = overlap
            best = t
    return best


# ─── Date Helpers ─────────────────────────────────────────────────────────────

def ms(y, m, d) -> int:
    return int(datetime(y, m, d, 18, 0).timestamp() * 1000)


def parse_due_date(due_str: str) -> int:
    due_str = due_str.strip().lower()
    today = datetime.now()
    if due_str in ("today", "now"):
        d = today
    elif due_str in ("tomorrow", "next day"):
        d = today + timedelta(days=1)
    elif "next week" in due_str or "in a week" in due_str:
        d = today + timedelta(days=7)
    elif "3 days" in due_str or due_str == "soon":
        d = today + timedelta(days=3)
    else:
        try:
            d = datetime.fromisoformat(due_str)
        except Exception:
            d = today + timedelta(days=1)
    return ms(d.year, d.month, d.day)


# ─── ClickUp Create ───────────────────────────────────────────────────────────

def create_task_in_clickup(list_id, name, description, assignee_id, due_ms, parent_task_id=None):
    payload = {"name": name, "description": description, "due_date": due_ms,
               "due_date_time": False, "assignees": [assignee_id], "priority": 2,
               "notify_all": False, "status": "to do"}
    if parent_task_id:
        payload["parent"] = parent_task_id
    r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                   headers=H, json=payload, timeout=20)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.post(f"https://api.clickup.com/api/v2/list/{list_id}/task",
                       headers=H, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


# ─── Placement Resolution ─────────────────────────────────────────────────────

def resolve_placement(task_desc, active_projects, project_hint="", auto_yes=False):
    """Auto-suggest placement based on keyword score. Returns chosen candidate or None.

    When auto_yes=True (non-interactive mode):
      - HIGH confidence → accepted automatically, no prompt
      - LOW confidence  → top candidate returned with a warning printed to stderr
    """
    candidates = score_all_projects(task_desc, active_projects, project_hint)
    if not candidates:
        print("  No active projects found.", file=sys.stderr)
        return None

    top = candidates[0]
    if top["confidence"] == "HIGH":
        proj_name = top["project"]["name"]
        list_name = top["list"]["name"]
        if auto_yes:
            print(f"  [auto] Placing under: {proj_name} -> {list_name}", file=sys.stderr)
            return top
        try:
            ans = input(f"  Suggest: {proj_name} -> {list_name}  Confirm? (y/n): ").strip().lower()
        except EOFError:
            ans = "y"
        if ans == "y":
            return top

    # LOW confidence
    top3 = candidates[:3]
    if auto_yes:
        print(f'  [warn] Low-confidence placement for "{task_desc}": using "{top["project"]["name"]} -> {top["list"]["name"]}"', file=sys.stderr)
        print(f'  Pass --list-id <id> for an exact placement.', file=sys.stderr)
        return top

    print(f'\n  Placement options for "{task_desc}":')
    for i, c in enumerate(top3, 1):
        flag = "[?]" if c["confidence"] == "LOW" else "   "
        print(f"  ({i}) {flag} {c['project']['name']} -> {c['list']['name']}")
    print(f"  ({len(top3)+1})    None of the above - skip this task")
    try:
        choice = input("\n  Your choice (number): ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(top3):
            return top3[idx]
    except (ValueError, EOFError):
        pass
    return None


# ─── Single Task Flow ─────────────────────────────────────────────────────────

def capture_single(task_desc, assignee_id, assignee_name, active_projects,
                   project_hint="", due_str="tomorrow", auto_yes=False, list_id_override=None):
    if list_id_override:
        # Direct placement — skip scoring entirely
        candidate = {"list": {"id": list_id_override, "name": list_id_override},
                     "project": {"name": "(direct)"}}
    else:
        candidate = resolve_placement(task_desc, active_projects, project_hint, auto_yes)
    if not candidate:
        print("  Skipped.")
        return None

    list_id = candidate["list"]["id"]
    project_name = candidate["project"]["name"]
    list_name = candidate["list"]["name"]

    parent = find_subtask_parent(task_desc, list_id)
    parent_id = None
    if parent:
        if auto_yes:
            # In non-interactive mode, never auto-nest as subtask; keep as parent task
            pass
        else:
            try:
                ans = input(f"  Subtask of '{parent['name']}'? (y/n): ").strip().lower()
                if ans == "y":
                    parent_id = parent["id"]
            except EOFError:
                pass

    due_ms = parse_due_date(due_str)
    due_date = datetime.fromtimestamp(due_ms / 1000).strftime("%Y-%m-%d")

    task = create_task_in_clickup(list_id, task_desc, task_desc,
                                  assignee_id, due_ms, parent_id)
    subtask_note = f" (subtask of '{parent['name']}')" if parent_id else ""
    print(f'\n  Created: "{task["name"]}"')
    print(f"     {project_name} -> {list_name}{subtask_note}")
    print(f"     Assigned: {assignee_name}  Due: {due_date}")
    print(f"     Link: {task.get('url', '')}")
    return task


# ─── Batch Flow ───────────────────────────────────────────────────────────────

def capture_batch(batch_file, active_projects, hr_ids, default_due="tomorrow", auto_yes=False):
    """Score and batch-confirm placements for multiple tasks from a JSON file.

    JSON format: [{"task": "...", "assignee": "...", "project": "", "due": ""}, ...]
    """
    path = Path(batch_file)
    if not path.exists():
        print(f"Batch file not found: {batch_file}")
        sys.exit(1)

    tasks_input = json.loads(path.read_text(encoding="utf-8"))
    print(f"\nScoring {len(tasks_input)} tasks...\n")

    rows = []
    for item in tasks_input:
        task_desc = item.get("task", "")
        assignee_hint = item.get("assignee", "")
        project_hint = item.get("project", "")
        due_str = item.get("due", default_due)

        assignee_id, assignee_name = None, "?"
        if assignee_hint:
            result = resolve_assignee(assignee_hint, hr_ids)
            if result:
                assignee_id, assignee_name = result

        candidates = score_all_projects(task_desc, active_projects, project_hint)
        top = candidates[0] if candidates else None
        confidence = top["confidence"] if top else "LOW"
        placement_str = f"{top['project']['name']} -> {top['list']['name']}" if top else "Unknown"

        rows.append({
            "task": task_desc,
            "assignee_id": assignee_id,
            "assignee_name": assignee_name,
            "assignee_unresolved": not assignee_id,
            "candidate": top,
            "confidence": confidence,
            "placement_str": placement_str,
            "due_str": due_str,
        })

    # Print summary table
    col_t = min(max(len(r["task"]) for r in rows), 40)
    col_p = min(max(len(r["placement_str"]) for r in rows), 45)
    print(f"  {'#':<3}  {'Task':<{col_t}}  {'Assignee':<16}  {'Placement':<{col_p}}  Conf")
    print(f"  {'-'*3}  {'-'*col_t}  {'-'*16}  {'-'*col_p}  ----")
    for i, row in enumerate(rows, 1):
        flag = "[?]" if row["confidence"] == "LOW" or row["assignee_unresolved"] else "   "
        print(f"  {i:<3}  {flag} {row['task'][:col_t-4]:<{col_t-4}}  "
              f"{row['assignee_name']:<16}  {row['placement_str'][:col_p]:<{col_p}}  {row['confidence']}")

    flagged = [i + 1 for i, r in enumerate(rows)
               if r["confidence"] == "LOW" or r["assignee_unresolved"]]
    if flagged:
        print(f"\n  Tasks needing clarification: {flagged}")

    if auto_yes:
        ans = "y"
    else:
        try:
            ans = input(
                "\nConfirm all? Or enter numbers to fix (e.g. 2,4), or 'n' to cancel: "
            ).strip().lower()
        except EOFError:
            ans = "n"

    if ans == "n":
        print("Cancelled.")
        return

    # Always fix flagged, plus any user-specified numbers
    to_fix = set(flagged)
    if ans not in ("y", "yes", ""):
        for part in ans.split(","):
            try:
                to_fix.add(int(part.strip()))
            except ValueError:
                pass

    for i, row in enumerate(rows, 1):
        if i not in to_fix:
            continue
        print(f'\n  Fixing task #{i}: "{row["task"]}"')
        if not row["assignee_id"]:
            result = prompt_assignee(hr_ids)
            if result:
                row["assignee_id"], row["assignee_name"] = result
        project_hint = row["candidate"]["project"]["name"] if row["candidate"] else ""
        new_candidate = resolve_placement(row["task"], active_projects, project_hint)
        if new_candidate:
            row["candidate"] = new_candidate
            row["placement_str"] = (
                f"{new_candidate['project']['name']} -> {new_candidate['list']['name']}"
            )

    print("\n  Final plan:")
    for i, row in enumerate(rows, 1):
        if row["candidate"] and row["assignee_id"]:
            print(f"  ok #{i}  {row['task'][:40]:<40}  {row['assignee_name']:<16}  {row['placement_str']}")
        else:
            print(f"  XX #{i}  {row['task'][:40]:<40}  SKIPPED (missing assignee or placement)")

    if auto_yes:
        confirm = "y"
    else:
        try:
            confirm = input("\nCreate all ok tasks? (y/n): ").strip().lower()
        except EOFError:
            confirm = "n"

    if confirm != "y":
        print("Cancelled.")
        return

    print()
    for i, row in enumerate(rows, 1):
        if not row["candidate"] or not row["assignee_id"]:
            print(f"  skip #{i}")
            continue
        list_id = row["candidate"]["list"]["id"]
        due_ms = parse_due_date(row["due_str"])
        try:
            task = create_task_in_clickup(
                list_id, row["task"], row["task"], row["assignee_id"], due_ms
            )
            print(f"  created #{i}: {task.get('url', task.get('id'))}")
        except Exception as e:
            print(f"  failed #{i}: {e}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Capture a task into ClickUp under the right project/list."
    )
    parser.add_argument("task", nargs="?", default=None, help="Task description")
    parser.add_argument("--assignee", default="", help="Assignee name (matched against hr_structure.json)")
    parser.add_argument("--list-id", default="", dest="list_id",
                        help="ClickUp list ID — skips placement scoring entirely")
    parser.add_argument("--project", default="", help="Project name hint to boost scoring")
    parser.add_argument("--due", default="tomorrow", help="Due date: ISO date, 'tomorrow', 'next week', '3 days'")
    parser.add_argument("--yes", action="store_true",
                        help="Non-interactive: auto-confirm HIGH confidence placements, skip all prompts")
    parser.add_argument("--batch", default="", metavar="FILE",
                        help="JSON file with multiple tasks [{\"task\": ..., \"assignee\": ..., \"due\": ...}]")
    args = parser.parse_args()

    registry = load_project_registry()
    hr_ids = load_hr_ids()
    active_projects = registry.get("projects", [])

    # Batch mode
    if args.batch:
        capture_batch(args.batch, active_projects, hr_ids, args.due, auto_yes=args.yes)
        return

    # Single task mode
    if not args.task:
        parser.print_help()
        sys.exit(1)

    task_desc = args.task
    print(f'Capturing task: "{task_desc}"')

    assignee_id, assignee_name = None, ""
    if args.assignee:
        result = resolve_assignee(args.assignee, hr_ids)
        if result:
            assignee_id, assignee_name = result
        else:
            print(f"  '{args.assignee}' not found in HR data.", file=sys.stderr)

    if not assignee_id:
        if args.yes:
            print("Error: --assignee is required in --yes (non-interactive) mode.", file=sys.stderr)
            sys.exit(1)
        result = prompt_assignee(hr_ids)
        if result:
            assignee_id, assignee_name = result

    if not assignee_id:
        print("No valid assignee. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"-> Assignee: {assignee_name}")
    capture_single(
        task_desc, assignee_id, assignee_name, active_projects,
        project_hint=args.project,
        due_str=args.due,
        auto_yes=args.yes,
        list_id_override=args.list_id or None,
    )


if __name__ == "__main__":
    main()
