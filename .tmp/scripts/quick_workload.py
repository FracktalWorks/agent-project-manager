#!/usr/bin/env python3
"""
Quick workload pull — directly query the 3 main project lists from ClickUp.
"""
import os
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "skills" / "clickup-ops" / "scripts"))
from clickup_client import ClickUpClient

client = ClickUpClient()

# Project list IDs from project_registry.json
LISTS = {
    "Penrose Pellet Extruder": "901611050642",
    "Julia Series": "901611246751",
    "MDS (Material Drying System)": "901612525485",
}

# Load hr_structure.json to map ClickUp user IDs → names
hr_file = Path(__file__).parent.parent.parent / "agent-data" / "hr_structure.json"
hr_data = json.loads(hr_file.read_text())

user_map = {}  # clickup_user_id → name
for dept in hr_data.get("departments", []):
    for team in dept.get("teams", []):
        for member in team.get("members", []):
            uid = member.get("clickup_user_id")
            if uid:
                user_map[uid] = member.get("name", "Unknown")

print("=" * 80)
print("FRACKTAL WORKS — TEAM WORKLOAD REPORT")
print(f"Source: ClickUp (live)")
print("=" * 80)

# Collect all tasks by assignee
workload = defaultdict(lambda: {"tasks": [], "task_count": 0})

for project_name, list_id in LISTS.items():
    print(f"\nFetching tasks from '{project_name}'...")
    try:
        tasks = client.get_tasks(list_id, include_closed=False)
        print(f"  Found {len(tasks)} open tasks")
        
        for task in tasks:
            task_name = task.get("name", "Unnamed")
            task_id = task.get("id", "?")
            assignees = task.get("assignees", [])
            priority_obj = task.get("priority")
            priority = priority_obj.get("priority", 3) if priority_obj else 3
            
            if assignees:
                for assignee in assignees:
                    if assignee is None:
                        continue
                    uid = assignee.get("id")
                    name = user_map.get(uid, f"Unknown (ID: {uid})")
                    workload[name]["tasks"].append({
                        "project": project_name,
                        "task": task_name,
                        "task_id": task_id,
                        "priority": priority,
                    })
                    workload[name]["task_count"] += 1
            else:
                # Task with no assignee
                workload["[UNASSIGNED]"]["tasks"].append({
                    "project": project_name,
                    "task": task_name,
                    "task_id": task_id,
                    "priority": priority,
                })
                workload["[UNASSIGNED]"]["task_count"] += 1
    except Exception as e:
        print(f"  ERROR: {e}")

# Print summary
print("\n" + "=" * 80)
print("TEAM WORKLOAD SUMMARY (Ranked by Load)")
print("=" * 80)

if not workload:
    print("No tasks found!")
else:
    sorted_people = sorted(workload.items(), key=lambda x: x[1]["task_count"], reverse=True)
    
    # Get team capacity from hr_structure
    capacity_map = {}
    for dept in hr_data.get("departments", []):
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                capacity_map[member.get("name")] = member.get("capacity_hours_per_week", 40)
    
    for name, data in sorted_people:
        count = data["task_count"]
        capacity = capacity_map.get(name, 40)
        # Rough estimate: assume 4 hours per task by default
        estimated_hours = count * 4
        utilization = (estimated_hours / capacity * 100) if capacity else 0
        
        # Status indicator
        if count == 0:
            status = "✅ AVAILABLE"
        elif utilization >= 100:
            status = "🔴 OVERLOADED"
        elif utilization >= 75:
            status = "🟠 HEAVILY LOADED"
        elif utilization >= 50:
            status = "🟡 MODERATELY LOADED"
        else:
            status = "🟢 LIGHTLY LOADED"
        
        print(f"\n{name}: {count} task(s) | {status}")
        print(f"  Estimated load: ~{estimated_hours} hrs/week | Capacity: {capacity} hrs/week ({utilization:.0f}% utilized)")
        
        for i, task_info in enumerate(data["tasks"], 1):
            priority_label = {1: "🔴 URGENT", 2: "🟠 HIGH", 3: "🟡 NORMAL", 4: "🟢 LOW"}.get(task_info["priority"], "? NONE")
            print(f"  {i}. [{priority_label}] {task_info['project']}")
            print(f"     → {task_info['task']}")

print("\n" + "=" * 80)
total_tasks = sum(d["task_count"] for d in workload.values())
print(f"TOTAL ASSIGNED TASKS: {total_tasks}")
print("=" * 80)

# Show who is available
print("\n📋 CAPACITY ANALYSIS")
print("=" * 80)
people_with_capacity = []
for name in capacity_map:
    task_count = workload.get(name, {}).get("task_count", 0)
    capacity = capacity_map[name]
    estimated_hours = task_count * 4
    utilization = (estimated_hours / capacity * 100) if capacity else 0
    available = capacity - estimated_hours
    
    people_with_capacity.append({
        "name": name,
        "tasks": task_count,
        "utilization": utilization,
        "available_hours": max(0, available),
        "capacity": capacity,
    })

available_people = sorted(
    [p for p in people_with_capacity if p["available_hours"] > 16],  # 4+ hours spare
    key=lambda x: x["available_hours"],
    reverse=True
)

if available_people:
    print("\n✅ PEOPLE WITH SIGNIFICANT CAPACITY (>16 hrs/week available):")
    for p in available_people:
        print(f"  • {p['name']}: {p['available_hours']:.0f} hrs available ({p['capacity'] - p['tasks']*4:.0f} hrs free)")
else:
    print("\n⚠️  No team members with significant available capacity.")

overloaded = [p for p in people_with_capacity if p["utilization"] > 100]
if overloaded:
    print("\n🔴 OVERLOADED TEAM MEMBERS:")
    for p in overloaded:
        print(f"  • {p['name']}: {p['tasks']} tasks (~{p['utilization']:.0f}% utilized)")

