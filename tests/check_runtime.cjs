// Headless first-load smoke test. Uses only built-in Node modules: no browser,
// network, RentCast calls, paid providers, or third-party dependencies.
// Catches runtime initialization errors that JS syntax checks cannot detect.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const html = fs.readFileSync("site/index.html", "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1].trim()).filter(Boolean);
assert.equal(scripts.length,1,"Expected exactly one inline application script");
const rentcast = JSON.parse(fs.readFileSync("site/data/rentcast.json","utf8"));
const manual = JSON.parse(fs.readFileSync("site/data/manual.json","utf8"));
const expectedTotal=rentcast.listings.length+manual.listings.length;
assert.ok(rentcast.listings.length>0,"The saved RentCast snapshot must contain test fixtures");

async function loadPage(selectedIds = [], hiddenIds = []) {
  const elements=new Map(),allElements=[],errors=[];
  class Node {
    constructor(tag="div") {
      this.tag=tag;this.children=[];this.dataset={};this.attributes={};
      this.style={};this.className="";this.textContent="";this.value="";
      this.disabled=false;this.hidden=false;this.checked=false;this.open=false;
      this.events={};
      const classes=new Set();
      this.classList={
        add:(...tokens)=>tokens.forEach(k=>classes.add(k)),
        remove:(...tokens)=>tokens.forEach(k=>classes.delete(k)),
        toggle:(token,force)=>{
          if(force===true)classes.add(token);
          else if(force===false)classes.delete(token);
          else if(classes.has(token))classes.delete(token);
          else classes.add(token);
          return classes.has(token);
        },
        contains:token=>classes.has(token)
      };
      allElements.push(this);
    }
    append(...children){this.children.push(...children);}
    appendChild(child){this.append(child);return child;}
    replaceChildren(...children){this.children=[...children];}
    setAttribute(k,v){this.attributes[k]=String(v);}
    getAttribute(k){return this.attributes[k]??null;}
    addEventListener(ev,fn){(this.events[ev]??=[]).push(fn);}
    closest(selector){return null;}
    remove(){}
    querySelector(selector){return null;}
    scrollIntoView(){}
  }
  function bySelector(selector){
    assert.ok(selector.startsWith("#"),"Unexpected querySelector: "+selector);
    const id=selector.slice(1);
    if(!elements.has(id)){
      const el=new Node("div");
      if(id==="source")el.value="rentcast";
      if(id==="beds")el.value="all";
      if(id==="area")el.value="";
      if(id==="sort")el.value="new";
      if(id==="minRent")el.value="2250";
      if(id==="rent")el.value="3000";
      if(id==="compare-dialog")el.open=false;
      elements.set(id,el);
    }
    return elements.get(id);
  }
  const document={
    body:new Node("body"),
    querySelector:bySelector,
    querySelectorAll:selector=>selector===".compare-toggle"?
      allElements.filter(x=>String(x.className).split(/\s+/).includes("compare-toggle")):[],
    createElement:tag=>new Node(tag),
    createElementNS:(ns,tag)=>new Node(tag),
    createDocumentFragment:()=>new Node("fragment")
  };
  const store=new Map([["nyc-apartment-comparison-v1",JSON.stringify(selectedIds)],["nyc-apartment-hidden-v1",JSON.stringify(hiddenIds)]]);
  const localStorage={
    getItem:k=>store.get(k)??null,
    setItem:(k,v)=>store.set(k,String(v))
  };
  const fetch=async path=>({
    ok:path==="./data/rentcast.json"||path==="./data/manual.json"||path==="./data/approved-photos.json",
    json:async ()=>path==="./data/rentcast.json"?rentcast:path==="./data/manual.json"?manual:{"photos":{}}
  });
  const logger={
    log:()=>{},warn:()=>{},
    error:(...args)=>errors.push(args.map(String).join(" "))
  };
  const sandbox={document,fetch,localStorage,URL,URLSearchParams,
    setTimeout,console:logger};
  vm.runInNewContext(scripts[0],sandbox,{filename:"site/index.html",timeout:5000});
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(errors.length,0,"The application failed while loading: "+errors.join(" | "));
  const count=bySelector("#count").textContent;
  assert.match(count,/^\d+ matching listings?/, "First page load must display a real count; got "+count);
  const displayedCount=Number(count.match(/^\d+/)[0]);
  assert.equal(displayedCount,expectedTotal-hiddenIds.length,"The default marketplace must include manual picks and exclude hidden listings");
  assert.equal(bySelector("#hidden-total").textContent,"("+hiddenIds.length+")","Hidden tab count should reflect matching hidden listings");
  assert.ok(bySelector("#cards").children.length>0,"Listing cards should be rendered");
  if(selectedIds.length){
    assert.ok(bySelector("#compare-count").textContent.includes("of 3 selected"),"Comparison state must initialize on reload");
  }
  return {elements,store,document,allElements};
}
function descendants(node){
  return [node,...(node.children||[]).flatMap(descendants)];
}

