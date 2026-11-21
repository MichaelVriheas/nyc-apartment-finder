// Zero-network syntax and UI guard checks. Runs on GitHub Actions Node.js.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const html = fs.readFileSync("site/index.html", "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1].trim()).filter(Boolean);

assert.ok(scripts.length, "Homepage must have executable inline JS");
for (const script of scripts) new vm.Script(script, { filename: "site/index.html" });
for (const phrase of ["const roomRental", "return southOfGWBridge(x)&&!roomRental(x)", "campusDistance", "private-unit status",
                      "Straight-line"]) {
  // Case insensitive because human-facing descriptions can vary in capitalization.
  assert.ok(html.toLowerCase().includes(phrase.toLowerCase()), "Missing UI safeguard: " + phrase);
}
assert.ok(html.includes('id="minRent"'), "Minimum rent control missing");
assert.ok(html.includes('value="2250"'), "Minimum rent should default to $2,250");
assert.ok(html.includes('Number(x.rent)>=minimum'), "Minimum rent must be applied to visible listings");
assert.ok(html.includes('$("#minRent").value="2250"'), "Reset should restore minimum rent");
assert.ok(html.includes("Walking route ↗"), "Walking directions must be available");
assert.ok(html.includes("Transit route ↗"), "Transit directions must be available");
assert.ok(html.includes("travelmode:mode"), "Walking/transit URLs must specify travel mode");
assert.ok(html.includes("RentCast sample capped"), "API result truncation must be visible");
// Compare selectors and functionality are self-contained in the static site.
for(const key of ['id="compare-dock"','id="compare-open"','id="compare-dialog"',
                  'id="compare-table-host"','class="compare-tip"','compareStorageKey',
                  "function toggleCompare(id)", "function renderCompareTable()",
                  "compareIds.length>=3", 'selected.length<2',
                  'aria-pressed', 'compareIds=validCompare',
                  'Base rent / month', 'Annualized base rent', 'Floor area',
                  'Base rent per sq ft / mo', 'Columbia straight-line distance',
                  'Walking to Columbia', 'Transit to Columbia', 'Entire private unit',
                  'Not independently verified', 'FirstMover · historical advertisement']){
  assert.ok(html.includes(key),"Comparison missing: "+key);
}
assert.ok(html.includes('localStorage.setItem(compareStorageKey'),"Comparison picks must persist locally");
assert.ok(html.includes('typeof dialog.showModal==="function"'),"Comparison modal must support keyboard-aware native dialog");
// Market Insights lives on its own site route; validate JS without network or browser.
const insights = fs.readFileSync("site/market-insights.html", "utf8");
const insightsScripts = [...insights.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m=>m[1].trim()).filter(Boolean);
assert.ok(insightsScripts.length===1,"Market Insights must have one static browser script");
for(const script of insightsScripts)new vm.Script(script,{filename:"site/market-insights.html"});
for(const key of ['id="area-filter"','id="bed-filter"','id="trend-chart"',
                  'id="neighborhood-bars"','market-history.json',
                  "sameMethod=snapshots.filter", 'source response capped',
                  'median withheld','studio','one_bed',
                  'FirstMover','historical initial advertisements']){
  assert.ok(insights.includes(key),"Market Insights missing: "+key);
}
assert.ok(html.includes('href="./market-insights.html"'),"Marketplace needs a Market Insights navigation link");
assert.ok(insights.includes('href="./index.html"'),"Market Insights needs a marketplace return link");
const history=JSON.parse(fs.readFileSync("site/data/market-history.json","utf8"));
assert.equal(history.schema_version,1,"Unexpected market-history version");
assert.equal(history.rent_min,2250);assert.equal(history.rent_max,3000);
assert.ok(history.snapshots.length>=1,"At least one genuine history snapshot required");
for(const record of history.snapshots){
  const all=record.overall?.all;
  assert.ok(all && Number.isInteger(all.count),"Each observation must have a sampled count");
  assert.ok(all.median==null || (all.median>=2250&&all.median<=3000),"Observed median must fit the advertised price band");
  assert.equal(Object.keys(record.neighborhoods||{}).length,8,"Each observation needs the 8 areas");
}
// Geographic policy must be reflected in both pages and all published RentCast data.
assert.ok(html.includes("const southOfGWBridge=x=>"),"Marketplace needs GW Bridge coordinate cutoff");
assert.ok(html.includes("historical=Array.isArray(h?.listings)?h.listings.filter(southOfGWBridge)"),"Historical cards must honor cutoff");
assert.ok(html.includes("rentcast=Array.isArray(r?.listings)?r.listings.filter(southOfGWBridge)"),"RentCast cards must honor cutoff");
assert.ok(insights.includes("<span>South of GW Bridge</span>"),"Market Insights must show the new scope");
const current=JSON.parse(fs.readFileSync("site/data/rentcast.json","utf8"));
const line=lon=>40.848624+(lon+73.937370)*((40.849438-40.848624)/(-73.939025+73.937370));
assert.equal(current.geographic_policy,"south-of-george-washington-bridge-approach-v1");
for(const x of current.listings||[]){
  assert.ok(Number(x.latitude)<=line(Number(x.longitude))+1e-10, "Stored listing north of GW Bridge: "+x.id);
}
const lastSaved=history.snapshots.find(p=>p.checked_at_utc===current.checked_at_utc);
assert.ok(lastSaved,"Current stored check must have a real Market Insights observation");
assert.equal(lastSaved.total_count,current.listings.length,"Market Insights count must match the saved listing sample");
assert.equal(lastSaved.geographic_policy,current.geographic_policy,"Market Insights must enforce same geography");

