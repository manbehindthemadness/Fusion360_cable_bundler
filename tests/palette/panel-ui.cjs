/* global require, __dirname */
const {
  Element, assert, descendants, harness, palette, readPaletteStyles, test,
} = require('./support.cjs');

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

test('closing pathway configuration returns to its Wire Details parent', () => {
  const { context } = palette();
  const definition = harness();

  context.openWireGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.wire-group-details-popup');
  const pathway = descendants(
    details,
    (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.dataset.nodeId === 'pathway:p',
  )[0];
  pathway.events.click();

  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), undefined);
  let configuration = context.document.body.querySelector('.pathway-popup');
  assert.equal(configuration.open, true);
  context.renderEditor(definition);
  configuration = context.document.body.querySelector('.pathway-popup');
  const close = descendants(
    configuration, (node) => node.tag === 'button' && node.textContent === 'Close',
  )[0];
  close.events.click();

  assert.equal(context.document.body.querySelector('.pathway-popup'), undefined);
  const restored = context.document.body.querySelector('.wire-group-details-popup');
  assert.equal(restored.open, true);
  const focused = descendants(
    restored,
    (node) => node.className?.split(' ').includes('wire-group-details-member')
      && node.className.split(' ').includes('focused'),
  )[0];
  assert.equal(focused.dataset.connectionId, 'a1');
});

test('closing junction configuration returns to its Wire Details parent', () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001', pathwayRelationships: [],
  };
  definition.junctions = [junction];

  context.openWireGroupDetails(definition, 'g1', 'a1');
  context.openJunctionRelationships(definition, junction);
  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), undefined);
  const configuration = context.document.body.querySelector('.junction-relationships-popup');
  const close = descendants(
    configuration, (node) => node.tag === 'button' && node.textContent === 'Close',
  )[0];
  close.events.click();

  assert.equal(context.document.body.querySelector('.junction-relationships-popup'), undefined);
  assert.equal(context.document.body.querySelector('.wire-group-details-popup').open, true);
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

test('editing a master end isolates keyboard and pointer events from Wire Details', () => {
  const { context, calls } = palette();
  const definition = harness();
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
  menu.children.find((item) => item.textContent === 'Rename').events.click();
  const input = end.querySelector('input');
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
  assert.equal(context.document.body.querySelector('.wire-group-details-popup'), undefined);
  assert.equal(end.querySelector('input'), input);
  input.value = 'Engine Bay End';
  input.events.blur();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.name, 'Engine Bay End');
});

test('Wire Details end nodes and rows share end-owned routing actions', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways[0].orderedControlIds = ['c1'];
  const actions = [];
  context.appendEndGuides = (_harness, connectionId) => actions.push(['guides', connectionId]);
  context.addEndRefine = (_harness, connectionId) => actions.push(['refine', connectionId]);
  context.openWireGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.wire-group-details-popup');
  const graphicEnd = descendants(
    details,
    (node) => node.className?.split(' ').includes('wire-group-details-node')
      && node.dataset.connectionId === 'a1',
  )[0];
  const member = descendants(
    details,
    (node) => node.className?.split(' ').includes('wire-group-details-member')
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


