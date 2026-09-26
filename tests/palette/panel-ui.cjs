/* global require, __dirname */
const {
  Element, assert, asyncTest, descendants, harness, palette, readPaletteStyles, test,
} = require('./support.cjs');

/** Return the named submenu branch from a rendered context menu. */
function contextMenuBranch(menu, label) {
  return menu.children.find(
    (item) => item.className === 'context-menu-branch'
      && item.children[0].textContent === label,
  );
}

/** Assert that Cable Details is open with the requested member focused. */
function assertFocusedCableDetails(context, connectionId) {
  const details = context.document.body.querySelector('.cable-group-details-popup');
  assert.equal(details.open, true);
  const focused = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-member')
      && node.className.split(' ').includes('focused'),
  )[0];
  assert.equal(focused.dataset.connectionId, connectionId);
}

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
  assertFocusedCableDetails(context, 'a1');
});

test('Cable Details end node opens its routing controls in traversal order', () => {
  const { context, calls } = palette();
  const definition = harness();
  const interpolationCalls = [];
  context.openInterpolationOptions = (...args) => interpolationCalls.push(args);
  context.window.confirm = () => true;
  definition.connections[0].members = [
    {
      index: 0, memberId: 'guide-1',
      interpolation: { approach_mm: 1, departure_mm: 2 },
      usesDefaults: false, hasLinkedGeometry: true,
    },
    {
      index: 1, memberId: 'guide-2',
      interpolation: { approach_mm: null, departure_mm: null },
      usesDefaults: true, hasLinkedGeometry: true,
    },
  ];
  definition.controls = [
    {
      controlId: 'refine-1', name: 'Refine 1', kind: 'refine',
      interpolation: { approach_mm: null, departure_mm: null },
      usesDefaults: true, hasLinkedGeometry: false,
    },
  ];
  definition.standaloneEnds[0].orderedControlIds = ['refine-1'];

  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const endNode = descendants(details, (node) => (
    node.className?.split(' ').includes('cable-group-details-node')
      && node.dataset.nodeId === 'connection:a1'
  ))[0];
  endNode.events.click();

  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
  let routing = context.document.body.querySelector('.cable-end-routing-popup');
  assert.equal(routing.open, true);
  assert.equal(routing.attributes['aria-label'], 'Cable end routing controls: a1');
  const section = routing.querySelector('.pathway-popup-entry');
  assert.equal(section.children[0].children[0].textContent, 'Routing Controls · Traversal Order');
  assert.equal(section.children[0].children[1].textContent, '3');
  const rows = descendants(
    section, (node) => node.className?.split(' ').includes('member-row'),
  );
  assert.deepEqual(rows.map((row) => row.children[1].textContent), [
    'Guide 1 #guide-1', 'Guide 2 #guide-2', 'Refine 1 #refine-1 (geometry missing)',
  ]);
  assert.equal(rows.every((row) => row.className.includes('has-sequence-position')), true);
  rows[0].querySelector('.options-button').events.click();
  assert.equal(interpolationCalls.length, 1);
  assert.deepEqual(interpolationCalls[0].slice(1), [
    'end', 'a1', 'Guide 1', { approach_mm: 1, departure_mm: 2 }, false, 'guide-1',
  ]);
  rows[1].querySelector('.danger').events.click();
  rows[2].querySelector('.danger').events.click();
  assert.equal(calls.length, 2);
  assert.equal(calls[0].action, 'remove_end_guide');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.memberId, 'guide-2');
  assert.equal(calls[1].action, 'remove_end_control');
  assert.equal(calls[1].payload.harnessId, 'h');
  assert.equal(calls[1].payload.connectionId, 'a1');
  assert.equal(calls[1].payload.controlId, 'refine-1');

  context.renderEditor(definition);
  routing = context.document.body.querySelector('.cable-end-routing-popup');
  const close = descendants(
    routing, (node) => node.tag === 'button' && node.textContent === 'Close',
  )[0];
  close.events.click();

  assert.equal(context.document.body.querySelector('.cable-end-routing-popup'), undefined);
  assertFocusedCableDetails(context, 'a1');
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

asyncTest('routing measurements use the active design length units', async () => {
  const { context } = palette();
  const definition = harness();
  definition.lengthUnits = { symbol: 'in', millimetersPerUnit: 25.4 };
  definition.gateDefaults = { approach_mm: 25.4, departure_mm: 50.8 };
  definition.endDefaults = { approach_mm: 76.2, departure_mm: null };
  definition.minimumClearanceMm = 2.54;
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openInterpolationOptions(definition, 'defaults');

  const dialog = context.document.body.querySelector('.cable-options');
  const field = (labelText) => descendants(
    dialog, (node) => node.tag === 'label' && node.textContent === labelText,
  )[0].querySelector('input');
  assert.equal(field('Gates · Approach transition (in)').value, '1');
  assert.equal(field('Gates · Departure transition (in)').value, '2');
  assert.equal(field('Ends · Terminal-side transition (in)').value, '3');
  assert.equal(field('Ends · Pathway-side transition (in)').value, '');
  assert.equal(field('Minimum member gap (in)').value, '0.1');

  field('Gates · Approach transition (in)').value = '1.5';
  field('Ends · Pathway-side transition (in)').value = '4';
  field('Minimum member gap (in)').value = '0.125';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'set_interpolation');
  assert.ok(Math.abs(calls[0].payload.settings.approach_mm - 38.1) < 1e-12);
  assert.ok(Math.abs(calls[0].payload.settings.departure_mm - 50.8) < 1e-12);
  assert.ok(Math.abs(calls[0].payload.endDefaults.approach_mm - 76.2) < 1e-12);
  assert.ok(Math.abs(calls[0].payload.endDefaults.departure_mm - 101.6) < 1e-12);
  assert.ok(Math.abs(calls[0].payload.minimumClearanceMm - 3.175) < 1e-12);
});

