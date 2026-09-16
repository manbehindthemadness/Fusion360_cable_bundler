/** Focused palette regression suite. */
/* global require, __dirname */
const { Element, assert, asyncTest, descendants, harness, join, palette, readFileSync, runInNewContext, test } = require('./support.cjs');

test('master context menu fits its labels and remains inside its surface', () => {
  const { context } = palette();
  const root = new Element('div');
  root.clientWidth = 260;
  root.clientHeight = 180;
  const show = context.addContextMenu(root, root);
  const menu = root.children[0];
  menu.clientWidth = 190;
  menu.clientHeight = 100;

  show(
    { clientX: 265, clientY: 185, preventDefault() {} },
    [{ label: 'A Longer Context Command', action() {} }],
  );

  assert.equal(menu.style.left, '66px');
  assert.equal(menu.style.top, '76px');
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(
    styles,
    /\.block-diagram-viewport > \.relationship-map-context-menu \{[^}]*display: inline-grid;[^}]*grid-template-columns: max-content;[^}]*width: fit-content;/s,
  );
  assert.match(
    styles,
    /\.block-diagram-viewport > \.relationship-map-context-menu button \{[^}]*width: auto;/s,
  );
  assert.match(
    styles,
    /\.relationship-map-context-menu button:hover \{[^}]*background: var\(--surface-subtle\);/s,
  );
  assert.doesNotMatch(
    styles,
    /\.relationship-map-context-menu button:focus(?:-visible)?[^{]*\{[^}]*background:/s,
  );
});

asyncTest('empty master graphic owns ordered harness commands', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.pathways = [];
  definition.wires = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  runInNewContext(
    'currentState = { harnesses: [definition] }; selectedHarnessKey = "h";',
    Object.assign(context, { definition }),
  );

  const graphic = context.renderRelationshipMap(definition, []);
  const workspace = descendants(
    graphic,
    (node) => node.className === 'block-diagram-workspace',
  )[0];
  const viewport = descendants(
    workspace,
    (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    workspace,
    (node) => node.className === 'relationship-map-context-menu',
  )[0];
  assert.equal(menu.parentElement, viewport);
  assert.ok(descendants(
    graphic, (node) => node.textContent === 'No pathways or junctions to display yet.',
  ).length);
  assert.equal(menu.hidden, true);
  let prevented = false;
  viewport.events.contextmenu({
    clientX: 80,
    clientY: 90,
    preventDefault: () => { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.equal(menu.hidden, false);
  assert.deepEqual(
    menu.children.map((item) => item.textContent),
    [
      'Preview Routes', 'Clear Preview', 'Generate Solids', 'Clear Solids',
      'Add Pathway', 'Add Junction', 'Add End', 'Materials', 'Defaults', 'Properties',
    ],
  );
  assert.equal(menu.children[0].disabled, true);
  assert.equal(menu.children[2].disabled, true);
  menu.children[4].events.click();
  await Promise.resolve();
  assert.equal(menu.hidden, true);
  assert.equal(calls[0].action, 'add_pathway');
  assert.equal(calls[0].payload.harnessId, 'h');

  viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });
  menu.children[5].events.click();
  await Promise.resolve();
  assert.equal(menu.hidden, true);
  assert.equal(calls[1].action, 'add_junction');
  assert.equal(calls[1].payload.harnessId, 'h');

  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  assert.doesNotMatch(
    html,
    /id="(?:clear-preview|generate-solids|clear-solids|material-defaults|interpolation-defaults)"/,
  );
  assert.match(html, /id="back"/);
  assert.match(html, /id="add-wires"/);
  assert.match(html, /id="create-from-editor"/);
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-map > \.block-diagram-workspace \.block-diagram-viewport \{[^}]*height: 390px;/s);
});

asyncTest('empty-space context menu previews grouped wire ends', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.wires = [];
  definition.wireGroups = [{ wireGroupId: 'g1', connectionIds: ['a1', 'b1'] }];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  runInNewContext(
    'currentState = { harnesses: [definition] }; selectedHarnessKey = "h";',
    Object.assign(context, { definition }),
  );
  const graphic = context.renderRelationshipMap(definition, []);
  const viewport = descendants(
    graphic, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];

  viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });

  assert.equal(menu.children[0].textContent, 'Preview Routes');
  assert.equal(menu.children[0].disabled, false);
  menu.children[0].events.click();
  await Promise.resolve();
  assert.equal(calls[0].action, 'preview_routes');
  assert.equal(calls[0].payload.harnessId, 'h');
});

asyncTest('existing master background menu runs moved toolbar commands', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.wireGroups = [{ wireGroupId: 'g1', connectionIds: ['a1', 'b1'] }];
  context.window.confirm = () => true;
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true, notice: 'Cleared.' };
  };
  runInNewContext(
    'currentState = { harnesses: [definition] }; selectedHarnessKey = "h";',
    Object.assign(context, { definition }),
  );
  const graphic = context.renderRelationshipMap(definition, []);
  const viewport = descendants(
    graphic, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  const choose = (index) => {
    viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });
    menu.children[index].events.click();
  };

  choose(1);
  await Promise.resolve();
  assert.equal(calls[0].action, 'clear_preview');

  choose(2);
  assert.equal(calls[1].action, 'generate_solids');
  assert.equal(calls[1].payload.harnessId, 'h');
  assert.equal(calls[1].payload.replaceExisting, true);

  choose(3);
  assert.equal(calls[2].action, 'clear_solids');
  assert.equal(calls[2].payload.harnessId, 'h');

  choose(6);
  await Promise.resolve();
  assert.equal(calls[3].action, 'add_end');
  assert.equal(calls[3].payload.harnessId, 'h');

  choose(7);
  const materials = descendants(
    context.document.body,
    (node) => node.className?.split(' ').includes('material-options'),
  )[0];
  assert.equal(materials.open, true);
  assert.equal(
    descendants(materials, (node) => node.tag === 'h2')[0].textContent,
    'Harness Materials',
  );

  choose(8);
  const defaults = descendants(
    context.document.body,
    (node) => node.className === 'wire-options'
      && node.attributes['aria-label'] === 'Generation defaults',
  )[0];
  assert.equal(defaults.open, true);

  choose(9);
  const properties = descendants(
    context.document.body,
    (node) => node.className?.split(' ').includes('harness-properties'),
  )[0];
  assert.equal(properties.open, true);
  assert.equal(
    descendants(properties, (node) => node.tag === 'h2')[0].textContent,
    'Harness Properties',
  );
});

test('isolated junction renders without traces and retains filtering and hover', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways = [];
  definition.wires = [];
  definition.controls = [{
    controlId: 'c1', name: 'Routing Gate 01', kind: 'routing_gate', hasLinkedGeometry: true,
  }];
  definition.junctions = [{
    junctionId: 'j1', name: 'Junction 01', controlId: 'c1',
    pathwayRelationships: [],
  }];
  const calls = [];
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });

  const graphic = context.renderRelationshipMap(definition, []);
  let junction = descendants(
    graphic, (node) => node.className === 'relationship-junction-hub',
  )[0];
  assert.ok(junction);
  assert.equal(junction.children[0].textContent, 'Junction 01');
  assert.equal(junction.children[1].textContent, 'Unconnected junction');
  assert.equal(descendants(
    graphic, (node) => node.className === 'relationship-connector',
  ).length, 0);
  assert.equal(descendants(
    graphic, (node) => node.className === 'relationship-chain-link',
  ).length, 0);
  junction.events.mouseenter();
  assert.deepEqual(calls, [{ type: 'junction', id: 'j1' }]);

  const filter = descendants(graphic, (node) => node.attributes['aria-label']
    === 'Filter master relationship graphic')[0];
  filter.value = 'missing';
  filter.events.input();
  assert.ok(descendants(
    graphic, (node) => node.textContent === 'No relationships match this filter.',
  ).length);
  filter.value = 'junction 01';
  filter.events.input();
  junction = descendants(
    graphic, (node) => node.className === 'relationship-junction-hub',
  )[0];
  assert.ok(junction);
});

