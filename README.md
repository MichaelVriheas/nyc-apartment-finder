# NYC Apartment Finder

A personal, self-updating apartment search dashboard for an **August 2027** move near Columbia University.

## Filters

- **Monthly base rent range:** $2,250–$3,000, inclusive (fees/utilities may be extra)
- **Apartment types:** Studio and one-bedroom
- **Manhattan:** Morningside Heights, Manhattan Valley, Manhattanville, Hamilton Heights, South Harlem, Northern Upper West Side, Central Harlem, Washington Heights

## Live website

https://michaelvriheas.github.io/nyc-apartment-finder/

## Data sources — clearly distinguished on the website

1. **RentCast API:** Long-term rental listings with provider-reported `Active` status at the most recent API check. Searched using one geographic query centered on Upper Manhattan. Neighborhood assignments for Manhattan are **approximate** coordinate ranges, not official boundaries. The 500-listing upper-Manhattan API page limit can exclude listings; this is not an exhaustive search. RentCast does not guarantee currently available apartments or an original listing URL, so the site links to an address web search.
2. **[FirstMover Open Data](https://www.firstmovernyc.com/open-data):** Free historical monthly CSV snapshots, prices as initially advertised. These records **do not** confirm availability or latest rent.

The site defaults to the RentCast feed when it has matching records. Choose a source in the drop-down to see the monthly historical data separately, or combine both for research.

## Entire-unit preference — no roommate listings

**Goal:** a self-contained **studio or one-bedroom apartment**, not a private bedroom inside a shared apartment.

The RentCast importer and FirstMover importer reject clearly identified room rentals, co-living, and shared-accommodation listings based on available listing descriptions, explicit room-numbered units, classification fields and explicitly reported zero bathrooms. **A studio is kept** when the dataset reports `bedrooms: 0`; a studio is not the same as a rental bedroom within a shared apartment.

**Minimum rent safeguard:** Both importers and the dashboard enforce $2,250–$3,000 inclusive, and the RentCast API query requests only that interval. This can eliminate some low-cost room listings, but rent is not a substitute for confirming an independent unit. The max-rent control cannot be lowered below the minimum; either bound can be tightened within the overall range.

**Important limitation:** Neither feed guarantees that a record covers an entire independent dwelling or includes a private kitchen and bathroom. When a provider omits these details, the listing remains marked `unverified_entire_unit`, never `confirmed`. Verify both private facilities and exclusive rights to the unit before applying or paying anything. A bedroom marketed as a studio may still slip through if its source has no room-sharing indicators.

To keep the old snapshot from showing obviously shared rentals, the frontend also checks identifying room/coliving language. Historical first-posting records remain separate from RentCast's provider-checked listings.

For location comparison the cards also show the **straight-line distance** from the listed coordinates to Columbia's Morningside campus, plus a sort option. This is **not** an estimate of walking distance, travel time, subway service, or transit accessibility. Manhattan neighborhood classifications remain approximate.

## Weekly listing changes

The website tracks two kinds of differences between successive **RentCast** snapshots:
- **Newly seen:** a rental ID appeared in the latest sampled search but was absent from the preceding saved sample; it may have been listed earlier and missed by the API search limit.
- **Price drop:** the same rental ID appears in both samples and has a lower advertised base rent than in the prior check.
- **Price increase:** also recorded, but not currently a separate dashboard filter.
- **Not found in latest sample:** counted separately, never described as rented or unavailable. The geographic query can return only the first 500 matches, so listings can disappear from the sample without their status changing.

The first imported snapshot is a baseline and displays no false "new" or "price drop" badges. Comparison cards appear after the **next successful scheduled RentCast run**. FirstMover's initial-posting historical records are not used to infer weekly price changes. The UI lets you filter by *All results*, *Newly seen*, and *Price drops*. Counts describe the full sampled RentCast search; filtered views might show fewer.

Unit tests run offline on each deployment using mocked API responses. They do not use free-tier RentCast calls.

## Automation and API usage safeguards

GitHub Actions workflows:
- Daily: fetch the newest publicly released monthly FirstMover file and redeploy the website.
- Weekly (Mondays, UTC): run **one** RentCast listing query, persist a small filtered JSON feed, then redeploy.
- Manual: use **Actions → Refresh data and publish site → Run workflow** for an extra RentCast refresh.

**Important:** The RentCast Developer plan includes 50 free API requests per month, after which overage charges may apply. To minimize the chance of charges, `scripts/fetch_rentcast.py` implements a conservative limit of **20 attempts within any rolling 31 days**, tracked in the committed `.rentcast-budget.json` file. The workflow commits the quota reservation **before** making requests; if that push fails, no API request is made. This counter tracks only calls made by this project's workflow. It cannot block calls made outside this repository, and it is **not a provider-side hard spending cap**. Check the RentCast billing dashboard for your actual usage and billing period.

The key is stored only in a GitHub Actions secret called `RENTCAST_API_KEY`. Never paste it in the repository, published JSON, or screenshots.

## Files

- `site/index.html`: searchable dashboard, map, source selector and local favorites
- `scripts/update_listings.py`: FirstMover monthly historical-data importer
- `scripts/fetch_rentcast.py`: RentCast API importer, filtering and budget reservation
- `.github/workflows/publish.yml`: daily site deployment and weekly RentCast checks
- `site/data/rentcast.json`: last filtered RentCast response published to the public repo
- `.rentcast-budget.json`: rolling API request reservation ledger

Favorites stay in the browser's local storage, not across devices. Apartment prices and statuses can change; verify all details with the listing provider before applying.