test('empty pathway end opens the current pathway popup', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [], metadata: [], startMetadata: [], endMetadata: [],
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

test('pathway end menu places Properties immediately below Route Editor', () => {
  const { context } = palette();
  const definition = harness();
  const diagram = context.renderRelationshipMap(definition);
  const pathwayEnd = descendants(diagram, (node) => (
    node.className?.split(' ').includes('relationship-end-list')
      && node.dataset.pathwayId === 'p'
      && node.dataset.endpoint === 'start'
  ))[0];

  pathwayEnd.children[0].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {},
    target: pathwayEnd.children[0],
  });

  const menu = descendants(
    diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Route Editor', 'Properties',
  ]);
  menu.children[1].events.click();
  assert.equal(
    context.document.body.querySelector('.pathway-end-properties').open,
    true,
  );
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
    ['Pathway', 'Junction', 'Interface', 'Ending'],
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

test('master diagram displays standalone Interface cards without pathways', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways = [];
  definition.junctions = [];
  definition.interfaces = [{
    interfaceId: 'interface-1', name: 'Socket A',
    targets: [{ kind: 'occurrence', hasLinkedGeometry: true }],
  }];
  const diagram = context.renderRelationshipMap(definition);
  const cards = descendants(diagram, (node) => node.className === 'relationship-interface-card');
  assert.equal(cards.length, 1);
  assert.equal(cards[0].children[0].textContent, 'Socket A');
  assert.equal(cards[0].children[1].textContent, 'occurrence · linked');
});

test('Select Contacts opens an empty Interface diagram with Manual, Row, and Plane modes', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const definition = harness();
  definition.interfaces = [{
    interfaceId: 'interface-1', name: 'Socket A',
    targets: [{ kind: 'occurrence', hasLinkedGeometry: true }],
  }];
  const rendered = context.renderRelationshipMap(definition);
  const card = descendants(rendered, (node) => node.className === 'relationship-interface-card')[0];
  card.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: card,
  });
  const menu = descendants(
    rendered, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  menu.children[0].events.click();

  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(dialog.open, true);
  assert.equal(dialog.children[0].textContent, 'Select Contacts · Socket A');
  const modes = dialog.children[1].children[0].children;
  assert.deepEqual(modes.map((button) => button.textContent), [
    'Manual', 'Row', 'Plane',
  ]);
  const naming = dialog.children[1].children[1].children;
  assert.deepEqual(naming.map((button) => button.textContent), ['Pos Import', 'Load brd']);
  assert.deepEqual(modes.map((button) => button.attributes['aria-pressed']), [
    'true', 'false', 'false',
  ]);
  assert.equal(dialog.children[2].className, 'interface-contacts-diagram');
  assert.equal(dialog.children[2].children[0].className,
    'block-diagram-workspace interface-contact-workspace');
  assert.equal(descendants(dialog.children[2], (node) => (
    node.className === 'interface-contact-item'
  )).length, 0);
  modes[0].events.click();
  assert.equal(launches[0].action, 'select_interface_contacts');
  assert.equal(launches[0].payload.interfaceId, 'interface-1');
  modes[1].events.click();
  naming[0].events.click();
  naming[1].events.click();
  assert.deepEqual(launches.slice(1).map((item) => item.action), [
    'pos_import_interface_contacts', 'load_brd_interface_contacts',
  ]);
  assert.deepEqual(modes.map((button) => button.attributes['aria-pressed']), [
    'false', 'true', 'false',
  ]);
  dialog.children[3].children[0].events.click();
  assert.equal(context.document.body.querySelector('.interface-contacts-popup'), undefined);
});

