/* global require, __dirname */
const {
  Element, assert, asyncTest, descendants, harness, palette, readPaletteStyles, test,
} = require('./support.cjs');

test('palette follows fixed Fusion themes and live device theme rollovers', () => {
  const { context } = palette(new Map(), new Map(), false);

  context.render({ harnesses: [], notice: '', theme: { mode: 'fixed', active: 'dark' } });
  assert.equal(context.document.documentElement.dataset.theme, 'dark');
  assert.equal(context.document.documentElement.style.colorScheme, 'dark');

  context.changeDeviceTheme(false);
  assert.equal(context.document.documentElement.dataset.theme, 'dark');

  context.render({ harnesses: [], notice: '', theme: { mode: 'device', active: 'dark' } });
  assert.equal(context.document.documentElement.dataset.theme, 'dark');
  context.changeDeviceTheme(false);
  assert.equal(context.document.documentElement.dataset.theme, 'light');
  context.changeDeviceTheme(true);
  assert.equal(context.document.documentElement.dataset.theme, 'dark');
});

asyncTest('device mode polls Fusion without refreshing harness state', async () => {
  const { context } = palette();
  const actions = [];
  context.send = async (action) => {
    actions.push(action);
    return { ok: true, theme: { mode: 'device', active: 'dark' } };
  };
  context.applyPaletteTheme({ mode: 'device', active: 'light' });

  assert.ok(context.intervals.some((timer) => timer.delay === 10000));
  await context.pollFusionTheme();

  assert.deepEqual(actions, ['get_theme']);
  assert.equal(context.document.documentElement.dataset.theme, 'dark');

  context.applyPaletteTheme({ mode: 'fixed', active: 'light' });
  await context.pollFusionTheme();
  assert.deepEqual(actions, ['get_theme']);
});

test('palette restores its last Fusion theme before the host state arrives', () => {
  const storage = new Map([
    ['cableBundler.paletteTheme', JSON.stringify({ mode: 'fixed', active: 'dark' })],
  ]);
  const { context } = palette(storage);

  assert.equal(context.document.documentElement.dataset.theme, 'dark');
  assert.equal(context.document.documentElement.style.colorScheme, 'dark');
});

test('palette theme changes preserve master cable material strokes', () => {
  const { context } = palette();
  const definition = harness();
  definition.cableGroups[0].materials = {
    ...definition.cableGroups[0].materials,
    mainColor: { name: 'Signal Red', hex: '#d72525' },
  };
  const diagram = context.renderRelationshipMap(definition);
  const trace = descendants(
    diagram,
    (node) => node.className?.split(' ').includes('cable-trace')
      && node.attributes.stroke === '#d72525',
  )[0];

  assert.ok(trace);
  context.applyPaletteTheme({ mode: 'fixed', active: 'dark' });
  assert.equal(trace.attributes.stroke, '#d72525');
  context.applyPaletteTheme({ mode: 'fixed', active: 'light' });
  assert.equal(trace.attributes.stroke, '#d72525');
});

test('master halos wrap contrast-demanding cables but never stripes', () => {
  const { context } = palette();
  const definition = harness();
  definition.cableGroups[0].materials = {
    ...definition.cableGroups[0].materials,
    mainColor: { name: 'Near Black', hex: '#101214' },
    stripes: [{
      color: { name: 'Black', hex: '#101214' }, pattern: 'solid', widthMm: 0.2,
    }],
  };

  const diagram = context.renderRelationshipMap(definition);
  const halos = descendants(
    diagram, (node) => node.className?.split(' ').includes('trace-contrast-halo'),
  );
  const cableHalo = halos.find((node) => (
    node.dataset.cableGroupId === 'g1'
      && node.className.split(' ').includes('trace-contrast-dark-theme')
  ));
  const cableTraces = descendants(
    diagram, (node) => node.className?.split(' ').includes('cable-trace'),
  );
  const stripeTraces = descendants(
    diagram, (node) => node.className?.split(' ').includes('stripe-trace'),
  );
  const exactTrace = descendants(diagram, (node) => (
    node.className?.split(' ').includes('cable-trace')
      && node.dataset.cableGroupId === 'g1'
      && node.attributes.stroke === '#101214'
  ))[0];

  assert.ok(cableHalo);
  assert.equal(cableHalo.className.includes('trace-contrast-light-theme'), false);
  assert.equal(halos.length, cableTraces.length);
  assert.ok(stripeTraces.some((node) => node.dataset.cableGroupId === 'g1'));
  assert.ok(exactTrace);
  assert.equal(context.traceContrastRatio('#000', '#fff'), 21);
});