(async()=>{
  await loadPage();
  assert.equal(manual.listings.length,1,"Expected one personally selected apartment");
  // A manual unit must still be visible even if RentCast is the default source.
  const onlyManual=await loadPage();
  onlyManual.elements.get("source").value="manual";
  onlyManual.elements.get("source").events.change[0]();
  assert.equal(onlyManual.elements.get("count").textContent,"1 matching listing",
    "My picks only must display the separately saved listing without RentCast");
  assert.equal(onlyManual.elements.get("cards").children[0].children.find(x=>x.className==="listing-card")?.dataset.listingId,
    manual.listings[0].id,"The visible card should have the permanent manual ID");
  await loadPage([String(rentcast.listings[0].id)]);
  const firstId=String(rentcast.listings[0].id);
  await loadPage([], [firstId]); // A hidden apartment remains hidden after a reload.
  const state=await loadPage([firstId]);
  const firstCard=state.elements.get("cards").children[0].children.find(n=>n.className==="listing-card");
  assert.ok(firstCard,"Expected first visible apartment card");
  const hide=descendants(firstCard).find(n=>n.className.split(/\s+/).includes("hide-listing-btn"));
  assert.ok(hide?.events.click?.[0],"Each listing needs a working Hide apartment control");
  const hiddenId=firstCard.dataset.listingId;
  hide.events.click[0]();
  assert.ok(JSON.parse(state.store.get("nyc-apartment-hidden-v1")).includes(hiddenId),"Hiding a listing must persist");
  assert.equal(state.elements.get("count").textContent,(expectedTotal-1)+" matching listings","Hiding should narrow visible marketplace results");
  assert.equal(state.elements.get("hidden-total").textContent,"(1)","Hidden count should increase");
  state.elements.get("hidden-listings").events.click[0]();
  assert.equal(state.elements.get("count").textContent,"1 hidden apartment","Hidden view should allow a user to find the excluded apartment");
  const hiddenCard=state.elements.get("cards").children[0].children.find(n=>n.className==="listing-card");
  const restore=descendants(hiddenCard).find(n=>n.className.split(/\s+/).includes("hide-listing-btn"));
  assert.ok(restore?.textContent.includes("Restore"),"Hidden apartments need a Restore action");
  restore.events.click[0]();
  assert.equal(JSON.parse(state.store.get("nyc-apartment-hidden-v1")).length,0,"Restoring should clear the personal exclusion");
  state.elements.get("all").events.click[0]();
  assert.equal(state.elements.get("count").textContent,expectedTotal+" matching listings","Restored apartment should return to marketplace");
  console.log("Passed startup smoke tests: listing refresh, saved comparisons, hide/restore and reload persistence.");
})().catch(err=>{console.error(err);process.exitCode=1;});