test('Interface contacts keep positions within orientation clusters', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'a', kind: 'profile', name: 'A', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [10, 0, 0], [10, 10, 0]]] },
    { contactId: 'b', kind: 'face', name: 'B', linked: true,
      normal: [0, 0, -1], loops: [[[30, 0, 0], [40, 0, 0], [40, 10, 0]]] },
    { contactId: 'c', kind: 'face', name: 'C', linked: true,
      normal: [1, 0, 0], loops: [[[0, 0, 0], [0, 10, 0], [0, 10, 10]]] },
  ]);
  const svg = diagram.contactState.svg;
  assert.equal(svg.children.length, 2);
  const firstPaths = descendants(svg.children[0], (node) => node.tag === 'path');
  assert.equal(firstPaths.length, 2);
  const firstX = Number(firstPaths[0].attributes.d.match(/M([\d.]+)/)[1]);
  const secondX = Number(firstPaths[1].attributes.d.match(/M([\d.]+)/)[1]);
  const firstLoop = diagram.contactState.items[0].loops[0];
  const padWidth = Math.abs(firstLoop[1][0] - firstLoop[0][0]);
  assert.equal(Math.abs(secondX - firstX) / padWidth, 3);
  assert.equal(descendants(svg.children[1], (node) => node.tag === 'path').length, 1);
});

test('imported contact names appear on pads when there is room', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'pad-1', kind: 'face', name: 'J5.2', assignedName: 'J5.2', linked: true,
    normal: [0, 0, 1], loops: [[[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0]]],
  }]);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className === 'interface-contact-label'
  ));
  assert.equal(labels.length, 1);
  assert.equal(labels[0].textContent, 'J5.2');
});

test('unnamed contacts have a distinct appearance and names appear as zoom permits', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'named', kind: 'face', name: 'A1', assignedName: 'A1', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]] },
    { contactId: 'unnamed', kind: 'face', name: 'Pad', assignedName: '', linked: true,
      normal: [0, 0, 1], loops: [[[20, 0, 0], [21, 0, 0], [21, 1, 0]]] },
  ]);
  assert.equal(contactItem(diagram, 'named').dataset.named, 'true');
  assert.equal(contactItem(diagram, 'unnamed').dataset.named, 'false');
  assert.match(readPaletteStyles(), /\[data-named="false"\] \.interface-contact-outline/);
  const label = descendants(contactItem(diagram, 'named'), (node) => (
    node.className === 'interface-contact-label'
  ))[0];
  assert.equal(label.style.display, 'none');
  const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
  for (let index = 0; index < 20; index += 1) zoomIn.events.click();
  assert.equal(label.style.display, '');
  assert.equal(descendants(contactItem(diagram, 'named'), (node) => node.tag === 'title')[0]
    .textContent, 'A1');
  assert.match(descendants(contactItem(diagram, 'unnamed'), (node) => node.tag === 'title')[0]
    .textContent, /Unnamed contact/);
});

