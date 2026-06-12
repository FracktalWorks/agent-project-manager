"""
update_julia_tasks.py — One-shot script to assign, date, reopen, create, and
sequence all Julia Series tasks for Sougata and Vijay.

Run:
    python scripts/update_julia_tasks.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".github/skills/clickup-ops/scripts")
from clickup_client import ClickUpClient  # noqa: E402

JULIA_LIST_ID = "901611246751"

SOUGATA_ID = 100932003
VIJAY_ID   = 236494607


def due_ms(year: int, month: int, day: int) -> int:
    """Return ClickUp-compatible due date (noon UTC) as milliseconds.
    Using noon UTC ensures the date renders correctly regardless of user timezone
    (avoids midnight-UTC rolling back one day in UTC+5:30 IST).
    """
    return int(datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


DUE_THU = due_ms(2026, 6, 5)   # Jun 5
DUE_FRI = due_ms(2026, 6, 6)   # Jun 6
DUE_SAT = due_ms(2026, 6, 7)   # Jun 7
DUE_MON = due_ms(2026, 6, 9)   # Jun 9

# Existing task IDs
TASK_TOP_PLATE         = "86d37yjmr"   # CAD: Top Plate Redesign          → Sougata, Thu
TASK_MOTOR_COOLING     = "86d37ymym"   # CAD: XYZ Motor Cooling Separation → Sougata, Fri
TASK_BACK_PANEL        = None          # NEW: Back Panel Fan Rearrangement → Sougata, Fri (create)
TASK_HEPA              = "86d37yjgx"   # CAD: HEPA Filter                  → Sougata, Sat (reopen + update)
TASK_CHAMBER_HEATING   = "86d0rjez4"   # CAD: Chamber Heating              → Sougata, Sat
TASK_PCB               = "86d3863mf"   # PCB Design: Legacy PCB            → Vijay, Sat, urgent
TASK_CARRIAGE          = "86d3863df"   # CAD: Updated Carriage             → Vijay, Mon


def main() -> None:
    client = ClickUpClient()

    print("=== Julia Series — bulk update ===\n")

    # ── 1. Top Plate Redesign — set due date only (already assigned to Sougata)
    print("1. Top Plate Redesign → due Thu Jun 5")
    client.update_task(TASK_TOP_PLATE, due_date=DUE_THU, due_date_time=False)

    # ── 2. XYZ Motor Cooling Separation — assign Sougata + due Fri
    print("2. XYZ Motor Cooling Separation → Sougata, due Fri Jun 6")
    client.update_task(
        TASK_MOTOR_COOLING,
        assignees={"add": [SOUGATA_ID]},
        due_date=DUE_FRI,
        due_date_time=False,
    )

    # ── 3. Subtask: Z-Axis Assembly Re-arrangement (optional/conditional)
    print("3. Creating subtask: Z-Axis Assembly Re-arrangement (if required)")
    subtask = client._request(
        "POST",
        f"/list/{JULIA_LIST_ID}/task",
        json={
            "name": "CAD: Z-Axis Assembly Re-arrangement (if required)",
            "description": (
                "Optional sub-task of XYZ Motor Cooling Separation. "
                "Re-arrange the Z assembly only if the motor-chamber separation "
                "exercise identifies clearance or interference issues that require it."
            ),
            "assignees": [SOUGATA_ID],
            "due_date": DUE_FRI,
            "due_date_time": False,
            "parent": TASK_MOTOR_COOLING,
        },
    )
    print(f"   Created subtask id: {subtask['id']}")

    # ── 4. NEW task: Back Panel — Fan Rearrangement & Smaller Fans
    print("4. Creating new task: Back Panel — Fan Rearrangement & Smaller Fans")
    new_back_panel = client.create_task(
        list_id=JULIA_LIST_ID,
        name="CAD: Back Panel — Fan Rearrangement & Smaller Fans",
        description=(
            "Re-arrange the fans on the back panel and replace with smaller fans. "
            "Update the back panel CAD to accommodate the new fan positions and sizes "
            "while maintaining adequate airflow."
        ),
        assignees=[SOUGATA_ID],
        due_date_ms=DUE_FRI,
    )
    print(f"   Created task id: {new_back_panel['id']}")

    # ── 5. HEPA Filter — reopen, update description, assign, due Sat
    print("5. HEPA Filter → reopen, update scope, assign Sougata, due Sat Jun 7")
    client.update_task(
        TASK_HEPA,
        status="to do",
        name="CAD: HEPA Filter — Smaller Filter & Active Air Circulation",
        description=(
            "Update the HEPA filter assembly to use a smaller filter unit. "
            "Redesign air circulation so that filtered air actively circulates through "
            "the chamber (not just passive exhaust). Ensure fitment within the new "
            "back panel layout."
        ),
        assignees={"add": [SOUGATA_ID]},
        due_date=DUE_SAT,
        due_date_time=False,
    )

    # ── 6. Chamber Heating — update name, assign Sougata, due Sat
    print("6. Chamber Heating → update name, assign Sougata, due Sat Jun 7")
    client.update_task(
        TASK_CHAMBER_HEATING,
        name="CAD: Chamber Heating — Compact Heater Addition",
        description=(
            "Design and integrate a compact/smaller heater unit into the printer chamber. "
            "Heater must support sustained elevated chamber temperatures for printing "
            "performance materials (ABS composites, carbon fibre composites)."
        ),
        assignees={"add": [SOUGATA_ID]},
        due_date=DUE_SAT,
        due_date_time=False,
    )

    # ── 7. PCB Design — assign Vijay, urgent, due Sat
    print("7. PCB Design: Legacy PCB → Vijay, urgent, due Sat Jun 7")
    client.update_task(
        TASK_PCB,
        assignees={"add": [VIJAY_ID]},
        priority=1,           # 1 = urgent
        due_date=DUE_SAT,
        due_date_time=False,
    )

    # ── 8. Updated Carriage — assign Vijay, due Mon
    print("8. CAD: Updated Carriage for Inductive Sensor → Vijay, due Mon Jun 9")
    client.update_task(
        TASK_CARRIAGE,
        assignees={"add": [VIJAY_ID]},
        due_date=DUE_MON,
        due_date_time=False,
    )

    print("\n=== All updates complete ===")
    print("\nSougata's Julia sequence:")
    print("  Thu Jun 5 → Top Plate Redesign")
    print("  Fri Jun 6 → XYZ Motor Cooling Separation")
    print("              ↳ Subtask: Z-Axis Assembly Re-arrangement (if required)")
    print("  Fri Jun 6 → Back Panel — Fan Rearrangement & Smaller Fans")
    print("  Sat Jun 7 → HEPA Filter — Smaller Filter & Active Air Circulation")
    print("  Sat Jun 7 → Chamber Heating — Compact Heater Addition")
    print("\nVijay's Julia tasks:")
    print("  Sat Jun 7 → PCB Design: Legacy PCB update [URGENT]")
    print("  Mon Jun 9 → CAD: Updated Carriage for Inductive Sensor")


if __name__ == "__main__":
    main()
