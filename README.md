# NYC Apartment Finder

A personal, self-updating apartment search dashboard for an **August 2027** move near Columbia University.

## Filters

- **Maximum base monthly rent:** $3,000 (fees/utilities may be extra)
- **Apartment types:** Studio and one-bedroom
- **Manhattan:** Morningside Heights, Manhattan Valley, Manhattanville, Hamilton Heights, South Harlem, Northern Upper West Side, Central Harlem, Washington Heights

## Live website

https://michaelvriheas.github.io/nyc-apartment-finder/

## Data sources — clearly distinguished on the website

1. **RentCast API:** Long-term rental listings with provider-reported `Active` status at the most recent API check. Searched using one geographic query centered on Upper Manhattan. Neighborhood assignments for Manhattan are **approximate** coordinate ranges, not official boundaries. The 500-listing upper-Manhattan API page limit can exclude listings; this is not an exhaustive search. RentCast does not guarantee currently available apartments or an original listing URL, so the site links to an address web search.
2. **[FirstMover Open Data](https://www.firstmovernyc.com/open-data):** Free historical monthly CSV snapshots, prices as initially advertised. These records **do not** confirm availability or latest rent.

The site defaults to the RentCast feed when it has matching records. Choose a source in the drop-down to see the monthly historical data separately, or combine both for research.

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
