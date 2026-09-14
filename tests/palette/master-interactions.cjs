/** Focused palette regression suite. */
/* global require, __dirname */
const { Element, assert, asyncTest, descendants, harness, join, palette, readFileSync, runInNewContext, test } = require('./support.cjs');

asyncTest('empty master graphic owns Add pathway and Add junction', async () => {
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
    ['Add pathway', 'Add end', 'Add junction'],
  );
  menu.children[0].events.click();
  await Promise.resolve();
  assert.equal(menu.hidden, true);
  assert.equal(calls[0].action, 'add_pathway');
  assert.equal(calls[0].payload.harnessId, 'h');

  viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });
  menu.children[2].events.click();
  await Promise.resolve();
  assert.equal(menu.hidden, true);
  assert.equal(calls[1].action, 'add_junction');
  assert.equal(calls[1].payload.harnessId, 'h');

  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  assert.doesNotMatch(html, /id="add-pathway"/);
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-map > \.block-diagram-workspace \.block-diagram-viewport \{[^}]*height: 390px;/s);
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
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Delete']);
  menu.children[0].events.click();
  await Promise.resolve();
  assert.equal(calls[0].action, 'remove_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'loose-end');

  viewport.events.contextmenu({ clientX: 80, clientY: 90, preventDefault: () => {} });
  menu.children[1].events.click();
  await Promise.resolve();
  assert.equal(calls[1].action, 'add_end');
  assert.equal(calls[1].payload.harnessId, 'h');
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
    kind: 'direct', d: 'M 0 20 C 50 20, 50 40, 100 40',
    points: [{ x: 0, y: 20 }, { x: 100, y: 40 }],
  };
  const fiveWires = [
    ...definition.wires,
    { ...definition.wires[0], wireId: 'w4' },
    { ...definition.wires[0], wireId: 'w5' },
  ];
  const lanes = context.renderTopologyEdge(edge, route, fiveWires);
  assert.equal(lanes.dataset.renderMode, 'lanes');
  assert.deepEqual(descendants(
    lanes, (node) => node.className?.split(' ').includes('relationship-wire-lane'),
  ).map((lane) => lane.dataset.laneOffset), ['-8', '-4', '0', '4', '8']);

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
    nodeId: 'pathway:p', side: 'right', point: { x: 100, y: 40 },
    wireIds: new Set(fiveWires.map((wire) => wire.wireId)), maximumLaneCount: 5,
  });
  assert.equal(port.attributes.height, '24');
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
  assert.match(warning, /1 wire/);
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

test('Create Wires selects only reachable pathway-end headers and cancels elsewhere', () => {
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
  assert.equal(menu.children[0].textContent, 'Create Wires');
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

  const close = descendants(dialog, (node) => node.textContent === 'Close')[0];
  close.events.click();
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

test('Create Wires popup lists contextually disconnected ends around an empty center', () => {
  const { context } = palette();
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

  const dialog = context.document.body.querySelector('.create-wires-popup');
  const columns = descendants(
    dialog, (node) => node.className?.split(' ').includes('create-wires-column'),
  );
  const cards = descendants(
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
});
