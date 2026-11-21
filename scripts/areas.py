"""Approximate neighborhood assignments using NYC DCP 2020 NTA polygons.

2020 Neighborhood Tabulation Areas are statistical units, not legally defined
neighborhoods. The narrower Manhattan Valley vs Northern UWS split is an
explicit, approximate local rule. Keep these caveats in the UI.
Source: https://data.cityofnewyork.us/d/9nt8-h7nd
"""
import json
import math
from functools import lru_cache
from pathlib import Path

BOUNDARIES = Path(__file__).resolve().parents[1] / "site" / "data" / "manhattan-nta-areas.geojson"
NTA_TO_AREA = {
    "MN0702": "Northern Upper West Side",
    "MN0703": "Manhattan Valley",
    "MN0901": "Morningside Heights",
    "MN0902": "Manhattanville",
    "MN0903": "Hamilton Heights",
    "MN1001": "South Harlem",
    "MN1002": "Central Harlem",
    "MN1201": "Washington Heights",
    "MN1202": "Washington Heights",
}

@lru_cache(maxsize=1)
def polygons():
    data = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    features = data.get("features", [])
    codes = {f.get("properties", {}).get("nta2020") for f in features}
    if codes != set(NTA_TO_AREA):
        raise RuntimeError("Manhattan NTA polygon reference is incomplete; refusing inaccurate classifications")
    return features

def inside_ring(lon, lat, ring):
    """Ray-casting point-in-ring for GeoJSON [longitude, latitude] vertices."""
    inside = False
    for i in range(len(ring)):
        a_lon, a_lat = ring[i]
        b_lon, b_lat = ring[(i + 1) % len(ring)]
        # On a boundary is assigned to the polygon rather than dropped.
        cross = (lon - a_lon) * (b_lat - a_lat) - (lat - a_lat) * (b_lon - a_lon)
        if abs(cross) < 1e-10 and min(a_lon, b_lon) - 1e-10 <= lon <= max(a_lon, b_lon) + 1e-10 and min(a_lat, b_lat) - 1e-10 <= lat <= max(a_lat, b_lat) + 1e-10:
            return True
        if (a_lat > lat) != (b_lat > lat) and lon < (b_lon-a_lon)*(lat-a_lat)/(b_lat-a_lat)+a_lon:
            inside = not inside
    return inside

def inside_feature(lon, lat, geometry):
    coordinates = geometry.get("coordinates") or []
    polygons_iter = coordinates if geometry.get("type") == "MultiPolygon" else [coordinates]
    for poly in polygons_iter:
        if poly and inside_ring(lon, lat, poly[0]) and not any(inside_ring(lon, lat, hole) for hole in poly[1:]):
            return True
    return False

def classify_area(latitude, longitude, state="NY"):
    """Return one target neighborhood, or None when outside target geography.

    Require usable coordinates. State is additionally checked if provided.
    """
    if state and str(state).upper() != "NY":
        return None
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and 40.77 <= lat <= 40.88 and -74.01 <= lon <= -73.90):
        return None
    for feature in polygons():
        if not inside_feature(lon, lat, feature["geometry"]):
            continue
        code = feature["properties"]["nta2020"]
        label = NTA_TO_AREA[code]
        # MN0702 extends into the central UWS. Our user explicitly wants its
        # northern portion; exclude points south of about West 83rd Street.
        if code == "MN0702" and lat < 40.787:
            return None
        # MN0703 includes both Manhattan Valley and northern UWS; its west
        # sub-area near West End/Riverside is a custom approximation.
        if code == "MN0703" and lon < -73.972 and lat >= 40.795:
            label = "Northern Upper West Side"
        return label
    return None
