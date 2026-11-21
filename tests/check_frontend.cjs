// Zero-network syntax and UI guard checks. Runs on GitHub Actions Node.js.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const html = fs.readFileSync("site/index.html", "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1].trim()).filter(Boolean);

assert.ok(scripts.length, "Homepage must have executable inline JS");
for (const script of scripts) new vm.Script(script, { filename: "site/index.html" });
for (const phrase of ["const roomRental", "return !roomRental(x)", "campusDistance", "private-unit status",
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
assert.ok(!html.includes("Fort Lee"), "Removed search area must not appear");
console.log("Passed JS syntax and room-rental UI guard checks.");
