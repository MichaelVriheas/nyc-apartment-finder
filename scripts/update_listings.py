#!/usr/bin/env python3
"""Publish a clearly labeled HISTORICAL rental snapshot from FirstMover's CC0 open data.
No claim of current listing availability. No scraping of listing sites.
"""
import csv
import io
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from scripts.unit_filter import room_rental_reason

API = "https://api.github.com/repos/benfwalla/firstmover-open-data-project/contents/public/data"
RAW = "https://raw.githubusercontent.com/benfwalla/firstmover-open-data-project/main/public/data/"
OUT = Path("site/data/listings.json")
MAX_RENT = 3000
HEADERS = {"User-Agent": "NYCApartmentFinder/1.0 (public historical data client)", "Accept": "application/vnd.github+json"}

def fetch(url):
    headers = dict(HEADERS)
    # Authenticate GitHub API directory lookups to avoid the shared anonymous rate limit.
    # Never send the GitHub token to raw.githubusercontent.com or third-party hosts.
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()

def number(value):
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None

def area(row):
    neighborhood = (row.get("neighborhood") or "").lower().strip()
    state = (row.get("state") or "").upper().strip()
    street = (row.get("street") or "").lower()
    if state not in ("NY", ""):
        return None
    aliases = {
        "Morningside Heights": ("morningside heights",),
        "Manhattan Valley": ("manhattan valley", "bloomingdale"),
        "Manhattanville": ("manhattanville",),
        "Hamilton Heights": ("hamilton heights",),
        "South Harlem": ("south harlem", "southwest harlem", "southeast harlem"),
        "Central Harlem": ("central harlem",),
        "Washington Heights": ("washington heights",),
        "Northern Upper West Side": ("upper west side",),
    }
    # Without coordinates, an entire UWS label is not sufficiently precise.
    # Use latitude for northern UWS, and label everything else only if explicit.
    lat = number(row.get("latitude"))
    for label, names in aliases.items():
        if neighborhood in names:
            if label == "Northern Upper West Side" and (lat is None or not 40.789 <= lat <= 40.806):
                return None
            return label
    # Generic Harlem may be South or Central: do not guess.
    return None

def photo_identifiers(row):
    """Preserve FirstMover's published identifiers only; do not download/serve images.

    Source photo IDs are metadata, not a grant to reproduce StreetEasy photos.
    """
    raw = str(row.get("photo_ids") or "")
    identifiers = []
    for item in raw.split(","):
        token = item.strip()
        if token and len(token) <= 128 and re.fullmatch(r"[A-Za-z0-9_-]+", token):
            if token not in identifiers:
                identifiers.append(token)
        if len(identifiers) >= 12:
            break
    lead = str(row.get("lead_photo_id") or "").strip()
    if lead and (len(lead) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", lead)):
        lead = ""
    return lead, identifiers

def main():
    # Use predictable direct public CSV URLs, bypassing GitHub API directory
    # rate limits. Recent monthly data may not be published until next month.
    current = datetime.now(timezone.utc)
    raw = None
    month = None
    for months_back in range(6):
        serial = current.year * 12 + current.month - 1 - months_back
        candidate = f"{serial // 12:04d}-{serial % 12 + 1:02d}.csv"
        try:
            raw = fetch(RAW + candidate)
            month = candidate
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    if raw is None or month is None:
        raise RuntimeError("No recent FirstMover monthly data was available")
    # UTF-8 BOM tolerant, stream CSV lines from fetched monthly snapshot
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    listings = {}
    filtered_rooms = 0
    for row in reader:
        place = area(row)
        price = number(row.get("price"))
        bedrooms = number(row.get("bedrooms"))
        if not place or price is None or not 0 < price <= MAX_RENT or bedrooms not in (0, 1):
            continue
        if room_rental_reason(row):
            filtered_rooms += 1
            continue
        url = (row.get("url") or "").strip()
        if not url.startswith("https://"):
            continue
        identifier = str(row.get("id") or url)
        lead_photo_id, photo_ids = photo_identifiers(row)
        media_assets = number(row.get("media_asset_count"))
        listings[identifier] = {
            "id": identifier,
            "area": place,
            "address": (row.get("street") or "Address not provided").strip(),
            "unit": (row.get("unit") or "").strip(),
            "rent": int(price),
            "bedrooms": int(bedrooms),
            "bathrooms": number(row.get("bathrooms")),
            "sqft": number(row.get("sqft")),
            "latitude": number(row.get("latitude")),
            "longitude": number(row.get("longitude")),
            "listed_at": (row.get("created_at_utc") or "").strip(),
            "available_date_at_posting": (row.get("available_date") or "").strip(),
            "no_fee_at_posting": (row.get("no_fee") or "").strip(),
            "lead_photo_id": lead_photo_id,
            "photo_ids": photo_ids,
            "media_asset_count_at_posting": int(media_assets) if media_assets is not None and media_assets >= 0 else None,
            "photos_usage": "references_only_not_licensed_for_public_display",
            "unit_scope": "unverified_entire_unit",
            "url": url
        }
    cleaned = sorted(listings.values(), key=lambda x: x["listed_at"], reverse=True)[:2500]
    payload = {
        "source": "FirstMover Open Data (CC0)",
        "source_url": "https://www.firstmovernyc.com/open-data",
        "data_month": month[:-4],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "historical_snapshot_unverified",
        "notice": "These were advertised when first posted. They may no longer be available and prices may have changed. Not a live inventory.",
        "photo_notice": "Photo IDs are source metadata only. This site does not reproduce original listing photographs without permission; visit the original listing for pictures.",
        "coverage_note": "Neighborhood names follow published tags. Northern Upper West Side uses a geographic latitude approximation. Only the eight selected Manhattan search areas are included.",
        "unit_policy": "Room rentals and co-living listings are removed when identifiable from source fields; verify entire-unit and private kitchen/bathroom with the original listing.",
        "rooms_excluded": filtered_rooms,
        "listings": cleaned
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Published {len(cleaned)} historical listings from {month}")
if __name__ == "__main__":
    main()
