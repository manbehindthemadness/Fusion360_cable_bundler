"use strict";
/** @typedef {{origin:number[], forward:number[], across:number[]}} MaterialFrame */
/** @typedef {{feature:string, space:string, paths:number[][][], frame:MaterialFrame|null, material_mm:number[]|null, details:Object<string,*>}} DisplayObject */
/** @typedef {{index:number, phase:string, basis:string, status:string, title:string, scene:DisplayObject[], details:Object<string,*>}} ConstructionStage */
/** @typedef {{id:string, label:string, kind:string, parents:string[], source:string}} FeatureDefinition */
(() => {
  const el = id => document.getElementById(id);
  let haltPlayback = () => {};
  const fail = error => { haltPlayback();el("error").hidden = false; el("error").textContent = String(error); };
  window.addEventListener("error", event => fail(event.message));
  window.addEventListener("unhandledrejection", event => fail(event.reason));
  try {
    /** @type {{fingerprint:string, header:{run_id:string, provenance:Object}, steps:ConstructionStage[], features:Object<string,FeatureDefinition>}} */
    const packet = JSON.parse(el("packet").textContent);
    const all = packet.steps, definitions = packet.features;
    let index = 0, selected = "", timer = null, yaw = -.7, pitch = .55, zoom = 1, drag = null;
    haltPlayback = stop;
    let visible = all.map((_, i) => i), bridgeSequence = 0;
    let retainedFit = null;
    const keys = ["iso", "xy", "xz", "yz"], views = keys.map(id => el(id));
    let drawScheduled=false, lastLayout="";
    function scheduleDraw() {
      if(drawScheduled)return;
      drawScheduled=true;
      window.requestAnimationFrame(()=>{drawScheduled=false;draw();});
    }
    function reportLayout(painted, force=false) {
      if(!window.adsk || !window.adsk.fusionSendData)return;
      const report={fingerprint:packet.fingerprint,viewport_width:window.innerWidth,viewport_height:window.innerHeight,painted_views:painted,canvases:views.map((canvas,i)=>({view:["iso","top","front","side"][i],width:canvas.clientWidth,height:canvas.clientHeight,pixel_width:canvas.width,pixel_height:canvas.height}))};
      const signature=JSON.stringify(report);
      if(!force&&signature===lastLayout)return;
      lastLayout=signature;
      Promise.resolve(window.adsk.fusionSendData("construction_layout",signature)).then(raw=>{if(raw){const result=JSON.parse(raw);if(result.error)fail(result.error);}}).catch(fail);
    }
    function connect(attempt=0) {
      const retry=()=>{if(attempt<40)window.setTimeout(()=>connect(attempt+1),100);else fail("Fusion did not acknowledge the construction viewer. Browser controls work locally; the Fusion viewport is not connected.");};
      if(!window.adsk || !window.adsk.fusionSendData){retry();return;}
      Promise.resolve(window.adsk.fusionSendData("construction_ready","{}")).then(raw=>{
        if(raw==="" || raw===null || raw===undefined){retry();return;}
        const response=typeof raw==="string"?JSON.parse(raw):raw;
        if(!response || response.ok!==true)throw new Error(response&&response.error||"Invalid Fusion readiness response");
        el("error").hidden=true;lastLayout="";scheduleDraw();bridge();
      }).catch(fail);
    }
    const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
    const points = scene => scene.flatMap(object => object.paths.flat());
    const bounds = values => {
      if (!values.length) return {center:[0,0,0], extent:10};
      const low = [0,1,2].map(k => Math.min(...values.map(p => p[k])));
      const high = [0,1,2].map(k => Math.max(...values.map(p => p[k])));
      return {center:low.map((v,k)=>(v+high[k])/2), extent:Math.max(1, ...low.map((v,k)=>high[k]-v))};
    };
    // A bounded streaming bound avoids spreading every recorded vertex into Math.min.
    const globalLow=[Infinity,Infinity,Infinity],globalHigh=[-Infinity,-Infinity,-Infinity];
    all.forEach(step=>step.scene.filter(o=>o.space==="world").forEach(o=>o.paths.forEach(path=>path.forEach(p=>p.forEach((v,k)=>{globalLow[k]=Math.min(globalLow[k],v);globalHigh[k]=Math.max(globalHigh[k],v);})))));
    const worldBounds=Number.isFinite(globalLow[0])?{center:globalLow.map((v,k)=>(v+globalHigh[k])/2),extent:Math.max(1,...globalLow.map((v,k)=>globalHigh[k]-v))}:{center:[0,0,0],extent:10};
    function bridge() {
      if (!window.adsk || !window.adsk.fusionSendData) return;
      const sequence = ++bridgeSequence;
      Promise.resolve(window.adsk.fusionSendData("construction_select", JSON.stringify({index, feature:selected, auto_zoom:el("auto_zoom").checked}))).then(raw=>{
        if(sequence !== bridgeSequence) return;
        if(raw==="" || raw===null || raw===undefined)throw new Error("Fusion did not acknowledge this step. The browser advanced locally; the Fusion viewport update is unconfirmed.");
        const response = typeof raw === "string" ? JSON.parse(raw) : raw;
        if(response && response.paused===true){if(Number.isInteger(response.index))choose(response.index,false);fail(response.error);return;}
        if(!response || response.ok!==true)throw new Error("Fusion display: " + (response&&response.error||"Invalid acknowledgement"));
        el("error").hidden=true;
      }).catch(fail);
    }
    function refreshList() {
      const phase=el("phase").value;
      visible=all.map((_,i)=>i).filter(i=>phase==="all"||all[i].phase===phase);
      el("steps").replaceChildren();
      visible.forEach(i=>{const option=document.createElement("option");option.value=String(i);option.textContent=`${String(i+1).padStart(3,"0")} · ${all[i].title}`;el("steps").append(option);});
      if(!visible.includes(index)) index=visible[0];
    }
    function move(direction) {
      const position=visible.indexOf(index), next=Math.max(0,Math.min(visible.length-1,position+direction));
      choose(visible[next]);
    }
    function stop() { if(timer!==null){clearInterval(timer);timer=null;}el("play").textContent="Play"; }
    function choose(next, notify=true) {
      if(!Number.isInteger(next)||next<0||next>=all.length) throw new Error("Invalid construction step");
      index=next;
      if(!visible.includes(index)){el("phase").value="all";refreshList();}
      const stage=all[index];el("steps").value=String(index);el("scrubber").value=String(index);el("position").textContent=`${index+1} / ${all.length}`;
      el("title").textContent=stage.title;el("badges").replaceChildren();
      for(const label of [stage.phase,stage.basis,stage.status]){const span=document.createElement("span");span.className="badge "+label;span.textContent=label;el("badges").append(span);}
      el("features").replaceChildren();
      stage.scene.forEach(object=>{const option=document.createElement("option");option.value=object.feature;option.textContent=definitions[object.feature].label;el("features").append(option);});
      if(!selected && stage.details.focus) selected=stage.details.focus;
      el("features").value=selected;
      el("previous").disabled=visible.indexOf(index)===0;el("next").disabled=visible.indexOf(index)===visible.length-1;
      const local=stage.scene.some(o=>o.space==="local");
      el("mode").textContent=local?"LOCAL primitive · millimeters":"WORLD placement · millimeters";
      el("notice").textContent=(local?"Local primitive at its construction origin; connector targets are intentionally absent. ":"")+(stage.details.partial_construction?"Partial assembly view; not a complete ribbon output. ":"")+(stage.details.geometry_notice||"")+(stage.basis==="reconstructed"?" Reconstructed from saved data; original construction decisions were not recorded.":stage.basis==="unavailable"?" This stage has no recorded geometry.":" Recorded event; acceptance applies only to its original stated checks.");
      describe();draw();if(notify)bridge();
    }
    function describe() {
      const object=all[index].scene.find(o=>o.feature===selected), feature=definitions[selected];
      el("lineage").textContent=feature?`${feature.label} · ${feature.kind} · source: ${feature.source}${object&&object.frame?" · entry origin (mm): "+object.frame.origin.map(v=>v.toFixed(3)).join(", "):""}${object&&object.material_mm?" · material "+object.material_mm.map(v=>v.toFixed(3)).join(" → ")+" mm":""}`:"Select a feature to inspect its origin, frame and material interval.";
      el("parents").replaceChildren();
      if(feature){const ancestry=[...new Set([...feature.parents,...(object&&object.details.placement_predecessor?[object.details.placement_predecessor]:[])])];ancestry.forEach(parent=>{const button=document.createElement("button");button.textContent="From "+definitions[parent].label;button.onclick=()=>{selected=parent;const first=all.findIndex(s=>s.scene.some(o=>o.feature===parent));choose(all[index].scene.some(o=>o.feature===parent)?index:first);};el("parents").append(button);});}
      el("details").textContent=JSON.stringify({stage:all[index].details, feature:feature||null, placement:object||null, provenance:packet.header.provenance},null,2);
      el("origin").disabled=!feature;
    }
    function draw() {
      const stage=all[index], local=stage.scene.some(o=>o.space==="local");
      const current=stage.scene.filter(o=>!el("isolate").checked||!selected||o.feature===selected);
      const previous=index&&el("compare").checked?all[index-1].scene.filter(o=>(o.space==="local")===local):[];
      if(el("auto_zoom").checked || retainedFit===null)retainedFit=el("isolate").checked||local||["input","preplot"].includes(stage.phase)?bounds(points(current)):worldBounds;
      const fit=retainedFit;
      let painted=0;
      views.forEach((canvas,view)=>{
        const box=canvas.getBoundingClientRect();if(box.width<2||box.height<2)return;
        const dpr=window.devicePixelRatio||1;canvas.width=Math.round(box.width*dpr);canvas.height=Math.round(box.height*dpr);
        const context=canvas.getContext("2d");context.setTransform(dpr,0,0,dpr,0,0);context.clearRect(0,0,box.width,box.height);
        const scale=.72*Math.min(box.width,box.height)/fit.extent*zoom;
        function project(point) {
          const p=point.map((v,k)=>v-fit.center[k]);let x,y;
          if(view===0){x=p[0]*Math.cos(yaw)-p[1]*Math.sin(yaw);y=(p[0]*Math.sin(yaw)+p[1]*Math.cos(yaw))*Math.sin(pitch)-p[2]*Math.cos(pitch);}
          else if(view===1){x=p[0];y=-p[1];}else if(view===2){x=p[0];y=-p[2];}else{x=p[1];y=-p[2];}
          return [box.width/2+x*scale,box.height/2+y*scale];
        }
        function line(path,color,width=1.4,dash=[]) {
          context.beginPath();path.forEach((p,i)=>{const q=project(p);if(i)context.lineTo(...q);else context.moveTo(...q);});context.strokeStyle=color;context.lineWidth=width;context.setLineDash(dash);context.stroke();context.setLineDash([]);
        }
        function render(object,ghost) {
          const old=index?all[index-1].scene.find(o=>o.feature===object.feature):null;
          const changed=!old||!same(old.paths,object.paths), definition=definitions[object.feature];
          const color=ghost?"#6c798c66":object.feature===selected?"#f0a2ff":stage.status==="rejected"?"#ff858b":changed?"#ffbd70":"#82b9ed";
          if(!ghost&&["fold","straight"].includes(definition.kind)&&object.paths.length===3){const left=object.paths[0],right=object.paths[2];for(let i=0;i<Math.min(left.length,right.length)-1;i++){const vertices=[left[i],left[i+1],right[i+1],right[i]];context.beginPath();vertices.forEach((p,k)=>{const q=project(p);if(k)context.lineTo(...q);else context.moveTo(...q);});context.closePath();context.fillStyle=color+"25";context.fill();}}
          object.paths.forEach(path=>line(path,color,ghost?1:object.feature===selected?2.5:1.4,ghost?[4,4]:[]));
          if(!ghost&&el("frames").checked&&object.frame){const f=object.frame,span=fit.extent*.045;line([f.origin,f.origin.map((v,k)=>v+f.forward[k]*span)],"#ff8e8e",2);line([f.origin,f.origin.map((v,k)=>v+f.across[k]*span)],"#8ae8af",2);}
          if(!ghost&&object.paths.length){const q=project(object.paths[0][0]);context.fillStyle=color;context.font="11px system-ui";if(object.feature===selected||definition.kind==="target")context.fillText(definition.label,q[0]+5,q[1]-5);}
        }
        previous.forEach(o=>render(o,true));current.forEach(o=>render(o,false));
        context.fillStyle="#9cacc2";context.font="10px system-ui";context.fillText(`${(fit.extent/zoom).toFixed(2)} mm view span`,10,box.height-9);
        canvas.dataset.painted=String(index);
        painted++;
      });
      reportLayout(painted);
    }
    el("run").textContent=packet.header.run_id;
    [...new Set(all.map(s=>s.phase))].forEach(phase=>{const option=document.createElement("option");option.value=phase;option.textContent=phase;el("phase").append(option);});
    el("scrubber").max=String(all.length-1);
    el("previous").onclick=()=>{stop();move(-1);};el("next").onclick=()=>{stop();move(1);};
    el("steps").onchange=event=>{stop();choose(Number(event.target.value));};
    el("phase").onchange=()=>{stop();refreshList();choose(index);};
    el("scrubber").oninput=event=>{stop();choose(Number(event.target.value));};
    el("features").onchange=event=>{selected=event.target.value;describe();draw();bridge();};
    el("clear").onclick=()=>{selected="";el("features").value="";describe();draw();bridge();};
    el("origin").onclick=()=>{stop();const first=all.findIndex(s=>s.scene.some(o=>o.feature===selected));if(first>=0)choose(first);};
    el("play").onclick=()=>{if(timer!==null){stop();return;}el("play").textContent="Pause";timer=setInterval(()=>{if(visible.indexOf(index)===visible.length-1){if(el("loop").checked){choose(visible[0]);}else{stop();}return;}move(1);},900);};
    for(const id of ["compare","frames","isolate"]) el(id).onchange=draw;
    el("auto_zoom").onchange=()=>{draw();bridge();};
    el("reset").onclick=()=>{yaw=-.7;pitch=.55;zoom=1;retainedFit=null;draw();};
    views[0].onpointerdown=event=>{drag=[event.clientX,event.clientY];views[0].setPointerCapture(event.pointerId);};
    views[0].onpointermove=event=>{if(!drag)return;yaw+=(event.clientX-drag[0])*.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+(event.clientY-drag[1])*.008));drag=[event.clientX,event.clientY];draw();};
    views[0].onpointerup=()=>{drag=null;};views[0].onpointercancel=()=>{drag=null;};
    views.forEach(canvas=>canvas.addEventListener("wheel",event=>{event.preventDefault();zoom=Math.max(.2,Math.min(10,zoom*Math.exp(-event.deltaY*.001)));draw();},{passive:false}));
    document.addEventListener("keydown",event=>{if(["INPUT","SELECT","TEXTAREA"].includes(event.target.tagName))return;if(event.key==="ArrowRight"){event.preventDefault();stop();move(1);}if(event.key==="ArrowLeft"){event.preventDefault();stop();move(-1);}});
    const observer=new ResizeObserver(scheduleDraw);views.forEach(view=>observer.observe(view));
    window.addEventListener("resize",scheduleDraw);
    window.addEventListener("load",scheduleDraw);
    document.addEventListener("visibilitychange",()=>{if(!document.hidden)scheduleDraw();});
    window.fusionJavaScriptHandler={handle(action){if(action==="construction_status"){lastLayout="";scheduleDraw();return "requested";}return "unsupported";}};
    window.constructionViewer={state:()=>({index,selected,steps:all.length,painted:views.map(v=>v.dataset.painted)}),choose,select:identity=>{selected=identity;describe();draw();bridge();}};
    const parameters=new URLSearchParams(window.location?window.location.hash.slice(1):"");
    const initial=Number(parameters.get("step")||0), feature=parameters.get("feature");
    if(feature&&definitions[feature])selected=feature;
    refreshList();choose(Number.isInteger(initial)&&initial>=0&&initial<all.length?initial:0);
    connect();
  } catch(error) { fail(error.stack||error); }
})();
