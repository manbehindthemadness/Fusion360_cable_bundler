/** Run with node tests/test_palette.cjs; no Fusion or browser dependencies. */
/* global require, __dirname, process, module */
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const testNameFilter = (process.argv[2] || '').toLocaleLowerCase();

/** Return whether a regression was selected by the optional command-line filter. */
function selectedTest(name) {
  return !testNameFilter || name.toLocaleLowerCase().includes(testNameFilter);
}

/** Run a synchronous regression and propagate assertion failures to the process. */
function test(name, check) {
  if (!selectedTest(name)) return;
  check();
  console.log(`PASS ${name}`);
}

/** Run an asynchronous regression and preserve a failing process exit status. */
function asyncTest(name, check) {
  if (!selectedTest(name)) return;
  Promise.resolve().then(check).then(
    () => console.log(`PASS ${name}`),
    (failure) => {
      console.error(`FAIL ${name}`);
      console.error(failure);
      process.exitCode = 1;
    },
  );
}

/** Minimal DOM boundary for testing the actual palette rendering and events. */
class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.dataset = {};
    this.style = {};
    /** @type {Object.<string, Function>} */
    this.events = {};
    this.attributes = {};
    this.classList = {
      add: (...names) => {
        this.className = [...new Set([
          ...(this.className || '').split(' ').filter(Boolean), ...names,
        ])].join(' ');
      },
      remove: (...names) => {
        this.className = (this.className || '').split(' ')
          .filter((name) => name && !names.includes(name)).join(' ');
      },
    };
    this.textContent = '';
    this.value = '';
    this.hidden = false;
    this.clientWidth = tag === 'dialog' ? 430 : 120;
    this.clientHeight = tag === 'dialog' ? 500 : 24;
    this.scrollWidth = this.clientWidth;
    this.scrollHeight = this.clientHeight;
    /** @type {Element|null} */
    this.parentElement = null;
  }
  append(...children) {
    for (const child of children) if (typeof child === 'object') child.parentElement = this;
    this.children.push(...children);
  }
  prepend(...children) {
    for (const child of children) if (typeof child === 'object') child.parentElement = this;
    this.children.unshift(...children);
  }
  insertBefore(child, reference) {
    child.parentElement = this;
    this.children.splice(this.children.indexOf(reference), 0, child);
  }
  remove() {
    if (this.parentElement) {
      this.parentElement.children = this.parentElement.children.filter((child) => child !== this);
    }
  }
  querySelector(selector) {
    const editorId = selector.match(/data-editor-id="([^"]+)"/);
    const sectionId = selector.match(/data-section="([^"]+)"/);
    const cableId = selector.match(/data-cable-id="([^"]+)"/);
    const endpoint = selector.match(/data-endpoint="([^"]+)"/);
    return descendants(this, (child) => {
      if (editorId) return child.dataset.editorId === editorId[1];
      if (sectionId) return child.dataset.section === sectionId[1];
      if (cableId) return child.dataset.cableId === cableId[1];
      if (endpoint) return child.dataset.endpoint === endpoint[1];
      if (selector.startsWith('.')) return child.className?.split(' ').includes(selector.slice(1));
      return child.tag === selector;
    })[0];
  }
  querySelectorAll(selector) {
    if (selector.startsWith('.')) {
      const className = selector.slice(1);
      return descendants(this, (child) => child.className?.split(' ').includes(className));
    }
    const tags = selector.split(',').map((item) => item.trim());
    return descendants(this, (child) => tags.includes(child.tag));
  }
  focus() {}
  select() {}
  showModal() { this.open = true; }
  close() { this.open = false; if (this.events.close) this.events.close(); }
  replaceChildren(...children) {
    for (const child of children) if (typeof child === 'object') child.parentElement = this;
    this.children = children;
  }
  addEventListener(event, handler) {
    const prior = this.events[event];
    this.events[event] = prior
      ? (...args) => { prior(...args); handler(...args); }
      : handler;
  }
  setAttribute(key, value) {
    this.attributes[key] = value;
    if (key === 'class') this.className = value;
  }
  scrollIntoView() { this.scrolledIntoView = true; }
  getBoundingClientRect() {
    const width = Number.parseFloat(this.style.width) || this.clientWidth;
    const height = Number.parseFloat(this.style.height) || this.clientHeight;
    let left = 10;
    let top = 10;
    let current = this;
    while (current) {
      left += Number.parseFloat(current.style.left || '0');
      top += Number.parseFloat(current.style.top || '0');
      current = current.parentElement;
    }
    return { left, top, right: left + width, bottom: top + height, width, height };
  }
  getClientRects() { return this.hidden ? [] : [this.getBoundingClientRect()]; }
  dispatchEvent(event) {
    if (this.events[event.type]) this.events[event.type](event);
    return true;
  }
  contains(candidate) {
    let node = candidate;
    while (node) {
      if (node === this) return true;
      node = node.parentElement;
    }
    return false;
  }
}