asyncTest('master graphic adds and renders one disconnected pathway end', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.connections.push({
    connectionId: 'loose-end', name: 'End B 001', hasLinkedGeometry: true,
  });
  definition.standaloneEnds = [{
    connectionId: 'loose-end', pathwayId: 'p', endpoint: 'end',
  }];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  runInNewContext(
    'currentState = { harnesses: [definition] }; selectedHarnessKey = "h";',
    Object.assign(context, { definition }),
  );

  const graphic = context.renderRelationshipMap(definition, []);
  const entries = descendants(
    graphic,
    (node) => node.className === 'relationship-end-entry'
      && node.dataset.connectionId === 'loose-end',
  );
  assert.equal(entries.length, 1);
  assert.deepEqual(entries[0].children.map((child) => child.textContent), [
    'End B 001', 'Disconnected',
  ]);
  assert.equal(entries[0].dataset.wireIds, '');
  assert.equal(entries[0].events.click, undefined);
  assert.ok(descendants(
    graphic,
    (node) => node.className === 'relationship-end-entry'
      && node.dataset.connectionId !== 'loose-end',
  ).every((entry) => entry.events.contextmenu === undefined));

  const viewport = descendants(
    graphic, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  const stage = descendants(
    graphic, (node) => node.className === 'block-diagram-stage',
  )[0];
  const zoom = descendants(
    graphic, (node) => node.className === 'block-diagram-zoom',
  )[0];
  descendants(graphic, (node) => node.title === 'Zoom in')[0].events.click();
  viewport.events.pointerdown({
    button: 1, pointerId: 7, clientX: 30, clientY: 30, preventDefault: () => {},
  });
  viewport.events.pointermove({ pointerId: 7, clientX: 55, clientY: 65 });
  viewport.events.pointerup({ pointerId: 7 });
  const renamedViewTransform = stage.style.transform;
  const renamedViewZoom = zoom.textContent;
  entries[0].children[1].textContent = 'Alternate metadata';
  let prevented = false;
  let stopped = false;
  entries[0].events.contextmenu({
    clientX: 60,
    clientY: 70,
    preventDefault: () => { prevented = true; },
    stopPropagation: () => { stopped = true; },
  });
  assert.equal(prevented, true);
  assert.equal(stopped, true);
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Rename', 'Delete']);
  menu.children[0].events.click();
  let input = descendants(entries[0], (node) => node.tag === 'input')[0];
  assert.equal(input.value, 'End B 001');
  assert.equal(input.attributes['aria-label'], 'End name');
  input.value = 'Bulkhead outlet';
  input.events.keydown({ key: 'Enter', preventDefault: () => {} });
  assert.equal(calls[0].action, 'rename_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'loose-end');
  assert.equal(calls[0].payload.name, 'Bulkhead outlet');
  definition.connections.find(
    (connection) => connection.connectionId === 'loose-end',
  ).name = 'Bulkhead outlet';
  const refreshed = context.renderRelationshipMap(definition, []);
  assert.equal(descendants(
    refreshed, (node) => node.className === 'block-diagram-stage',
  )[0].style.transform, renamedViewTransform);
  assert.equal(descendants(
    refreshed, (node) => node.className === 'block-diagram-zoom',
  )[0].textContent, renamedViewZoom);
  const otherHarness = context.renderRelationshipMap({ ...definition, harnessId: 'other' }, []);
  assert.notEqual(descendants(
    otherHarness, (node) => node.className === 'block-diagram-stage',
  )[0].style.transform, renamedViewTransform);

  entries[0].events.contextmenu({
    clientX: 60, clientY: 70, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[0].events.click();
  input = descendants(entries[0], (node) => node.tag === 'input')[0];
  input.value = 'Cancelled rename';
  input.events.keydown({ key: 'Escape', preventDefault: () => {} });
  assert.equal(calls.length, 1);

  entries[0].events.contextmenu({
    clientX: 60, clientY: 70, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[0].events.click();
  input = descendants(entries[0], (node) => node.tag === 'input')[0];
  input.value = 'Blurred rename';
  input.events.blur();
  assert.equal(calls[1].action, 'rename_standalone_end');
  assert.equal(calls[1].payload.name, 'Blurred rename');

  entries[0].events.contextmenu({
    clientX: 60, clientY: 70, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[1].events.click();
  await Promise.resolve();
  assert.equal(calls[2].action, 'remove_standalone_end');
  assert.equal(calls[2].payload.harnessId, 'h');
  assert.equal(calls[2].payload.connectionId, 'loose-end');

  viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });
  menu.children[2].events.click();
  await Promise.resolve();
  assert.equal(calls[3].action, 'add_end');
  assert.equal(calls[3].payload.harnessId, 'h');
});

test('connected wire-end Details opens and refreshes group route details', () => {
  const { context } = palette();
  const definition = harness();
  definition.wires = [];
  definition.standaloneEnds = [
    { connectionId: 'a1', pathwayId: 'p', endpoint: 'start' },
    { connectionId: 'b1', pathwayId: 'p', endpoint: 'end' },
  ];
  definition.wireGroups = [{
    wireGroupId: 'g1',
    connectionIds: ['a1', 'b1'],
    routeLegs: [{
      routeId: 'leg-1', label: 'Group 1 Leg 1', startConnectionId: 'a1',
      endConnectionId: 'b1', controlSteps: [], pathwayIds: ['p'],
    }],
  }];
  definition.wireGroupRouteError = null;
  let graphic = context.renderRelationshipMap(definition, []);
  let entries = descendants(
    graphic, (node) => node.className === 'relationship-end-entry',
  );
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  const contextEvent = {
    clientX: 60, clientY: 70, preventDefault() {}, stopPropagation() {},
  };

  entries[0].events.contextmenu(contextEvent);
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Details', 'Rename', 'Delete']);
  menu.children[0].events.click();
  let dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(dialog.open, true);
  assert.equal(descendants(dialog, (node) => node.tag === 'h2')[0].textContent, 'Wire Details');
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-member'),
  ).length, 2);
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('focused'),
  )[0].dataset.connectionId, entries[0].dataset.connectionId);

  const initialDialog = dialog;
  const initialGraphic = descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-graphic'),
  )[0];
  const memberRows = descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-member'),
  );
  const selectedRow = memberRows.find(
    (row) => row.dataset.connectionId !== entries[0].dataset.connectionId,
  );
  const selectedReference = selectedRow.querySelector('.member-reference');
  let redrawFrames = 0;
  context.window.requestAnimationFrame = (callback) => { redrawFrames += 1; callback(); };
  selectedReference.events.click();
  const replacementGraphic = descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-graphic'),
  )[0];

  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), initialDialog);
  assert.notEqual(replacementGraphic, initialGraphic);
  assert.equal(redrawFrames, 1);
  assert.equal(selectedRow.className.split(' ').includes('focused'), true);
  assert.equal(selectedReference.attributes['aria-pressed'], 'true');
  assert.equal(memberRows.find(
    (row) => row.dataset.connectionId === entries[0].dataset.connectionId,
  ).querySelector('.member-reference').attributes['aria-pressed'], 'false');
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('focused'),
  )[0].dataset.connectionId, selectedRow.dataset.connectionId);
  selectedReference.events.click();
  assert.equal(redrawFrames, 1);
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-graphic'),
  )[0], replacementGraphic);

  context.renderEditor(definition);
  dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(context.document.body.querySelectorAll('.wire-group-details-popup').length, 1);
  assert.equal(dialog.open, true);
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('focused'),
  )[0].dataset.connectionId, selectedRow.dataset.connectionId);

  context.closeWireGroupDetails();
  graphic = context.renderRelationshipMap(definition, []);
  entries = descendants(graphic, (node) => node.className === 'relationship-end-entry');
  const refreshedMenu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  entries[1].events.contextmenu(contextEvent);
  refreshedMenu.children[0].events.click();
  dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('focused'),
  )[0].dataset.connectionId, entries[1].dataset.connectionId);

  context.closeWireGroupDetails();
  definition.wireGroupRouteError = 'The connected ends are not reachable.';
  context.openWireGroupDetails(definition, 'g1', 'a1');
  dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.match(descendants(
    dialog, (node) => node.className === 'wire-group-route-error',
  )[0].textContent, /not reachable/);
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-graphic'),
  ).length, 0);
  const unavailableRows = descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-member'),
  );
  const unavailableSelection = unavailableRows.find(
    (row) => row.dataset.connectionId === 'b1',
  );
  unavailableSelection.querySelector('.member-reference').events.click();
  assert.equal(unavailableSelection.className.split(' ').includes('focused'), true);

  definition.wireGroupRouteError = null;
  context.renderEditor(definition);
  dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('focused'),
  )[0].dataset.connectionId, 'b1');

  definition.wireGroups = [];
  context.renderEditor(definition);
  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), undefined);
});

