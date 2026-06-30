import sys, os, json
from load_env import load_env; load_env()
sys.path.insert(0, '.github/skills/clickup-ops/scripts')
from clickup_client import ClickUpClient

client = ClickUpClient()

# List all pages in the Hardware Projects doc
result = client._request("GET", "/doc/2kz0eqmc-18436/page")
pages = result.get("pages", [])
print(f"Pages in Hardware Projects doc ({len(pages)}):")
for p in pages:
    print(f"  {p['id']} | {p['name']}")

# Also show content of any Julia Series page if it exists
for p in pages:
    if "julia" in p["name"].lower():
        print(f"\n--- Julia page content ---")
        detail = client._request("GET", f"/doc/2kz0eqmc-18436/page/{p['id']}")
        print(detail.get("text_content","")[:3000])
