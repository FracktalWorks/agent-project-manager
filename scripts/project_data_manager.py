"""
project_data_manager.py — Load and save project step JSON files under outputs/.

Usage (import):
    from project_data_manager import load_step, save_step, slugify

    plan = load_step("website-redesign", 1, "project_plan")
    save_step("website-redesign", 2, "hr_assignments", {"assignments": [...]})
"""
from __future__ import annotations

import json
import re
from pathlib import Path

AGENT_DIR   = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = AGENT_DIR / "outputs"


def slugify(name: str) -> str:
    """Convert a project name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _step_path(slug: str, step: int, label: str) -> Path:
    return OUTPUTS_DIR / slug / f"step_{step}_{label}.json"


def save_step(slug: str, step: int, label: str, data: dict) -> Path:
    path = _step_path(slug, step, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_step(slug: str, step: int, label: str) -> dict | None:
    path = _step_path(slug, step, label)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_steps(slug: str) -> list[Path]:
    project_dir = OUTPUTS_DIR / slug
    if not project_dir.exists():
        return []
    return sorted(project_dir.glob("step_*.json"))
