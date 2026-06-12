"""
create_julia_doc_page.py — Create the Julia Series project page in the
Hardware Projects Reference doc (2kz0eqmc-18436).
"""
from __future__ import annotations
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".github/skills/clickup-ops/scripts")
from clickup_client import ClickUpClient  # noqa: E402

DOC_ID = "2kz0eqmc-18436"

JULIA_PAGE_CONTENT = """Julia Series — Next-Gen Desktop 3D Printer

Status: Active
ClickUp List: https://app.clickup.com/90161241740/90165087954/list/901611246751
Last Updated: 2026-06-05

---

1. What Is This Project?

The Julia Series is Fracktal's next-generation desktop 3D printer, redesigned from the ground up for printing performance materials — carbon fibre composites, ABS composites, and similar engineering-grade feedstocks. Primary target market: industrial tooling, jigs, and fixtures applications.

2. Why Does It Exist?

Fracktal's existing printers are not optimised for performance composites at desktop scale. The Julia Series addresses this gap by combining an enclosed heated chamber, CAN-bus toolheads, and a novel eddy-current inductive sensor — enabling calibrated material profiling and reliable printing of structural engineering materials for the industrial tooling and light manufacturing segment.

3. Current Phase

Design

4. Design Philosophy

Modular and parametric CAD — the chassis is designed to be reusable and scalable across all Julia variants. Changing the printer volume for a new variant only requires scaling the parametric model; no full redesign is needed.

CAN bus toolhead — extruder electronics live on the toolhead, simplifying wiring and enabling plug-and-play tool head replaceability.

Eddy current inductive sensor — a toolhead-mounted sensor measuring minute nozzle displacement relative to the extruder body. This enables:
  - Automatic pressure advance / linear advance calibration per material
  - Nozzle-as-probe bed levelling
  - Dual nozzle offset calculation (IDEX variant)

5. Variants

Julia Single
  Build volume: 256 x 256 x 300 mm
  Motion: Single CoreXY
  Additions: Optional HEPA filter, optional chamber heater
  Target: Performance material desktop printing

Julia IDEX
  Build volume: 256 x 256 x 300 mm
  Motion: Hybrid CoreXY — Klipper IDEX (similar to Voron Tridex / RatRig V4)
  Additions: Second Y-axis, dual carriages
  Capabilities: Dual extrusion + support material printing

6. Team

Project Lead: Vijay Raghav Varada
Mechanical / CAD: SOUGATA MAJI
Mechatronics: Ayush Sarkar

7. Current Sprint — Julia CAD & PCB (Sprint ends Sat 7 Jun 2026)

Sougata (SOUGATA MAJI):
  Thu Jun 5  — CAD: Top Plate Redesign [in progress]
  Fri Jun 6  — CAD: XYZ Motor Cooling — Motor-Chamber Separation
  Fri Jun 6  —   Subtask: Z-Axis Assembly Re-arrangement (if required)
  Fri Jun 6  — CAD: Back Panel — Fan Rearrangement & Smaller Fans
  Sat Jun 7  — CAD: HEPA Filter — Smaller Filter & Active Air Circulation
  Sat Jun 7  — CAD: Chamber Heating — Compact Heater Addition

Vijay Raghav Varada:
  Sat Jun 7  — PCB Design: Legacy PCB update for MKS Robin v3 [URGENT]
  Mon Jun 9  — CAD: Updated Carriage for Inductive Sensor

Completed:
  CAD: 3.5 Inch RPi Resistive Touch Display [done]

8. Open Questions

- Toolhead CAN bus controller: custom PCB or off-shelf (e.g. EBB36 / similar)? (owner: Vijay)
- IDEX second carriage Y-axis motion: belt or leadscrew? (owner: Vijay)
- Chamber heater target temperature: 60 C for ABS or higher for CF composites? (owner: Vijay)
- Eddy current sensor: off-shelf unit selection or in-house PCB? (owner: Ayush)

9. Notes & History

2026-06-05: Julia Series 2026 redesign kickoff sprint. CAD work covers back panel fan rearrangement, motor-chamber thermal separation, HEPA and chamber heating modules, and top plate. PCB team updating legacy MKS Robin v3 board. Inductive sensor carriage update follows sprint close (Mon Jun 9). IDEX variant follows single-extruder baseline build validation.
"""


def main() -> None:
    client = ClickUpClient()
    # ClickUp Docs page creation requires API v3
    # Override base URL for this single call
    import httpx, os
    token = os.environ.get("CLICKUP_API_TOKEN", "")
    headers = {"Authorization": token, "Content-Type": "application/json"}

    # v3 endpoint: POST /workspaces/{workspace_id}/docs/{doc_id}/pages
    workspace_id = os.environ.get("CLICKUP_TEAM_ID", "")
    url = f"https://api.clickup.com/api/v3/workspaces/{workspace_id}/docs/{DOC_ID}/pages"
    payload = {
        "name": "Julia Series",
        "content": JULIA_PAGE_CONTENT,
        "content_format": "text/md",
    }
    r = httpx.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {r.status_code}")
    print(r.text[:1000])
    if r.is_success:
        data = r.json()
        page_id = data.get("id", "unknown")
        print(f"\nCreated Julia Series page: {page_id}")
        print(f"URL: https://app.clickup.com/90161241740/docs/{DOC_ID}/{page_id}")
    return


if __name__ == "__main__":
    main()