test('current pathway popup retains gate ordering and interpolation controls', () => {
  const { context } = palette();
  const definition = harness();
  definition.gateDefaults = { approach_mm: null, departure_mm: null };
  definition.endDefaults = { approach_mm: null, departure_mm: null };
  definition.controls = [1, 2, 3].map((index) => ({
    controlId: `c${index}`, name: `Gate ${index}`, kind: 'routing_gate',
    interpolation: { approach_mm: null, departure_mm: null },
    usesDefaults: true, hasLinkedGeometry: true,
  }));
  definition.pathways[0].orderedControlIds = ['c1', 'c2', 'c3'];

  context.openPathwayPopup(definition, 'p');

  const popup = context.document.body.querySelector('.pathway-popup');
  const gateRows = descendants(
    popup, (node) => node.className?.split(' ').includes('member-row'),
  );
  const options = descendants(
    popup, (node) => node.className?.split(' ').includes('options-button'),
  )[0];
  assert.equal(popup.open, true);
  assert.ok(gateRows.some((row) => row.dataset.reorder === 'true'));

  options.events.click();
  const interpolation = context.document.body.querySelector('.cable-options');
  assert.equal(interpolation.open, true);
  assert.equal(interpolation.attributes['aria-label'], 'Interpolation · Gate 1');
});

test('closing pathway configuration returns to its Cable Details parent', () => {
  const { context } = palette();
  const definition = harness();

  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const pathway = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-node')
      && node.dataset.nodeId === 'pathway:p',
  )[0];
  pathway.events.click();

  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
  let configuration = context.document.body.querySelector('.pathway-popup');
  assert.equal(configuration.open, true);
  context.renderEditor(definition);
  configuration = context.document.body.querySelector('.pathway-popup');
  const close = descendants(
    configuration, (node) => node.tag === 'button' && node.textContent === 'Close',
  )[0];
  close.events.click();

  assert.equal(context.document.body.querySelector('.pathway-popup'), undefined);
  const restored = context.document.body.querySelector('.cable-group-details-popup');
  assert.equal(restored.open, true);
  const focused = descendants(
    restored,
    (node) => node.className?.split(' ').includes('cable-group-details-member')
      && node.className.split(' ').includes('focused'),
  )[0];
  assert.equal(focused.dataset.connectionId, 'a1');
});

test('closing junction configuration returns to its Cable Details parent', () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001', pathwayRelationships: [],
  };
  definition.junctions = [junction];

  context.openCableGroupDetails(definition, 'g1', 'a1');
  context.openJunctionRelationships(definition, junction);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
  const configuration = context.document.body.querySelector('.junction-relationships-popup');
  const close = descendants(
    configuration, (node) => node.tag === 'button' && node.textContent === 'Close',
  )[0];
  close.events.click();

  assert.equal(context.document.body.querySelector('.junction-relationships-popup'), undefined);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup').open, true);
});

test('generation defaults expose persisted generation preferences', () => {
  const { context } = palette();
  const definition = harness();
  definition.gateDefaults = { approach_mm: null, departure_mm: null };
  definition.endDefaults = { approach_mm: null, departure_mm: null };
  definition.minimumClearanceMm = 0.35;
  definition.autoTransitionPreset = 'relaxed';

  context.openInterpolationOptions(definition, 'defaults');

  const dialog = context.document.body.querySelector('.cable-options');
  const clearance = descendants(
    dialog, (node) => node.attributes?.['aria-label'] === 'Minimum member gap (mm)',
  )[0];
  const relaxation = descendants(
    dialog,
    (node) => node.attributes?.['aria-label'] === 'Automatic transition relaxation',
  )[0];
  const relaxationHeading = descendants(
    dialog, (node) => node.className === 'auto-transition-heading',
  )[0];
  const endpointLabels = descendants(
    dialog, (node) => node.className === 'auto-transition-endpoints',
  );
  assert.equal(dialog.attributes['aria-label'], 'Generation defaults');
  assert.equal(clearance.value, '0.35');
  assert.equal(clearance.min, '0');
  assert.equal(relaxation.type, 'range');
  assert.equal(relaxation.value, '3');
  assert.equal(relaxation.min, '0');
  assert.equal(relaxation.max, '4');
  assert.equal(relaxation.step, '1');
  assert.equal(relaxation.attributes['aria-valuetext'], 'Relaxed');
  assert.equal(relaxationHeading.children[0].textContent, 'Automatic transition relaxation');
  assert.equal(relaxationHeading.children[1].textContent, 'Relaxed');
  assert.equal(endpointLabels.length, 0);
});