test('wire details sub-graphic shares one junction across a pigtail group', () => {
  const { context } = palette();
  const definition = harness();
  definition.wires = [];
  definition.pathways = ['p1', 'p2', 'p3'].map((pathwayId, index) => ({
    pathwayId, name: `Path ${index + 1}`, startName: '', endName: '', orderedControlIds: [],
  }));
  definition.connections = ['a', 'b', 'c'].map((connectionId) => ({
    connectionId, name: `End ${connectionId.toUpperCase()}`, hasLinkedGeometry: true,
  }));
  definition.standaloneEnds = [
    { connectionId: 'a', pathwayId: 'p1', endpoint: 'start' },
    { connectionId: 'b', pathwayId: 'p2', endpoint: 'end' },
    { connectionId: 'c', pathwayId: 'p3', endpoint: 'end' },
  ];
  definition.junctions = [{
    junctionId: 'j1', name: 'Shared junction', controlId: 'junction-control',
    pathwayRelationships: [
      { pathwayId: 'p1', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
      { pathwayId: 'p3', endpoint: 'start' },
    ],
  }];
  definition.wireGroups = [{
    wireGroupId: 'g1', connectionIds: ['a', 'b', 'c'], routeLegs: [{
      routeId: 'leg-1', label: 'Group 1 Leg 1', startConnectionId: 'a',
      endConnectionId: 'b', pathwayIds: ['p1', 'p2'],
      controlSteps: [{ controlId: 'junction-control', reversed: false }],
    }, {
      routeId: 'leg-2', label: 'Group 1 Leg 2', startConnectionId: null,
      endConnectionId: 'c', pathwayIds: ['p3'],
      controlSteps: [{ controlId: 'junction-control', reversed: false }],
    }],
  }];
  definition.wireGroupRouteError = null;

  context.openWireGroupDetails(definition, 'g1', 'a');
  const dialog = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('connection'),
  ).length, 3);
  assert.equal(descendants(
    dialog, (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.className.split(' ').includes('junction'),
  ).length, 1);
  assert.equal(descendants(dialog, (node) => node.className === 'wire-group-route-link').length, 6);
});

asyncTest('wire details background menu preserves Materials across state refresh', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  definition.wires = [];
  definition.standaloneEnds = [
    { connectionId: 'a1', pathwayId: 'p', endpoint: 'start' },
    { connectionId: 'b1', pathwayId: 'p', endpoint: 'end' },
  ];
  definition.wireGroups = [{
    wireGroupId: 'g1', connectionIds: ['a1', 'b1'], diameterMm: 1.5,
    materials: definition.materialDefaults,
    materialOverrides: {
      insulationMaterial: null, conductorMaterial: null, mainColor: null,
      appearance: null, stripes: null, manufacturer: null, partNumber: null, notes: null,
    },
    routeLegs: [{
      routeId: 'leg-1', label: 'Group 1 Leg 1', startConnectionId: 'a1',
      endConnectionId: 'b1', controlSteps: [], pathwayIds: ['p'],
    }],
  }];
  definition.wireGroupRouteError = null;
  context.send = async (action, payload) => {
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    requests.push({ action, payload });
    return { ok: true };
  };
  context.openWireGroupDetails(definition, 'g1', 'a1');
  const dialog = context.document.body.querySelector('.wire-group-details-popup');
  const content = dialog.querySelector('.wire-group-details-content');
  const menu = dialog.querySelector('.relationship-map-context-menu');
  const backgroundEvent = {
    target: content, clientX: 70, clientY: 80, preventDefault() {}, stopPropagation() {},
  };
  dialog.events.contextmenu(backgroundEvent);
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Materials', 'Properties']);
  assert.equal(menu.hidden, false);

  menu.hidden = true;
  const member = dialog.querySelector('.wire-group-details-member');
  dialog.events.contextmenu({ ...backgroundEvent, target: member });
  assert.equal(menu.hidden, true);
  const node = dialog.querySelector('.wire-group-details-node');
  dialog.events.contextmenu({ ...backgroundEvent, target: node });
  assert.equal(menu.hidden, true);

  dialog.events.contextmenu(backgroundEvent);
  menu.children[1].events.click();
  const properties = context.document.body.querySelector('.wire-group-properties');
  assert.equal(properties.open, true);
  assert.equal(descendants(properties, (item) => item.type === 'number').length, 1);
  properties.close();

  dialog.events.contextmenu(backgroundEvent);
  menu.children[0].events.click();
  const materials = context.document.body.querySelector('.material-options');
  assert.equal(materials.open, true);
  assert.equal(descendants(materials, (item) => item.type === 'number').length, 0);
  await descendants(materials, (item) => item.textContent === 'Apply')[0].events.click();
  assert.equal(materials.open, true);
  assert.equal(descendants(materials, (item) => item.attributes.role === 'alert')[0].textContent,
    'Applied.');

  context.renderEditor(definition);
  assert.equal(context.document.body.querySelector('.material-options'), materials);
  assert.equal(materials.open, true);
  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), dialog);

  const colorOverride = descendants(materials, (item) => item.type === 'checkbox')[0];
  const colorPicker = descendants(materials, (item) => item.type === 'color')[0];
  colorOverride.checked = true;
  colorOverride.events.change();
  colorPicker.value = '#112233';
  const form = descendants(materials, (item) => item.tag === 'form')[0];
  form.events.submit({ preventDefault() {} });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(materials.open, false);
  assert.equal(requests.length, 2);
  assert.equal(requests[1].payload.overrides.mainColor.red, 17);
  assert.equal(requests[1].payload.overrides.mainColor.green, 34);
  assert.equal(requests[1].payload.overrides.mainColor.blue, 51);
  context.renderEditor(definition);
  const refreshedDetails = context.document.body.querySelector('.wire-group-details-popup');
  assert.notEqual(refreshedDetails, dialog);
  assert.equal(refreshedDetails.open, true);
});

asyncTest('junction popup matches pathway styling and shows traversing wire members', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Branch', startName: '', endName: '', orderedControlIds: [],
  });
  definition.junctions = [
    { junctionId: 'j1', name: 'Intersection', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ] },
    { junctionId: 'j2', name: 'Owner', controlId: 'c2', pathwayRelationships: [
      { pathwayId: 'p2', endpoint: 'start' },
    ] },
  ];
  definition.wires[0].orderedPathwayIds = ['p', 'p2'];
  definition.wires[1].orderedPathwayIds = ['p', 'p2'];

  const rendered = context.renderRelationshipMap(definition, []);
  descendants(rendered, (node) => (
    node.className === 'relationship-junction-hub'
      && node.children[0].textContent === 'Intersection'
  ))[0].events.click();
  const dialog = context.document.body.querySelector('.junction-relationships-popup');
  const junctionSection = dialog.querySelector('[data-section="junction:j1"]');
  const relationshipSection = dialog.querySelector('[data-section="junction:j1:relationships"]');
  const occupancySection = dialog.querySelector('[data-section="junction:j1:occupancy"]');
  assert.equal(dialog.className, 'junction-relationships-popup');
  assert.ok(junctionSection.className.split(' ').includes('pathway-popup-entry'));
  assert.equal(junctionSection.open, true);
  assert.ok(!relationshipSection.open);
  assert.ok(!occupancySection.open);
  assert.match(junctionSection.children[0].children[1].textContent, /2 pathway endpoints · 2 wires/);
  const inputs = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(inputs.length, 1);
  assert.equal(inputs[0].value, 'Intersection');
  assert.equal(inputs[0].attributes['aria-label'], 'Junction Name');
  assert.equal(descendants(
    dialog, (node) => node.textContent === 'Junction Name',
  ).length, 0);
  inputs[0].value = 'Main Splice';
  inputs[0].events.change();
  assert.equal(calls[0].action, 'rename_junction');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.junctionId, 'j1');
  assert.equal(calls[0].payload.name, 'Main Splice');
  const relationshipRows = descendants(
    relationshipSection, (node) => node.className === 'member-row',
  );
  assert.equal(relationshipRows.length, 2);
  assert.equal(descendants(
    relationshipRows[0], (node) => node.className === 'member-reference',
  )[0].textContent, 'lower fuse box path · End B');
  assert.equal(descendants(
    dialog, (node) => ['Branch', 'Owner'].includes(node.textContent),
  ).length, 0);
  const wireRows = descendants(
    occupancySection, (node) => node.className === 'member-row',
  );
  assert.deepEqual(wireRows.map((row) => row.dataset.wireId), ['w1', 'w2']);
  assert.deepEqual(
    wireRows.map((row) => descendants(
      row, (node) => node.className === 'member-reference',
    )[0].textContent),
    ['Wire #001', 'Wire #002'],
  );
  context.window.confirm = () => true;
  descendants(relationshipRows[0], (node) => node.textContent === '×')[0].events.click();
  assert.equal(calls[1].action, 'remove_junction_relationship');
  assert.equal(calls[1].payload.pathwayId, 'p');
  runInNewContext(
    'currentState = { harnesses: [definition] }; selectedHarnessKey = "h";',
    Object.assign(context, { definition }),
  );
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  const add = descendants(dialog, (node) => node.textContent === '+ Add Relationship')[0];
  assert.ok(descendants(
    relationshipSection, (node) => node === add,
  ).length);
  assert.equal(descendants(
    occupancySection, (node) => node.textContent === '+ Add Relationship',
  ).length, 0);
  add.events.click();
  await Promise.resolve();

  assert.equal(calls.at(-1).action, 'add_junction_relationship');
  assert.equal(calls.at(-1).payload.junctionId, 'j1');
  definition.junctions[0].name = 'Updated Junction';
  context.renderEditor(definition);
  const refreshed = context.document.body.querySelector('.junction-relationships-popup');
  assert.equal(context.document.body.querySelectorAll('.junction-relationships-popup').length, 1);
  assert.equal(
    refreshed.querySelector('[data-section="junction:j1"]').children[0].children[0].textContent,
    'Updated Junction',
  );
});

