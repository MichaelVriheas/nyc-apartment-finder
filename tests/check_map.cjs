// Offline dynamic map interaction regression test (Leaflet and DOM are mocked).
// Verifies map hover/touch/click behavior and external link semantics without
// browsers, network access, paid APIs or third-party packages.
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const html=fs.readFileSync("site/index.html","utf8");
const script=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(m=>m[1].trim()).find(Boolean);
assert.ok(script,"Inline map script not found");
const rentcast=JSON.parse(fs.readFileSync("site/data/rentcast.json","utf8"));
const manual=JSON.parse(fs.readFileSync("site/data/manual.json","utf8"));
assert.ok(manual.listings.length>0,"Manual My Picks must contain a saved apartment");
// The map shows the default "Newest advertised" sort, not JSON file order.
const example=[...rentcast.listings].sort((a,b)=>String(b.listed_at||b.last_seen||"").localeCompare(String(a.listed_at||a.last_seen||"")))[0];
assert.ok(example?.url?.startsWith("https:"),"Expected a saved RentCast listing URL");
const historical={
  id:"historical-test-unit",source_kind:"historical",
  latitude:40.810,longitude:-73.960,area:"Morningside Heights",
  bedrooms:1,bathrooms:1,rent:2550,address:"Example Historic Building",unit:"5A",
  sqft:550,listed_at:"2026-11-01",no_fee_at_posting:"",
  url:"https://streeteasy.com/building/example-historic-building/5a"
};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function test(){
  const ids=new Map(),allNodes=[],errors=[],markerList=[];
  let cardScrolled=false;
  class Node {
    constructor(tag="div"){
      this.tag=tag;this.children=[];this.className="";this.dataset={};this.style={};
      this.textContent="";this.value="";this.attributes={};this.events={};
      this.checked=false;this.hidden=false;this.open=false;this.disabled=false;
      const states=new Set();
      this.classList={
        add:(...tokens)=>tokens.forEach(x=>states.add(x)),
        remove:(...tokens)=>tokens.forEach(x=>states.delete(x)),
        toggle:(token,force)=>{
          if(force===true)states.add(token);
          else if(force===false)states.delete(token);
          else if(states.has(token))states.delete(token);
          else states.add(token);
          return states.has(token);
        },
        contains:x=>states.has(x)
      };
      allNodes.push(this);
    }
    append(...nodes){this.children.push(...nodes);}
    appendChild(node){this.append(node);return node;}
    replaceChildren(...nodes){this.children=[...nodes];}
    setAttribute(key,value){this.attributes[key]=String(value);}
    getAttribute(key){return this.attributes[key]??null;}
    addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
    querySelector(){return null;}
    querySelectorAll(selector){
      const results=[],queryClass=selector.startsWith(".")?selector.slice(1):null;
      function find(node){
        if(!node||typeof node!=="object")return;
        if(queryClass&&String(node.className).split(/\s+/).includes(queryClass))results.push(node);
        for(const child of node.children||[])find(child);
      }
      find(this);return results;
    }
    contains(node){
      if(node===this)return true;
      return this.children.some(c=>c?.contains?.(node));
    }
    closest(){return null;}
    scrollIntoView(){cardScrolled=true;}
    remove(){}
    get outerHTML(){return '<div class="'+this.className+'"></div>';}
  }
  function get(selector){
    if(!selector.startsWith("#"))throw Error("Unexpected selector: "+selector);
    const id=selector.slice(1);
    if(!ids.has(id)){
      const el=new Node();
      if(id==="source")el.value="rentcast";
      if(id==="beds")el.value="all";
      if(id==="sort")el.value="new";
      if(id==="minRent")el.value="2250";
      if(id==="rent")el.value="3000";
      if(id==="area")el.value="";
      ids.set(id,el);
    }
    return ids.get(id);
  }
  const document={
    body:new Node("body"),
    querySelector:get,
    querySelectorAll:selector=>selector===".compare-toggle"?
      allNodes.filter(n=>String(n.className).split(/\s+/).includes("compare-toggle")):[],
    createElement:tag=>new Node(tag),
    createElementNS:(ns,tag)=>new Node(tag),
    createDocumentFragment:()=>new Node("fragment")
  };
  const fakeMap={
    setView(){return this;},fitBounds(){return this;},getZoom(){return 13;},
    invalidateSize(){return this;}
  };
  const fakeLayers={
    addTo(){return this;},
    clearLayers(){markerList.length=0;}
  };
  const L={
    map:()=>fakeMap,
    layerGroup:()=>fakeLayers,
    tileLayer:()=>({addTo(){return this;}}),
    circleMarker:()=>({addTo(){return this;},bindPopup(){return this;}}),
    divIcon:config=>config,
    latLngBounds:()=>({pad(){return this;}}),
    marker:(coords,options)=>{
      const handlers={},el=new Node("div");
      let isOpen=false,popup=null;
      const pin={
        coords,options,handlers,
        bindPopup(content,settings){
          popup={content,settings,getElement:()=>el};
          return this;
        },
        getPopup:()=>popup,
        on(name,fn){handlers[name]=fn;return this;},
        addTo(){markerList.push(this);return this;},
        openPopup(){isOpen=true;handlers.popupopen?.();return this;},
        closePopup(){isOpen=false;handlers.popupclose?.();return this;},
        isPopupOpen:()=>isOpen,
        getLatLng:()=>({lat:coords[0],lng:coords[1]})
      };
      return pin;
    }
  };
  const localStorage={getItem:()=>null,setItem:()=>{}};
  const fetch=async path=>({
    ok:true,
    json:async()=>path.endsWith("rentcast.json")?rentcast:
      path.endsWith("listings.json")?{listings:[historical],data_month:"2026-11"}:
      path.endsWith("manual.json")?manual:{photos:{}}
  });
  const sandbox={document,L,localStorage,fetch,URL,URLSearchParams,setTimeout,clearTimeout,
    window:{matchMedia:()=>({matches:false})},console:{log(){},warn(){},
      error(...args){errors.push(args.join(" "));}}};
  vm.runInNewContext(script,sandbox,{filename:"site/index.html",timeout:5000});
  await delay(30);
  assert.equal(errors.length,0,"Map first load failed: "+errors.join("; "));
  assert.equal(markerList.length,rentcast.listings.length+manual.listings.length,
    "Default map should show both RentCast and My Picks");
  const descendants=(node)=>[node,...node.children.flatMap(descendants)];
  const marker=markerList.find(pin=>descendants(pin.getPopup().content).some(n=>n.textContent===example.address));
  assert.ok(marker,"Newest RentCast listing must have a map marker");
  assert.ok(marker.handlers.mouseover&&marker.handlers.mouseout&&marker.handlers.click,
    "Markers need hover and click handlers");
  assert.equal(marker.options.keyboard,true,"Map pins must support keyboard activation");
  assert.equal(marker.getPopup().settings.className,"map-listing-popup");
  marker.handlers.mouseover();
  assert.equal(marker.isPopupOpen(),true,"Hover must open the apartment preview");
  const content=marker.getPopup().content;
  const displayed=descendants(content).map(n=>n.textContent).join(" ");
  assert.ok(displayed.includes(example.address),"Popup needs apartment address");
  assert.ok(displayed.includes("$"+example.rent.toLocaleString()),"Popup needs monthly asking rent");
  assert.ok(displayed.includes("provider-reported active"),"RentCast must be marked unverified");
  const link=descendants(content).find(n=>n.tag==="a");
  assert.ok(link?.href===example.url,"RentCast pin must link to its saved address search");
  assert.equal(link.textContent,"Search address ↗","Don't falsely call a RentCast address search the original listing");
  assert.equal(link.target,"_blank");
  assert.equal(link.rel,"noopener noreferrer");
  const jump=descendants(content).find(n=>n.tag==="button");
  assert.ok(jump?.events.click?.length,"Map popup must link to the listing card");
  jump.events.click[0]();
  assert.ok(cardScrolled,"Clicking View apartment card should scroll to a card");

  // Moving the mouse from a small marker into its popup must not close it.
  marker.handlers.mouseout();
  marker.getPopup().getElement().events.mouseenter[0]();
  await delay(400);
  assert.equal(marker.isPopupOpen(),true,"Popup should remain open while cursor is over its links");
  marker.getPopup().getElement().events.mouseleave[0]();
  await delay(400);
  assert.equal(marker.isPopupOpen(),false,"Unpinned hover preview should close on pointer exit");
  marker.handlers.click();
  marker.handlers.mouseout();
  await delay(400);
  assert.equal(marker.isPopupOpen(),true,"Click/tap must keep the popup open");
  marker.closePopup();

  // Manual My Picks must have its own pin with direct original listing link.
  get("#source").value="manual";
  get("#source").events.change[0]();
  assert.equal(markerList.length,manual.listings.length,"My Picks source must show only manually selected apartments");
  const userPin=markerList[0];
  userPin.handlers.mouseover();
  const manualContent=descendants(userPin.getPopup().content);
  const userLink=manualContent.find(n=>n.tag==="a");
  assert.equal(userLink?.href,manual.listings[0].url,"Manually selected pin must link back to user's StreetEasy URL");
  assert.equal(userLink.textContent,"Original listing ↗","Manual listing must not be called address search");
  const status=manualContent.map(n=>n.textContent).join(" ");
  assert.ok(status.includes("availability unverified"),"Manual listing must never claim verified availability");
  assert.ok(status.includes("December 23, 2026"),"Manual popup should show advertised availability date");
  assert.ok(userPin.options.icon.options.html.includes("manual"),"Manual listings must use distinctive pin styling");

  // FirstMover is historical and has a real source listing URL, not an address lookup.
  get("#source").value="historical";
  get("#source").events.change[0]();
  assert.equal(markerList.length,1,"Historical map filter should show its own pin");
  const oldPin=markerList[0];
  oldPin.handlers.mouseover();
  const oldContent=descendants(oldPin.getPopup().content);
  const oldLink=oldContent.find(n=>n.tag==="a");
  assert.equal(oldLink?.textContent,"Original listing ↗");
  assert.equal(oldLink.href,historical.url,"Historical popup should use source listing URL");
  assert.ok(oldContent.map(n=>n.textContent).join(" ").includes("historical advertisement"),
    "Historical listing must not be presented as currently available");
  assert.ok(html.includes("Hover over a pin for apartment details"));
  console.log("Passed map hover previews, interactive links, click/tap persistence, and historical/RentCast distinction.");
}
test().catch(e=>{console.error(e);process.exitCode=1;});