test('empty pathway end opens the current pathway popup', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [], metadata: [],
  });

  const diagram = context.renderRelationshipMap(definition);
  const emptyEnd = descendants(diagram, (node) => (
    node.className?.split(' ').includes('relationship-end-list')
      && node.dataset.pathwayId === 'p2'
  ))[0];
  emptyEnd.children[0].events.click({ preventDefault() {} });

  const popup = context.document.body.querySelector('.pathway-popup');
  assert.equal(popup.open, true);
  assert.equal(popup.attributes['aria-label'], 'Pathway configuration: Pathway 002');
});

test('master diagram Materials action opens harness materials', () => {
  const { context } = palette();
  const definition = harness();
  const diagram = context.renderRelationshipMap(definition);
  const viewport = descendants(
    diagram, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    viewport, (node) => node.className === 'relationship-map-context-menu',
  )[0];

  viewport.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: viewport,
  });
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(materialDialog.children[0].children[0].textContent, 'Harness Materials');
});

test('master diagram shows and edits the persisted harness name', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.componentName = 'Fusion Component';
  definition.definitionName = 'Engine Harness';
  context.renderEditor(definition);
  const section = context.ui.editor.children[0];
  const summary = section.children[0];

  assert.equal(summary.children[0].textContent, 'Engine Harness');
  assert.equal(summary.children[1].textContent, 'Edit');
  assert.equal(summary.children[1].attributes['aria-label'], 'Edit harness name');
  assert.equal(descendants(
    section, (node) => node.className === 'relationship-map-identity',
  ).length, 0);

  summary.children[1].events.click({ preventDefault() {}, stopPropagation() {} });
  const input = summary.querySelector('input');
  assert.equal(input.value, 'Engine Harness');
  input.value = 'Cabin Harness';
  input.events.keydown({ key: 'Enter', preventDefault() {}, stopPropagation() {} });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_harness');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.name, 'Cabin Harness');
});

test('master diagram groups render and add actions into submenus', () => {
  const { context } = palette();
  const definition = harness();
  definition.hasRoutePreview = true;
  definition.hasGeneratedSolids = false;
  definition.hasFinalizedGeometry = false;
  const actions = [];
  context.previewRoutes = () => actions.push('preview');
  context.clearPreview = () => actions.push('clear-preview');
  context.generateSolids = () => actions.push('solids');
  context.clearSolids = () => actions.push('clear-solids');
  context.finalizeSolids = () => actions.push('finalize');
  const diagram = context.renderRelationshipMap(definition);
  const viewport = descendants(
    diagram, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    viewport, (node) => node.className === 'relationship-map-context-menu',
  )[0];

  viewport.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: viewport,
  });
  const branches = menu.children.filter((item) => item.className === 'context-menu-branch');
  const renderBranch = branches.find((item) => item.children[0].textContent === 'Render');
  const addBranch = branches.find((item) => item.children[0].textContent === 'Add');
  const renderRows = renderBranch.children[1].children;
  const preview = renderRows.find((row) => row.children[0].textContent === 'Preview');
  const solids = renderRows.find((row) => row.children[0].textContent === 'Solids');
  const finalize = renderRows.find((row) => row.children[0].textContent === 'Finalize');

  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Pathway', 'Junction', 'Ending'],
  );
  assert.equal(preview.children[1].checked, true);
  assert.equal(solids.children[1].checked, false);
  assert.equal(finalize.children[1].checked, false);
  preview.children[0].events.click();
  preview.children[1].checked = false;
  preview.children[1].events.click({ stopPropagation() {} });
  solids.children[1].checked = true;
  solids.children[1].events.click({ stopPropagation() {} });
  solids.children[0].events.click();
  solids.children[1].checked = false;
  solids.children[1].events.click({ stopPropagation() {} });
  finalize.children[0].events.click();
  finalize.children[1].checked = true;
  finalize.children[1].events.click({ stopPropagation() {} });
  finalize.children[1].checked = false;
  finalize.children[1].events.click({ stopPropagation() {} });

  assert.deepEqual(actions, [
    'preview', 'clear-preview', 'solids', 'solids', 'clear-solids',
    'finalize', 'finalize', 'clear-solids',
  ]);
});