test('junction popup reports when no procedural wires traverse it', () => {
  const { context } = palette();
  const definition = harness();
  definition.junctions = [{
    junctionId: 'j1', name: 'Intersection', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
    ],
  }];

  const rendered = context.renderRelationshipMap(definition, []);
  descendants(rendered, (node) => node.className === 'relationship-junction-hub')[0]
    .events.click();
  const dialog = context.document.body.querySelector('.junction-relationships-popup');
  const occupancySection = dialog.querySelector('[data-section="junction:j1:occupancy"]');
  assert.equal(descendants(
    occupancySection, (node) => node.textContent === 'No wires traverse this junction.',
  ).length, 1);
  assert.equal(descendants(
    occupancySection, (node) => node.className === 'member-row',
  ).length, 0);
});

asyncTest('junction relationship removal warns only for traversing wire pathways', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Branch', startName: '', endName: '', orderedControlIds: [],
  });
  definition.junctions = [{
    junctionId: 'j1', name: 'Intersection', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  }];
  definition.wires.forEach((wire) => { wire.orderedPathwayIds = ['p', 'p2']; });
  const confirmations = [];
  context.window.confirm = (message) => {
    confirmations.push(message);
    return confirmations.length > 1;
  };

  const rendered = context.renderRelationshipMap(definition, []);
  descendants(rendered, (node) => node.className === 'relationship-junction-hub')[0]
    .events.click();
  const dialog = context.document.body.querySelector('.junction-relationships-popup');
  const removes = descendants(dialog, (node) => node.textContent === '×');
  removes[0].events.click();
  await Promise.resolve();
  assert.equal(calls.length, 0);
  assert.match(confirmations[0], /3 wire pathways traverse/);

  removes[0].events.click();
  await Promise.resolve();
  assert.equal(calls[0].action, 'remove_junction_relationship');
  assert.equal(calls[0].payload.pathwayId, 'p');
});

test('branching topology renders each incident endpoint once', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push(
    { pathwayId: 'p2', name: 'Branch A', startName: '', endName: '', orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Branch B', startName: '', endName: '', orderedControlIds: [] },
  );
  definition.junctions = [{
    junctionId: 'j1', name: 'Intersection', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
      { pathwayId: 'p3', endpoint: 'start' },
    ],
  }];

  const rendered = context.renderRelationshipMap(definition, []);
  const overlay = descendants(
    rendered, (node) => node.className === 'relationship-topology-edges',
  )[0];

  assert.equal(descendants(
    rendered, (node) => node.className === 'relationship-pathway-hub',
  ).length, 3);
  assert.equal(descendants(
    rendered, (node) => node.className === 'relationship-junction-hub',
  ).length, 1);
  assert.equal(descendants(
    overlay, (node) => node.className === 'structural-trace',
  ).length, 3);
});

test('master topology focus follows complete wire routes and clears transiently', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push(
    { pathwayId: 'p2', name: 'Continuation', startName: '', endName: '', orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Unoccupied', startName: '', endName: '', orderedControlIds: [] },
  );
  definition.junctions = [{
    junctionId: 'j1', name: 'Intersection', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  }];
  definition.wires.forEach((wire) => { wire.orderedPathwayIds = ['p', 'p2']; });

  const rendered = context.renderRelationshipMap(definition, []);
  const pathwayHubs = descendants(
    rendered, (node) => node.className === 'relationship-pathway-hub',
  );
  const nodes = descendants(
    rendered, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  );
  const occupiedHub = pathwayHubs.find((hub) => hub.children[0].textContent === 'lower fuse box path');
  occupiedHub.events.mouseenter();
  assert.equal(rendered.className.includes('relationship-focus-active'), true);
  assert.equal(nodes.find((node) => node.dataset.pathwayId === 'p3')
    .className.includes('relationship-focus-dimmed'), true);
  assert.ok(nodes.filter((node) => node.dataset.pathwayId !== 'p3')
    .every((node) => node.className.includes('relationship-focus-match')));
  occupiedHub.events.mouseleave();
  assert.equal(rendered.className.includes('relationship-focus-active'), false);
  assert.equal(occupiedHub.className.includes('relationship-focus-source'), false);
  assert.ok(nodes.every((node) => !node.className.includes('relationship-focus-dimmed')));

  const endEntry = descendants(
    rendered, (node) => node.className === 'relationship-end-entry',
  ).find((entry) => entry.dataset.wireIds === 'w1');
  endEntry.events.focus();
  const traces = descendants(
    rendered, (node) => node.className?.split(' ').includes('wire-trace'),
  );
  assert.ok(traces.filter((trace) => trace.dataset.wireId === 'w1')
    .every((trace) => trace.className.includes('relationship-focus-match')));
  assert.ok(traces.filter((trace) => trace.dataset.wireId === 'w2')
    .every((trace) => trace.className.includes('relationship-focus-dimmed')));
  endEntry.events.blur();
  assert.equal(rendered.className.includes('relationship-focus-active'), false);
});

test('topology edges use bounded adaptive lanes and counted bundles', () => {
  const { context } = palette();
  const definition = harness();
  const edge = {
    sourceId: 'pathway:p', targetId: 'junction:j1',
    junction: { junctionId: 'j1' }, relationship: { pathwayId: 'p', endpoint: 'end' },
  };
  const route = {
    kind: 'orthogonal', d: 'M 0 20 L 0 0 L 100 0 L 100 40',
    points: [
      { x: 0, y: 20 }, { x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 40 },
    ],
    sourcePort: { id: 'edge:source', side: 'top' },
    targetPort: { id: 'edge:target', side: 'top' },
  };
  const fiveWires = [
    ...definition.wires,
    { ...definition.wires[0], wireId: 'w4' },
    { ...definition.wires[0], wireId: 'w5' },
  ];
  const lanes = context.renderTopologyEdge(edge, route, fiveWires);
  assert.equal(lanes.dataset.renderMode, 'lanes');
  const laneTraces = descendants(
    lanes, (node) => node.className?.split(' ').includes('relationship-wire-lane'),
  );
  assert.deepEqual(laneTraces.map((lane) => lane.dataset.laneOffset), [
    '-8', '-4', '0', '4', '8',
  ]);
  assert.deepEqual(laneTraces.map((lane) => lane.attributes['data-source-x']), [
    '-8', '-4', '0', '4', '8',
  ]);
  assert.ok(laneTraces.every((lane) => lane.attributes.transform === undefined));

  const sixWires = [
    ...fiveWires,
    { ...definition.wires[0], wireId: 'w6', materials: {
      ...definition.materialDefaults, mainColor: { name: 'Red', hex: '#cc1122' },
    } },
  ];
  const bundle = context.renderTopologyEdge(edge, route, sixWires);
  assert.equal(bundle.dataset.renderMode, 'bundle');
  assert.equal(descendants(
    bundle, (node) => node.className?.split(' ').includes('relationship-wire-lane'),
  ).length, 0);
  const bundleTrace = descendants(
    bundle, (node) => node.className?.split(' ').includes('relationship-wire-bundle'),
  )[0];
  assert.equal(bundleTrace.attributes.stroke, '#526f85');
  assert.equal(descendants(
    bundle, (node) => node.className === 'relationship-wire-count',
  )[0].children[1].textContent, '×6');
  const sharedColorBundle = context.renderTopologyEdge(
    edge,
    route,
    [...fiveWires, { ...definition.wires[0], wireId: 'w6' }],
  );
  assert.equal(descendants(
    sharedColorBundle,
    (node) => node.className?.split(' ').includes('relationship-wire-bundle'),
  )[0].attributes.stroke, '#202020');

  const empty = context.renderTopologyEdge(edge, route, []);
  assert.equal(empty.dataset.renderMode, 'structure');
  assert.equal(descendants(empty, (node) => node.className === 'wire-trace').length, 0);
  const port = context.renderTopologyPort({
    id: 'edge:source', nodeId: 'pathway:p', side: 'right',
    point: { x: 100, y: 40 }, wires: fiveWires,
  });
  assert.equal(port.attributes.width, '24');
  assert.equal(port.attributes.height, '24');
  assert.equal(port.dataset.portId, 'edge:source');
  assert.equal(port.dataset.wireIds, 'w1 w2 w3 w4 w5');
});

