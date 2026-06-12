"""Create MDS tasks in ClickUp with assignees and due dates."""
import datetime
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}
LIST_ID = "901612525485"

SURYANSH = 100842374
ANIRUDH  = 101084653
KIRAN    = 100858676


def ms(yyyy: int, mm: int, dd: int) -> int:
    return int(datetime.datetime(yyyy, mm, dd, 18, 0).timestamp() * 1000)


def create(name: str, desc: str, due: int, assignees: list, priority: int = 3) -> str:
    payload = {
        "name": name,
        "description": desc,
        "due_date": due,
        "due_date_time": False,
        "assignees": assignees,
        "priority": priority,
        "notify_all": False,
    }
    r = httpx.post(
        f"https://api.clickup.com/api/v2/list/{LIST_ID}/task",
        headers=H, json=payload, timeout=20,
    )
    if r.status_code == 429:
        time.sleep(62)
        r = httpx.post(
            f"https://api.clickup.com/api/v2/list/{LIST_ID}/task",
            headers=H, json=payload, timeout=20,
        )
    r.raise_for_status()
    t = r.json()
    print(f"  Created: {t['id']} — {t['name']}")
    return t["id"]


print("Creating MDS tasks...")

# 1 — Manufacturing drawings (URGENT)
create(
    "Complete manufacturing drawings and send to vendor for quotation",
    (
        "Finalise all sheet metal and machined part drawings. Send to vendor for "
        "quotation and confirm lead time. Identify a backup vendor.\n\n"
        "This is the critical path blocker — must be done Saturday June 7."
    ),
    ms(2026, 6, 7),
    [SURYANSH],
    priority=1,
)

# 2 — Place fabrication order
create(
    "Place fabrication order with vendor",
    (
        "Once quotation is received and approved, place the order. "
        "Confirm delivery date is within the week window."
    ),
    ms(2026, 6, 8),
    [SURYANSH],
    priority=1,
)

# 3 — BOM + ODOO naming (Monday deadline, 3 assignees)
create(
    "Generate BOM from CAD and update ODOO naming conventions",
    (
        "Export the full Bill of Materials directly from the CAD design. "
        "Update all component names and product names in the CAD file and ODOO "
        "to match the subsystem naming convention used across ODOO.\n\n"
        "Suryansh, Anirudh, and Kiran to complete this together. "
        "Hard deadline: Monday June 9."
    ),
    ms(2026, 6, 9),
    [SURYANSH, ANIRUDH, KIRAN],
    priority=1,
)

# 4 — Inventory issuance & procurement
create(
    "Issue components from inventory / procure missing parts",
    (
        "Run full BOM-vs-inventory check. Issue all available components from stock. "
        "For anything not in inventory, raise purchase orders immediately. "
        "Flag any items with lead times > 2 days to Vijay."
    ),
    ms(2026, 6, 10),
    [SURYANSH],
    priority=2,
)

# 5 — Write test plan
create(
    "Write MDS test plan",
    (
        "Document the test plan covering all required tests before sign-off:\n\n"
        "- Spool replacement ergonomics: 1 kg and 3 kg spools, tool-free swap < 60 seconds\n"
        "- 3 kg spool fitment on spindle (hub diameter clearance check)\n"
        "- Desiccant replacement: tool-free via dedicated port, accessible with gloves\n"
        "- Heating subsystem: reaches setpoint within 30 min, holds within +/-2 deg C\n"
        "- Pneumatic subsystem: filament feeds without kinking, fitting is airtight during print\n"
        "- Electronics subsystem: temperature display/control, safety cutout at >85 deg C\n"
        "- Full unit assembly DFA check: single-person assembly, all fasteners accessible, "
        "no assembly-order conflicts\n"
        "- Noise level: check against < 45 dB target"
    ),
    ms(2026, 6, 10),
    [SURYANSH],
    priority=2,
)

# 6 — Assembly
create(
    "Assemble MDS unit (Suryansh to build)",
    (
        "Assemble the complete MDS unit following the assembly SOP once all fabricated "
        "and bought-out parts are available. Suryansh to do this himself to validate the "
        "assembly process and catch any DFA issues first-hand."
    ),
    ms(2026, 6, 11),
    [SURYANSH],
    priority=2,
)

# 7 — Execute tests
create(
    "Execute test plan and close all punch-list items",
    (
        "Run every test item in the test plan. Document pass/fail results. "
        "Any failures must be investigated and resolved before sign-off. "
        "Suryansh to run all tests himself. Sign-off deadline: Friday June 13."
    ),
    ms(2026, 6, 13),
    [SURYANSH],
    priority=2,
)

print("Done.")