test('Cable Details Materials action opens group materials', () => {
  const { context } = palette();
  const definition = harness();
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');

  details.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: details,
  });
  const menu = details.querySelector('.relationship-map-context-menu');
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(
    materialDialog.children[0].children[0].textContent,
    'Connected Cable Group Materials',
  );
});

test('master end menu exposes end-owned guide and refine actions', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways[0].orderedControlIds = ['c1'];
  const actions = [];
  context.appendEndGuides = (_harness, connectionId) => actions.push(['guides', connectionId]);
  context.addEndRefine = (_harness, connectionId) => actions.push(['refine', connectionId]);
  const diagram = context.renderRelationshipMap(definition);
  const end = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];

  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  const menu = descendants(
    diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  menu.children.find((item) => item.textContent === 'Add Guides').events.click();
  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  menu.children.find((item) => item.textContent === 'Add Refine Point').events.click();

  assert.deepEqual(actions, [['guides', 'a1'], ['refine', 'a1']]);
});

test('master end menu switches only disconnected ends immediately above Rename', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.cableGroups = definition.cableGroups.slice(1);
  const diagram = context.renderRelationshipMap(definition);
  const disconnected = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];
  const connected = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a2',
  )[0];
  const openMenu = (end) => {
    end.events.contextmenu({
      clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
    });
    return descendants(
      diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
    )[0];
  };

  let menu = openMenu(disconnected);
  const labels = menu.children.map((item) => item.textContent);
  assert.equal(labels.indexOf('Switch'), labels.indexOf('Rename') - 1);
  assert.equal(labels.at(-1), 'Properties');
  menu.children.find((item) => item.textContent === 'Switch').events.click();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'switch_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');

  menu = openMenu(connected);
  assert.equal(menu.children.some((item) => item.textContent === 'Switch'), false);
});

test('Route Editor opens Details only for connected cable ends', () => {
  const { context } = palette();
  const definition = harness();
  definition.cableGroups = definition.cableGroups.slice(1);
  const left = context.resolveCableCreationBoundary(
    definition, { pathwayId: 'p', endpoint: 'start' },
  );
  const right = context.resolveCableCreationBoundary(
    definition, { pathwayId: 'p', endpoint: 'end' },
  );
  context.openCreateCablesPopup(definition, left, right);
  const editor = context.document.body.querySelector('.create-cables-popup');
  const cards = descendants(
    editor, (node) => node.className?.split(' ').includes('create-cables-end-card'),
  );
  const connected = cards.find((candidate) => candidate.dataset.connectionId === 'a2');
  const disconnected = cards.find((candidate) => candidate.dataset.connectionId === 'a1');
  const openMenu = (connectionId) => {
    const card = cards.find((candidate) => candidate.dataset.connectionId === connectionId);
    card.events.contextmenu({
      clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: card,
    });
    return editor.querySelector('.relationship-map-context-menu');
  };

  let menu = openMenu('a2');
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Details', 'Rename', 'Delete',
  ]);
  menu.children[0].events.click();
  assert.equal(editor.open, true);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup').open, true);

  context.closeCableGroupDetails();
  connected.closest = () => null;
  connected.setPointerCapture = () => {};
  connected.hasPointerCapture = () => false;
  connected.events.pointerdown({
    button: 0, clientX: 20, clientY: 20, pointerId: 1, target: connected,
  });
  connected.events.pointermove({
    clientX: 1000, clientY: 1000, preventDefault() {}, target: connected,
  });
  connected.events.pointerup({ pointerId: 1, target: connected });
  connected.events.click({
    preventDefault() {}, stopPropagation() {}, target: connected,
  });
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);

  connected.events.pointerdown({
    button: 0, clientX: 20, clientY: 20, pointerId: 2, target: connected,
  });
  connected.events.pointerup({ pointerId: 2, target: connected });
  connected.events.click({ target: connected });
  assert.equal(editor.open, true);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup').open, true);

  context.closeCableGroupDetails();
  menu = openMenu('a1');
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Rename', 'Delete']);
  disconnected.events.click?.({ target: disconnected });
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
});