asyncTest('pathway node context menu adds a refine to that pathway', async () => {
  const { context, calls } = palette();
  const definition = harness();
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  const graphic = context.renderRelationshipMap(definition, []);
  const workspace = descendants(
    graphic,
    (node) => node.className === 'block-diagram-workspace',
  )[0];
  const hub = descendants(
    workspace,
    (node) => node.className === 'relationship-pathway-hub',
  )[0];
  const menu = descendants(
    workspace,
    (node) => node.className === 'relationship-map-context-menu',
  )[0];
  let prevented = false;
  let stopped = false;

  hub.events.contextmenu({
    clientX: 120,
    clientY: 140,
    preventDefault: () => { prevented = true; },
    stopPropagation: () => { stopped = true; },
  });

  assert.equal(prevented, true);
  assert.equal(stopped, true);
  assert.equal(menu.hidden, false);
  assert.equal(menu.children[0].textContent, 'Add refine point');
  const nestedMenuTarget = new Element('span');
  menu.children[0].append(nestedMenuTarget);
  context.document.dispatchEvent({ type: 'mousedown', target: nestedMenuTarget });
  assert.equal(menu.hidden, false);
  let outsidePrevented = false;
  let outsideStopped = false;
  context.document.dispatchEvent({
    type: 'mousedown',
    target: workspace,
    preventDefault: () => { outsidePrevented = true; },
    stopPropagation: () => { outsideStopped = true; },
  });
  assert.equal(menu.hidden, true);
  assert.equal(outsidePrevented, false);
  assert.equal(outsideStopped, false);

  hub.events.contextmenu({
    clientX: 120,
    clientY: 140,
    preventDefault: () => {},
    stopPropagation: () => {},
  });
  menu.children[0].events.click();
  await Promise.resolve();
  assert.equal(menu.hidden, true);
  assert.equal(calls[0].action, 'add_pathway_refine');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.pathwayId, 'p');
});

asyncTest('pathway context menu deletes after confirmation and keeps cancellation local', async () => {
  const { context, calls } = palette();
  const definition = harness();
  context.window.confirm = () => false;
  const graphic = context.renderRelationshipMap(definition, []);
  const workspace = descendants(
    graphic, (node) => node.className === 'block-diagram-workspace',
  )[0];
  const hub = descendants(
    workspace, (node) => node.className === 'relationship-pathway-hub',
  )[0];
  const menu = descendants(
    workspace, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  hub.events.contextmenu({
    clientX: 120, clientY: 140, preventDefault: () => {}, stopPropagation: () => {},
  });
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Add refine point', 'Segment', 'Delete',
  ]);
  menu.children[2].events.click();
  await Promise.resolve();
  assert.equal(calls.length, 0);

  let warning = '';
  context.window.confirm = (message) => {
    warning = message;
    return true;
  };
  hub.events.contextmenu({
    clientX: 120, clientY: 140, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[2].events.click();
  await Promise.resolve();
  assert.match(warning, /Delete lower fuse box path/);
  assert.match(warning, /3 wires/);
  assert.match(warning, /undone in Fusion/);
  assert.equal(calls[0].action, 'remove_pathway');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.pathwayId, 'p');
});

asyncTest('junction context menu deletes after confirmation and keeps cancellation local', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Branch', startName: '', endName: '', orderedControlIds: [],
  });
  definition.junctions = [{
    junctionId: 'j1', name: 'Main junction', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  }];
  definition.wires[0].orderedPathwayIds = ['p', 'p2'];
  context.window.confirm = () => false;
  const graphic = context.renderRelationshipMap(definition, []);
  const workspace = descendants(
    graphic, (node) => node.className === 'block-diagram-workspace',
  )[0];
  const hub = descendants(
    workspace, (node) => node.className === 'relationship-junction-hub',
  )[0];
  const menu = descendants(
    workspace, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  hub.events.contextmenu({
    clientX: 120, clientY: 140, preventDefault: () => {}, stopPropagation: () => {},
  });
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Open junction configuration', 'Delete',
  ]);
  menu.children[1].events.click();
  await Promise.resolve();
  assert.equal(calls.length, 0);

  let warning = '';
  context.window.confirm = (message) => {
    warning = message;
    return true;
  };
  hub.events.contextmenu({
    clientX: 120, clientY: 140, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[1].events.click();
  await Promise.resolve();
  assert.match(warning, /Delete Main junction/);
  assert.match(warning, /pathways, wires, and neighboring junctions will be kept/);
  assert.match(warning, /undone in Fusion/);
  assert.equal(calls[0].action, 'remove_junction');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.junctionId, 'j1');
});

asyncTest('pathway context menu segments eligible controls and renders its junction', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.controls = [1, 2, 3].map((index) => ({
    controlId: `c${index}`, name: `Routing Gate 0${index}`, kind: 'routing_gate',
  }));
  definition.pathways[0].orderedControlIds = ['c1', 'c2', 'c3'];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  let graphic = context.renderRelationshipMap(definition, []);
  let workspace = descendants(
    graphic, (node) => node.className === 'block-diagram-workspace',
  )[0];
  let hub = descendants(
    workspace, (node) => node.className === 'relationship-pathway-hub',
  )[0];
  let menu = descendants(
    workspace, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  hub.events.contextmenu({
    clientX: 120, clientY: 140, preventDefault: () => {}, stopPropagation: () => {},
  });
  assert.equal(menu.children[1].textContent, 'Segment');
  assert.equal(menu.children[1].disabled, false);
  menu.children[1].events.click();
  await Promise.resolve();
  assert.equal(calls[0].action, 'segment_pathway');
  assert.equal(calls[0].payload.pathwayId, 'p');

  definition.pathways = [
    { ...definition.pathways[0], orderedControlIds: ['c1'] },
    { pathwayId: 'p2', name: 'lower fuse box path ext 1', startName: '',
      endName: 'CAN_BUS-ctrl', orderedControlIds: ['c3'] },
  ];
  definition.pathways[0].endName = '';
  definition.junctions = [{ junctionId: 'j1', name: 'Junction 01', controlId: 'c2',
    pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ] }];
  definition.wires.forEach((wire) => { wire.orderedPathwayIds = ['p', 'p2']; });
  graphic = context.renderRelationshipMap(definition, []);
  workspace = descendants(graphic, (node) => node.className === 'block-diagram-workspace')[0];
  const junction = descendants(
    workspace, (node) => node.className === 'relationship-junction-hub',
  )[0];
  const endLists = descendants(
    workspace, (node) => node.className?.startsWith('relationship-end-list'),
  );
  const connectors = descendants(
    workspace, (node) => node.className === 'relationship-connector',
  );
  const junctionLinks = descendants(
    workspace, (node) => node.className === 'relationship-topology-edges',
  );
  const pathwayGroup = descendants(
    workspace, (node) => node.className === 'relationship-pathway-group',
  )[0];
  assert.ok(junction);
  assert.equal(junction.children[0].textContent, 'Junction 01');
  assert.deepEqual(endLists.map((list) => [list.dataset.pathwayId, list.dataset.endpoint]), [
    ['p', 'start'], ['p', 'end'], ['p2', 'start'], ['p2', 'end'],
  ]);
  assert.deepEqual(endLists.map((list) => descendants(
    list, (node) => node.className === 'relationship-end-entry',
  ).length), [3, 0, 0, 3]);
  assert.equal(connectors.length, 4);
  assert.ok(connectors.every((connector) => descendants(
    connector, (node) => node.className === 'wire-trace',
  ).length === 3));
  assert.equal(junctionLinks.length, 1);
  assert.equal(descendants(
    junctionLinks[0], (node) => node.className === 'structural-trace',
  ).length, 2);
  assert.equal(descendants(
    junctionLinks[0], (node) => node.className?.split(' ').includes('wire-trace'),
  ).length, 6);
  assert.equal(pathwayGroup.style.gridTemplateColumns, [
    '210px', '32px', '154px', '32px', 'max-content',
  ].join(' '));
  assert.equal(pathwayGroup.style.width, undefined);
  junction.events.mouseenter();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'highlight_member');
  assert.equal(calls.at(-1).payload.memberType, 'junction');
  assert.equal(calls.at(-1).payload.memberId, 'j1');
});

