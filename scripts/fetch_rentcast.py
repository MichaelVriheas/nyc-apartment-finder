#!/usr/bin/env python3
"""Fetch RentCast long-term rental listings while enforcing a durable, conservative
rolling-31-day request budget. Call --reserve and COMMIT + PUSH its ledger *before*
--fetch. Reserved calls count even when a request subsequently fails.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

LEDGER = Path(".rentcast-budget.json")
OUTPUT = Path("site/data/rentcast.json")
BUDGET = 20  # At most 20 attempted calls in ANY rolling 31-day window.
CALLS_PER_RUN = 2
SEARCHES = [
    ("Upper Manhattan", {"latitude": "40.8215", "longitude": "-73.9562", "radius": "3.7"}),
    ("Fort Lee", {"city": "Fort Lee", "state": "NJ"}),
]
ENDPOINT = "https://api.rentcast.io/v1/listings/rental/long-term"

def now():
    return datetime.now(timezone.utc)

def run_key():
    run = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if not run or not attempt:
        raise RuntimeError("Requires a GitHub Actions run ID and attempt to manage quota")
    return f"{run}-{attempt}"

def ledger_entries():
    if not LEDGER.exists():
        return []
    raw = json.loads(LEDGER.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        raise RuntimeError("Invalid usage ledger; refusing to make any API requests")
    return raw["entries"]

def relevant(entries):
    threshold = now() - timedelta(days=31)
    valid = []
    for item in entries:
        try:
            ts = datetime.fromisoformat(item["at"])
            count = int(item["calls"])
            if ts.tzinfo is None or count <= 0:
                raise ValueError("invalid entry")
        except (ValueError, TypeError, KeyError) as e:
            raise RuntimeError("Invalid usage ledger; refusing API requests") from e
        if ts > threshold:
            valid.append(item)
    return valid

def reserve():
    entries = relevant(ledger_entries())
    key = run_key()
    if any(e["run"] == key for e in entries):
        print("This workflow attempt has already reserved calls; refusing duplicate requests")
        return
    used = sum(int(e["calls"]) for e in entries)
    if used + CALLS_PER_RUN > BUDGET:
        print(f"RentCast skipped: {used}/{BUDGET} API calls reserved in the previous 31 days")
        return
    entries.append({"run": key, "at": now().isoformat(), "calls": CALLS_PER_RUN})
    LEDGER.write_text(json.dumps({"policy": "max_20_attempted_requests_per_rolling_31_days", "entries": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"Reserved {CALLS_PER_RUN} RentCast requests; rolling budget {used + CALLS_PER_RUN}/{BUDGET}")

def maybe_num(v):
    try:
        return float(v) if v is not None and str(v).strip() else None
    except (ValueError, TypeError):
        return None

def classify(row, search):
    state = str(row.get("state") or "").upper()
    city = str(row.get("city") or "").lower()
    if search == "Fort Lee":
        return "Fort Lee" if state == "NJ" and city == "fort lee" else None
    if state != "NY":
        return None
    lat = maybe_num(row.get("latitude"))
    lon = maybe_num(row.get("longitude"))
    if lat is None or lon is None:
        return None
    # Approximate research search regions, NOT official neighborhood polygons.
    if 40.787 <= lat < 40.799 and -73.984 < lon < -73.957:
        return "Northern Upper West Side"
    if 40.799 <= lat < 40.807 and -73.982 < lon < -73.952:
        return "Manhattan Valley"
    if 40.807 <= lat < 40.818 and -73.979 < lon < -73.954:
        return "Morningside Heights"
    if 40.816 <= lat < 40.829 and -73.976 < lon < -73.950:
        return "Manhattanville"
    if 40.828 <= lat < 40.843 and -73.970 < lon < -73.949:
        return "Hamilton Heights"
    if 40.806 <= lat < 40.822 and -73.954 <= lon < -73.927:
        return "South Harlem"
    if 40.821 <= lat < 40.839 and -73.950 <= lon < -73.927:
        return "Central Harlem"
    if 40.838 <= lat <= 40.865 and -73.964 < lon < -73.916:
        return "Washington Heights"
    return None

def retrieve(query, secret):
    params = dict(query)
    params.update({"bedrooms": "0|1", "price": "*:3000", "status": "Active", "limit": "500"})
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        "X-Api-Key": secret, "Accept": "application/json",
        "User-Agent": "NYC-Apartment-Finder/1.0"
    })
    with urllib.request.urlopen(request, timeout=45) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Unexpected RentCast status {resp.status}")
        data = json.load(resp)
    if not isinstance(data, list):
        raise RuntimeError("Unexpected RentCast response format")
    return data

def fetch():
    key = run_key()
    entries = relevant(ledger_entries())
    if not any(e.get("run") == key and int(e.get("calls", 0)) == CALLS_PER_RUN for e in entries):
        print("No persisted reservation for this run; no RentCast requests will be made")
        return
    secret = os.environ.get("RENTCAST_API_KEY")
    if not secret:
        raise RuntimeError("Missing GitHub Actions secret RENTCAST_API_KEY")
    all_rows = {}
    counts = {}
    for label, query in SEARCHES:
        try:
            rows = retrieve(query, secret)
        except urllib.error.HTTPError as e:
            # Never print headers, secret, request object, or API response body.
            raise RuntimeError(f"RentCast request failed with HTTP {e.code} for {label}") from None
        counts[label] = {"returned": len(rows), "matched": 0}
        for row in rows:
            area = classify(row, label)
            rent = maybe_num(row.get("price"))
            bedrooms = maybe_num(row.get("bedrooms"))
            if not area or rent is None or not 0 < rent <= 3000 or bedrooms not in (0, 1):
                continue
            if row.get("status") != "Active":
                continue
            identifier = str(row.get("id") or "")
            if not identifier:
                continue
            counts[label]["matched"] += 1
            addr = str(row.get("formattedAddress") or row.get("addressLine1") or "Address not provided")
            # RentCast does not promise a deep link to the original listing.
            # Provide a clearly labeled address-search link instead.
            search_url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": f"{addr} apartment rent"})
            all_rows[identifier] = {
                "id": "rentcast-" + identifier, "source_kind": "rentcast",
                "area": area, "area_estimated": area != "Fort Lee",
                "address": addr, "unit": "",
                "rent": int(rent), "bedrooms": int(bedrooms),
                "bathrooms": maybe_num(row.get("bathrooms")), "sqft": maybe_num(row.get("squareFootage")),
                "latitude": maybe_num(row.get("latitude")), "longitude": maybe_num(row.get("longitude")),
                "listed_at": str(row.get("listedDate") or ""),
                "last_seen": str(row.get("lastSeenDate") or ""),
                "status_at_check": "Active",
                "no_fee_at_posting": "",
                "url": search_url,
                "link_label": "Search for listing ↗"
            }
    output = {
        "source": "RentCast rental listings API",
        "status": "provider_reported_active_at_check",
        "checked_at_utc": now().isoformat(),
        "warning": "Provider-reported active status is not a guarantee of availability. Verify independently. Neighborhood classifications are approximate.",
        "query_counts": counts,
        "requests_reserved_in_31_days": sum(int(x["calls"]) for x in entries),
        "listings": sorted(all_rows.values(), key=lambda r: r["last_seen"], reverse=True)
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("RentCast test results (no secret or addresses shown): " + json.dumps(counts))
    print(f"Published {len(all_rows)} provider-reported active rental listings; not independently verified")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["reserve", "fetch"])
    mode = parser.parse_args().mode
    (reserve if mode == "reserve" else fetch)()