asyncTest('editing a master end isolates keyboard and pointer events until saved', async () => {
  const { context, calls } = palette();
  const definition = harness();
  const highlights = [];
  let finishSave;
  context.highlightMember = (_harness, memberType, memberId) => {
    highlights.push([memberType, memberId]);
  };
  context.mutate = (action, payload) => {
    calls.push({ action, payload });
    return new Promise((resolve) => { finishSave = resolve; });
  };
  const diagram = context.renderRelationshipMap(definition);
  const end = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];
  const otherEnd = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a2',
  )[0];

  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  const menu = descendants(
    diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  menu.children.find((item) => item.textContent === 'Rename').events.click();
  const input = end.querySelector('input');
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, []);
  assert.equal(diagram.className.includes('relationship-focus-active'), false);
  ['mousedown', 'click'].forEach((eventName) => {
    let pointerPropagationStopped = false;
    input.events[eventName]({
      stopPropagation() { pointerPropagationStopped = true; },
    });
    if (!pointerPropagationStopped && eventName === 'click') end.events.click();
    assert.equal(pointerPropagationStopped, true);
  });
  let contextPropagationStopped = false;
  let contextDefaultPrevented = false;
  input.events.contextmenu({
    stopPropagation() { contextPropagationStopped = true; },
    preventDefault() { contextDefaultPrevented = true; },
  });
  assert.equal(contextPropagationStopped, true);
  assert.equal(contextDefaultPrevented, false);
  assert.equal(menu.hidden, true);
  let propagationStopped = false;
  let defaultPrevented = false;
  input.events.keydown({
    key: ' ',
    stopPropagation() { propagationStopped = true; },
    preventDefault() { defaultPrevented = true; },
  });
  if (!propagationStopped) end.events.keydown({ key: ' ', preventDefault() {} });

  assert.equal(propagationStopped, true);
  assert.equal(defaultPrevented, false);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
  assert.equal(end.querySelector('input'), input);
  input.value = 'Engine Bay End';
  input.events.blur();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.name, 'Engine Bay End');
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, []);
  assert.equal(diagram.className.includes('relationship-focus-active'), false);

  finishSave();
  await new Promise((resolve) => setTimeout(resolve, 0));
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, [['connection', 'a2']]);
  assert.equal(diagram.className.includes('relationship-focus-active'), true);
});

test('Cable Details end nodes and rows share end-owned routing actions', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways[0].orderedControlIds = ['c1'];
  const actions = [];
  context.appendEndGuides = (_harness, connectionId) => actions.push(['guides', connectionId]);
  context.addEndRefine = (_harness, connectionId) => actions.push(['refine', connectionId]);
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const graphicEnd = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-node')
      && node.dataset.connectionId === 'a1',
  )[0];
  const member = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-member')
      && node.dataset.connectionId === 'a1',
  )[0];
  const menu = details.querySelector('.relationship-map-context-menu');

  graphicEnd.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: graphicEnd,
  });
  menu.children.find((item) => item.textContent === 'Add Guides').events.click();
  member.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: member,
  });
  menu.children.find((item) => item.textContent === 'Add Refine Point').events.click();

  assert.deepEqual(actions, [['guides', 'a1'], ['refine', 'a1']]);
  assert.equal(menu.children.at(-1).textContent, 'Properties');
});

test('Cable Details pathway and junction nodes share master diagram interactions', () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'cj', name: 'Branch',
    pathwayRelationships: [{ pathwayId: 'p', endpoint: 'start' }], metadata: [],
  };
  definition.junctions = [junction];
  definition.cableGroups[0].routeLegs[0].controlSteps = [{ controlId: 'cj' }];
  const actions = [];
  context.activatePathwayNode = (_harness, pathway) => (
    actions.push(['open-pathway', pathway.pathwayId])
  );
  context.activateJunctionNode = (_harness, item) => (
    actions.push(['open-junction', item.junctionId])
  );
  context.addPathwayRefine = (_harness, pathway) => (
    actions.push(['refine', pathway.pathwayId])
  );
  context.removeJunction = (_harness, item) => (
    actions.push(['delete-junction', item.junctionId])
  );
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const node = (nodeId) => descendants(details, (candidate) => (
    candidate.className?.split(' ').includes('cable-group-details-node')
      && candidate.dataset.nodeId === nodeId
  ))[0];
  const menu = details.querySelector('.relationship-map-context-menu');
  const invokeContextMenu = (target) => target.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target,
  });

  node('pathway:p').events.click();
  node('junction:j1').events.click();
  invokeContextMenu(node('pathway:p'));
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Add refine point', 'Segment', 'Delete', 'Properties',
  ]);
  menu.children[0].events.click();
  invokeContextMenu(node('junction:j1'));
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Open junction configuration', 'Delete', 'Properties',
  ]);
  menu.children[1].events.click();

  assert.deepEqual(actions, [
    ['open-pathway', 'p'],
    ['open-junction', 'j1'],
    ['refine', 'p'],
    ['delete-junction', 'j1'],
  ]);
});