test('Route Editor selects only reachable pathway-end headers and cancels elsewhere', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways = [
    { pathwayId: 'p1', name: 'Source path', startName: '', endName: '',
      orderedControlIds: [] },
    { pathwayId: 'p2', name: 'Middle path', startName: '', endName: '',
      orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Target path', startName: '', endName: '',
      orderedControlIds: [] },
    { pathwayId: 'p4', name: 'Disconnected path', startName: '', endName: '',
      orderedControlIds: [] },
  ];
  definition.connections = [
    { connectionId: 'source', name: 'End A 001', hasLinkedGeometry: true },
    { connectionId: 'target', name: 'End B 001', hasLinkedGeometry: true },
    { connectionId: 'isolated', name: 'End A 002', hasLinkedGeometry: true },
  ];
  definition.wires = [];
  definition.standaloneEnds = [
    { connectionId: 'source', pathwayId: 'p1', endpoint: 'start' },
    { connectionId: 'target', pathwayId: 'p3', endpoint: 'end' },
    { connectionId: 'isolated', pathwayId: 'p4', endpoint: 'start' },
  ];
  definition.junctions = [
    { junctionId: 'j1', name: 'Junction 1', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p1', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ] },
    { junctionId: 'j2', name: 'Junction 2', controlId: 'c2', pathwayRelationships: [
      { pathwayId: 'p2', endpoint: 'end' },
      { pathwayId: 'p3', endpoint: 'start' },
    ] },
  ];

  const graphic = context.renderRelationshipMap(definition, []);
  const endLists = descendants(
    graphic, (node) => node.className?.startsWith('relationship-end-list'),
  );
  const boundary = (pathwayId, endpoint) => endLists.find(
    (list) => list.dataset.pathwayId === pathwayId && list.dataset.endpoint === endpoint,
  );
  const source = boundary('p1', 'start').children[0];
  const target = boundary('p3', 'end').children[0];
  const isolated = boundary('p4', 'start').children[0];
  const empty = boundary('p1', 'end').children[0];
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  const contextEvent = {
    clientX: 80, clientY: 90, preventDefault: () => {}, stopPropagation: () => {},
  };

  empty.events.contextmenu(contextEvent);
  assert.equal(menu.children[0].textContent, 'Route Editor');
  assert.equal(menu.children[0].disabled, true);
  assert.equal(menu.children[0].title, 'Requires at least one end');

  boundary('p1', 'start').open = false;
  source.events.contextmenu(contextEvent);
  assert.equal(menu.children[0].disabled, false);
  menu.children[0].events.click();
  assert.ok(source.className.includes('wire-creation-source'));
  assert.ok(target.className.includes('wire-creation-target'));
  assert.ok(isolated.className.includes('wire-creation-unavailable'));

  let prevented = false;
  let stopped = false;
  context.document.dispatchEvent({
    type: 'click', button: 0, target,
    preventDefault: () => { prevented = true; },
    stopPropagation: () => { stopped = true; },
  });
  assert.equal(prevented, true);
  assert.equal(stopped, true);
  const dialog = context.document.body.querySelector('.create-wires-popup');
  assert.equal(dialog.open, true);
  assert.equal(dialog.attributes['aria-labelledby'], 'create-wires-title');

  const cancel = descendants(dialog, (node) => node.textContent === 'Cancel')[0];
  cancel.events.click();
  assert.equal(context.document.body.querySelector('.create-wires-popup'), undefined);

  source.events.contextmenu(contextEvent);
  menu.children[0].events.click();
  let escapePrevented = false;
  context.document.dispatchEvent({
    type: 'keydown', key: 'Escape', target: source,
    preventDefault: () => { escapePrevented = true; }, stopPropagation: () => {},
  });
  assert.equal(escapePrevented, true);
  assert.equal(source.className.includes('wire-creation-source'), false);

  source.events.contextmenu(contextEvent);
  menu.children[0].events.click();
  let outsidePrevented = false;
  context.document.dispatchEvent({
    type: 'click', button: 0, target: graphic,
    preventDefault: () => { outsidePrevented = true; }, stopPropagation: () => {},
  });
  assert.equal(outsidePrevented, true);
  assert.equal(source.className.includes('wire-creation-source'), false);
  assert.equal(context.document.body.querySelector('.create-wires-popup'), undefined);

  source.events.contextmenu(contextEvent);
  menu.children[0].events.click();
  context.renderEditor(definition);
  assert.equal(source.className.includes('wire-creation-source'), false);
  let staleListenerPrevented = false;
  context.document.dispatchEvent({
    type: 'click', button: 0, target: graphic,
    preventDefault: () => { staleListenerPrevented = true; }, stopPropagation: () => {},
  });
  assert.equal(staleListenerPrevented, false);
});

asyncTest('Route Editor popup interacts with loose ends and survives refreshes', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const definition = harness();
  definition.pathways = [
    { pathwayId: 'p1', name: 'Source path', startName: '', endName: '',
      orderedControlIds: [] },
    { pathwayId: 'p2', name: 'Target path', startName: '', endName: '',
      orderedControlIds: [] },
  ];
  definition.connections = [
    { connectionId: 'cross-a', name: 'End A 001', hasLinkedGeometry: true },
    { connectionId: 'cross-b', name: 'End B 001', hasLinkedGeometry: true },
    { connectionId: 'elsewhere-a', name: 'End A 002', hasLinkedGeometry: true },
    { connectionId: 'elsewhere-b', name: 'Other boundary', hasLinkedGeometry: true },
    { connectionId: 'loose-b', name: 'End B 002', hasLinkedGeometry: true },
  ];
  definition.wires = [
    { wireId: 'cross', wireNumber: '001', profileId: 'profile',
      startConnectionId: 'cross-a', endConnectionId: 'cross-b',
      orderedPathwayIds: ['p1', 'p2'] },
    { wireId: 'elsewhere', wireNumber: '002', profileId: 'profile',
      startConnectionId: 'elsewhere-a', endConnectionId: 'elsewhere-b',
      orderedPathwayIds: ['p1'] },
  ];
  definition.wires.forEach((wire) => {
    wire.materials = definition.materialDefaults;
    wire.materialOverrides = {
      insulationMaterial: null, conductorMaterial: null, mainColor: null,
      appearance: null, stripes: null, manufacturer: null, partNumber: null, notes: null,
    };
  });
  definition.standaloneEnds = [
    { connectionId: 'loose-b', pathwayId: 'p2', endpoint: 'end' },
  ];
  definition.junctions = [{
    junctionId: 'j1', name: 'Junction', controlId: 'c1', pathwayRelationships: [
      { pathwayId: 'p1', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  }];

  const graphic = context.renderRelationshipMap(definition, []);
  const boundary = (pathwayId, endpoint) => descendants(
    graphic,
    (node) => node.className?.startsWith('relationship-end-list')
      && node.dataset.pathwayId === pathwayId && node.dataset.endpoint === endpoint,
  )[0];
  const source = boundary('p1', 'start').children[0];
  const target = boundary('p2', 'end').children[0];
  const menu = descendants(
    graphic, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  source.events.contextmenu({
    clientX: 80, clientY: 90, preventDefault: () => {}, stopPropagation: () => {},
  });
  menu.children[0].events.click();
  context.document.dispatchEvent({
    type: 'click', button: 0, target, preventDefault: () => {}, stopPropagation: () => {},
  });

  let dialog = context.document.body.querySelector('.create-wires-popup');
  const heading = descendants(dialog, (node) => node.id === 'create-wires-title')[0];
  assert.equal(heading.textContent, 'Route Editor');
  let columns = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-column'),
  );
  let cards = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-end-card'),
  );
  assert.equal(columns.length, 3);
  assert.deepEqual(columns.map((column) => column.children[0].textContent), [
    'Source path · End A', 'Wire Assignments', 'Target path · End B',
  ]);
  assert.deepEqual(cards.map((card) => card.dataset.connectionId), [
    'elsewhere-a', 'loose-b',
  ]);
  assert.ok(cards.every((card) => card.children[1].textContent === 'Disconnected'));
  assert.deepEqual(cards.map((card) => [card.dataset.pathwayId, card.dataset.endpoint]), [
    ['p1', 'start'], ['p2', 'end'],
  ]);
  const center = descendants(
    dialog, (node) => node.className === 'create-wires-assignment-content',
  )[0];
  assert.equal(center.children.length, 0);
  assert.equal(cards[0].events.contextmenu, undefined);
  cards[0].events.mouseenter();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'highlight_member');
  assert.equal(calls.at(-1).payload.memberType, 'connection');
  assert.equal(calls.at(-1).payload.memberId, 'elsewhere-a');
  cards[0].events.mouseleave();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'clear_highlight');
  cards[1].events.mouseenter();
  await Promise.resolve();
  assert.equal(calls.at(-1).payload.memberId, 'loose-b');

  let prevented = false;
  let stopped = false;
  cards[1].events.contextmenu({
    clientX: 70,
    clientY: 80,
    preventDefault: () => { prevented = true; },
    stopPropagation: () => { stopped = true; },
  });
  assert.equal(prevented, true);
  assert.equal(stopped, true);
  let popupMenu = descendants(
    dialog, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  assert.deepEqual(popupMenu.children.map((item) => item.textContent), ['Rename', 'Delete']);
  popupMenu.children[0].events.click();
  let input = descendants(cards[1], (node) => node.tag === 'input')[0];
  assert.equal(input.value, 'End B 002');
  input.value = 'Bulkhead outlet';
  input.events.keydown({ key: 'Enter', preventDefault: () => {} });
  assert.equal(calls.some((call) => call.action === 'rename_standalone_end'), false);

  columns.forEach((column, index) => { column.scrollTop = (index + 1) * 17; });
  context.renderEditor(definition);
  dialog = context.document.body.querySelector('.create-wires-popup');
  assert.equal(dialog.open, true);
  columns = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-column'),
  );
  assert.deepEqual(columns.map((column) => column.scrollTop), [17, 34, 51]);
  cards = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-end-card'),
  );
  assert.deepEqual(cards.map((card) => card.children[0].textContent), [
    'End A 002', 'Bulkhead outlet',
  ]);

  cards[1].events.contextmenu({
    clientX: 70, clientY: 80, preventDefault: () => {}, stopPropagation: () => {},
  });
  popupMenu = descendants(
    dialog, (node) => node.className === 'relationship-map-context-menu',
  )[0];
  popupMenu.children[1].events.click();
  assert.equal(calls.some((call) => call.action === 'remove_standalone_end'), false);
  cards = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-end-card'),
  );
  assert.deepEqual(cards.map((card) => card.dataset.connectionId), ['elsewhere-a']);

  descendants(dialog, (node) => node.textContent === 'Cancel')[0].events.click();
  assert.equal(context.document.body.querySelector('.create-wires-popup'), undefined);

  const left = context.resolveWireCreationBoundary(
    definition, { pathwayId: 'p1', endpoint: 'start' },
  );
  const right = context.resolveWireCreationBoundary(
    definition, { pathwayId: 'p2', endpoint: 'end' },
  );
  context.openCreateWiresPopup(definition, left, right);
  dialog = context.document.body.querySelector('.create-wires-popup');
  cards = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-end-card'),
  );
  assert.equal(cards.find((card) => card.dataset.connectionId === 'loose-b').children[0].textContent,
    'End B 002');
  context.renderEditor({ ...definition, harnessId: 'other-harness' });
  assert.equal(context.document.body.querySelector('.create-wires-popup'), undefined);
});

