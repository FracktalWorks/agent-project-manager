"""
Shared .env loader — canonical pattern for all agent scripts.

Usage:
    from load_env import load_env
    load_env()  # populates os.environ from AGENT_DIR/.env

Why not python-dotenv?  load_dotenv() relies on frame.f_back which is None in
the CommandCenter runtime, causing AssertionError.  This manual parser has zero
dependencies and works universally.
"""
from __future__ import annotations

import os
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent.parent


def load_env(env_path: Path | None = None) -> None:
    """Parse KEY=VALUE lines from .env into os.environ (setdefault semantics)."""
    if env_path is None:
        env_path = AGENT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
