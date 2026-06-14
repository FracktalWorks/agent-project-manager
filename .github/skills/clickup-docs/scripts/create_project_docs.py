"""
create_project_docs.py — Create (or rebuild) a structured multi-page ClickUp Doc
inside a List's Doc view for any project.

Page structure (every project gets all of these):
  📋 Overview          — index page: one-para summary, status, team, links to other pages
  🗺  Project Plan      — objectives, scope, timeline, milestones
  📄 Product Requirements — what the product must do, constraints, acceptance criteria
  📐 Product Documentation — architecture, design decisions, how it works
  ⚙️  Subsystems        — one section per major subsystem
  ❓ Open Questions & Risks — blockers, risks

The Overview page is created last so it can link to the real page IDs of all other pages.

Usage:
  # Create / rebuild docs for a project from its spec file
  python .github/skills/clickup-docs/scripts/create_project_docs.py \\
    --spec outputs/julia-series/project-docs/spec.json

  # Re-create (wipes existing pages and starts fresh)
  python .github/skills/clickup-docs/scripts/create_project_docs.py \\
    --spec outputs/julia-series/project-docs/spec.json --rebuild

Environment:
  CLICKUP_API_TOKEN, CLICKUP_TEAM_ID
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
WORKSPACE_ID = os.environ.get("CLICKUP_TEAM_ID", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}
V2 = "https://api.clickup.com/api/v2"
V3 = "https://api.clickup.com/api/v3"

REGISTRY_PATH = REPO_ROOT / "outputs" / "_memory" / "project_registry.json"


# ---------------------------------------------------------------------------
# ClickUp API helpers
# ---------------------------------------------------------------------------

def get_list_views(list_id: str) -> list[dict]:
    r = httpx.get(f"{V2}/list/{list_id}/view", headers=H, timeout=15)
    r.raise_for_status()
    return r.json().get("views", [])


def create_doc_view(list_id: str, name: str) -> str:
    r = httpx.post(f"{V2}/list/{list_id}/view", headers=H,
                   json={"name": name, "type": "doc"}, timeout=15)
    r.raise_for_status()
    return r.json().get("view", r.json())["id"]


def delete_view(view_id: str) -> int:
    r = httpx.delete(f"{V2}/view/{view_id}", headers=H, timeout=15)
    return r.status_code


def add_page(doc_id: str, name: str, content: str, parent_page_id: str = "") -> str:
    payload: dict = {"name": name, "content": content, "content_format": "text/md"}
    if parent_page_id:
        payload["parent_page_id"] = parent_page_id
    r = httpx.post(f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages",
                   headers=H, json=payload, timeout=20)
    r.raise_for_status()
    return r.json().get("id", "")


def update_page(doc_id: str, page_id: str, content: str) -> None:
    r = httpx.put(f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}",
                  headers=H, json={"content": content, "content_format": "text/md"}, timeout=20)
    r.raise_for_status()


def list_pages(doc_id: str) -> list[dict]:
    r = httpx.get(f"{V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages",
                  headers=H, timeout=15)
    if r.is_success:
        data = r.json()
        return data.get("pages", data) if isinstance(data, dict) else data
    return []


# ---------------------------------------------------------------------------
# Page content builders
# ---------------------------------------------------------------------------

def page_url(doc_view_id: str, page_id: str) -> str:
    return f"https://app.clickup.com/{WORKSPACE_ID}/docs/{doc_view_id}/{page_id}"


def build_overview(spec: dict, page_ids: dict[str, str], doc_view_id: str) -> str:
    name = spec["name"]
    status = spec.get("status", "Active")
    phase = spec.get("phase", "Design")
    description = spec.get("description", "")
    team = spec.get("team", [])
    milestones = spec.get("milestones", [])
    risks = spec.get("risks", [])[:3]
    links = spec.get("external_links", {})
    clickup_list_url = spec.get("clickup_list_url", "")

    status_icon = {"Active": "🟢", "Paused": "🟡", "On Hold": "🔴"}.get(status, "🟢")

    lines = [
        f"# {name}",
        "",
        f"**Status:** {status_icon} {status} &nbsp;|&nbsp; **Phase:** `{phase}` &nbsp;|&nbsp; **Updated:** {spec.get('last_updated', '2026-06-06')}",
        "",
        f"{description}",
        "",
        "---",
        "",
        "## 📑 Documentation",
        "",
        "| Section | Description |",
        "|---------|-------------|",
    ]

    page_labels = {
        "project_plan":   ("🗺 Project Plan",          "Objectives, scope, timeline, milestones"),
        "requirements":   ("📄 Product Requirements",   "What the product must do, acceptance criteria"),
        "product_docs":   ("📐 Product Documentation",  "Architecture, design decisions, how it works"),
        "subsystems":     ("⚙️ Subsystems",              "Breakdown of each major subsystem"),
        "open_questions": ("❓ Open Questions & Risks",  "Unresolved decisions and active risks"),
    }
    for key, (label, desc) in page_labels.items():
        pid = page_ids.get(key, "")
        if pid:
            url = page_url(doc_view_id, pid)
            lines.append(f"| [{label}]({url}) | {desc} |")
        else:
            lines.append(f"| {label} | {desc} |")

    lines += ["", "---", "", "## 👥 Team", ""]
    if team:
        lines += ["| Name | Role |", "|------|------|"]
        for m in team:
            lines.append(f"| {m.get('name','')} | {m.get('role','')} |")
    else:
        lines.append("*Team not yet assigned.*")

    lines += ["", "---", "", "## 🏁 Key Milestones", ""]
    if milestones:
        lines += ["| Milestone | Target Date | Status |", "|-----------|-------------|--------|"]
        for m in milestones:
            lines.append(f"| {m.get('milestone','')} | {m.get('date','')} | {m.get('status','Upcoming')} |")
    else:
        lines.append("*Milestones not yet defined.*")

    lines += ["", "---", "", "## ⚠️ Top Risks", ""]
    if risks:
        lines += ["| Risk | Likelihood | Impact |", "|------|-----------|--------|"]
        for r in risks:
            lines.append(f"| {r.get('risk','')} | {r.get('likelihood','M')} | {r.get('impact','M')} |")
    else:
        lines.append("*No risks registered yet.*")

    if links or clickup_list_url:
        lines += ["", "---", "", "## 🔗 External Links", ""]
        lines += ["| Resource | Link |", "|----------|------|"]
        if clickup_list_url:
            lines.append(f"| ClickUp List | [{name} Tasks]({clickup_list_url}) |")
        for label, url_str in links.items():
            lines.append(f"| {label} | {url_str} |")

    return "\n".join(lines)


def build_project_plan(spec: dict) -> str:
    name = spec["name"]
    objectives = spec.get("objectives", [])
    scope_in = spec.get("scope_in", [])
    scope_out = spec.get("scope_out", [])
    milestones = spec.get("milestones", [])
    dependencies = spec.get("dependencies", [])
    timeline = spec.get("timeline", {})

    lines = [
        f"# 🗺 Project Plan — {name}",
        "",
        f"**Period:** {timeline.get('start', 'TBD')} → {timeline.get('end', 'TBD')}",
        "",
        "---",
        "",
        "## Objectives",
        "",
    ]
    if objectives:
        lines += [f"- {o}" for o in objectives]
    else:
        lines.append("*To be defined.*")

    lines += ["", "---", "", "## Scope", ""]
    if scope_in:
        lines.append("**In scope:**")
        lines += [f"- {s}" for s in scope_in]
        lines.append("")
    if scope_out:
        lines.append("**Out of scope:**")
        lines += [f"- {s}" for s in scope_out]
        lines.append("")

    lines += ["---", "", "## Milestones", ""]
    if milestones:
        lines += ["| Milestone | Target Date | Owner | Status |",
                  "|-----------|-------------|-------|--------|"]
        for m in milestones:
            lines.append(
                f"| {m.get('milestone','')} | {m.get('date','')} "
                f"| {m.get('owner','TBD')} | {m.get('status','Upcoming')} |"
            )
    else:
        lines.append("*Milestones not yet defined.*")

    lines += ["", "---", "", "## Dependencies", ""]
    if dependencies:
        lines += [f"- {d}" for d in dependencies]
    else:
        lines.append("*No external dependencies identified.*")

    return "\n".join(lines)


def build_requirements(spec: dict) -> str:
    name = spec["name"]
    functional = spec.get("functional_requirements", [])
    nonfunctional = spec.get("nonfunctional_requirements", [])
    constraints = spec.get("constraints", [])
    personas = spec.get("personas", [])

    lines = [
        f"# 📄 Product Requirements — {name}",
        "",
        "> This page defines what the product must do. It is the contract between design, engineering, and stakeholders.",
        "",
        "---",
        "",
        "## Functional Requirements",
        "",
        "| # | Requirement | Priority | Status |",
        "|---|-------------|----------|--------|",
    ]
    for i, fr in enumerate(functional, 1):
        if isinstance(fr, dict):
            lines.append(f"| FR-{i:02d} | {fr.get('req','')} | {fr.get('priority','M')} | {fr.get('status','Open')} |")
        else:
            lines.append(f"| FR-{i:02d} | {fr} | M | Open |")

    if not functional:
        lines.append("| — | *Not yet defined* | — | — |")

    lines += ["", "---", "", "## Non-Functional Requirements", ""]
    if nonfunctional:
        lines += ["| # | Requirement | Target | Status |",
                  "|---|-------------|--------|--------|"]
        for i, nfr in enumerate(nonfunctional, 1):
            if isinstance(nfr, dict):
                lines.append(f"| NFR-{i:02d} | {nfr.get('req','')} | {nfr.get('target','')} | {nfr.get('status','Open')} |")
            else:
                lines.append(f"| NFR-{i:02d} | {nfr} | TBD | Open |")
    else:
        lines.append("*Not yet defined.*")

    lines += ["", "---", "", "## Constraints", ""]
    if constraints:
        lines += [f"- {c}" for c in constraints]
    else:
        lines.append("*No constraints documented.*")

    lines += ["", "---", "", "## Target Users / Personas", ""]
    if personas:
        for p in personas:
            lines.append(f"**{p.get('name','')}:** {p.get('description','')}")
            lines.append("")
    else:
        lines.append("*Not yet defined.*")

    return "\n".join(lines)


def build_product_docs(spec: dict) -> str:
    name = spec["name"]
    architecture = spec.get("architecture", "")
    design_decisions = spec.get("design_decisions", [])
    how_it_works = spec.get("how_it_works", "")
    external_links = spec.get("external_links", {})

    lines = [
        f"# 📐 Product Documentation — {name}",
        "",
        "> This page describes how the product works: its architecture, key design decisions, and where to find the source files.",
        "",
        "---",
        "",
        "## System Overview",
        "",
        architecture if architecture else "*Architecture overview to be documented.*",
        "",
        "---",
        "",
        "## How It Works",
        "",
        how_it_works if how_it_works else "*Functional description to be documented.*",
        "",
        "---",
        "",
        "## Key Design Decisions",
        "",
    ]

    if design_decisions:
        for dd in design_decisions:
            if isinstance(dd, dict):
                lines += [
                    f"### {dd.get('title', 'Decision')}",
                    "",
                    f"**Context:** {dd.get('context', '')}",
                    f"**Decision:** {dd.get('decision', '')}",
                    f"**Rationale:** {dd.get('rationale', '')}",
                    f"**Consequences:** {dd.get('consequences', '')}",
                    "",
                ]
            else:
                lines += [f"- {dd}", ""]
    else:
        lines.append("*Design decisions to be documented.*")

    lines += ["", "---", "", "## Files & Resources", ""]
    if external_links:
        lines += ["| Resource | Link |", "|----------|------|"]
        for label, url in external_links.items():
            lines.append(f"| {label} | {url} |")
    else:
        lines.append("*Links to CAD, firmware repos, datasheets, and drive folders to be added here.*")

    return "\n".join(lines)


def build_subsystems(spec: dict) -> str:
    name = spec["name"]
    subsystems = spec.get("subsystems", [])

    lines = [
        f"# ⚙️ Subsystems — {name}",
        "",
        "> Each major subsystem is described below: what it does, how it works, current status, and known issues.",
        "",
        "---",
        "",
    ]

    if not subsystems:
        lines.append("*Subsystem breakdown to be documented.*")
        return "\n".join(lines)

    for ss in subsystems:
        sname = ss.get("name", "Subsystem")
        lines += [
            f"## {sname}",
            "",
            f"**Status:** {ss.get('status', 'Design')}",
            f"**Owner:** {ss.get('owner', 'TBD')}",
            "",
            ss.get("description", "*Description to be added.*"),
            "",
        ]
        specs_list = ss.get("specs", [])
        if specs_list:
            lines += ["**Key specs:**", ""]
            lines += [f"- {s}" for s in specs_list]
            lines.append("")

        issues = ss.get("known_issues", [])
        if issues:
            lines += ["**Known issues:**", ""]
            lines += [f"- {i}" for i in issues]
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_open_questions(spec: dict) -> str:
    name = spec["name"]
    questions = spec.get("open_questions", [])
    risks = spec.get("risks", [])

    lines = [
        f"# ❓ Open Questions & Risks — {name}",
        "",
        "> This page tracks unresolved decisions that are blocking progress, and active risks.",
        "",
        "---",
        "",
        "## Open Questions",
        "",
    ]

    if questions:
        lines += ["| # | Question | Owner | Status |",
                  "|---|----------|-------|--------|"]
        for i, q in enumerate(questions, 1):
            if isinstance(q, dict):
                lines.append(f"| Q-{i:02d} | {q.get('question','')} | {q.get('owner','TBD')} | {q.get('status','Open')} |")
            else:
                lines.append(f"| Q-{i:02d} | {q} | TBD | Open |")
    else:
        lines.append("*No open questions logged.*")

    lines += ["", "---", "", "## Risk Register", ""]
    if risks:
        lines += ["| Risk | Likelihood | Impact | Mitigation | Owner |",
                  "|------|-----------|--------|------------|-------|"]
        for r in risks:
            lines.append(
                f"| {r.get('risk','')} | {r.get('likelihood','M')} | {r.get('impact','M')} "
                f"| {r.get('mitigation','')} | {r.get('owner','TBD')} |"
            )
    else:
        lines.append("*No risks logged.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"projects": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def update_registry(slug: str, updates: dict) -> None:
    registry = load_registry()
    found = False
    for p in registry["projects"]:
        if p["slug"] == slug:
            p.update(updates)
            found = True
            break
    if not found:
        registry["projects"].append({"slug": slug, **updates})
    save_registry(registry)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(spec_path: Path, rebuild: bool = False) -> None:
    if not TOKEN or not WORKSPACE_ID:
        print("ERROR: CLICKUP_API_TOKEN and CLICKUP_TEAM_ID required.", file=sys.stderr)
        sys.exit(1)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    name = spec["name"]
    slug = spec["slug"]
    list_id = spec["list_id"]
    doc_view_name = spec.get("doc_view_name", f"{name} — Documentation")

    print(f"\n{'='*60}")
    print(f"  Building docs for: {name}")
    print(f"{'='*60}\n")

    # ── Find or create the doc view ────────────────────────────────────────
    views = get_list_views(list_id)
    doc_views = [v for v in views if v.get("type") == "doc"]
    existing_view = next((v for v in doc_views if "Documentation" in v["name"] or v["name"] == doc_view_name), None)

    if rebuild and existing_view:
        print(f"  Rebuild: deleting existing doc view '{existing_view['name']}'...")
        delete_view(existing_view["id"])
        existing_view = None

    if existing_view:
        doc_view_id = existing_view["id"]
        print(f"  Reusing doc view: {existing_view['name']} ({doc_view_id})")
    else:
        print(f"  Creating doc view '{doc_view_name}'...")
        doc_view_id = create_doc_view(list_id, doc_view_name)
        print(f"  Doc view ID: {doc_view_id}")

    doc_view_url = f"https://app.clickup.com/{WORKSPACE_ID}/docs/{doc_view_id}"

    # ── Build content for each page ────────────────────────────────────────
    pages_to_create = [
        ("project_plan",   "🗺 Project Plan",           build_project_plan(spec)),
        ("requirements",   "📄 Product Requirements",    build_requirements(spec)),
        ("product_docs",   "📐 Product Documentation",   build_product_docs(spec)),
        ("subsystems",     "⚙️ Subsystems",               build_subsystems(spec)),
        ("open_questions", "❓ Open Questions & Risks",   build_open_questions(spec)),
    ]

    # Check for pre-existing pages (on rebuild=False)
    page_ids: dict[str, str] = {}
    existing_pages = list_pages(doc_view_id)
    existing_by_name = {p["name"]: p["id"] for p in existing_pages if isinstance(p, dict)}

    for key, page_name, content in pages_to_create:
        if page_name in existing_by_name:
            pid = existing_by_name[page_name]
            print(f"  Updating page '{page_name}'...")
            update_page(doc_view_id, pid, content)
            page_ids[key] = pid
        else:
            print(f"  Creating page '{page_name}'...")
            pid = add_page(doc_view_id, page_name, content)
            page_ids[key] = pid
        print(f"    ID: {page_ids[key]}")

    # ── Build and publish Overview last (knows all page IDs) ───────────────
    overview_content = build_overview(spec, page_ids, doc_view_id)
    overview_name = "📋 Overview"
    if overview_name in existing_by_name:
        print(f"  Updating page '{overview_name}'...")
        update_page(doc_view_id, existing_by_name[overview_name], overview_content)
        page_ids["overview"] = existing_by_name[overview_name]
    else:
        print(f"  Creating page '{overview_name}'...")
        page_ids["overview"] = add_page(doc_view_id, overview_name, overview_content)
    print(f"    ID: {page_ids['overview']}")

    # ── Save results ────────────────────────────────────────────────────────
    spec_out = spec_path.parent / "doc_ids.json"
    doc_ids = {"doc_view_id": doc_view_id, "doc_view_url": doc_view_url, "pages": page_ids}
    spec_out.write_text(json.dumps(doc_ids, indent=2), encoding="utf-8")
    print(f"\n  IDs saved to: {spec_out.relative_to(REPO_ROOT)}")

    update_registry(slug, {
        "name": name,
        "clickup_list_id": list_id,
        "clickup_list_doc_view_id": doc_view_id,
        "clickup_list_doc_view_url": doc_view_url,
        "clickup_list_doc_pages": page_ids,
        "clickup_list_doc_overview_url": f"{doc_view_url}/{page_ids.get('overview','')}"
    })
    print(f"  Registry updated.")

    print(f"\n  ✅ Done. Open the doc:")
    print(f"  {doc_view_url}")
    overview_pid = page_ids.get("overview", "")
    if overview_pid:
        print(f"  Overview: {doc_view_url}/{overview_pid}")


def main() -> None:
    p = argparse.ArgumentParser(description="Create multi-page project docs in a ClickUp List")
    p.add_argument("--spec", required=True, help="Path to project spec JSON")
    p.add_argument("--rebuild", action="store_true", help="Delete existing doc view and rebuild from scratch")
    args = p.parse_args()

    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    run(spec_path, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