asyncTest('Route Editor visually pairs dragged ends without mutating the harness', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const definition = harness();
  definition.pathways = [
    { pathwayId: 'left-path', name: 'Left path', startName: '', endName: '',
      orderedControlIds: [] },
    { pathwayId: 'right-path', name: 'Right path', startName: '', endName: '',
      orderedControlIds: [] },
  ];
  definition.connections = [
    { connectionId: 'left-1', name: 'Left 1', hasLinkedGeometry: true },
    { connectionId: 'left-2', name: 'Left 2', hasLinkedGeometry: true },
    { connectionId: 'left-3', name: 'Left 3', hasLinkedGeometry: true },
    { connectionId: 'right-1', name: 'Right 1', hasLinkedGeometry: true },
    { connectionId: 'right-2', name: 'Right 2', hasLinkedGeometry: true },
  ];
  definition.wires = [];
  definition.junctions = [];
  definition.standaloneEnds = [
    ...['left-1', 'left-2', 'left-3'].map((connectionId) => ({
      connectionId, pathwayId: 'left-path', endpoint: 'start',
    })),
    ...['right-1', 'right-2'].map((connectionId) => ({
      connectionId, pathwayId: 'right-path', endpoint: 'end',
    })),
  ];
  const left = context.resolveWireCreationBoundary(
    definition, { pathwayId: 'left-path', endpoint: 'start' },
  );
  const right = context.resolveWireCreationBoundary(
    definition, { pathwayId: 'right-path', endpoint: 'end' },
  );
  context.openCreateWiresPopup(definition, left, right);

  const dialog = () => context.document.body.querySelector('.create-wires-popup');
  const center = () => descendants(
    dialog(), (node) => node.className === 'create-wires-assignment-content',
  )[0];
  const lists = () => descendants(
    dialog(), (node) => node.className === 'create-wires-end-list',
  );
  const cards = () => descendants(
    dialog(), (node) => node.className?.split(' ').includes('create-wires-end-card'),
  );
  const card = (connectionId, location) => cards().find(
    (candidate) => candidate.dataset.connectionId === connectionId
      && candidate.dataset.assignmentLocation === location,
  );
  const rows = () => descendants(
    center(), (node) => node.className === 'create-wires-assignment-row',
  );
  const bounds = (leftEdge, top, width, height) => ({
    left: leftEdge, top, right: leftEdge + width, bottom: top + height, width, height,
    x: leftEdge, y: top, toJSON() { return {}; },
  });
  const prepareSurfaces = () => {
    center().getBoundingClientRect = () => bounds(250, 100, 400, 400);
    lists()[0].getBoundingClientRect = () => bounds(0, 100, 200, 400);
    lists()[1].getBoundingClientRect = () => bounds(700, 100, 200, 400);
  };
  const drag = (item, x, y, inspectMarker = () => {}) => {
    item.setPointerCapture = () => {};
    item.hasPointerCapture = () => true;
    item.releasePointerCapture = () => {};
    const event = (clientX, clientY) => ({
      button: 0, pointerId: 1, clientX, clientY,
      target: { closest: () => null }, preventDefault() {},
    });
    item.events.pointerdown(event(30, 120));
    item.events.pointermove(event(x, y));
    inspectMarker();
    item.events.pointerup(event(x, y));
  };

  prepareSurfaces();
  drag(card('left-1', 'pool'), 300, 140, () => {
    assert.equal(center().dataset.drop, 'empty');
    assert.equal(center().dataset.dropSide, 'left');
  });
  assert.deepEqual(rows().map((row) => row.dataset.complete), [undefined]);
  assert.equal(card('left-1', 'center').dataset.assignmentSide, 'left');

  prepareSurfaces();
  rows()[0].getBoundingClientRect = () => bounds(250, 120, 400, 50);
  drag(card('left-2', 'pool'), 300, 190);
  assert.equal(card('left-1', 'pool').dataset.assignmentSide, 'left');
  assert.equal(card('left-2', 'center').dataset.assignmentSide, 'left');
  assert.deepEqual(
    lists()[0].children.filter((child) => child.dataset?.connectionId)
      .map((child) => child.dataset.connectionId),
    ['left-1', 'left-3'],
  );

  prepareSurfaces();
  const pendingRightSlot = descendants(
    rows()[0], (node) => node.className === 'create-wires-assignment-slot right',
  )[0];
  pendingRightSlot.getBoundingClientRect = () => bounds(460, 120, 180, 50);
  drag(card('right-1', 'pool'), 500, 450, () => {
    assert.equal(pendingRightSlot.dataset.drop, 'slot');
    assert.equal(pendingRightSlot.dataset.dropSide, 'right');
  });
  assert.equal(rows()[0].dataset.complete, 'true');
  assert.equal(descendants(
    rows()[0], (node) => node.className === 'create-wires-assignment-connector',
  ).length, 1);
  assert.equal(calls.every((call) => call.action === 'clear_highlight'), true);
  const pairedRight = card('right-1', 'center');
  assert.equal(pairedRight.children[1].textContent, 'Connected');
  assert.equal(pairedRight.children[1].hidden, false);
  pairedRight.events.mouseenter();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'highlight_member');
  assert.equal(calls.at(-1).payload.memberId, 'right-1');
  pairedRight.events.contextmenu({
    clientX: 500, clientY: 140, preventDefault() {}, stopPropagation() {},
  });
  const popupMenu = descendants(
    dialog(), (node) => node.className === 'relationship-map-context-menu',
  )[0];
  assert.deepEqual(popupMenu.children.map((item) => item.textContent), ['Rename', 'Delete']);

  prepareSurfaces();
  drag(card('left-2', 'center'), 750, 130);
  assert.equal(card('left-2', 'center').dataset.assignmentSide, 'left');

  prepareSurfaces();
  const leftPoolCards = lists()[0].children.filter((child) => child.dataset?.connectionId);
  leftPoolCards[0].getBoundingClientRect = () => bounds(0, 100, 200, 40);
  leftPoolCards[1].getBoundingClientRect = () => bounds(0, 180, 200, 40);
  drag(card('left-2', 'center'), 100, 160);
  assert.deepEqual(
    lists()[0].children.filter((child) => child.dataset?.connectionId)
      .map((child) => child.dataset.connectionId),
    ['left-1', 'left-2', 'left-3'],
  );
  assert.equal(rows()[0].dataset.complete, undefined);
  assert.equal(card('right-1', 'center').dataset.assignmentSide, 'right');

  prepareSurfaces();
  const pendingLeftSlot = descendants(
    rows()[0], (node) => node.className === 'create-wires-assignment-slot left',
  )[0];
  pendingLeftSlot.getBoundingClientRect = () => bounds(270, 120, 180, 50);
  drag(card('left-3', 'pool'), 350, 140);
  assert.equal(rows()[0].dataset.complete, 'true');

  prepareSurfaces();
  const remainingLeftCards = lists()[0].children.filter(
    (child) => child.dataset?.connectionId,
  );
  remainingLeftCards.forEach((item, index) => {
    item.getBoundingClientRect = () => bounds(0, 100 + index * 50, 200, 40);
  });
  drag(card('left-3', 'center'), 100, 450);
  assert.deepEqual(
    lists()[0].children.filter((child) => child.dataset?.connectionId)
      .map((child) => child.dataset.connectionId),
    ['left-1', 'left-2', 'left-3'],
  );
  assert.equal(card('right-1', 'center').dataset.assignmentSide, 'right');

  prepareSurfaces();
  const restoredPendingLeftSlot = descendants(
    rows()[0], (node) => node.className === 'create-wires-assignment-slot left',
  )[0];
  restoredPendingLeftSlot.getBoundingClientRect = () => bounds(270, 120, 180, 50);
  drag(card('left-3', 'pool'), 350, 140);
  assert.equal(rows()[0].dataset.complete, 'true');

  prepareSurfaces();
  rows()[0].getBoundingClientRect = () => bounds(250, 120, 400, 50);
  drag(card('left-1', 'pool'), 300, 450);
  assert.equal(rows().length, 2);
  assert.equal(rows()[0].dataset.complete, 'true');
  assert.equal(rows()[1].dataset.complete, undefined);
  assert.equal(card('left-1', 'center').parentElement.className,
    'create-wires-assignment-slot left');

  prepareSurfaces();
  const secondPendingRightSlot = descendants(
    rows()[1], (node) => node.className === 'create-wires-assignment-slot right',
  )[0];
  secondPendingRightSlot.getBoundingClientRect = () => bounds(460, 180, 180, 50);
  drag(card('right-2', 'pool'), 500, 450, () => {
    assert.equal(secondPendingRightSlot.dataset.drop, 'slot');
  });
  assert.equal(rows().length, 2);
  assert.equal(rows()[0].dataset.complete, 'true');
  assert.equal(rows()[1].dataset.complete, 'true');
  assert.equal(card('right-2', 'center').parentElement.parentElement.dataset.assignmentRow, '1');

  prepareSurfaces();
  card('left-1', 'center').getBoundingClientRect = () => bounds(270, 180, 180, 40);
  drag(card('left-3', 'center'), 350, 200, () => {
    assert.equal(card('left-1', 'center').dataset.drop, 'swap');
    assert.equal(card('left-1', 'center').dataset.dropSide, 'left');
  });
  assert.deepEqual(rows().map((row) => [
    row.children[0].children[0].dataset.connectionId,
    row.children[2].children[0].dataset.connectionId,
  ]), [['left-1', 'right-1'], ['left-3', 'right-2']]);

  prepareSurfaces();
  card('right-2', 'center').getBoundingClientRect = () => bounds(460, 180, 180, 40);
  drag(card('right-1', 'center'), 550, 200, () => {
    assert.equal(card('right-2', 'center').dataset.drop, 'swap');
    assert.equal(card('right-2', 'center').dataset.dropSide, 'right');
  });
  assert.deepEqual(rows().map((row) => [
    row.children[0].children[0].dataset.connectionId,
    row.children[2].children[0].dataset.connectionId,
  ]), [['left-1', 'right-2'], ['left-3', 'right-1']]);

  prepareSurfaces();
  card('left-3', 'center').getBoundingClientRect = () => bounds(270, 180, 180, 40);
  card('right-2', 'center').getBoundingClientRect = () => bounds(460, 120, 180, 40);
  drag(card('left-1', 'center'), 550, 140, () => {
    assert.equal(card('right-2', 'center').dataset.drop, undefined);
  });
  assert.deepEqual(rows().map((row) => row.children[0].children[0].dataset.connectionId), [
    'left-1', 'left-3',
  ]);

  prepareSurfaces();
  card('left-1', 'center').getBoundingClientRect = () => bounds(270, 120, 180, 40);
  drag(card('left-1', 'center'), 350, 140);
  assert.deepEqual(rows().map((row) => row.children[0].children[0].dataset.connectionId), [
    'left-1', 'left-3',
  ]);

  prepareSurfaces();
  drag(card('left-1', 'center'), 500, 450);
  assert.deepEqual(rows().map((row) => row.children[0].children[0].dataset.connectionId), [
    'left-1', 'left-3',
  ]);

  definition.connections.find((connection) => connection.connectionId === 'right-1').name =
    'Renamed Right';
  context.renderEditor(definition);
  assert.equal(rows().length, 2);
  assert.equal(rows()[0].dataset.complete, 'true');
  assert.equal(rows()[1].dataset.complete, 'true');
  assert.equal(card('right-1', 'center').children[0].textContent, 'Renamed Right');
  assert.deepEqual(rows().map((row) => [
    row.children[0].children[0].dataset.connectionId,
    row.children[2].children[0].dataset.connectionId,
  ]), [['left-1', 'right-2'], ['left-3', 'right-1']]);

  descendants(dialog(), (node) => node.textContent === 'Cancel')[0].events.click();
  context.openCreateWiresPopup(
    definition,
    context.resolveWireCreationBoundary(
      definition, { pathwayId: 'left-path', endpoint: 'start' },
    ),
    context.resolveWireCreationBoundary(
      definition, { pathwayId: 'right-path', endpoint: 'end' },
    ),
  );
  assert.equal(rows().length, 0);
  assert.equal(cards().every((item) => item.dataset.assignmentLocation === 'pool'), true);
});

