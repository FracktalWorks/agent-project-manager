"""
fix_julia_dates.py — Correct due dates for all Julia tasks (were off by 1 day due
to midnight UTC / IST timezone shift). Uses noon UTC to land on the right calendar day.
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".github/skills/clickup-ops/scripts")
from clickup_client import ClickUpClient  # noqa: E402

def due_ms(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

DUE_THU = due_ms(2026, 6, 5)
DUE_FRI = due_ms(2026, 6, 6)
DUE_SAT = due_ms(2026, 6, 7)
DUE_MON = due_ms(2026, 6, 9)

FIXES = [
    ("86d37yjmr", "CAD: Top Plate Redesign",                          DUE_THU),
    ("86d37ymym", "CAD: XYZ Motor Cooling Separation",                DUE_FRI),
    ("86d38d5py", "CAD: Back Panel — Fan Rearrangement & Smaller Fans", DUE_FRI),
    ("86d37yjgx", "CAD: HEPA Filter — Smaller Filter & Air Circ.",    DUE_SAT),
    ("86d0rjez4", "CAD: Chamber Heating — Compact Heater Addition",   DUE_SAT),
    ("86d3863mf", "PCB Design: Legacy PCB (MKS Robin v3)",            DUE_SAT),
    ("86d3863df", "CAD: Updated Carriage for Inductive Sensor",       DUE_MON),
]

def main() -> None:
    client = ClickUpClient()
    for task_id, label, due in FIXES:
        client.update_task(task_id, due_date=due, due_date_time=False)
        due_date = datetime.fromtimestamp(due / 1000, tz=timezone.utc).date()
        print(f"  ✓  {label} → {due_date}")

if __name__ == "__main__":
    main()
