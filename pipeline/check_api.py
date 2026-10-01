"""Phase 0 check: confirm the EIA API key works."""
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("EIA_API_KEY")
if not key:
    sys.exit("EIA_API_KEY is missing. Copy .env.example to .env and add your key.")

resp = requests.get("https://api.eia.gov/v2/electricity/", params={"api_key": key}, timeout=30)
if resp.status_code != 200:
    sys.exit(f"EIA API returned {resp.status_code}: {resp.text[:200]}")

routes = [r["id"] for r in resp.json()["response"]["routes"]]
print("EIA API key works. Electricity datasets available:")
for r in routes:
    print(f"  - {r}")