test('contact projection views asymmetric layouts from the picked face side', () => {
  const { context } = palette();
  for (const [normal, expectedRight, expectedUp] of [
    [[0, 0, 2], [-4, 0], [0, 2]],
    [[0, 0, -2], [4, 0], [0, 2]],
  ]) {
    const direction = context.contactOrientation(normal);
    const right = context.contactPlanePoint([4, 0, 0], direction);
    const up = context.contactPlanePoint([0, 2, 0], direction);
    assert.ok(right.every((value, index) => value === expectedRight[index]));
    assert.ok(up.every((value, index) => value === expectedUp[index]));
    const diagram = context.document.createElement('div');
    context.renderInterfaceContacts(diagram, [
      { contactId: 'front', kind: 'face', linked: true, normal,
        loops: [[[0, 0, 0], [4, 0, 0], [4, 2, 0]]] },
      { contactId: 'back', kind: 'face', linked: true, normal: normal.map((value) => -value),
        loops: [[[6, 0, 0], [7, 0, 0], [7, 1, 0]]] },
    ]);
    assert.equal(diagram.contactState.svg.children.length, 1);
    const [front, back] = diagram.contactState.items;
    const offset = back.loops[0][0][0] - front.loops[0][0][0];
    assert.equal(Math.sign(offset), Math.sign(expectedRight[0]),
      'opposite normals share the viewing side of the first picked face');
  }
});

test('board contact projection keeps the small pads below the long pads', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'long', kind: 'face', linked: true, normal: [0, 0, 1],
      parentAxes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      loops: [[[0, 0, 0], [4, 0, 0], [4, 1, 0]]] },
    { contactId: 'small', kind: 'face', linked: true, normal: [0, 0, 1],
      parentAxes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      loops: [[[0, 5, 0], [1, 5, 0], [1, 6, 0]]] },
  ]);
  assert.ok(diagram.contactState.items[1].loops[0][0][1]
    > diagram.contactState.items[0].loops[0][0][1]);
});

test('contact clusters retain their local layout when the parent tilts and rotates', () => {
  const { context } = palette();
  const axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const contacts = [
    { contactId: 'a', kind: 'face', linked: true, normal: [0, 0, 1], parentAxes: axes,
      loops: [[[0, 0, 0], [4, 0, 0], [4, 1, 0]]] },
    { contactId: 'b', kind: 'face', linked: true, normal: [0, 0, -1],
      parentAxes: [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
      loops: [[[2, 5, 0], [3, 5, 0], [3, 6, 0]]] },
    { contactId: 'c', kind: 'face', linked: true, normal: [1, 0, 0], parentAxes: axes,
      loops: [[[0, 0, 0], [0, 4, 0], [0, 4, 1]]] },
  ];
  const baseline = context.document.createElement('div');
  context.renderInterfaceContacts(baseline, contacts);
  for (const angle of [0.4, 1.2, Math.PI / 2, Math.PI]) {
    const rotate = ([x, y, z]) => {
      const c = Math.cos(angle);
      const s = Math.sin(angle);
      const tiltedY = c * y - s * z;
      const tiltedZ = s * y + c * z;
      return [c * x - s * tiltedY, s * x + c * tiltedY, tiltedZ];
    };
    const rotated = contacts.map((contact) => ({
      ...contact,
      normal: rotate(contact.normal), parentAxes: contact.parentAxes.map(rotate),
      loops: contact.loops.map((loop) => loop.map((point) => (
        rotate(point).map((value, index) => value + [10, -20, 30][index])
      ))),
    }));
    const diagram = context.document.createElement('div');
    context.renderInterfaceContacts(diagram, rotated);
    assert.equal(diagram.contactState.svg.children.length, 2);
    diagram.contactState.items.forEach((item, index) => {
      item.loops[0].forEach((point, vertex) => {
        point.forEach((value, axis) => assert.ok(
          Math.abs(value - baseline.contactState.items[index].loops[0][vertex][axis]) < 1e-8,
          'parent rotation must preserve the complete projected arrangement',
        ));
      });
    });
  }
});

test('small contact pads fit the diagram without strokes swallowing their gaps', () => {
  const { context } = palette();
  for (const modelScale of [0.01, 1, 1000]) {
    const diagram = context.document.createElement('div');
    const contacts = Array.from({ length: 7 }, (_unused, index) => {
      const width = index < 5 ? 4 : 1.2;
      return {
        contactId: `pad-${index}`, kind: 'face', name: `Pad ${index}`, linked: true,
        normal: [0, 0, 1],
        loops: [[[0, index], [width, index], [width, index + 0.6], [0, index + 0.6]]
          .map(([x, y]) => [(20 + x) * modelScale, (30 + y) * modelScale, 0])],
      };
    });
    context.renderInterfaceContacts(diagram, contacts);
    const { items, svg, diagramHeight } = diagram.contactState;
    assert.equal(items.length, 7);
    const loops = items.map((item) => item.loops[0]);
    const width = Math.abs(loops[0][1][0] - loops[0][0][0]);
    const height = Math.abs(loops[0][2][1] - loops[0][1][1]);
    assert.ok(height > 10, 'pad interiors remain visible at the initial display scale');
    assert.ok(Math.abs(width / height - 4 / 0.6) < 1e-8);
    for (let index = 1; index < loops.length; index += 1) {
      assert.ok(loops[index][0][1] - loops[index - 1][2][1] > 3,
        'neighboring pad strokes must not overlap');
    }
    assert.ok(loops[6][2][1] < diagramHeight);
    assert.equal(svg.style.height, `${diagramHeight}px`, 'labels use display units');
  }
});

/** Convert a diagram-space point into mock pointer coordinates. */
function contactPointer(svg, x, y, pointerId = 1) {
  const bounds = svg.getBoundingClientRect();
  const [, , width, height] = svg.attributes.viewBox.split(' ').map(Number);
  return {
    button: 0, pointerId,
    clientX: bounds.left + x * bounds.width / width,
    clientY: bounds.top + y * bounds.height / height,
    target: svg, preventDefault() {},
  };
}

/** Return one contact's drawn group by its durable ID. */
function contactItem(diagram, id) {
  return descendants(diagram, (node) => node.dataset?.contactId === id)[0];
}

asyncTest('left clicking a contact edits its saved name without losing selection', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contact = { contactId: 'pad-1', kind: 'face', name: 'Pad', assignedName: 'J5.2',
    linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0]]] };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [contact],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  const state = diagram.contactState;
  const [x, y] = state.items[0].loops[0][0];
  const item = contactItem(diagram, 'pad-1');
  const pointer = { ...contactPointer(state.svg, x, y), target: item };
  state.workspace.viewport.events.pointerdown(pointer);
  state.workspace.viewport.events.pointerup({ ...pointer, type: 'pointerup' });
  assert.equal(item.dataset.selected, 'true');
  const editor = diagram.querySelector('.interface-contact-name-editor');
  assert.equal(editor.dataset.contactId, 'pad-1');
  const input = editor.children[1];
  assert.equal(input.value, 'J5.2');
  input.value = 'J5.4';
  editor.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'set_interface_contact_name');
  assert.equal(launches[0].payload.harnessId, 'harness-1');
  assert.equal(launches[0].payload.interfaceId, 'interface-1');
  assert.equal(launches[0].payload.contactId, 'pad-1');
  assert.equal(launches[0].payload.name, 'J5.4');
  assert.equal(diagram.querySelector('.interface-contact-name-editor'), undefined);
});

