"""Persist compact, source-transparent statistics for every successful RentCast check.

Historical FirstMover ads are deliberately excluded. Snapshot records keep
sample counts, median advertised base rents and a search-method identifier,
not individual apartment addresses or provider secrets. No API requests.
"""
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from scripts.areas import GWB_POLICY, south_of_gwb

OUT = Path("site/data/market-history.json")
SCHEMA_VERSION = 1
BED_TYPES = ("all", "studio", "one_bed")
AREAS = (
    "Morningside Heights", "Manhattan Valley", "Manhattanville",
    "Hamilton Heights", "South Harlem", "Northern Upper West Side",
    "Central Harlem", "Washington Heights",
)

def summarize(values):
    vals = sorted(int(v) for v in values)
    if not vals:
        return {"count": 0, "median": None}
    med = median(vals)
    return {"count": len(vals), "median": int(med) if med == int(med) else med}

def buckets(listings):
    result = {"all": [], "studio": [], "one_bed": []}
    for row in listings:
        result["all"].append(row["rent"])
        result["studio" if int(row["bedrooms"]) == 0 else "one_bed"].append(row["rent"])
    return {bed: summarize(values) for bed, values in result.items()}

def make_snapshot(source):
    """Summarize just the filtered, deduplicated snapshot shown on the website."""
    if not isinstance(source, dict) or not source.get("checked_at_utc") or not isinstance(source.get("listings"), list):
        raise ValueError("A valid timestamped RentCast snapshot is required")
    rents = []
    groups = defaultdict(list)
    for row in source["listings"]:
        if not isinstance(row, dict) or row.get("source_kind") != "rentcast":
            raise ValueError("Only RentCast listing rows may be used for market history")
        if source.get("geographic_policy") == GWB_POLICY and not south_of_gwb(row.get("latitude"), row.get("longitude")):
            raise ValueError("Market history cannot include an apartment north of the GW Bridge or without coordinates")
        if row.get("area") not in AREAS or int(row.get("bedrooms", -1)) not in (0, 1):
            raise ValueError("Market snapshot contained an unsupported neighborhood or unit type")
        try:
            price = int(row["rent"])
        except (ValueError, TypeError, KeyError) as e:
            raise ValueError("Each record needs a numeric rent") from e
        if not 2250 <= price <= 3000:
            raise ValueError("Snapshot contained a rent outside the declared $2,250–$3,000 range")
        item = {"rent": price, "bedrooms": row["bedrooms"]}
        rents.append(item)
        groups[row["area"]].append(item)
    query_counts = source.get("query_counts") or {}
    capped = bool(source.get("search_response_limit_hit")) or any(
        isinstance(q, dict) and (q.get("at_response_limit") is True or
                                  (isinstance(q.get("returned"), (int, float)) and q["returned"] >= 500))
        for q in query_counts.values()
    )
    return {
        "checked_at_utc": source["checked_at_utc"],
        "search_method": str(source.get("search_method") or "unspecified"),
        "geographic_policy": str(source.get("geographic_policy") or "unspecified"),
        "legacy_reclassified": bool(source.get("snapshot_reclassified")),
        "response_cap_hit": capped,
        "total_count": len(rents),
        "overall": buckets(rents),
        "neighborhoods": {area: buckets(groups[area]) for area in AREAS}
    }

def load_history(path=OUT):
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "source": "RentCast saved rental-search snapshots only",
            "rent_min": 2250,
            "rent_max": 3000,
            "scope": "Eight targeted Manhattan areas south of the approximate George Washington Bridge approach; studios and 1-bedroom listings",
            "geographic_policy": GWB_POLICY,
            "note": "Filtered to the south-of-GW Bridge target area. Sampled advertised base rents only, not comprehensive market statistics, current verified availability, or inflation-adjusted prices. FirstMover historical posts excluded.",
            "snapshots": []
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION
            or data.get("rent_min") != 2250 or data.get("rent_max") != 3000
            or not isinstance(data.get("snapshots"), list)):
        raise ValueError("Market-history file is invalid; do not overwrite stored history")
    return data

def update_history(source, path=OUT):
    """Append a unique observed check; preserve old methods as separate samples.

    Exact same timestamp replays are idempotent. Existing timestamps are never
    silently overwritten by new data or backfilled with fake observations.
    """
    data = load_history(path)
    point = make_snapshot(source)
    exists = next((p for p in data["snapshots"] if p.get("checked_at_utc") == point["checked_at_utc"]), None)
    if exists:
        if exists != point:
            raise ValueError("Conflicting existing observation for the same RentCast check")
        return False
    data["snapshots"].append(point)
    data["snapshots"].sort(key=lambda p: p["checked_at_utc"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return True
