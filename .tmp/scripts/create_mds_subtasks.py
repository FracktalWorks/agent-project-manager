"""Create subtasks for all MDS tasks in ClickUp."""
import os
import time

import httpx
from load_env import load_env; load_env()

TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
H = {"Authorization": TOKEN, "Content-Type": "application/json"}
LIST_ID = "901612525485"

SURYANSH = 100842374
ANIRUDH  = 101084653
KIRAN    = 100858676


def subtask(parent_id: str, name: str, desc: str = "", assignees: list = None, due: int = None, priority: int = 3) -> str:
    payload: dict = {
        "name": name,
        "parent": parent_id,
        "assignees": assignees or [],
        "priority": priority,
        "notify_all": False,
    }
    if desc:
        payload["description"] = desc
    if due:
        payload["due_date"] = due
        payload["due_date_time"] = False
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
    print(f"    Subtask: {t['id']} — {t['name']}")
    return t["id"]


import datetime
def ms(yyyy, mm, dd):
    return int(datetime.datetime(yyyy, mm, dd, 18, 0).timestamp() * 1000)


# ─── Task IDs created by create_mds_tasks.py ────────────────────────────────
DRAWINGS_ID   = "86d38kd15"   # Manufacturing drawings
ORDER_ID      = "86d38kd17"   # Place fabrication order
BOM_ID        = "86d38kd18"   # BOM + ODOO naming
INVENTORY_ID  = "86d38kd19"   # Issue / procure
TESTPLAN_ID   = "86d38kd1a"   # Write test plan
ASSEMBLY_ID   = "86d38kd1b"   # Assemble unit
EXECUTE_ID    = "86d38kd1e"   # Execute test plan


# ── 1. Manufacturing drawings ────────────────────────────────────────────────
print("\n[1] Manufacturing drawings subtasks")
subtask(DRAWINGS_ID, "Draw enclosure / body panels",              assignees=[SURYANSH], due=ms(2026,6,7), priority=1)
subtask(DRAWINGS_ID, "Draw spool spindle assembly",               assignees=[SURYANSH], due=ms(2026,6,7), priority=1)
subtask(DRAWINGS_ID, "Draw desiccant chamber & access port",      assignees=[SURYANSH], due=ms(2026,6,7), priority=1)
subtask(DRAWINGS_ID, "Draw pneumatic feed-through bracket/mount", assignees=[SURYANSH], due=ms(2026,6,7), priority=1)
subtask(DRAWINGS_ID, "DFA review of all drawings before sending", assignees=[SURYANSH], due=ms(2026,6,7), priority=1,
        desc="Check that all fasteners are accessible, assembly sequence is single-person, no blind holes etc.")
subtask(DRAWINGS_ID, "Send drawing package to vendor and request quotation", assignees=[SURYANSH], due=ms(2026,6,7), priority=1)

# ── 2. Place fabrication order ───────────────────────────────────────────────
print("\n[2] Fabrication order subtasks")
subtask(ORDER_ID, "Review vendor quotation and confirm lead time", assignees=[SURYANSH], due=ms(2026,6,8), priority=1)
subtask(ORDER_ID, "Place order and obtain order confirmation",     assignees=[SURYANSH], due=ms(2026,6,8), priority=1)
subtask(ORDER_ID, "Confirm expected delivery date vs assembly window", assignees=[SURYANSH], due=ms(2026,6,8), priority=1)

# ── 3. BOM + ODOO naming ─────────────────────────────────────────────────────
print("\n[3] BOM + ODOO naming subtasks")
subtask(BOM_ID, "Export full BOM from CAD (all components, quantities, part numbers)", assignees=[SURYANSH], due=ms(2026,6,9), priority=1)
subtask(BOM_ID, "Cross-check BOM against ODOO part master — flag missing parts",       assignees=[ANIRUDH],  due=ms(2026,6,9), priority=1)
subtask(BOM_ID, "Update CAD component names to match ODOO subsystem naming convention",assignees=[SURYANSH], due=ms(2026,6,9), priority=1)
subtask(BOM_ID, "Update ODOO product names for all MDS components",                    assignees=[KIRAN],    due=ms(2026,6,9), priority=1)
subtask(BOM_ID, "Final BOM review and sign-off",                                       assignees=[SURYANSH, ANIRUDH, KIRAN], due=ms(2026,6,9), priority=1)