test('contact diagram zooms, pans, and box-selects individual contacts', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  const contacts = [
    { contactId: 'a', kind: 'profile', name: 'A', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [10, 0, 0], [10, 10, 0]]] },
    { contactId: 'b', kind: 'face', name: 'B', linked: true,
      normal: [0, 0, 1], loops: [[[50, 0, 0], [60, 0, 0], [60, 10, 0]]] },
  ];
  context.renderInterfaceContacts(diagram, contacts);
  const { workspace, svg } = diagram.contactState;
  const viewport = workspace.viewport;
  const firstPath = descendants(contactItem(diagram, 'a'), (node) => node.tag === 'path')[0];
  const firstX = Number(firstPath.attributes.d.match(/M([\d.]+)/)[1]);
  const firstY = Number(firstPath.attributes.d.match(/M[\d.]+ ([\d.]+)/)[1]);
  const start = contactPointer(svg, firstX - 2, firstY - 2);
  const end = contactPointer(svg, firstX + 12, firstY + 12);
  viewport.events.pointerdown(start);
  viewport.events.pointermove(end);
  viewport.events.pointerup({ ...end, type: 'pointerup' });
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'true');
  assert.equal(contactItem(diagram, 'b').dataset.selected, 'false');
  assert.equal(diagram.contactState.count.textContent, '1 selected');

  const zoomBefore = workspace.zoomValue.textContent;
  viewport.events.wheel({ deltaY: -1, clientX: 50, clientY: 50, preventDefault() {} });
  assert.notEqual(workspace.zoomValue.textContent, zoomBefore);
  const panButton = descendants(diagram, (node) => node.textContent === 'Pan' && node.tag === 'button')[0];
  panButton.events.click();
  const transformBefore = workspace.stage.style.transform;
  viewport.events.pointerdown({ ...start, pointerId: 2 });
  viewport.events.pointermove({ ...end, pointerId: 2 });
  viewport.events.pointerup({ ...end, pointerId: 2, type: 'pointerup' });
  assert.notEqual(workspace.stage.style.transform, transformBefore);
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'true');
  const boxButton = descendants(diagram, (node) => node.textContent === 'Box' && node.tag === 'button')[0];
  boxButton.events.click();
  const bounds = svg.getBoundingClientRect();
  svg.getBoundingClientRect = () => ({ ...bounds, left: bounds.left + 40,
    top: bounds.top + 20, width: bounds.width * 1.5, height: bounds.height * 1.5 });
  const secondPath = descendants(contactItem(diagram, 'b'), (node) => node.tag === 'path')[0];
  const secondX = Number(secondPath.attributes.d.match(/M([\d.]+)/)[1]);
  const secondY = Number(secondPath.attributes.d.match(/M[\d.]+ ([\d.]+)/)[1]);
  const secondStart = contactPointer(svg, secondX - 2, secondY - 2, 3);
  const secondEnd = contactPointer(svg, secondX + 12, secondY + 12, 3);
  viewport.events.pointerdown(secondStart);
  viewport.events.pointermove(secondEnd);
  viewport.events.pointerup({ ...secondEnd, type: 'pointerup' });
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'false');
  assert.equal(contactItem(diagram, 'b').dataset.selected, 'true');
});

