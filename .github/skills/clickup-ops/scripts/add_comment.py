"""
add_comment.py — Post a follow-up comment on a ClickUp task.

Usage:
    python .github/skills/clickup-ops/scripts/add_comment.py \
        --task-id abc123 \
        --comment "@alice quick check-in: is there anything blocking this task?"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clickup_client import ClickUpClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a comment to a ClickUp task.")
    parser.add_argument("--task-id",  required=True, help="ClickUp task ID")
    parser.add_argument("--comment",  required=True, help="Comment text")
    parser.add_argument("--notify-all", action="store_true",
                        help="Notify all task assignees and followers")
    args = parser.parse_args()

    client = ClickUpClient()
    result = client.add_comment(
        task_id=args.task_id,
        comment=args.comment,
        notify_all=args.notify_all,
    )
    print(f"✅ Comment posted: {result.get('id', 'ok')}")


if __name__ == "__main__":
    main()