// Deliberately omit the former unsupported amenities filter and laundry checks.
for(const removed of ['id="laundry"','laundryStorageKey','laundryStatus(x)',
                      'approved-amenities.json','I checked: both in unit']){
  assert.ok(!html.includes(removed),"Removed laundry UI must stay absent: "+removed);
}
// Map popups should support hover, keyboard/tap selection and working source links.
for(const key of ['function buildMapPreview(x)','function focusListingFromMap(id)',
  'marker.on("mouseover"','marker.on("mouseout"','marker.on("click"',
  'marker.on("popupopen"','marker.on("popupclose"',
  'map-listing-popup','map-preview-actions','map-preview-link',
  'View apartment card','Original listing ↗','Search address ↗',
  'x.source_kind==="historical"?"Original listing ↗":"Search address ↗"',
  'marker.getPopup()?.getElement()','cancelMapPreviewClose()',
  'card.dataset.listingId=String(x.id)','keyboard:true',
  'Hover over a pin for apartment details']){
  assert.ok(html.includes(key),"Interactive map feature missing: "+key);
}
// Broker fee is informational, not a filtering criterion. Keep any fee
// labels on cards and comparisons, but no broker-fee selection control.
for(const removed of ['id="noFee"','for="noFee"','$("#noFee")','fee-field','fee-check']){
  assert.ok(!html.includes(removed),"Broker fee search control must be absent: "+removed);
}
assert.ok(html.includes('const feeReported=x=>'),"Source-reported fee information should remain available");
assert.ok(html.includes('✓ No fee reported'),"Retain informational no-fee listing badges");
assert.ok(html.includes('{label:"Broker fee"'),"Retain fee information in the comparison table");
assert.ok(html.includes('for(const id of ["source","area","beds","sort"])'),
  "The other search controls must still trigger rendering");
assert.ok(html.includes('$("#sort").value="new"'),
  "Reset should still restore the default sort");
assert.ok(html.includes('function buildMapPreview(x)')&&html.includes('function refreshPins(list)'),
  "Interactive map must remain intact");
assert.ok(!html.includes("Fort Lee"), "Removed search area must not appear");
console.log("Passed JS syntax and room-rental UI guard checks.");