# ── 4. Inventory / procurement ───────────────────────────────────────────────
print("\n[4] Inventory / procurement subtasks")
subtask(INVENTORY_ID, "Run BOM vs inventory check — generate shortfall list",          assignees=[SURYANSH], due=ms(2026,6,10), priority=2)
subtask(INVENTORY_ID, "Issue all available components from stock (stock issue request)",assignees=[SURYANSH], due=ms(2026,6,10), priority=2)
subtask(INVENTORY_ID, "Raise purchase orders for all missing components",               assignees=[SURYANSH], due=ms(2026,6,10), priority=2)
subtask(INVENTORY_ID, "Confirm receipt of all purchased/issued parts",                  assignees=[SURYANSH], due=ms(2026,6,11), priority=2)

# ── 5. Write test plan ───────────────────────────────────────────────────────
print("\n[5] Write test plan subtasks")
subtask(TESTPLAN_ID, "Draft test plan document (all 9 test areas)",   assignees=[SURYANSH], due=ms(2026,6,10), priority=2)
subtask(TESTPLAN_ID, "Review and finalise test plan before assembly", assignees=[SURYANSH], due=ms(2026,6,10), priority=2)

# ── 6. Assembly ──────────────────────────────────────────────────────────────
print("\n[6] Assembly subtasks")
subtask(ASSEMBLY_ID, "Assemble enclosure / structural body",             assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Mount spool spindle assembly",                     assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Install heating element and thermal sensor",       assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Install desiccant chamber and access port",        assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Route pneumatic feed-through and PTFE tube",       assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Wire electronics and temperature controller",      assignees=[SURYANSH], due=ms(2026,6,11), priority=2)
subtask(ASSEMBLY_ID, "Final assembly close-up and visual inspection",    assignees=[SURYANSH], due=ms(2026,6,11), priority=2)

# ── 7. Execute test plan ─────────────────────────────────────────────────────
print("\n[7] Execute test plan subtasks")
subtask(EXECUTE_ID, "Test: 1 kg spool swap — tool-free, < 60 seconds",
        desc="Load and unload a 1 kg spool. Time the swap. Must be < 60 sec without tools.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: 3 kg spool swap — tool-free, < 60 seconds",
        desc="Load and unload a 3 kg spool. Time the swap. Must be < 60 sec without tools.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: 3 kg spool hub fitment on spindle",
        desc="Verify the spindle clears the inner hub of a 3 kg spool. Check multiple brands if available.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: Desiccant canister replacement (tool-free, gloves on)",
        desc="Replace desiccant canister via dedicated port without opening main lid. Must work with gloves.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: Heating subsystem — reach setpoint within 30 min, hold +/-2 deg C",
        desc="Set target temperature, measure time to reach setpoint and temperature stability over 1 hour.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: Pneumatic feed-through — no kinking, airtight during print simulation",
        desc="Thread filament, simulate print pull forces, check for kinking and air leakage at fitting.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: Electronics — temperature display accuracy and safety cutout > 85 deg C",
        desc="Verify display matches actual temperature (use reference thermometer). Verify thermal fuse / cutout fires above 85 deg C.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: DFA check — single-person assembly, all fasteners accessible, correct sequence",
        desc="Disassemble and reassemble the full unit alone. Document any ergonomic issues or assembly-order conflicts.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Test: Noise level < 45 dB at 1 m",
        desc="Measure noise during heating cycle at 1 m distance. Must be < 45 dB.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)
subtask(EXECUTE_ID, "Document all test results and close punch-list items",
        desc="Record pass/fail for each test. Investigate and resolve any failures before final sign-off.",
        assignees=[SURYANSH], due=ms(2026,6,13), priority=2)

print("\nDone — all subtasks created.")
