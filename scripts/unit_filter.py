"""Conservative filter for room/share listings, not a guarantee of unit privacy.

Rows from RentCast or FirstMover often lack explicit 'entire place' status.
Only reject clear room/shared-accommodation evidence; do not confuse studio
(bedrooms=0) with a room in someone else's apartment.
"""
import re

ROOM_SCOPE = re.compile(
    r"\b(?:private\s+room|single\s+room|room\s+for\s+rent|room\s+available|"
    r"bedroom\s+for\s+rent|rent(?:ing)?\s+(?:a\s+)?(?:single\s+|private\s+)?room|"
    r"(?:room|bedroom)\s+in\s+(?:a\s+|an\s+)?(?:(?:\\d+|two|three|four)[-\\s]+bed(?:room)?[-\\s]+)?(?:shared\s+)?(?:apartment|house|home|flat)|"
    r"shared\s+(?:apartment|flat|house|housing|bedroom|bathroom|kitchen|living|space)|"
    r"roommates?\s+(?:wanted|needed|welcome)|looking\s+for\s+(?:a\s+)?roommate|"
    r"co[- ]?living|room\s?share|house\s?share|bed\s?space|per\s+bedroom|"
    r"individual\s+rooms?|by\s+the\s+room|master\s+bedroom)\b",
    re.IGNORECASE,
)
ROOM_UNIT = re.compile(
    r"^(?:\s*(?:room|rm|bedroom|bed\s?space)\s*[-#:]?\s*[a-z0-9]+(?:\b|$))",
    re.IGNORECASE,
)
ROOM_CLASS = re.compile(
    r"\b(?:private\s+room|shared\s+(?:housing|room|bedroom|unit)|"
    r"room\s?share|co[- ]?living|room\s+only|room\s+rental)\b",
    re.IGNORECASE,
)

def room_rental_reason(row):
    """Return a reason only for explicit room/share signals; otherwise None."""
    if not isinstance(row, dict):
        return "invalid record"
    # Unlike an unknown bathroom count (None), an explicit zero points away from
    # a self-contained studio or one-bedroom. This is a conservative exclusion.
    bathrooms = row.get("bathrooms")
    if bathrooms is not None and str(bathrooms).strip() in ("0", "0.0"):
        return "zero bathrooms reported"
    for field in ("unit", "addressLine2"):
        value = str(row.get(field) or "").strip()
        if ROOM_UNIT.search(value):
            return "address or unit is identified as a room"
    for field in ("unit_type", "unitType", "rental_type", "listingType", "propertyType",
                  "building_type", "source_type", "listing_type"):
        value = str(row.get(field) or "").strip()
        if value.lower() in ("room", "bedroom", "shared", "room share", "room rental", "co-living", "coliving") or ROOM_CLASS.search(value) or ROOM_UNIT.search(value):
            return "listing classified as room or shared accommodation"
    for field in ("title", "headline", "description", "address", "formattedAddress", "street"):
        if ROOM_SCOPE.search(str(row.get(field) or "")):
            return "room or shared-accommodation description"
    return None
