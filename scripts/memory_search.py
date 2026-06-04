"""
memory_search.py — FTS5 full-text search across Tier 2 project memory (project_memory.db).

Usage:
    python scripts/memory_search.py --query "auger lead time"
    python scripts/memory_search.py --query "penrose" --type decisions
    python scripts/memory_search.py --query "supply chain" --project penrose-pellet-extruder --type risks
"""

import argparse
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("outputs/_memory/project_memory.db")

VALID_TYPES = {"facts", "decisions", "risks", "interactions", "entities", "lessons"}


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist yet."""
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS facts
            USING fts5(entity, content, tags, project, created);
        CREATE VIRTUAL TABLE IF NOT EXISTS decisions
            USING fts5(project, decision, context, rationale, outcome, owner, date);
        CREATE VIRTUAL TABLE IF NOT EXISTS risks
            USING fts5(project, title, category, mitigation, owner, status, created);
        CREATE VIRTUAL TABLE IF NOT EXISTS interactions
            USING fts5(summary, topics, date);
        CREATE VIRTUAL TABLE IF NOT EXISTS entities
            USING fts5(name, type, description, project);
        CREATE VIRTUAL TABLE IF NOT EXISTS lessons
            USING fts5(title, pattern, fix, project);
    """)
    conn.commit()


def search(query: str, table: str, project: str | None, limit: int) -> list[dict]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    tables = [table] if table else list(VALID_TYPES)
    results = []

    for tbl in tables:
        try:
            if project:
                rows = conn.execute(
                    f"SELECT *, '{tbl}' AS source FROM {tbl} WHERE {tbl} MATCH ? AND project MATCH ? LIMIT ?",
                    (query, project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT *, '{tbl}' AS source FROM {tbl} WHERE {tbl} MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
            results.extend([dict(r) for r in rows])
        except sqlite3.OperationalError:
            # Table may not have 'project' column (e.g. interactions)
            try:
                rows = conn.execute(
                    f"SELECT *, '{tbl}' AS source FROM {tbl} WHERE {tbl} MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
                results.extend([dict(r) for r in rows])
            except sqlite3.OperationalError:
                pass

    conn.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Search project memory (FTS5 SQLite)")
    parser.add_argument("--query", required=True, help="Search text")
    parser.add_argument(
        "--type",
        choices=list(VALID_TYPES),
        default=None,
        help="Restrict search to a specific memory table",
    )
    parser.add_argument("--project", default=None, help="Filter by project slug")
    parser.add_argument("--limit", type=int, default=10, help="Max results per table")
    args = parser.parse_args()

    hits = search(args.query, args.type, args.project, args.limit)
    if not hits:
        print("No results found.")
        return

    for hit in hits:
        print(json.dumps(hit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
