const {
  assert, descendants, harness, palette, test,
} = require('./support.cjs');

test('group-only palette state drives pathway occupancy', () => {
  const { context } = palette();
  const definition = harness();

  assert.equal(definition.schemaVersion, 14);
  assert.equal(Object.hasOwn(definition, 'wires'), false);
  assert.equal(Object.hasOwn(definition, 'profiles'), false);
  assert.deepEqual(
    Array.from(context.relationshipPathwayGroups(definition, 'p'), (group) => group.wireGroupId),
    ['g1', 'g2', 'g3'],
  );
});

test('group-only palette resolves standalone ends to their groups', () => {
  const { context } = palette();
  const definition = harness();
  const connections = new Map(
    definition.connections.map((connection) => [connection.connectionId, connection]),
  );

  const ends = context.relationshipEndGroups(definition, 'p', 'start', connections);

  assert.deepEqual(Array.from(ends, (end) => end.wireGroupId), ['g1', 'g2', 'g3']);
  assert.ok(ends.every((end) => end.groups.length === 1));
});

test('master diagram survives a host refresh that adds a pathway', () => {
  const { context } = palette();
  const definition = harness();

  context.renderEditor(definition);
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).length, 1);

  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  context.renderEditor(definition);

  assert.equal(context.ui.editor.children.length, 1);
  assert.equal(context.ui.editor.children[0].dataset.section, 'master-relationship-graphic');
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).length, 2);
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className === 'relationship-topology-edges',
  ).length, 1);
});

test('master diagram can reorganize and fit for its resized viewport', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  definition.junctions.push({
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
    pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  });

  const diagram = context.renderRelationshipMap(definition);
  const workspace = descendants(
    diagram, (node) => node.className === 'block-diagram-workspace',
  )[0];
  const toolbar = descendants(
    workspace, (node) => node.className === 'block-diagram-toolbar',
  )[0];
  const viewport = descendants(
    workspace, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const stack = descendants(
    workspace, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  const reorganize = toolbar.children[0];

  assert.equal(reorganize.textContent, 'Reorganize');
  assert.equal(reorganize.title, 'Reorganize and fit diagram');
  viewport.clientWidth = 200;
  viewport.clientHeight = 800;
  reorganize.events.click();

  assert.equal(stack.dataset.diagramFlow, 'vertical');
  const organizedTransform = workspace.children[1].children[0].style.transform;
  assert.match(organizedTransform, /scale\(/);

  context.renderEditor(definition);
  const refreshedStack = descendants(
    context.ui.editor, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  const refreshedStage = descendants(
    context.ui.editor, (node) => node.className === 'block-diagram-stage',
  )[0];
  assert.equal(refreshedStack.dataset.diagramFlow, 'vertical');
  assert.equal(refreshedStage.style.transform, organizedTransform);
});

test('master relationship traces attach to visible pathway ends', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  definition.junctions.push({
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
    pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  });

  const diagram = context.renderRelationshipMap(definition);
  const ports = descendants(
    diagram, (node) => node.className === 'relationship-topology-port',
  );
  const pathwayPorts = ports.filter((port) => port.dataset.nodeId.startsWith('pathway:'));

  assert.deepEqual(
    Array.from(pathwayPorts, (port) => [port.dataset.nodeId, port.dataset.side]).sort(),
    [['pathway:p', 'right'], ['pathway:p2', 'left']],
  );
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
  const interpolation = context.document.body.querySelector('.wire-options');
  assert.equal(interpolation.open, true);
  assert.equal(interpolation.attributes['aria-label'], 'Interpolation · Gate 1');
});

test('generation defaults expose persisted generation preferences', () => {
  const { context } = palette();
  const definition = harness();
  definition.gateDefaults = { approach_mm: null, departure_mm: null };
  definition.endDefaults = { approach_mm: null, departure_mm: null };
  definition.minimumClearanceMm = 0.35;
  definition.autoTransitionPreset = 'relaxed';

  context.openInterpolationOptions(definition, 'defaults');

  const dialog = context.document.body.querySelector('.wire-options');
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
    orderedControlIds: [],
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

test('Wire Details Materials action opens group materials', () => {
  const { context } = palette();
  const definition = harness();
  context.openWireGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.wire-group-details-popup');

  details.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: details,
  });
  const menu = details.querySelector('.relationship-map-context-menu');
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(
    materialDialog.children[0].children[0].textContent,
    'Connected Wire Group Materials',
  );
});
