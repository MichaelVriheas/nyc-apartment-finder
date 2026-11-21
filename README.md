# NYC Apartment Finder

Free personal apartment research dashboard for a planned **August 2027** move near Columbia University.

## Search preferences

- Advertised monthly base rent **$3,000 maximum**
- **Studio and one-bedroom** apartments
- Manhattan: **Morningside Heights, Manhattan Valley, Manhattanville, Hamilton Heights, South Harlem, Northern Upper West Side, Central Harlem, Washington Heights**
- New Jersey: **Fort Lee**

## Launch the website

1. Open **Settings → Pages** in this GitHub repository.
2. Select **GitHub Actions** under **Build and deployment → Source**.
3. Visit **Actions → Refresh data and publish site → Run workflow**. You might need to enable workflows in the Actions tab first.
4. Once deployment succeeds, visit **https://michaelvriheas.github.io/nyc-apartment-finder/**.

If a run fails, inspect its job logs under **Actions**. For a private repo, GitHub Pages availability may depend on plan; this repo is currently public.

## What is implemented

- Responsive apartment listing cards
- Neighborhood / base-rent / studio-vs-one-bedroom / advertised no-fee filters
- Map markers using OpenStreetMap and Leaflet
- Browser-local favorites
- Link to original listing
- Python importer that reads the newest **monthly** public FirstMover CSV and filters for your criteria
- GitHub Actions workflow checking daily for newly posted CSV files and redeploying the site

### Important limitation: not a live inventory

The first feed comes from [FirstMover Open Data](https://www.firstmovernyc.com/open-data), published as **monthly historical rental snapshots** under CC0. Records reflect what was advertised at initial posting. Current price, status and move-in availability **are not confirmed**. The daily schedule checks for updated *monthly* files; it does not magically make the dataset live.

The published dataset primarily covers NYC. Fort Lee is configured as a search area, but source coverage may be limited or zero until an authorized free NJ source is added.

There is no paid API, unauthorized web scraping, or hidden key in this prototype. In the future, we can add additional sources only after confirming their licensing and access terms. This site is a research tool, not an indication that any displayed apartment can be booked.

## Project structure

- `site/index.html`: dashboard
- `scripts/update_listings.py`: public data importer
- `.github/workflows/publish.yml`: scheduled GitHub Pages publisher
- `site/data/listings.json`: generated during the workflow run (not necessarily present on the repository branch)

The website uses the published snapshot as a static JSON file. Favorites stay in the current browser rather than being synchronized.
