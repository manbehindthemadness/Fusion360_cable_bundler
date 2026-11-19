"use strict";
// Exercise the real bundled controller with a bounded fake DOM, not a live browser.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

class Element {
  constructor(id) {
    this.id = id;
    this.children = [];
    this.value = id === "phase" ? "all" : "";
    this.checked = ["frames","auto_zoom"].includes(id);
    this.dataset = {};
    this.textContent = "";
    this.hidden = id === "error";
    this.tagName = "DIV";
    this.cssWidth=440;
    this.cssHeight=215;
    this.context = {
      setTransform() {}, clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
      stroke() {}, setLineDash() {}, closePath() {}, fill() {}, fillText:(text)=>{this.lastText=text;}
    };
  }
  replaceChildren() { this.children = []; }
  append(child) { this.children.push(child); }
  getBoundingClientRect() { return {width:this.cssWidth, height:this.cssHeight}; }
  get clientWidth() { return this.cssWidth; }
  get clientHeight() { return this.cssHeight; }
  getContext() { return this.context; }
  addEventListener() {}
  setPointerCapture() {}
}

async function main() {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  const object = {feature:"F1", space:"world", paths:[[[0,0,0],[2,1,0]]], frame:null, material_mm:[0,2], details:{}};
  get("packet").textContent = JSON.stringify({
    fingerprint:"a".repeat(64),
    header:{run_id:"controller unit test", provenance:{}},
    features:{F1:{id:"F1", label:"Fold 1", kind:"fold", parents:[], source:"test:primitive"}},
    steps:[
      {index:0, title:"input", phase:"input", status:"reference", basis:"observed", scene:[object], details:{}},
      {index:1, title:"local primitive", phase:"primitive", status:"reference", basis:"reconstructed", scene:[{...object, space:"local", paths:[[[0,0,0],[20,0,0]]]}], details:{focus:"F1"}},
      {index:2, title:"failed correction", phase:"correction", status:"rejected", basis:"observed", scene:[object], details:{}}
    ]
  });
  const calls = [];
  let scheduled = null;
  const windowEvents=new Map(), documentEvents=new Map();
  const browserWindow = {
    devicePixelRatio:1,innerWidth:1120,innerHeight:870,location:{hash:""},
    addEventListener(name,handler) {windowEvents.set(name,handler);},
    requestAnimationFrame:callback=>callback(),
    adsk:{fusionSendData(action, data) { calls.push({action, data:JSON.parse(data)}); return Promise.resolve('{"ok":true}'); }}
  };
  const context = {
    window:browserWindow,
    document:{getElementById:get, createElement:tag=>new Element(tag), hidden:false,addEventListener(name,handler) {documentEvents.set(name,handler);}},
    URLSearchParams,
    ResizeObserver:class { observe() {} },
    requestAnimationFrame:callback=>callback(),
    setInterval:callback=>{scheduled=callback; return 1;},
    clearInterval:()=>{scheduled=null;},
    console
  };
  vm.runInNewContext(fs.readFileSync(new URL("../devtools/ribbon_analysis/construction/viewer.js", import.meta.url),"utf8"), context);
  const viewer = browserWindow.constructionViewer;
  assert.ok(viewer, get("error").textContent);
  assert.equal(viewer.state().index,0);
  assert.ok(viewer.state().painted.every(value=>value==="0"));
  const initialSpan=get("iso").lastText;
  get("auto_zoom").checked=false;
  get("auto_zoom").onchange();
  assert.equal(calls.at(-1).data.auto_zoom,false);
  get("next").onclick();
  assert.equal(get("iso").lastText,initialSpan,"Turning off auto-zoom holds framing across differently sized local/world stages");
  get("reset").onclick();
  assert.notEqual(get("iso").lastText,initialSpan,"Manual fit still works with auto-zoom off");
  get("previous").onclick();
  get("auto_zoom").checked=true;
  get("auto_zoom").onchange();
  assert.equal(get("iso").lastText,initialSpan);
  get("next").onclick();
  assert.equal(viewer.state().index,1);
  assert.equal(viewer.state().selected,"F1");
  assert.match(get("mode").textContent,/LOCAL/);
  assert.match(get("notice").textContent,/Reconstructed/);
  get("origin").onclick();
  assert.equal(viewer.state().index,0);
  get("scrubber").oninput({target:{value:"2"}});
  assert.equal(viewer.state().index,2);
  get("phase").value="primitive";
  get("phase").onchange();
  assert.equal(viewer.state().index,1);
  assert.equal(get("steps").children.length,1);
  get("phase").value="all";
  get("phase").onchange();
  get("play").onclick();
  assert.ok(scheduled);
  scheduled();
  assert.equal(viewer.state().index,2);
  scheduled();
  assert.equal(scheduled,null);
  assert.equal(get("play").textContent,"Play");
  get("loop").checked=true;
  get("play").onclick();
  scheduled();
  assert.equal(viewer.state().index,0,"Loop wraps from the final step to the first");
  assert.ok(scheduled,"Loop keeps playback running");
  assert.equal(calls.at(-1).data.index,0,"Fusion follows the wrapped selection");
  scheduled();
  get("play").onclick();
  assert.equal(scheduled,null,"Pause also stops looping playback");
  get("phase").value="primitive";
  get("phase").onchange();
  get("play").onclick();
  scheduled();
  assert.equal(viewer.state().index,1,"Loop stays within the active phase filter");
  assert.ok(scheduled);
  get("loop").checked=false;
  scheduled();
  assert.equal(scheduled,null,"Turning loop off restores stopping at the end");
  get("phase").value="all";
  get("phase").onchange();
  get("clear").onclick();
  assert.equal(viewer.state().selected,"");
  get("previous").onclick();
  get("compare").checked=true;
  get("compare").onchange();
  get("frames").checked=false;
  get("frames").onchange();
  get("reset").onclick();
  const retained=viewer.state().index;
  for(const key of ["iso","xy","xz","yz"]) {get(key).cssWidth=0;get(key).cssHeight=0;}
  windowEvents.get("resize")();
  assert.equal(calls.at(-1).action,"construction_layout");
  assert.equal(calls.at(-1).data.painted_views,0);
  for(const key of ["iso","xy","xz","yz"]) {get(key).cssWidth=440;get(key).cssHeight=215;}
  windowEvents.get("load")();
  documentEvents.get("visibilitychange")();
  assert.equal(viewer.state().index,retained);
  assert.equal(calls.at(-1).data.painted_views,4);
  assert.equal(calls.at(-1).data.canvases.length,4);
  browserWindow.location.hash="#step=2&feature=F1";
  vm.runInNewContext(fs.readFileSync(new URL("../devtools/ribbon_analysis/construction/viewer.js", import.meta.url),"utf8"), context);
  assert.equal(browserWindow.constructionViewer.state().index,2);
  assert.equal(browserWindow.constructionViewer.state().selected,"F1");
  const nativeBridge=browserWindow.adsk;
  let readiness=null;
  browserWindow.adsk=null;
  browserWindow.setTimeout=callback=>{readiness=callback;return 1;};
  vm.runInNewContext(fs.readFileSync(new URL("../devtools/ribbon_analysis/construction/viewer.js", import.meta.url),"utf8"), context);
  assert.ok(readiness,"A late Fusion bridge must get a bounded readiness check");
  browserWindow.adsk=nativeBridge;
  readiness();
  await new Promise(resolve=>setTimeout(resolve,0));
  const connectedLayout=[...calls].reverse().find(call=>call.action==="construction_layout");
  assert.equal(connectedLayout.data.painted_views,4);
  assert.equal(calls.at(-1).action,"construction_select");
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(get("error").hidden,true,get("error").textContent);
  assert.ok(calls.length >= 8);
  assert.ok(calls.every(call=>["construction_select","construction_layout","construction_ready"].includes(call.action)));
  assert.ok(browserWindow.constructionViewer.state().painted.every(value=>value===String(browserWindow.constructionViewer.state().index)));
  await new Promise(resolve=>setTimeout(resolve,0));
  const currentViewer=browserWindow.constructionViewer;
  currentViewer.choose(2);
  await new Promise(resolve=>setTimeout(resolve,0));
  browserWindow.adsk={fusionSendData(action){return Promise.resolve(action==="construction_select"?JSON.stringify({paused:true,error:"Playback paused: finish the active command",index:1}):'{"ok":true}');}};
  get("loop").checked=true;
  get("play").onclick();
  scheduled();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(scheduled,null,"A temporary Fusion interruption stops looping playback");
  assert.equal(currentViewer.state().index,1,"Paused playback returns to the last confirmed native step");
  assert.match(get("error").textContent,/Playback paused/);
  browserWindow.adsk=nativeBridge;
  get("next").onclick();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(currentViewer.state().index,2);
  assert.equal(get("error").hidden,true,"Manual continuation clears the pause after a valid acknowledgement");
  browserWindow.adsk={fusionSendData(){return Promise.resolve('{"error":"source drift"}');}};
  get("play").onclick();
  scheduled();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(scheduled,null,"A permanent Fusion error also stops looping playback");
  browserWindow.adsk=nativeBridge;
  let readyAttempts=0;
  browserWindow.adsk={fusionSendData(action){if(action==="construction_ready")readyAttempts++;return Promise.resolve("");}};
  vm.runInNewContext(fs.readFileSync(new URL("../devtools/ribbon_analysis/construction/viewer.js", import.meta.url),"utf8"), context);
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(get("error").textContent,/did not acknowledge this step/);
  assert.doesNotMatch(get("error").textContent,/SyntaxError|JSON input/);
  for(let attempt=0;attempt<40;attempt++){readiness();await new Promise(resolve=>setTimeout(resolve,0));}
  assert.equal(readyAttempts,41,"Only the read-only handshake retries, within its finite bound");
  assert.match(get("error").textContent,/viewport is not connected/);
  browserWindow.adsk=nativeBridge;
  vm.runInNewContext(fs.readFileSync(new URL("../devtools/ribbon_analysis/construction/viewer.js", import.meta.url),"utf8"), context);
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(get("error").hidden,true,"A valid readiness acknowledgement reconnects the current step");
  console.log("Construction viewer controller: navigation, first-open resize/visibility paint recovery, retained selection and Fusion messages passed");
}

await main();
