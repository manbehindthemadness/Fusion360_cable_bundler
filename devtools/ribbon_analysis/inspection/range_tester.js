"use strict";

/** @typedef {{name:string,label:string,minimum:number,maximum:?number,integer:boolean}} RangeTestField */
/** @typedef {{ranges:Object<string,{min:string,max:string,step:string}>,mode:string,seed:number,stop_on_warnings:boolean,maximum_cases:number,keep_awake?:boolean,avoid_adjacent_zones?:boolean,screenshots?:{enabled:boolean,directory:string}}} RangeTestSpecification */
/** @typedef {{zone:number,face:number,roll?:number,roll_degrees?:number}} RangeTestGoal */
/** @typedef {{seed:number,lines:number,diameter_mm:number,void_percent:number,zone_percent:number}} RangeTestConfig */
/** @typedef {{available:boolean,fields:RangeTestField[],specification:?RangeTestSpecification,defaults:RangeTestSpecification,active:boolean,phase:string,reason:string,attempted:number,passed:number,warnings:number,elapsed_seconds:number,current:?{config:RangeTestConfig,a:RangeTestGoal,b:RangeTestGoal},directory:?string,input:?string,job:?string,keep_awake?:{active:boolean,pid:?number},screenshot?:?{path:string,seconds:number,bytes:number}}} RangeTestState */
/** Range controls share the diagnostic bridge; they never run a solver in JavaScript. */
window.RangeTestPanel = class {
  /**
   * @param {function(string):any} element
   * @param {function():any} selection
   * @param {function(string,object=):void} send
   * @param {function():void} stop
   */
  constructor(element, selection, send, stop) {
    this.element = element;
    this.selection = selection;
    this.send = send;
    this.stop = stop;
    this.initialized = false;
    /** @type {?RangeTestState} */ this.current = null;
    /** @type {RangeTestField[]} */ this.fields = [];
    element("testerStart").onclick = () => this.start();
    element("testerStop").onclick = stop;
    element("testerInspect").onclick = () => send("tester_inspect", {});
  }

  /** @param {?RangeTestState} state */
  render(state) {
    this.current = state;
    this.element("rangeTesterPanel").hidden = !state?.available;
    if (!state?.available) return;
    if (!this.initialized) {
      this.fields = state.fields;
      const spec = state.specification || state.defaults;
      this.element("testerRanges").replaceChildren(...this.fields.map(field => {
        const row = document.createElement("tr"), label = document.createElement("th");
        label.scope = "row"; label.textContent = field.label; row.append(label);
        for (const part of ["min", "max", "step"]) {
          const cell = document.createElement("td"), input = document.createElement("input");
          input.type = "number"; input.required = true;
          input.id = `tester_${field.name}_${part}`;
          input.setAttribute("aria-label", `${field.label} ${part}`);
          input.step = field.integer ? "1" : "any";
          if (part !== "step") {
            input.min = String(field.minimum);
            if (field.maximum !== null) input.max = String(field.maximum);
          } else input.min = field.integer ? "1" : "0";
          input.value = spec.ranges[field.name][part];
          cell.append(input); row.append(cell);
        }
        return row;
      }));
      this.element("testerMode").value = spec.mode;
      this.element("testerSeed").value = spec.seed;
      this.element("testerLimit").value = spec.maximum_cases;
      this.element("testerWarnings").checked = spec.stop_on_warnings;
      this.element("testerKeepAwake").checked = spec.keep_awake ?? state.defaults.keep_awake ?? false;
      this.element("testerAvoidAdjacent").checked = spec.avoid_adjacent_zones ?? true;
      this.element("testerScreenshots").checked = spec.screenshots?.enabled || false;
      this.element("testerScreenshotDirectory").value = spec.screenshots?.directory || "~/Pictures/testxyz";
      this.initialized = true;
    }
    const lines = [
      `${state.phase}: ${state.reason}`,
      `Attempts ${state.attempted} · passed ${state.passed} · warning passes ${state.warnings} · ${state.elapsed_seconds.toFixed(1)} s`,
    ];
    if (state.current) {
      const c = state.current.config, a = state.current.a, b = state.current.b;
      lines.push(`Current: seed ${c.seed} · ${c.lines} conductors · D ${c.diameter_mm} mm · void ${c.void_percent}% · zones ${c.zone_percent}%`);
      lines.push(`A zone ${a.zone + 1}/face ${a.face + 1}/roll ${a.roll_degrees ?? (a.roll ?? 0) * 90}° · B zone ${b.zone + 1}/face ${b.face + 1}/roll ${b.roll_degrees ?? (b.roll ?? 0) * 90}°`);
    }
    if (state.directory) lines.push(`Test logs: ${state.directory}`);
    if (state.input) lines.push(`Input snapshot: ${state.input}`);
    if (state.job) lines.push(`Current job: ${state.job}`);
    else if (state.current) lines.push("No solver worker was launched for this prepared case.");
    if (state.screenshot) lines.push(`Screenshot (${state.screenshot.seconds.toFixed(2)} s): ${state.screenshot.path}`);
    if (state.keep_awake?.active) lines.push("Keep awake: Mac and display held awake while testing.");
    this.element("testerStatus").textContent = lines.join("\n");
  }

  /**
   * @param {boolean} blocked
   * @param {boolean} stopQueued
   */
  controls(blocked, stopQueued) {
    const active = Boolean(this.current?.active);
    for (const input of this.element("rangeTesterPanel").querySelectorAll("input,select")) input.disabled = blocked || active;
    this.element("testerStart").disabled = blocked || active || !this.initialized;
    this.element("testerInspect").disabled = blocked || active || !this.current?.current;
    // A native call can occupy Fusion's thread: queue Stop locally while that request finishes.
    this.element("testerStop").disabled = !active || stopQueued;
    this.element("testerStop").textContent = stopQueued ? "Stop queued…" : "Stop testing";
  }

  start() {
    const panel = this.element("rangeTesterPanel");
    for (const input of panel.querySelectorAll("input")) if (!input.reportValidity()) return;
    const ranges = {};
    for (const field of this.fields) {
      ranges[field.name] = Object.fromEntries(["min", "max", "step"].map(part => [part, this.element(`tester_${field.name}_${part}`).value]));
    }
    const selection = this.selection();
    if (!selection) return;
    this.send("tester_start", {selection, specification: {
      ranges, mode: this.element("testerMode").value,
      seed: Number(this.element("testerSeed").value),
      stop_on_warnings: this.element("testerWarnings").checked,
      keep_awake: this.element("testerKeepAwake").checked,
      avoid_adjacent_zones: this.element("testerAvoidAdjacent").checked,
      maximum_cases: Number(this.element("testerLimit").value),
      screenshots: {enabled: this.element("testerScreenshots").checked, directory: this.element("testerScreenshotDirectory").value},
    }});
  }
};
