#!/usr/bin/env python3
"""
estimate_task_times.py — Analyse task names and backfill ClickUp time_estimate.

Fetches all active tasks, estimates hours per task based on keyword analysis
of the task name, and writes the time_estimate to ClickUp (only when currently
missing or zero). Skips backlog tasks by default.

Usage:
  # Preview only — no writes to ClickUp
  python .github/skills/daily-morning-report/scripts/estimate_task_times.py --dry-run

  # Backfill all active tasks that lack a time_estimate
  python .github/skills/daily-morning-report/scripts/estimate_task_times.py

  # Force-update ALL active tasks (overwrite existing estimates)
  python .github/skills/daily-morning-report/scripts/estimate_task_times.py --force

  # Scope to a single list
  python .github/skills/daily-morning-report/scripts/estimate_task_times.py --list-id 901611050642
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parent.parent
REPO_ROOT  = SKILLS_DIR.parent.parent

OUTPUT_FILE = REPO_ROOT / "outputs" / "time_estimate_log.json"


def load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def get_client():
    sys.path.insert(0, str(SKILLS_DIR / "clickup-ops" / "scripts"))
    from clickup_client import ClickUpClient  # noqa: E402
    return ClickUpClient()


# ---------------------------------------------------------------------------
# Time estimation engine — keyword-based heuristics
# ---------------------------------------------------------------------------
# Each rule is (regex_pattern, hours, confidence_note).
# Patterns are checked in order; first match wins.
# Hours are in decimal (e.g. 2.5 = 2h 30m).

ESTIMATION_RULES: list[tuple[str, float, str]] = [
    # NOTE: Order matters — first match wins.
    # Rules are ordered from most-specific/narrowest → broadest/generic.

    # ── Review / approval (BEFORE design/dev — otherwise "Review Design" → 20h) ─
    (r"\breview\b.*\b(?:design|cad|model|code|architecture|schematic|pcb)\b", 6.0, "technical review"),
    (r"\breview\b", 3.0, "review"),
    (r"\bapprov(?:e|al)\b", 2.0, "approval"),
    (r"\bfinali[sz]e\b", 4.0, "finalization"),

    # ── Quick coordination (low effort, check early) ──────────────────────
    (r"\bfollow[\s-]*up\b", 1.5, "follow-up"),
    (r"\b(?:coordinate|coordination|liaise)\b", 3.0, "coordination"),
    (r"\bkt\b", 2.0, "knowledge transfer"),
    (r"\b(?:meeting|call|discuss)\b", 2.0, "meeting"),
    (r"\bdemo(?:nstration)?\b.*\b(?:prep|preparation|plan)\b", 8.0, "demo preparation"),
    (r"\bdemo(?:nstration)?\b", 6.0, "demo"),
    (r"\bpresentation\b", 6.0, "presentation"),

    # ── Assembly / manufacturing (BEFORE testing — avoid description false matches) ─
    (r"\bassembl(?:e|y|ing)\b", 12.0, "assembly"),
    (r"\binstall(?:ation)?\b", 8.0, "installation"),
    (r"\bfabricat(?:e|ion)\b", 12.0, "fabrication"),
    (r"\bmanufactur(?:e|ing)\b", 10.0, "manufacturing"),
    (r"\bevaporator|cooling\s*unit|thermal\b", 16.0, "thermal/mechanical design"),

    # ── BOM / procurement (BEFORE CAD/design — "BOM from CAD" is BOM work) ─
    (r"\bbill\s*of\s*materials?\b", 6.0, "BOM creation"),
    (r"\bbom\b.*\b(?:from|update|generate|create|cad|naming)\b", 6.0, "BOM work"),
    (r"\bbom\b", 5.0, "BOM"),
    (r"\bprocure(?:ment)?\b", 4.0, "procurement"),
    (r"\b(?:order|purchase)\b.*\b(?:component|part|material|hardware)\b", 3.0, "ordering parts"),
    (r"\b(?:vendor|supplier)\b", 4.0, "vendor coordination"),

    # ── Research (BEFORE design — "Research Alternative Design" is research) ─
    (r"\bresearch\b.*\b(?:alternative|new|novel|design)\b", 20.0, "exploratory research"),
    (r"\bresearch\b", 12.0, "research"),
    (r"\b(?:feasibility|proof.of.concept|poc)\b", 16.0, "feasibility study"),
    (r"\banalysis\b", 8.0, "analysis"),
    (r"\b(?:algorithm|algo)\b", 16.0, "algorithm work"),

    # ── 3D printing / simple prints (BEFORE general "print" matches) ──────
    (r"\bspacers?\s*to\s*be\s*printed\b", 2.0, "spacer printing"),
    (r"\b3d\s*print(?:ing|ed)?\b", 3.0, "3D printing"),
    (r"\b(?:sla|fdm|mjf|sls)\b", 3.0, "3D printing job"),
    (r"\bprint\b.*\b(?:settings?|part|component|spacer|case|cover|pla|tpu|abs)\b", 3.0, "3D printing"),
    (r"\b(?:print|printing)\b.*\b(?:quantity|quantit)\b", 3.0, "3D printing batch"),
    (r"\b(?:quantity|quantit)\b.*\b(?:print|printing)\b", 3.0, "3D printing batch"),
    (r"\bprint\b", 3.0, "3D printing"),

    # ── Testing / QA (BEFORE documentation — "test plan" > "document") ────
    (r"\b(?:test\s*plan|test\s*campaign|qa\s*plan)\b", 12.0, "test planning"),
    (r"\b(?:execute|run)\s*(?:test|the\s*test)", 8.0, "test execution"),
    (r"\bpunch.list\b", 8.0, "punch list"),
    (r"\b(?:test|testing|validate)\b", 6.0, "testing"),
    (r"\bverify\b", 4.0, "verification"),

    # ── Documentation / PPAP ──────────────────────────────────────────────
    (r"\b(?:user\s*manual|user\s*guide|instruction\s*manual)\b", 16.0, "user manual"),
    (r"\b(?:ppap|production\s*part\s*approval)\b", 12.0, "PPAP documentation"),
    (r"\bdocument(?:ation|s)?\b", 6.0, "documentation"),
    (r"\b(?:write|draft|prepare)\b.*\b(?:doc|report|proposal|quotation|bid)\b", 6.0, "document drafting"),
    (r"\b(?:quotation|quote|bid)\b.*\b(?:package|document|prepar)", 5.0, "quotation prep"),
    (r"\bquote\s*system\b", 8.0, "quote system"),
    (r"\bgithub\s*repos?\b", 3.0, "GitHub repo setup"),
    (r"\b(?:dashboard|agent)\b.*\b(?:track|develop|build|create)\b", 12.0, "dashboard/agent dev"),
    (r"\bdashboard\b", 8.0, "dashboard work"),
    (r"\b(?:packing|packaging)\s*cover\b", 3.0, "packing job"),
    (r"\b(?:packing|packag)\b", 4.0, "packing"),

    # ── Finance / compliance ──────────────────────────────────────────────
    (r"\b(?:gstr|gst\s*r|tax\s*filing|tax\s*return)\b", 4.0, "tax filing"),
    (r"\b(?:audit|reconciliation|reconcile)\b", 5.0, "finance audit/recon"),
    (r"\b(?:invoice|billing|payment)\b", 2.0, "billing/payment"),
    (r"\b(?:bank\s*account|current\s*account)\b", 3.0, "banking"),
    (r"\b(?:registration|renew|license|permit)", 4.0, "registration"),
    (r"\bpolicy\b", 5.0, "policy document"),
    (r"\b(?:tally|accounting)\b", 4.0, "accounting"),
    (r"\b(?:crm|salesforce|pipeline)\b.*\b(?:update|sync|clean)\b", 4.0, "CRM update"),
    (r"\bcurrent\s*account", 3.0, "banking"),
    (r"\b(?:bank|icici|hdfc|sbi)\s*account", 3.0, "banking"),

    # ── HR / admin / office ───────────────────────────────────────────────
    (r"\b(?:hire|recruit|onboarding)\b", 8.0, "hiring"),
    (r"\b(?:order|buy|purchase)\b.*\b(?:t[-\s]?shirts?|hard\s*disk|tool\s*kit|bags?|chairs?)\b", 2.0, "office procurement"),
    (r"\blogistic(?:s)?\b", 4.0, "logistics"),
    (r"\b(?:setup|set\s*up|organi[sz]e)\b.*\b(?:storage|inventory|workspace)\b", 8.0, "setup/organize"),
    (r"\bsop\b", 5.0, "SOP writing"),
    (r"\b(?:printed?|print)\s*t[-\s]?shirts?\b", 3.0, "merchandise"),
    (r"\bpt\b", 2.0, "professional tax filing"),

    # ── Legal / agreements ────────────────────────────────────────────────
    (r"\b(?:agreement|contract|reseller)\b", 6.0, "legal/agreement"),

    # ── Packaging / distribution (BEFORE general dev, bidirectional match) ─
    (r"\b(?:electron|app|application|software|desktop)\b.*\b(?:bundl|distribut|packag|release\s*pipeline)", 12.0, "app packaging/release"),
    (r"\b(?:bundl|distribut|packag|release\s*pipeline).*\b(?:app|application|electron|software|desktop)\b", 12.0, "app packaging/release"),
    (r"\bdeploy", 8.0, "deployment"),
    (r"\b(?:packag|bundl|distribut)", 6.0, "packaging"),

    # ── High-effort design / engineering ──────────────────────────────────
    (r"\bpcb\s*design\b", 24.0, "PCB design"),
    (r"\bcad\b.*\b(?:design|model|assembly|finali[sz]ation)\b", 20.0, "CAD design"),
    (r"\bcad\b", 12.0, "CAD work"),
    (r"\b(?:full\s+)?(?:mechanical\s+)?design\b", 20.0, "design work"),
    (r"\bschematic\b", 12.0, "schematic design"),
    (r"\barchitect(?:ure|ural)\b", 16.0, "architecture"),
    (r"\b(?:system|software)\s+architect", 20.0, "system architecture"),

    # ── Development / coding ──────────────────────────────────────────────
    (r"\b(?:develop|build|implement)\b.*\b(?:app|application|software|platform|portal|dashboard|engine)\b", 24.0, "app development"),
    (r"\b(?:develop|implement)\b", 12.0, "development"),
    (r"\b(?:code|program|script)\b", 8.0, "coding"),
    (r"\b(?:debug|bug\s*fix|fix\s*the)\b", 6.0, "debugging"),
    (r"\b(?:refactor|rewrite|rework)\b", 12.0, "refactoring"),
    (r"\bui[/\\]?ux\b", 12.0, "UI/UX work"),
    (r"\b(?:frontend|backend|full.stack)\b", 12.0, "software dev"),

    # ── Training / education ──────────────────────────────────────────────
    (r"\b(?:train|teach|educat|course)\b", 8.0, "training"),
    (r"\bcertification\b", 4.0, "certification"),

    # ── Fallback by scope indicators (broad patterns last) ────────────────
    (r"\b(?:complete|deliver|finali[sz]e)\b.*\b(?:project|delivery|manual|report)\b", 16.0, "completion/delivery"),
    (r"\b(?:create|generate|produce)\b", 6.0, "creation"),
    (r"\b(?:update|upgrade|migrate)\b", 5.0, "update/upgrade"),
    (r"\b(?:fix|repair|troubleshoot)\b", 5.0, "fix/repair"),
    (r"\b(?:configure|setup|set\s*up|install)\b", 4.0, "setup/configure"),
    (r"\b(?:check|confirm|ensure)\b", 2.0, "check/verify"),
    (r"\b(?:prepare|organi[sz]e|arrange)\b", 4.0, "preparation"),
    (r"\b\w+\s+\w+\s+support\b", 4.0, "field support"),
]

# Fallback when no keyword matches at all
DEFAULT_ESTIMATE_HOURS = 4.0


def estimate_hours_from_name(task_name: str, description: str = "") -> tuple[float, str]:
    """Return (hours, reason) for a task based on its name and description."""
    search_text = f"{task_name} {description[:200]}".lower().strip()
    if not search_text:
        return DEFAULT_ESTIMATE_HOURS, "empty name (fallback)"

    for pattern, hours, reason in ESTIMATION_RULES:
        if re.search(pattern, search_text):
            return hours, reason

    return DEFAULT_ESTIMATE_HOURS, "no keyword match (fallback)"


# ---------------------------------------------------------------------------
# Status helpers (mirror generate_morning_report.py)
# ---------------------------------------------------------------------------

CLOSED_STATUSES = {"done", "closed", "complete", "completed",
                   "cancelled", "canceled", "backlog"}


def task_status_str(task: dict) -> str:
    raw = task.get("status")
    if isinstance(raw, dict):
        return raw.get("status", "unknown")
    return str(raw or "unknown")


def is_backlog(task: dict) -> bool:
    return task_status_str(task).lower() in ("backlog",)


def is_closed(task: dict) -> bool:
    return task_status_str(task).lower() in CLOSED_STATUSES


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def fetch_active_tasks(client, list_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch tasks from all active (green) lists, or a single list if specified."""
    all_tasks: list[dict[str, Any]] = []

    if list_id:
        tasks = client.get_tasks(list_id, include_closed=False)
        lst = client.get_list(list_id)
        for t in tasks:
            t["_list_id"] = list_id
            t["_list_name"] = lst.get("name", list_id)
            t["_space_name"] = ""
        return tasks

    spaces = client.get_spaces()
    print(f"Scanning {len(spaces)} space(s) for active lists...")

    for space in spaces:
        space_id = space["id"]
        space_name = space.get("name", space_id)

        # Foldered lists
        try:
            folders = client.get_folders(space_id)
        except Exception:
            folders = []
        for folder in folders:
            try:
                lists = client.get_lists(folder["id"])
            except Exception:
                continue
            for lst in lists:
                _collect_active(client, lst, space_name, all_tasks)

        # Folderless lists
        try:
            folderless = client.get_folderless_lists(space_id)
        except Exception:
            folderless = []
        for lst in folderless:
            _collect_active(client, lst, space_name, all_tasks)

    return all_tasks


