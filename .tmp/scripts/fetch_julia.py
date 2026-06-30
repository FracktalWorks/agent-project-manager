import sys, os
from load_env import load_env; load_env()
sys.path.insert(0, '.github/skills/clickup-ops/scripts')
from clickup_client import ClickUpClient
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

client = ClickUpClient()
tasks = client.get_tasks('901611246751', include_closed=False)
for t in tasks:
    due = t.get('due_date')
    due_str = datetime.fromtimestamp(int(due)/1000, tz=IST).date().isoformat() if due else 'None'
    assignees = [a.get('username','') for a in t.get('assignees',[])]
    status = t.get('status',{}).get('status','')
    priority = t.get('priority') or {}
    prio_str = priority.get('priority','') if priority else ''
    print(f"{t['id']} | {t['name']} | {status} | due:{due_str} | assignees:{assignees} | priority:{prio_str}")
