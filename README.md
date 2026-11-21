# NYC Apartment Finder

A personal, self-updating apartment search dashboard for an **August 2027** move near Columbia University.

## Filters

- **Monthly base rent range:** $2,250–$3,000, inclusive (fees/utilities may be extra)
- **Apartment types:** Studio and one-bedroom
- **Manhattan:** Morningside Heights, Manhattan Valley, Manhattanville, Hamilton Heights, South Harlem, Northern Upper West Side, Central Harlem, and Washington Heights **only south of the George Washington Bridge**

## Live website

https://michaelvriheas.github.io/nyc-apartment-finder/

## Data sources — clearly distinguished on the website

1. **RentCast API:** Long-term rental listings with provider-reported `Active` status at the most recent API check. Searched with two smaller circular queries covering the target Manhattan NTAs **south of the GW Bridge approach**; duplicate listing IDs are merged. Areas use NYC DCP's [2020 Neighborhood Tabulation Areas](https://data.cityofnewyork.us/d/9nt8-h7nd), statistical polygons that **do not define neighborhoods definitively**. The Manhattan Valley/Northern UWS distinction is a documented custom approximation. Each query can still return at most 500 listings; the search is not exhaustive. RentCast does not guarantee currently available apartments or an original listing URL, so the site links to an address web search.
2. **[FirstMover Open Data](https://www.firstmovernyc.com/open-data):** Free historical monthly CSV snapshots, prices as initially advertised. These records **do not** confirm availability or latest rent.

The site defaults to the RentCast feed when it has matching records. Choose a source in the drop-down to see the monthly historical data separately, or combine both for research.

## Entire-unit preference — no roommate listings

**Goal:** a self-contained **studio or one-bedroom apartment**, not a private bedroom inside a shared apartment.

The RentCast importer and FirstMover importer reject clearly identified room rentals, co-living, and shared-accommodation listings based on available listing descriptions, explicit room-numbered units, classification fields and explicitly reported zero bathrooms. **A studio is kept** when the dataset reports `bedrooms: 0`; a studio is not the same as a rental bedroom within a shared apartment.

**Minimum rent safeguard:** Both importers and the dashboard enforce $2,250–$3,000 inclusive, and the RentCast API query requests only that interval. This can eliminate some low-cost room listings, but rent is not a substitute for confirming an independent unit. The max-rent control cannot be lowered below the minimum; either bound can be tightened within the overall range.

**Important limitation:** Neither feed guarantees that a record covers an entire independent dwelling or includes a private kitchen and bathroom. When a provider omits these details, the listing remains marked `unverified_entire_unit`, never `confirmed`. Verify both private facilities and exclusive rights to the unit before applying or paying anything. A bedroom marketed as a studio may still slip through if its source has no room-sharing indicators.

To keep the old snapshot from showing obviously shared rentals, the frontend also checks identifying room/coliving language. Historical first-posting records remain separate from RentCast's provider-checked listings.

For location comparison the cards also show the **straight-line distance** from the listed coordinates to Columbia's Morningside campus, plus a sort option. **Walking route** and **Transit route** links open Google Maps from each listing to Columbia's Broadway/116th Street entrance. Google Maps calculates live, route-specific travel times when opened; this website does not store those times or guarantee future (August 2027) service. Routing links use [free Maps URLs](https://developers.google.com/maps/documentation/urls/get-started), **not a billable Google Maps Directions API key**.

## Interactive map apartment previews

The apartment map supports a **hover preview** of each visible pin on desktop and **tap/click to keep the preview open** on touch, mobile and keyboard (pins support keyboard activation). The preview shows the **monthly advertised base rent, unit type, neighborhood, address**, and reported size/bathrooms when available. It makes status transparency explicit: **RentCast** means provider-reported active but unverified, and **FirstMover** means a historical advertisement, not current availability.

Each popup has a **View apartment card** button that scrolls to and highlights the corresponding listing on the page, plus an external link. For FirstMover this opens the **original listing** (which might be gone), while RentCast provides an accurately labeled **Search address** web search because its API response does not guarantee an original listing deep link. The popup remains open briefly when moving from the pin to the clickable links; touch/click keeps it open until dismissed or another marker is selected. The page's map and listings still obey all rent, source, geographic, and favorite filters. No new API calls or map subscriptions are required.

The GitHub Actions workflow runs `tests/check_map.cjs` in addition to first-load and JavaScript syntax checks, to prevent regressions affecting marker events, popup content, links or switching between historical and RentCast listings.

## Side-by-side apartment comparisons

Select **Compare +** on up to **three** listing cards. Once two listings are selected, use the bottom comparison dock's **Compare side by side** button to review their most recent stored data in a responsive table. Compare choices persist as listing IDs in the **same browser** using `localStorage`, independently of saved favorites. They continue working across source, neighborhood, and favorite filters; if a property disappears from the refreshed feeds, its comparison selection is removed rather than retaining outdated rental figures. Use the dock or modal's Remove controls to change a selection, or Clear to reset.

The comparison table includes monthly and annualized **advertised base rent** (annual is simply monthly × 12, not an all-in cost), reported floor area and base-rent-per-square-foot when available, bedrooms, bathrooms, approximate neighborhood, reported fee status, whether a self-contained unit has been independently verified (currently **not verified**), listing source and freshness, and **straight-line** Columbia distance. When there is complete comparable numerical data for a row, lowest values are highlighted. Missing fields are shown as **Not reported**, never guessed.

For real walking or subway routes, the table links out to Google Maps for current directions and travel times; it **does not estimate, store or compare future commute times** or make any additional API calls. RentCast statuses are provider-reported, and FirstMover entries are historical advertisements, so a side-by-side comparison does not prove current availability or lease terms.

## Market Insights (separate page)

Open [Market Insights](https://michaelvriheas.github.io/nyc-apartment-finder/market-insights.html) from the navigation bar beside **Marketplace**. This is a separate static page (`site/market-insights.html`); it does not clutter the apartment marketplace and it does not need an additional hosting service.

- **Snapshot overview:** number of sampled matching listings, median advertised base rent (when at least three observations exist), distinct comparable data checks, and latest check date
- **Neighborhood medians:** side-by-side comparisons across the eight selected Manhattan areas, with counts visible; medians for fewer than three sampled matches are deliberately withheld
- **Historical trend:** a chart of only **actual saved RentCast observations**, selectable by neighborhood and studio/one-bedroom type. A single baseline is shown as one point, not an invented monthly line. Observations collected using a different search method are **never connected** as though directly comparable
- **Data caveats:** the data covers only rentals already filtered to $2,250–$3,000, not all rental inventory; RentCast availability is provider-reported, API searches can be capped at 500 results each, and smaller neighborhood labels are approximate. FirstMover's historical initial advertisements are not included in these median series

`site/data/market-history.json` begins with the **actual November 21, 2026 saved snapshot** (60 qualifying RentCast records after geographic reclassification and the GW Bridge cutoff). This was a one-region, response-limited sample, so it remains distinct from the next two-region methodology. **Each successful future RentCast refresh adds a compact, dated aggregate record** via `scripts/rent_history.py`, and the workflow commits it together with `site/data/rentcast.json`. The November 21 observation was further re-filtered to the new GW Bridge cutoff (60 matching records rather than the previous 74), without a fresh provider request. There are no fabricated months, no extra RentCast API requests for analytics, and no paid chart libraries.

## Geographic search coverage and change-tracking reset

Previously a single 3.7-mile circular query reached the RentCast 500-result cap, and simple latitude/longitude rectangles incorrectly categorized Bronx addresses as South Harlem. The saved November 21, 2026 snapshot was **reclassified without making API requests**, reducing the stored RentCast records from 114 to 74 target-area matches, then to **60** after excluding **14** addresses north of the George Washington Bridge. These removals are geographic—not proof of rentals or unavailable units. The 60 records are **not a complete inventory**.

The new workflow uses a southern circle centered at (40.8000, -73.9635) with a 1.85-mile radius and a northern circle centered at (40.8310, -73.9450) with a 1.65-mile radius. RentCast measures `radius` in miles. These cover the relevant portions of the compact DCP NTA polygons in `site/data/manhattan-nta-areas.geojson` SOUTH of the cutoff; records are retained only if they land within those polygons and meet all other filters. A response with 500 listings gets an explicit cap flag in the published JSON, since even two smaller searches can truncate the data.

**Comparability:** Switching from a single large circle to two smaller circles changes which listings are sampled. The first successful run with the new methodology will establish a **new baseline** instead of treating removed or reclassified apartments as rented, missing or newly found. Subsequent successful weekly comparisons will show changes normally.

## George Washington Bridge northern boundary

The search stops at an **approximate sloped boundary along the GW Bridge's Manhattan approach**, near the West 178th–179th Street alignment. We use two mapped reference points: (40.848624, -73.937370) around Broadway at West 178th/179th and (40.849438, -73.939025) around Fort Washington Avenue at West 179th. These define an approximate street-grid cutoff rather than an authoritative surveyed bridge footprint. Apartments with coordinates **north** of that line are excluded; southern Washington Heights listings are still included.

The same rule lives in `scripts/areas.py` for both new RentCast and FirstMover imports, and independently in `site/index.html` as a safeguard against older cached data. The site also drops now-out-of-area comparison and favorite IDs in the same browser. `site/data/market-history.json` has been re-aggregated from the surviving **real November 21 provider snapshot**, with its original observation date retained; the count change is not a new check or a price trend. The next successful two-circle RentCast update starts a new methodology baseline so it does not count all changed-scope listings as newly discovered or rented. **No new RentCast requests** were needed for this adjustment.

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
- Weekly (Mondays, UTC): run **two targeted** RentCast listing queries, persist a deduplicated filtered JSON feed, then redeploy.
- Manual: use **Actions → Refresh data and publish site → Run workflow** for an extra RentCast refresh.

**Important:** The RentCast Developer plan includes 50 free API requests per month, after which overage charges may apply. To minimize the chance of charges, `scripts/fetch_rentcast.py` implements a conservative limit of **20 attempts within any rolling 31 days** (two reserved requests per weekly refresh), tracked in the committed `.rentcast-budget.json` file. The workflow commits the quota reservation **before** making requests; if that push fails, no API request is made. This counter tracks only calls made by this project's workflow. It cannot block calls made outside this repository, and it is **not a provider-side hard spending cap**. Check the RentCast billing dashboard for your actual usage and billing period.

The key is stored only in a GitHub Actions secret called `RENTCAST_API_KEY`. Never paste it in the repository, published JSON, or screenshots.

## Files

- `site/index.html`: searchable dashboard, map, source selector, local favorites and side-by-side comparison UI
- `site/market-insights.html`: standalone neighborhood market statistics and observed rent charts
- `site/data/market-history.json` and `scripts/rent_history.py`: compact genuine saved RentCast aggregate history
- `scripts/update_listings.py`: FirstMover monthly historical-data importer
- `scripts/areas.py` and `site/data/manhattan-nta-areas.geojson`: NTA polygon matching and source geometry (NYC DCP)
- `scripts/fetch_rentcast.py`: RentCast API importer, filtering and budget reservation
- `.github/workflows/publish.yml`: daily site deployment and weekly RentCast checks
- `site/data/rentcast.json`: last filtered RentCast response published to the public repo
- `.rentcast-budget.json`: rolling API request reservation ledger

Favorites stay in the browser's local storage, not across devices. Apartment prices and statuses can change; verify all details with the listing provider before applying.
