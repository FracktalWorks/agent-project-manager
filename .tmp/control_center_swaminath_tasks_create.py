import os
import sys
import json
import time
import httpx
from datetime import datetime

LIST_ID = "901611246899"
ASSIGNEE = 101084655
DUE_DATE_MS = int(datetime(2026, 6, 12, 18, 0).timestamp() * 1000)

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
if not TOKEN:
    print("ERROR: CLICKUP_API_TOKEN is not set")
    sys.exit(1)

H = {"Authorization": TOKEN, "Content-Type": "application/json"}
BASE = "https://api.clickup.com/api/v2"

PLAN = [
    {
        "name": "Build Clean Raspberry Pi OS Lite Baseline",
        "description": "Deliver a reproducible Raspberry Pi OS Lite base for Control Center and OctoPrint.\n\nPrerequisites: Target Pi hardware list confirmed\nDone when: All subtasks are done and baseline boots reliably.",
        "subtasks": [
            "Lock one Raspberry Pi OS Lite version for rollout",
            "Install only required system packages for Control Center and OctoPrint",
            "Create one reproducible setup script for baseline provisioning"
        ]
    },
    {
        "name": "Bring Up PyQt5 Xinit Runtime for Control Center",
        "description": "Enable PyQt5 Control Center on X windows using xinit on Raspberry Pi OS Lite.\n\nPrerequisites: Baseline image available\nDone when: Control Center launches automatically and survives reboot.",
        "subtasks": [
            "Install minimal Xorg and xinit stack",
            "Install and validate PyQt5 runtime dependencies",
            "Configure xinit startup script to launch Control Center"
        ]
    },
    {
        "name": "Upgrade OctoPrint to Latest Stable",
        "description": "Move printer backend to the latest stable OctoPrint with safe migration path.\n\nPrerequisites: Baseline and runtime tasks completed\nDone when: OctoPrint is upgraded and basic APIs respond.",
        "subtasks": [
            "Install latest stable OctoPrint in isolated environment",
            "Migrate existing OctoPrint configuration safely",
            "Validate basic OctoPrint API connectivity"
        ]
    },
    {
        "name": "Update Control Center for OctoPrint Compatibility",
        "description": "Ensure Control Center works with latest OctoPrint and supports legacy behavior where required.\n\nPrerequisites: OctoPrint upgrade task completed\nDone when: Breaking auth/API paths are handled and app flow remains intact.",
        "subtasks": [
            "Implement OctoPrint version detection in Control Center",
            "Add legacy login and API fallback path where needed",
            "Patch breaking auth and API integration calls"
        ]
    },
    {
        "name": "Validate Critical End-to-End Control Center Flows",
        "description": "Verify essential operator workflows after Linux and OctoPrint updates.\n\nPrerequisites: Compatibility update complete\nDone when: Core workflows pass on updated image.",
        "subtasks": [
            "Validate login and user session flow",
            "Validate printer connect and start pause resume cancel actions",
            "Validate reboot recovery and auto reconnect behavior"
        ]
    },
    {
        "name": "Apply Linux Kernel Hardening and Performance Tuning",
        "description": "Tune Linux boot and runtime configuration for stable 3D printer operation.\n\nPrerequisites: Baseline image available\nDone when: Kernel and startup tuning changes are applied and validated.",
        "subtasks": [
            "Tune boot startup parameters for stable USB serial and low latency IO",
            "Disable unnecessary services and modules to reduce jitter",
            "Validate short and long print stability after tuning"
        ]
    },
    {
        "name": "Prepare Release Hardening and Rollback",
        "description": "Prepare a safe release baseline with minimal operational safeguards.\n\nPrerequisites: Validation tasks complete\nDone when: Dependencies are pinned and rollback path is documented.",
        "subtasks": [
            "Pin dependency versions for repeatable deployment",
            "Add basic service health and restart policy",
            "Document rollback to previous known good image"
        ]
    }
]

def request(method, path, payload=None):
    url = f"{BASE}{path}"
    r = httpx.request(method, url, headers=H, json=payload, timeout=30)
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.request(method, url, headers=H, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

list_data = request("GET", f"/list/{LIST_ID}")
statuses = [s.get("status", "") for s in list_data.get("statuses", [])]
status = None
for candidate in ["to do", "todo", "to_do", "to-do"]:
    if candidate in statuses:
        status = candidate
        break
if status is None and statuses:
    status = statuses[0]

created = []
for parent in PLAN:
    payload = {
        "name": parent["name"],
        "description": parent["description"],
        "assignees": [ASSIGNEE],
        "due_date": DUE_DATE_MS,
        "due_date_time": False,
        "notify_all": False,
    }
    if status:
        payload["status"] = status

    p = request("POST", f"/list/{LIST_ID}/task", payload)
    parent_id = p["id"]
    entry = {"parent": parent["name"], "parent_id": parent_id, "subtasks": []}

    for st in parent["subtasks"]:
        sp = {
            "name": st,
            "parent": parent_id,
            "assignees": [ASSIGNEE],
            "due_date": DUE_DATE_MS,
            "due_date_time": False,
            "notify_all": False,
        }
        if status:
            sp["status"] = status
        s = request("POST", f"/list/{LIST_ID}/task", sp)
        entry["subtasks"].append({"name": st, "id": s["id"]})

    created.append(entry)

print(json.dumps({"list_id": LIST_ID, "status_used": status, "created_count": len(created), "created": created}, indent=2))