test('material color context menus copy and paste between swatches', () => {
  const { context } = palette();
  const definition = harness();
  definition.materialDefaults.stripes = [
    {
      color: { name: 'Red', hex: '#ff0000' }, widthMm: 0.4,
      pattern: 'dashed', angleDeg: 0, repeatMm: 6,
    },
    {
      color: { name: 'Gray', hex: '#c0c0c0' }, widthMm: 0.4,
      pattern: 'dashed', angleDeg: 90, repeatMm: 6,
    },
  ];
  context.openMaterialOptions(definition);
  const dialog = context.document.body.querySelector('.material-options');
  const swatches = descendants(dialog, (node) => node.type === 'color');
  const contextMenu = (swatch) => descendants(
    swatch.parentElement,
    (node) => node.className?.split(' ').includes('relationship-map-context-menu'),
  )[0];

  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  assert.equal(
    contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste').disabled,
    true,
  );
  swatches[0].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[0],
  });
  contextMenu(swatches[0]).children.find((item) => item.textContent === 'Copy').events.click();
  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste').events.click();
  assert.equal(swatches[2].value, '#202020');

  swatches[1].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[1],
  });
  contextMenu(swatches[1]).children.find((item) => item.textContent === 'Copy').events.click();

  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  const paste = contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste');
  assert.equal(paste.disabled, false);
  paste.events.click();

  assert.equal(swatches[2].value, '#ff0000');
});

asyncTest('connected cable metadata inherits until explicitly overridden', async () => {
  const { context } = palette();
  const definition = harness();
  const cableGroup = definition.cableGroups[0];
  definition.metadata = [{ key: 'project', value: 'Orion' }];
  cableGroup.metadata = [{ key: 'project', value: 'Orion' }];
  cableGroup.metadataOverrides = [];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableGroupProperties(definition, cableGroup);

  const dialog = context.document.body.querySelector('.cable-group-properties');
  const row = dialog.querySelector('.metadata-row');
  const value = row.querySelector('.metadata-value');
  const override = descendants(row, (node) => node.type === 'checkbox')[0];
  assert.equal(value.value, 'Orion');
  assert.equal(value.disabled, true);
  override.checked = true;
  override.events.change();
  value.value = 'Apollo';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_group_properties');
  assert.equal(JSON.stringify(calls[0].payload.metadataOverrides), JSON.stringify([
    { key: 'project', value: 'Apollo' },
  ]));
  assert.equal(descendants(dialog, (node) => node.textContent === 'Notes').length, 0);
});

asyncTest('pathway Properties edits only pathway metadata', async () => {
  const { context } = palette();
  const definition = harness();
  const pathway = definition.pathways[0];
  pathway.metadata = [{ key: 'zone', value: 'forward' }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openPathwayProperties(definition, pathway);

  const dialog = context.document.body.querySelector('.pathway-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  assert.equal(fields[0].value, 'zone');
  assert.equal(fields[1].value, 'forward');
  fields[1].value = 'aft';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_pathway_properties');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'zone', value: 'aft' },
  ]));
});

asyncTest('junction Properties edits only junction metadata', async () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'cj', name: 'Branch',
    pathwayRelationships: [], metadata: [{ key: 'panel', value: 'P2' }],
  };
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openJunctionProperties(definition, junction);

  const dialog = context.document.body.querySelector('.junction-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  fields[1].value = 'P3';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_junction_properties');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'panel', value: 'P3' },
  ]));
});

asyncTest('cable-end Properties edits only the selected end metadata', async () => {
  const { context } = palette();
  const definition = harness();
  definition.connections[0].metadata = [{ key: 'connector', value: 'J1' }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableEndProperties(definition, 'a1');

  const dialog = context.document.body.querySelector('.cable-end-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  fields[1].value = 'J2';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_end_properties');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'connector', value: 'J2' },
  ]));
});
