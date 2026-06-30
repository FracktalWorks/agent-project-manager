"""
publish_plan_to_list.py — Publish a project_plan.md as a Doc view inside a ClickUp List.

Strategy: POST a 'doc' type view to the list (v2 Views API), then POST the plan
content as a page using the view ID as the doc ID (v3 Pages API).

The resulting doc appears in the list's view bar alongside Board, Gantt, etc.

Usage:
  # Publish a plan file directly
  python .github/skills/clickup-docs/scripts/publish_plan_to_list.py \\
    --plan outputs/penrose-v2/project-plan/project_plan.md \\
    --list-id 901611246751 \\
    --doc-name "Penrose V2 — Project Plan"

  # Update an existing doc view (replaces the page content)
  python .github/skills/clickup-docs/scripts/publish_plan_to_list.py \\
    --plan outputs/penrose-v2/project-plan/project_plan.md \\
    --list-id 901611246751 \\
    --doc-view-id 2kz0eqmc-20156   # existing view ID to update

  # Publish plan by project slug (reads metadata.json automatically)
  python .github/skills/clickup-docs/scripts/publish_plan_to_list.py \\
    --slug penrose-v2

Environment variables required:
  CLICKUP_API_TOKEN
  CLICKUP_TEAM_ID
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / ".tmp" / "scripts"))
from load_env import load_env; load_env()

import httpx

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
WORKSPACE_ID = os.environ.get("CLICKUP_TEAM_ID", "")
OUTPUTS_DIR = REPO_ROOT / "outputs"

H = {"Authorization": TOKEN, "Content-Type": "application/json"}
V2 = "https://api.clickup.com/api/v2"
V3 = "https://api.clickup.com/api/v3"


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def create_doc_view(list_id: str, doc_name: str) -> dict:
    """Create a 'doc' type view on a ClickUp List. Returns the view object."""
    r = httpx.post(
        f"{V2}/list/{list_id}/view",
        headers=H,
        json={"name": doc_name, "type": "doc"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("view", r.json())


def get_doc_pages(doc_id: str) -> list[dict]:
    """List all pages in a doc (by doc/view ID)."""
    r = httpx.get(
        f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("pages", data) if isinstance(data, dict) else data


def create_page(doc_id: str, page_name: str, content: str) -> dict:
    """Create a new page in a doc."""
    r = httpx.post(
        f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages",
        headers=H,
        json={"name": page_name, "content": content, "content_format": "text/md"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def update_page(doc_id: str, page_id: str, content: str) -> dict:
    """Update an existing page's content."""
    r = httpx.put(
        f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}",
        headers=H,
        json={"content": content, "content_format": "text/md"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_list_name(list_id: str) -> str:
    """Fetch the list's display name."""
    r = httpx.get(f"{V2}/list/{list_id}", headers=H, timeout=15)
    if r.is_success:
        return r.json().get("name", list_id)
    return list_id


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def load_metadata(slug: str) -> dict:
    meta_path = OUTPUTS_DIR / slug / "project-plan" / "metadata.json"
    if not meta_path.exists():
        print(f"ERROR: metadata.json not found at {meta_path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(meta_path.read_text(encoding="utf-8"))


def save_metadata(slug: str, updates: dict) -> None:
    meta_path = OUTPUTS_DIR / slug / "project-plan" / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(updates)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  Metadata updated: {meta_path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Main publish logic
# ---------------------------------------------------------------------------

def publish(
    plan_path: Path,
    list_id: str,
    doc_name: str,
    doc_view_id: str | None = None,
    slug: str | None = None,
) -> None:
    if not TOKEN or not WORKSPACE_ID:
        print("ERROR: CLICKUP_API_TOKEN and CLICKUP_TEAM_ID must be set in .env", file=sys.stderr)
        sys.exit(1)

    if not plan_path.exists():
        print(f"ERROR: Plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    content = plan_path.read_text(encoding="utf-8")
    # Use the first H1 line as the page name
    page_name = doc_name
    for line in content.splitlines():
        if line.startswith("# "):
            page_name = line[2:].strip()
            break

    list_display = get_list_name(list_id)
    print(f"List: {list_display} ({list_id})")
    print(f"Plan: {plan_path.relative_to(REPO_ROOT)}")
    print()

    # ── Step 1: create or reuse the doc view ───────────────────────────────
    if doc_view_id:
        print(f"Reusing existing doc view: {doc_view_id}")
    else:
        print(f"Creating doc view '{doc_name}' on list...")
        view = create_doc_view(list_id, doc_name)
        doc_view_id = view.get("id", "")
        print(f"  Doc view created: {doc_view_id}")

    doc_url = f"https://app.clickup.com/{WORKSPACE_ID}/docs/{doc_view_id}"

    # ── Step 2: check for existing page to update vs create ────────────────
    existing_page_id = None
    try:
        pages = get_doc_pages(doc_view_id)
        if pages:
            existing_page_id = pages[0].get("id") if isinstance(pages[0], dict) else None
    except Exception:
        pass  # No pages yet — will create fresh

    if existing_page_id:
        print(f"Updating existing page: {existing_page_id}")
        page = update_page(doc_view_id, existing_page_id, content)
        page_id = page.get("id", existing_page_id)
        action = "updated"
    else:
        print(f"Creating new page: '{page_name}'")
        page = create_page(doc_view_id, page_name, content)
        page_id = page.get("id", "")
        action = "created"

    page_url = f"{doc_url}/{page_id}"
    print(f"  Page {action}: {page_id}")
    print()
    print(f"Doc view URL:  {doc_url}")
    print(f"Page URL:      {page_url}")

    # ── Step 3: save IDs back to metadata.json ─────────────────────────────
    if slug:
        save_metadata(slug, {
            "clickup_list_id": list_id,
            "clickup_doc_view_id": doc_view_id,
            "clickup_doc_view_url": doc_url,
            "clickup_plan_page_id": page_id,
            "clickup_plan_page_url": page_url,
        })

    print()
    print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Publish a project_plan.md as a Doc view inside a ClickUp List"
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", help="Path to project_plan.md")
    g.add_argument("--slug", help="Project slug (auto-finds plan via outputs/{slug}/project-plan/)")

    p.add_argument("--list-id", help="ClickUp List ID to attach the doc to")
    p.add_argument(
        "--doc-name",
        default=None,
        help="Name for the doc view (default: '{Project Name} — Project Plan')",
    )
    p.add_argument(
        "--doc-view-id",
        default=None,
        help="Existing doc view ID to update instead of creating a new one",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.slug:
        meta = load_metadata(args.slug)
        plan_path = REPO_ROOT / meta["plan_md"]
        list_id = args.list_id or meta.get("clickup_list_id", "")
        doc_view_id = args.doc_view_id or meta.get("clickup_doc_view_id")
        project_name = meta.get("project_name", args.slug)
        slug = args.slug
    else:
        plan_path = Path(args.plan).resolve()
        list_id = args.list_id or ""
        doc_view_id = args.doc_view_id
        # Infer slug from path
        slug = plan_path.parent.parent.name if "project-plan" in str(plan_path) else None
        project_name = plan_path.stem.replace("_", " ").title()

    if not list_id:
        print("ERROR: --list-id is required (or set clickup_list_id in metadata.json)", file=sys.stderr)
        sys.exit(1)

    doc_name = args.doc_name or f"{project_name} — Project Plan"

    publish(
        plan_path=plan_path,
        list_id=list_id,
        doc_name=doc_name,
        doc_view_id=doc_view_id,
        slug=slug,
    )


if __name__ == "__main__":
    main()
