"""
clickup_client.py — Low-level ClickUp REST API v2 wrapper.

All methods raise on non-2xx responses.
Reads credentials from environment:
    CLICKUP_API_TOKEN  — personal API token
    CLICKUP_TEAM_ID    — workspace / team ID
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

BASE_URL = "https://api.clickup.com/api/v2"
_RATE_LIMIT_WAIT = 62  # seconds to wait on 429


class ClickUpClient:
    def __init__(self, token: str = "", team_id: str = "") -> None:
        self._token   = token   or os.environ.get("CLICKUP_API_TOKEN", "")
        self._team_id = team_id or os.environ.get("CLICKUP_TEAM_ID", "")
        if not self._token:
            raise ValueError(
                "CLICKUP_API_TOKEN is not set. "
                "Add it to .env or pass token= to ClickUpClient()."
            )
        self._headers = {
            "Authorization": self._token,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{BASE_URL}{path}"
        for attempt in range(2):
            r = httpx.request(method, url, headers=self._headers, timeout=30, **kwargs)
            if r.status_code == 429:
                if attempt == 0:
                    time.sleep(_RATE_LIMIT_WAIT)
                    continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()  # re-raise after retry

    # ------------------------------------------------------------------ Teams
    def get_teams(self) -> list[dict]:
        return self._request("GET", "/team").get("teams", [])

    # ----------------------------------------------------------------- Spaces
    def get_spaces(self) -> list[dict]:
        return self._request("GET", f"/team/{self._team_id}/space").get("spaces", [])

    def create_space(self, name: str) -> dict:
        return self._request(
            "POST",
            f"/team/{self._team_id}/space",
            json={"name": name},
        )

    # ---------------------------------------------------------------- Folders
    def get_folders(self, space_id: str) -> list[dict]:
        return self._request("GET", f"/space/{space_id}/folder").get("folders", [])

    def create_folder(self, space_id: str, name: str) -> dict:
        return self._request(
            "POST",
            f"/space/{space_id}/folder",
            json={"name": name},
        )

    # ------------------------------------------------------------------ Lists
    def get_lists(self, folder_id: str) -> list[dict]:
        return self._request("GET", f"/folder/{folder_id}/list").get("lists", [])

    def get_folderless_lists(self, space_id: str) -> list[dict]:
        return self._request("GET", f"/space/{space_id}/list").get("lists", [])

    def create_list(self, folder_id: str, name: str, due_date_ms: int | None = None) -> dict:
        payload: dict[str, Any] = {"name": name}
        if due_date_ms is not None:
            payload["due_date"] = due_date_ms
        return self._request("POST", f"/folder/{folder_id}/list", json=payload)

    # ------------------------------------------------------------------ Tasks
    def get_tasks(self, list_id: str, include_closed: bool = False) -> list[dict]:
        params: dict[str, Any] = {"include_closed": str(include_closed).lower()}
        return self._request("GET", f"/list/{list_id}/task", params=params).get("tasks", [])

    def create_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        assignees: list[int] | None = None,
        due_date_ms: int | None = None,
        priority: int | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if assignees:
            payload["assignees"] = assignees
        if due_date_ms is not None:
            payload["due_date"] = due_date_ms
        if priority is not None:
            # ClickUp priority: 1=urgent, 2=high, 3=normal, 4=low
            payload["priority"] = priority
        if tags:
            payload["tags"] = tags
        return self._request("POST", f"/list/{list_id}/task", json=payload)

    def update_task(self, task_id: str, **fields: Any) -> dict:
        return self._request("PUT", f"/task/{task_id}", json=fields)

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/task/{task_id}")

    # --------------------------------------------------------------- Comments
    def add_comment(self, task_id: str, comment: str, notify_all: bool = False) -> dict:
        return self._request(
            "POST",
            f"/task/{task_id}/comment",
            json={"comment_text": comment, "notify_all": notify_all},
        )

    # ---------------------------------------------------------------- Members
    def get_members(self) -> list[dict]:
        """Return all workspace members (extracted from the /team response)."""
        teams = self._request("GET", "/team").get("teams", [])
        for team in teams:
            if str(team.get("id")) == str(self._team_id):
                return team.get("members", [])
        # Fallback: return members from the first team if ID didn't match
        if teams:
            return teams[0].get("members", [])
        return []

    def find_member_id(self, name_or_email: str) -> int | None:
        """Return ClickUp user ID for a member by name or email (case-insensitive)."""
        needle = name_or_email.lower()
        for m in self.get_members():
            user = m.get("user", {})
            if needle in user.get("username", "").lower():
                return user["id"]
            if needle in user.get("email", "").lower():
                return user["id"]
        return None


# ------------------------------------------------------------------ CLI helper
if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="ClickUp client CLI helper.")
    parser.add_argument("--list-members", action="store_true")
    parser.add_argument("--list-spaces",  action="store_true")
    parser.add_argument("--list-tasks",   metavar="LIST_ID")
    args = parser.parse_args()

    client = ClickUpClient()
    if args.list_members:
        print(json.dumps(client.get_members(), indent=2))
    elif args.list_spaces:
        print(json.dumps(client.get_spaces(), indent=2))
    elif args.list_tasks:
        print(json.dumps(client.get_tasks(args.list_tasks), indent=2))
    else:
        parser.print_help()