test('Route Editor retains only the newly exposed pending row when a pair is broken', () => {
  const { context } = palette();
  const assignments = {
    pools: { left: [], right: [] },
    rows: [
      {
        left: { connectionId: 'paired-left', returnIndex: 0 },
        right: { connectionId: 'paired-right', returnIndex: 0 },
      },
      { left: { connectionId: 'old-pending', returnIndex: 0 }, right: null },
    ],
  };

  context.unassignWireCreationRowItem(assignments, 'left', 0, 0);

  assert.deepEqual(assignments.pools.left, ['old-pending', 'paired-left']);
  assert.deepEqual(assignments.rows, [
    { left: null, right: { connectionId: 'paired-right', returnIndex: 0 } },
  ]);
});

test('Route Editor opens persisted cross-boundary groups as center rows', () => {
  const { context } = palette();
  const assignments = context.initialWireCreationAssignments({
    left: [
      { connectionId: 'left-paired', wireGroupId: 'group-1' },
      { connectionId: 'left-offscreen', wireGroupId: 'group-2' },
      { connectionId: 'left-loose', wireGroupId: '' },
    ],
    right: [
      { connectionId: 'right-paired', wireGroupId: 'group-1' },
      { connectionId: 'right-loose', wireGroupId: '' },
    ],
  });

  assert.deepEqual(assignments.pools.left, ['left-offscreen', 'left-loose']);
  assert.deepEqual(assignments.pools.right, ['right-loose']);
  assert.deepEqual(JSON.parse(JSON.stringify(assignments.rows)), [{
    left: { connectionId: 'left-paired', returnIndex: 0 },
    right: { connectionId: 'right-paired', returnIndex: 0 },
  }]);
  assert.equal(assignments.initialPartners['left-paired'], 'right-paired');
  assert.equal(assignments.initialPartners['right-paired'], 'left-paired');
});

asyncTest('Route Editor Save submits complete staged changes in one transaction', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const assignments = {
    pools: { left: [], right: [] },
    rows: [
      {
        left: { connectionId: 'left-1', returnIndex: 0 },
        right: { connectionId: 'right-2', returnIndex: 0 },
      },
      { left: { connectionId: 'incomplete', returnIndex: 0 }, right: null },
    ],
    initialPartners: { 'left-1': 'right-1', 'right-1': 'left-1' },
    movedConnectionIds: { 'left-1': true },
    renames: { 'right-2': 'Renamed', deleted: 'Ignored rename' },
    deletedConnectionIds: { deleted: true },
  };
  const save = { disabled: false };

  await context.saveWireCreationAssignments(
    { harnessId: 'h' },
    {
      left: { pathway: { pathwayId: 'left-path' }, endpoint: 'start' },
      right: { pathway: { pathwayId: 'right-path' }, endpoint: 'end' },
    },
    assignments,
    save,
  );

  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'save_wire_editor');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].payload)), {
    harnessId: 'h',
    leftBoundary: { pathwayId: 'left-path', endpoint: 'start' },
    rightBoundary: { pathwayId: 'right-path', endpoint: 'end' },
    pairings: [{ leftConnectionId: 'left-1', rightConnectionId: 'right-2' }],
    detachedConnectionIds: ['left-1'],
    renames: [{ connectionId: 'right-2', name: 'Renamed' }],
    deletedConnectionIds: ['deleted'],
  });
});

test('Route Editor swaps occupied same-side members while partners stay in place', () => {
  const { context } = palette();
  const leftA = { connectionId: 'left-a', returnIndex: 0 };
  const leftB = { connectionId: 'left-b', returnIndex: 1 };
  const rightA = { connectionId: 'right-a', returnIndex: 0 };
  const assignments = {
    pools: { left: [], right: [] },
    rows: [
      { left: leftA, right: rightA },
      { left: leftB, right: null },
    ],
  };

  context.swapWireCreationRowItems(assignments, 'left', 0, 1);
  assert.deepEqual(assignments.rows, [
    { left: leftB, right: rightA },
    { left: leftA, right: null },
  ]);

  context.swapWireCreationRowItems(assignments, 'right', 0, 1);
  context.swapWireCreationRowItems(assignments, 'left', 0, 0);
  assert.deepEqual(assignments.rows, [
    { left: leftB, right: rightA },
    { left: leftA, right: null },
  ]);
});