test('freeform selection treats multi-outline contacts as single items across refreshes', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  const contacts = [
    { contactId: 'a', kind: 'profile', name: 'A', linked: true, normal: [0, 0, 1], loops: [
      [[0, 0, 0], [10, 0, 0], [10, 10, 0]],
      [[15, 0, 0], [20, 0, 0], [20, 5, 0]],
    ] },
    { contactId: 'b', kind: 'face', name: 'B', linked: true,
      normal: [0, 0, 1], loops: [[[50, 0, 0], [60, 0, 0], [60, 10, 0]]] },
  ];
  context.renderInterfaceContacts(diagram, contacts);
  const freeform = descendants(diagram, (node) => (
    node.tag === 'button' && node.textContent === 'Freeform'
  ))[0];
  freeform.events.click();
  const svg = diagram.contactState.svg;
  const viewport = diagram.contactState.workspace.viewport;
  const [x, y] = diagram.contactState.items[0].loops[1][0];
  const corners = [[x - 2, y - 2], [x + 7, y - 2], [x + 7, y + 7], [x - 2, y + 7]];
  const points = corners.map(([pointX, pointY]) => contactPointer(svg, pointX, pointY));
  viewport.events.pointerdown(points[0]);
  points.slice(1).forEach((point) => viewport.events.pointermove(point));
  viewport.events.pointerup({ ...points[0], type: 'pointerup' });
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'true');
  assert.equal(contactItem(diagram, 'b').dataset.selected, 'false');
  const transform = diagram.contactState.workspace.stage.style.transform;
  context.renderInterfaceContacts(diagram, contacts);
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'true');
  assert.equal(diagram.contactState.workspace.stage.style.transform, transform);
});

test('filled contact profiles preserve holes and select their interior as one item', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'ring', kind: 'face', linked: true, normal: [0, 0, 1], loops: [
      [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]],
      [[4, 4, 0], [6, 4, 0], [6, 6, 0], [4, 6, 0]],
    ],
  }]);
  const { items, svg, workspace } = diagram.contactState;
  const paths = descendants(items[0].node, (node) => node.tag === 'path');
  assert.equal(paths.length, 1);
  assert.equal(paths[0].attributes['fill-rule'], 'evenodd');
  assert.equal((paths[0].attributes.d.match(/M/g) || []).length, 2);
  const [outer, hole] = items[0].loops;
  const center = [(hole[0][0] + hole[2][0]) / 2, (hole[0][1] + hole[2][1]) / 2];
  const holeArea = context.contactBox([center[0] - 1, center[1] - 1],
    [center[0] + 1, center[1] + 1]);
  assert.equal(context.contactIntersectsArea(items[0], holeArea), false);
  const point = contactPointer(svg, (outer[0][0] + hole[0][0]) / 2, center[1]);
  workspace.viewport.events.pointerdown({ ...point, target: paths[0] });
  workspace.viewport.events.pointerup({ ...point, target: paths[0], type: 'pointerup' });
  assert.equal(items[0].node.attributes['aria-selected'], 'true');
});