def _collect_active(client, lst: dict, space_name: str,
                    target: list) -> None:
    """Add tasks from a green (active) list to target."""
    list_id = lst.get("id", "")
    if lst.get("archived", False):
        return
    color = (lst.get("status") or {}).get("status", "").lower()
    if color and color not in ("green", ""):
        return

    list_name = lst.get("name", list_id)
    try:
        tasks = client.get_tasks(list_id, include_closed=False)
        for task in tasks:
            task["_list_id"] = list_id
            task["_list_name"] = list_name
            task["_space_name"] = space_name
        target.extend(tasks)
    except Exception as exc:
        print(f"  [WARN] {list_name}: {exc}")


def hours_to_ms(hours: float) -> int:
    return int(hours * 3600 * 1000)


def ms_to_hours(ms: int | None) -> float | None:
    if ms is None or ms == 0:
        return None
    return ms / (3600 * 1000)


def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(
        description="Estimate and backfill ClickUp task time_estimate values")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview estimates without writing to ClickUp")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing time_estimate values")
    parser.add_argument("--list-id",
                        help="Only process tasks in a specific list")
    parser.add_argument("--include-backlog", action="store_true",
                        help="Also estimate backlog tasks (skipped by default)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON to stdout")
    args = parser.parse_args()

    client = get_client()
    print("Fetching active tasks...", flush=True)
    tasks = fetch_active_tasks(client, args.list_id)

    # Filter
    estimatable: list[dict] = []
    skipped_backlog = 0
    skipped_closed = 0
    skipped_has_estimate = 0

    for t in tasks:
        if is_closed(t):
            skipped_closed += 1
            continue
        if not args.include_backlog and is_backlog(t):
            skipped_backlog += 1
            continue
        existing_ms = t.get("time_estimate")
        if not args.force and existing_ms and existing_ms > 0:
            skipped_has_estimate += 1
            continue
        estimatable.append(t)

    total_tasks = len(tasks)
    print(f"  {total_tasks} total tasks fetched")
    print(f"  {skipped_closed} closed -> skipped")
    if not args.include_backlog:
        print(f"  {skipped_backlog} backlog -> skipped")
    print(f"  {skipped_has_estimate} already have time_estimate -> skipped")
    print(f"  {len(estimatable)} tasks to estimate\n")

    if not estimatable:
        print("Nothing to estimate.")
        return

    results: list[dict[str, Any]] = []
    updated = 0
    errors = 0

    for task in estimatable:
        task_id = task["id"]
        task_name = task.get("name", "")
        description = task.get("description", "") or ""
        list_name = task.get("_list_name", "?")
        current_ms = task.get("time_estimate")
        current_hrs = ms_to_hours(current_ms)

        hours, reason = estimate_hours_from_name(task_name, description)
        new_ms = hours_to_ms(hours)

        result = {
            "task_id": task_id,
            "task_name": task_name,
            "list": list_name,
            "estimated_hours": hours,
            "reason": reason,
            "previous_hours": current_hrs,
        }

        if args.dry_run:
            result["action"] = "would_update"
            results.append(result)
            print(f"  [DRY RUN] {task_name[:70]:<70} -> {hours:.1f}h  ({reason})")
        else:
            try:
                client.update_task(task_id, time_estimate=new_ms)
                result["action"] = "updated"
                results.append(result)
                updated += 1
                marker = "~" if current_ms and current_ms > 0 else "+"
                print(f"  [{marker}] {task_name[:70]:<70} -> {hours:.1f}h  ({reason})")
            except Exception as exc:
                result["action"] = "error"
                result["error"] = str(exc)
                results.append(result)
                errors += 1
                print(f"  [ERR] {task_name[:70]:<70} -- {exc}")

    # Summary
    print(f"\n{'DRY RUN - no changes made' if args.dry_run else 'Done.'}")
    print(f"  Estimated: {len(estimatable)}")
    if not args.dry_run:
        print(f"  Updated:   {updated}")
        print(f"  Errors:    {errors}")

    # Save log
    from datetime import datetime
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "force": args.force,
        "tasks_estimated": len(estimatable),
        "tasks_updated": updated if not args.dry_run else 0,
        "errors": errors,
        "results": results,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(log_data, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(f"  Log: {OUTPUT_FILE}")

    if args.json:
        print(json.dumps(log_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
