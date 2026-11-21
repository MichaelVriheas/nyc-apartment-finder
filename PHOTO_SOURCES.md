# Apartment photo sources and display permissions

## What we currently have

**FirstMover** monthly public data includes `lead_photo_id`, `photo_ids`, and `media_asset_count`. Our importer preserves up to 12 published photo identifiers and the asset count in `site/data/listings.json`. This is metadata only; it **does not** constitute a license to display Zillow/StreetEasy photos. Those original photos are **not** downloaded, proxied, embedded, or copied. When FirstMover indicates the listing had photographs, the website links to the **original listing** to view them there (if it is still accessible).

**RentCast** rental-listing API supplies rental details and statuses, but its published listing response schema does not offer unit photo URLs. Its cards continue using illustrations and an address-search link.

## Adding photographs with permission

The website reads `site/data/approved-photos.json` and can display a photo only when a record explicitly includes `usage_approved: true`, a full `https://` photo URL, a `scope` of either `unit` or `building`, and identifying source/permission details.

The file has an initial empty `photos` object. An example record (illustrative URLs only; do **not** paste directly as if it were licensed):

```json
{
  "photos": {
    "rentcast-listing-id-goes-here": {
      "image_url": "https://images.example.com/licensed-building-photo.jpg",
      "source_url": "https://property-manager.example.com/listings/unit-1",
      "credit": "Property manager name",
      "scope": "building",
      "license_note": "Written display permission dated YYYY-MM-DD for this site",
      "usage_approved": true
    }
  }
}
```

Use an exact listing identifier as the key. For `scope: "building"`, the card must say **Building photo — not a unit photo**. For `scope: "unit"`, verify the exact rental unit matches the listing. Check that redistribution or hotlinking is authorized, and that display rights cover a public GitHub Pages site. Store no private contact details or permission documents in this public repository.

If an approved image fails to load, the card falls back to its illustration. Actual photo files and URLs from Zillow/StreetEasy should not be copied merely because identifiers are present in FirstMover's data.

## Potential future sources

- Permission from individual leasing offices or property managers in Morningside Heights and the surrounding Manhattan neighborhoods, including official listing image feeds
- A properly licensed display feed with matching listing IDs, photos and explicit public display rights (possibly paid)
- Directly supplied owner/agent photos where authorization for this website has been documented

**Not a solution:** Free public visibility, direct hotlinks, a Zillow syndication **publisher upload** feed, or a property photo on a Google search result, none of which by themselves prove third-party display permission.

No RentCast API calls are needed for this photo manifest. The existing weekly RentCast and daily FirstMover schedule remain unchanged.
