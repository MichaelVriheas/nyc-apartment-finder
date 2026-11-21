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
assert.ok(rentcast.listings.length>0,"The saved RentCast snapshot must contain test fixtures");

async function loadPage(selectedIds = []) {
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
  const store=new Map([["nyc-apartment-comparison-v1",JSON.stringify(selectedIds)]]);
  const localStorage={
    getItem:k=>store.get(k)??null,
    setItem:(k,v)=>store.set(k,String(v))
  };
  const fetch=async path=>({
    ok:path==="./data/rentcast.json"||path==="./data/approved-photos.json",
    json:async ()=>path==="./data/rentcast.json"?rentcast:{"photos":{}}
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
  assert.equal(displayedCount,rentcast.listings.length,"All saved matching RentCast listings should be shown on fresh load");
  assert.ok(bySelector("#cards").children.length>0,"Listing cards should be rendered");
  if(selectedIds.length){
    assert.ok(bySelector("#compare-count").textContent.includes("of 3 selected"),"Comparison state must initialize on reload");
  }
}

(async()=>{
  await loadPage();
  await loadPage([String(rentcast.listings[0].id)]);
  console.log("Passed startup smoke tests: listings and comparison reinitialize on page reload.");
})().catch(err=>{console.error(err);process.exitCode=1;});