/** Evaluate the complete palette script with the Fusion transport mocked. */
function palette(storage = new Map(), preferences = storage, prefersDark = false) {
  const calls = [];
  const intervals = [];
  const themeListeners = [];
  const deviceTheme = {
    matches: prefersDark,
    addEventListener: (event, handler) => {
      if (event === 'change') themeListeners.push(handler);
    },
  };
  /** @type {*} Palette functions are defined dynamically by the evaluated HTML script. */
  const context = {
    document: {
      body: new Element('body'),
      documentElement: new Element('html'),
      scrollingElement: { scrollTop: 0 },
      events: {},
      createElement: (tag) => new Element(tag),
      createElementNS: (_namespace, tag) => new Element(tag),
      getElementById: () => new Element('div'),
      addEventListener(event, handler) { this.events[event] = handler; },
      removeEventListener(event, handler) {
        if (this.events[event] === handler) delete this.events[event];
      },
      dispatchEvent(event) {
        if (this.events[event.type]) this.events[event.type](event);
      },
    },
    window: {
      innerWidth: 800,
      innerHeight: 700,
      Event: class Event { constructor(type) { this.type = type; } },
      requestAnimationFrame: (callback) => callback(),
      matchMedia: () => deviceTheme,
      setInterval: (callback, delay) => {
        const timer = { callback, delay };
        intervals.push(timer);
        return timer;
      },
      clearInterval: (timer) => {
        const index = intervals.indexOf(timer);
        if (index >= 0) intervals.splice(index, 1);
      },
      scrollTo: () => {},
      sessionStorage: {
        getItem: (key) => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
      },
      localStorage: {
        getItem: (key) => preferences.get(key) || null,
        setItem: (key, value) => preferences.set(key, value),
      },
    },
  };
  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  const scripts = [...html.matchAll(/<script src="([^"]+)"><\/script>/g)]
    .map((match) => readFileSync(join(__dirname, '..', '..', match[1]), 'utf8'));
  runInNewContext(scripts.join('\n'), context);
  context.ui = runInNewContext('ui', context);
  context.intervals = intervals;
  context.deviceTheme = deviceTheme;
  context.changeDeviceTheme = (matches) => {
    deviceTheme.matches = matches;
    themeListeners.forEach((listener) => listener({ matches }));
  };
  context.mutate = (action, payload) => calls.push({ action, payload });
  return { context, calls };
}

/** Read every palette stylesheet in the production document order. */
function readPaletteStyles() {
  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  return [...html.matchAll(/<link rel="stylesheet" href="([^"]+)">/g)]
    .map((match) => readFileSync(join(__dirname, '..', '..', match[1]), 'utf8'))
    .join('\n');
}

/** Collect rendered descendants using a predicate. */
function descendants(root, predicate) {
  return root.children.flatMap((child) => typeof child === 'object'
    ? [...(predicate(child) ? [child] : []), ...descendants(child, predicate)] : []);
}

/** Return three cable groups sharing one pathway. */
function harness() {
  const materialDefaults = {
    insulationMaterial: 'PVC', conductorMaterial: 'Copper',
    mainColor: { name: 'Black', hex: '#202020' }, appearance: null, stripes: [],
    manufacturer: '', partNumber: '', notes: '',
  };
  const connections = [1, 2, 3].flatMap((i) => ['a', 'b'].map((end) => ({
    connectionId: `${end}${i}`, name: `${end}${i}`, hasLinkedGeometry: true, metadata: [],
  })));
  const standaloneEnds = [1, 2, 3].flatMap((i) => [
    { connectionId: `a${i}`, pathwayId: 'p', endpoint: 'start', orderedControlIds: [] },
    { connectionId: `b${i}`, pathwayId: 'p', endpoint: 'end', orderedControlIds: [] },
  ]);
  const cableGroups = [1, 2, 3].map((i) => ({
    cableGroupId: `g${i}`, connectionIds: [`a${i}`, `b${i}`], diameterMm: 1.5,
    materials: materialDefaults,
    materialOverrides: { insulationMaterial: null, conductorMaterial: null,
      mainColor: null, appearance: null, stripes: null, manufacturer: null,
      partNumber: null, notes: null },
    metadata: [], metadataOverrides: [],
    routeLegs: [{ routeId: `r${i}`, label: `Group ${i} Leg 1`,
      startConnectionId: `a${i}`, endConnectionId: `b${i}`,
      pathwayIds: ['p'], controlSteps: [] }],
  }));
  return {
    harnessId: 'h', componentName: 'Harness_001', definitionName: 'Harness_001',
    schemaVersion: 15, routingMode: 'Routing Gates', status: 'valid',
    minimumClearanceMm: 0,
    autoTransitionPreset: 'tight',
    validationMessages: [], materialDefaults, metadata: [], controls: [], connections,
    pathways: [{ pathwayId: 'p', name: 'lower fuse box path', startName: 'O2-sensor',
      endName: 'CAN_BUS-ctrl', orderedControlIds: [], metadata: [],
      startMetadata: [], endMetadata: [] }],
    junctions: [], standaloneEnds, cableGroups, cableGroupRouteError: null,
  };
}

module.exports = {
  Element,
  assert,
  asyncTest,
  descendants,
  harness,
  join,
  palette,
  readPaletteStyles,
  readFileSync,
  runInNewContext,
  test,
};
