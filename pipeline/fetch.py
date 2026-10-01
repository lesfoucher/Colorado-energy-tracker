"""Download Colorado electricity data from the EIA API v2 and save the raw responses."""
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
BASE_URL = "https://api.eia.gov/v2/electricity"
PAGE_SIZE = 5000

# Fuel codes the tracker uses. See docs/requirements.md for what each one means.
FUELS = ["ALL", "COW", "NG", "WND", "SUN", "HYC", "AOR", "REN", "DPV"]

DATASETS = {
    "generation": {
        "route": "electric-power-operational-data",
        "params": [("data[]", "generation"), ("facets[location][]", "CO"), ("facets[sectorid][]", "99")]
        + [("facets[fueltypeid][]", f) for f in FUELS],
    },
    "retail": {
        "route": "retail-sales",
        "params": [("data[]", "price"), ("data[]", "sales"), ("data[]", "customers"), ("facets[stateid][]", "CO")],
    },
    # Annual totals from the EIA's Colorado state profile, used as an independent check.
    "profile": {
        "route": "state-electricity-profiles/source-disposition",
        "frequency": "annual",
        "params": [("data[]", "total-net-generation"), ("facets[state][]", "CO")],
    },
}


def api_key():
    load_dotenv(ROOT / ".env")
    key = (os.getenv("EIA_API_KEY") or "").strip()  # a pasted key can carry a trailing newline
    if not key:
        raise SystemExit("EIA_API_KEY is missing. Copy .env.example to .env and add your key.")
    return key


def get_page(route, params, offset, key, frequency="monthly", retries=3):
    query = [("api_key", key), ("frequency", frequency), ("offset", offset), ("length", PAGE_SIZE),
             ("sort[0][column]", "period"), ("sort[0][direction]", "asc")] + params
    for attempt in range(retries):
        resp = requests.get(f"{BASE_URL}/{route}/data/", params=query, timeout=60)
        if resp.status_code == 200:
            return resp.json()["response"]
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"EIA API returned {resp.status_code} for {route}: {resp.text[:200]}")


def fetch_dataset(name, key):
    """Fetch every page of a dataset and return all rows."""
    spec = DATASETS[name]
    rows, offset = [], 0
    while True:
        page = get_page(spec["route"], spec["params"], offset, key, spec.get("frequency", "monthly"))
        rows.extend(page["data"])
        offset += len(page["data"])
        if not page["data"] or offset >= int(page["total"]):
            break
    if offset != int(page["total"]):
        raise RuntimeError(f"{name}: expected {page['total']} rows, got {offset}")
    return rows


def fetch_all():
    """Download both datasets and save them to data/raw/. Returns {name: rows}."""
    key = api_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in DATASETS:
        rows = fetch_dataset(name, key)
        (RAW_DIR / f"{name}.json").write_text(json.dumps(rows))
        result[name] = rows
        print(f"Fetched {len(rows):,} {name} rows")
    return result


def load_raw():
    """Read the saved raw responses, so the pipeline can rerun without calling the API."""
    result = {}
    for name in DATASETS:
        path = RAW_DIR / f"{name}.json"
        if not path.exists():
            raise SystemExit(f"No saved data at {path}. Run the pipeline without --offline first.")
        result[name] = json.loads(path.read_text())
    return result