test('contact clicks select individual items with additive and toggle modifiers', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'a', kind: 'sketch_point', name: 'A', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0]]] },
    { contactId: 'b', kind: 'sketch_point', name: 'B', linked: true,
      normal: [0, 0, 1], loops: [[[30, 0, 0]]] },
  ]);
  const viewport = diagram.contactState.workspace.viewport;
  const svg = diagram.contactState.svg;
  const click = (id, modifiers = {}) => {
    const target = contactItem(diagram, id).children[1];
    const point = contactPointer(svg, Number(target.attributes.cx), Number(target.attributes.cy));
    viewport.events.pointerdown({ ...point, target, ...modifiers });
    viewport.events.pointerup({ ...point, target, type: 'pointerup', ...modifiers });
  };
  click('a');
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'true');
  click('b', { shiftKey: true });
  assert.equal(diagram.contactState.count.textContent, '2 selected');
  click('a', { ctrlKey: true });
  assert.equal(contactItem(diagram, 'a').dataset.selected, 'false');
  assert.equal(contactItem(diagram, 'b').dataset.selected, 'true');
  viewport.events.keydown({ key: 'Escape' });
  assert.equal(diagram.contactState.count.textContent, '0 selected');
  contactItem(diagram, 'b').events.keydown({ key: 'Enter', preventDefault() {} });
  assert.equal(contactItem(diagram, 'b').attributes['aria-selected'], 'true');
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

test('Cable Details header shows and renames its cable group', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.cableGroups[0].name = 'Engine loom';

  context.openCableGroupDetails(definition, 'g1', 'a1');

  const details = context.document.body.querySelector('.cable-group-details-popup');
  const heading = details.querySelector('.cable-group-details-heading');
  const title = descendants(heading, (node) => node.tag === 'h2')[0];
  const rename = descendants(
    heading, (node) => node.tag === 'button' && node.textContent === 'Rename',
  )[0];
  assert.equal(title.textContent, 'Engine loom');
  assert.equal(descendants(heading, (node) => node.tag === 'p')[0].textContent, '2 assigned ends');
  assert.equal(descendants(details, (node) => node.tag === 'h3')[0].textContent, 'Assigned Ends');
  assert.equal(descendants(heading, (node) => node.textContent === 'Cable Details').length, 0);

  rename.events.click();
  const input = heading.querySelector('input');
  assert.equal(input.value, 'Engine loom');
  assert.equal(input.attributes['aria-label'], 'Cable group name');
  input.value = 'Cabin data';
  input.events.keydown({ key: 'Enter', stopPropagation() {}, preventDefault() {} });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_cable_group');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.cableGroupId, 'g1');
  assert.equal(calls[0].payload.name, 'Cabin data');
});

test('master end menu groups connection and routing actions under Add', () => {
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
  let addBranch = contextMenuBranch(menu, 'Add');
  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Connection', 'Guides', 'Refine'],
  );
  addBranch.children[1].children[1].events.click();
  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  addBranch = contextMenuBranch(menu, 'Add');
  addBranch.children[1].children[2].events.click();

  assert.deepEqual(actions, [['guides', 'a1'], ['refine', 'a1']]);
});

test('master end menu switches only unassigned ends immediately above Rename', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.cableGroups = definition.cableGroups.slice(1);
  const diagram = context.renderRelationshipMap(definition);
  const unassigned = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];
  const assigned = descendants(
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

  assert.equal(unassigned.children[1].textContent, 'Unassigned');
  assert.equal(unassigned.attributes['aria-label'], 'a1, unassigned end');
  assert.equal(assigned.children[1].textContent, 'Assigned');
  assert.equal(assigned.attributes['aria-label'], 'a2, assigned end');

  let menu = openMenu(unassigned);
  const labels = menu.children.map((item) => item.textContent);
  assert.equal(labels.indexOf('Switch'), labels.indexOf('Rename') - 1);
  assert.equal(labels.at(-1), 'Properties');
  menu.children.find((item) => item.textContent === 'Switch').events.click();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'switch_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');

  menu = openMenu(assigned);
  assert.equal(menu.children.some((item) => item.textContent === 'Switch'), false);
});
