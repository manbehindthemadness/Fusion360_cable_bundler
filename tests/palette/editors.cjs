/** Focused palette regression suite. */
/* global require */
const { assert, asyncTest, descendants, harness, palette, test } = require('./support.cjs');

test('interactive wire diagram replaces the old node strip and uses precise names', () => {
  const { context } = palette();
  const definition = harness();
  const rendered = context.renderWireRoutes(definition);
  const labels = descendants(rendered, (node) => node.tag === 'text')
    .map((node) => node.textContent);
  assert.ok(labels.includes('Data input'));
  assert.ok(labels.includes('Data output'));
  assert.ok(labels.includes('a2'));
  assert.ok(labels.includes('lower fuse box path'));
  assert.equal(descendants(rendered, (node) => node.className === 'route-flow').length, 0);
  assert.equal(descendants(rendered, (node) => node.className?.split(' ').includes('route-node')).length, 3);
});

test('wire diagram nodes configure ends and open pathway popup by mouse or keyboard', () => {
  const { context } = palette();
  const definition = harness();
  context.renderEditor(definition);
  const startNode = descendants(context.ui.editor, (node) => (
    node.dataset.editorId === 'end-a-w1'
  ))[0];
  const endNode = descendants(context.ui.editor, (node) => (
    node.dataset.editorId === 'end-b-w1'
  ))[0];
  const startEditor = descendants(context.ui.editor, (node) => node.id === 'end-a-w1')[0];
  const endEditor = descendants(context.ui.editor, (node) => node.id === 'end-b-w1')[0];
  assert.equal(startEditor.hidden, true);
  startNode.events.keydown({ key: 'Enter', preventDefault() {} });
  assert.equal(startEditor.hidden, false);
  assert.equal(startNode.attributes['aria-expanded'], 'true');
  endNode.events.click();
  assert.equal(startEditor.hidden, true);
  assert.equal(endEditor.hidden, false);
  assert.equal(startNode.attributes['aria-expanded'], 'false');
  const pathwayNode = descendants(context.ui.editor, (node) => (
    node.className === 'wire-relationship-node pathway' && node.dataset.pathwayId === 'p'
  ))[0];
  pathwayNode.events.keydown({ key: ' ', preventDefault() {} });
  const popup = context.document.body.querySelector('.pathway-popup');
  const pathwaySection = popup.querySelector('[data-section="pathway:p"]');
  const occupancySection = popup.querySelector('[data-section="pathway:p:occupancy"]');
  assert.equal(popup.open, true);
  assert.equal(pathwaySection.open, true);
  assert.equal(descendants(
    occupancySection,
    (node) => node.className === 'member-row',
  ).length, 3);
  assert.equal(descendants(
    popup,
    (node) => node.textContent === '+ Add Wire Pairs',
  ).length, 0);
});

test('each end editor contains only its own profile and sends its wire identity', () => {
  const { context, calls } = palette();
  const rendered = context.renderWireRoutes(harness());
  const editors = descendants(rendered, (node) => node.className === 'end-editor');
  assert.equal(editors.length, 6);
  for (const editor of editors) {
    assert.equal(descendants(editor, (node) => node.className === 'member-row').length, 1);
    assert.equal(descendants(editor, (node) => node.className === 'member-reference')[0].textContent, '1');
  }
  const input = descendants(editors[2], (node) => node.tag === 'input')[0];
  input.value = 'Second input';
  input.events.change();
  assert.equal(calls[0].payload.wireId, 'w2');
  assert.equal(calls[0].payload.name, 'Second input');
});

test('wire and pathway names are editable and traversal fields bracket gates', () => {
  const { context, calls } = palette();
  const wires = context.renderWireRoutes(harness());
  assert.equal(descendants(wires, (node) => node.textContent === 'Wire Name').length, 0);
  const pen = descendants(wires, (node) => node.title === 'Rename wire')[0];
  pen.events.click();
  const wireField = descendants(wires, (node) => node.attributes['aria-label'] === 'Wire name')[0];
  wireField.value = 'Signal';
  wireField.events.keydown({ key: 'Enter', preventDefault() {} });
  assert.equal(calls[0].action, 'rename_wire');
  const pathways = context.renderPathways(harness());
  const fields = descendants(pathways, (node) => node.tag === 'label');
  assert.deepEqual(fields.map((node) => node.textContent), ['Pathway Name', 'Start Name', 'End Name']);
  fields[0].children[0].value = 'New path';
  fields[0].children[0].events.change();
  assert.equal(calls[1].payload.field, 'name');
  const gateContainer = descendants(pathways, (node) => node.children.some((child) => child.textContent === 'Start Name'))[0];
  assert.equal(gateContainer.children[0].textContent, 'Start Name');
  assert.equal(gateContainer.children[1].className, 'sequence');
  assert.equal(gateContainer.children[2].textContent, 'End Name');
});

test('wire header collapses details and highlights only on hover', () => {
  const storage = new Map();
  const { context, calls } = palette(storage);
  context.highlightMember = (...args) => calls.push(args);
  const rendered = context.renderWireRoutes(harness());
  const header = descendants(rendered, (node) => node.title === 'Expand or collapse wire')[0];
  const details = descendants(rendered, (node) => node.className === 'wire-details')[0];
  assert.equal(details.hidden, true);
  header.events.click();
  assert.equal(details.hidden, false);
  assert.equal(calls.length, 0);
  header.parentElement.events.mouseenter();
  assert.equal(calls[0][1], 'preview_wire');
  assert.equal(calls[0][2], 'w1');
  const restored = palette(storage).context.renderWireRoutes(harness());
  assert.equal(descendants(restored, (node) => node.className === 'wire-details')[0].hidden, false);
  header.events.click();
  assert.equal(details.hidden, true);
  assert.equal(descendants(rendered, (node) => node.textContent === '↔').length, 0);
});

test('clearly labeled wire options combine diameter and material controls', () => {
  const { context } = palette();
  const rendered = context.renderWireRoutes(harness());
  const button = descendants(rendered, (node) => (
    node.title === 'Edit wire diameter and material options'
  ))[0];
  assert.match(button.textContent, /^Wire options · 1\.5 mm · Black PVC/);
  button.events.click();
  const dialog = context.document.body.children[0];
  assert.equal(dialog.open, true);
  assert.equal(descendants(dialog, (node) => node.tag === 'h2')[0].textContent, 'Wire options · Wire #001');
  const diameter = descendants(dialog, (node) => node.type === 'number')[0];
  assert.equal(diameter.value, '1.5');
  descendants(dialog, (node) => node.textContent === 'Cancel')[0].events.click();
  assert.equal(context.document.body.children.length, 0);
});

test('diagram stripe cues stay centered within each wire trace', () => {
  const { context } = palette();
  const definition = harness();
  definition.wires[0].materials = {
    ...definition.materialDefaults,
    stripes: [{ color: { name: 'White', hex: '#ffffff' }, pattern: 'solid' }],
  };
  const graphic = descendants(
    context.renderWireRoutes(definition),
    (node) => node.className === 'wire-relationship-graphic',
  )[0];
  const stripeLines = descendants(graphic, (node) => (
    node.tag === 'line' && node.attributes.stroke === '#ffffff'
  ));
  const baseLines = descendants(graphic, (node) => (
    node.tag === 'line' && node.attributes.stroke === '#202020'
  ));
  assert.ok(stripeLines.length > 0);
  assert.equal(stripeLines.length, baseLines.length);
  assert.ok(stripeLines.every((line, index) => (
    line.attributes.y1 === baseLines[index].attributes.y1
      && line.attributes.y2 === baseLines[index].attributes.y2
  )));
  const master = context.renderRelationshipMap(definition, []);
  const connector = descendants(master, (node) => node.className === 'relationship-connector')[0];
  const base = descendants(connector, (node) => (
    node.className === 'wire-trace' && node.attributes['data-wire-id'] === 'w1'
  ))[0];
  const stripe = descendants(connector, (node) => (
    node.className === 'stripe-trace' && node.attributes['data-wire-id'] === 'w1'
  ))[0];
  assert.equal(stripe.attributes.d, base.attributes.d);
  assert.equal(context.centeredStripeOffset(0, 2, 2), -1);
  assert.equal(context.centeredStripeOffset(1, 2, 2), 1);
});

test('hover scopes distinguish pathway nodes, group headings, and members', () => {
  const { context, calls } = palette();
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });
  const definition = harness();
  definition.controls = [{ controlId: 'g1', name: 'Gate 1', hasLinkedGeometry: true }];
  definition.pathways[0].orderedControlIds = ['g1'];
  const routes = context.renderWireRoutes(definition);
  descendants(routes, (node) => node.className === 'wire-relationship-node pathway')[0]
    .events.mouseenter();
  assert.equal(calls.pop().type, 'pathway_gates');
  const pathways = context.renderPathways(definition);
  const sections = descendants(pathways, (node) => node.tag === 'details');
  sections.find((node) => node.dataset.section === 'pathway:p').children[0].events.mouseenter();
  assert.equal(calls.pop().type, 'pathway');
  sections.find((node) => node.dataset.section === 'pathway:p:gates').children[0].events.mouseenter();
  assert.equal(calls.pop().type, 'pathway_gates');
  sections.find((node) => node.dataset.section === 'pathway:p:occupancy').children[0].events.mouseenter();
  assert.equal(calls.pop().type, 'pathway_wires');
  const gateRow = descendants(pathways, (node) => node.className === 'member-row')[0];
  gateRow.events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'control', id: 'g1' });
});

test('end member controls target one member and warn before deleting the last', () => {
  const { context, calls } = palette();
  const definition = harness();
  const rendered = context.renderWireRoutes(definition);
  const editor = descendants(rendered, (node) => node.className === 'end-editor')[0];
  const replace = descendants(editor, (node) => node.title === 'Replace member')[0];
  replace.events.click();
  assert.equal(calls.pop().payload.editAction, 'replace');
  context.window.confirm = () => false;
  const remove = descendants(editor, (node) => node.title === 'Remove member')[0];
  remove.events.click();
  assert.equal(calls.length, 0);
  context.window.confirm = () => true;
  remove.events.click();
  assert.equal(calls.pop().action, 'remove_end_member');
  descendants(editor, (node) => node.title === 'Add member after this member')[0].events.click();
  assert.equal(calls.pop().payload.editAction, 'add');
  definition.connections = definition.connections.filter((connection) => connection.connectionId !== 'a1');
  const missing = context.renderWireRoutes(definition);
  descendants(missing, (node) => node.dataset.editorId === 'end-a-w1')[0].events.click();
  assert.equal(calls.pop().payload.expectedMembers, 0);
});

test('end menu retains state after replacement and palette reload', () => {
  const storage = new Map();
  const { context, calls } = palette(storage);
  const definition = harness();
  let rendered = context.renderWireRoutes(definition);
  const endA = descendants(rendered, (node) => node.dataset.editorId === 'end-a-w1')[0];
  endA.events.click();
  const editor = descendants(rendered, (node) => node.id === 'end-a-w1')[0];
  assert.equal(editor.hidden, false);
  descendants(editor, (node) => node.title === 'Replace member')[0].events.click();
  assert.equal(calls.pop().payload.editAction, 'replace');
  definition.connections[0].name = 'Replacement';
  rendered = context.renderWireRoutes(definition);
  assert.equal(descendants(rendered, (node) => node.id === 'end-a-w1')[0].hidden, false);
  assert.equal(descendants(rendered, (node) => node.dataset.editorId === 'end-a-w1')[0].attributes['aria-expanded'], 'true');
  rendered = palette(storage).context.renderWireRoutes(definition);
  assert.equal(descendants(rendered, (node) => node.id === 'end-a-w1')[0].hidden, false);
  const endB = descendants(rendered, (node) => node.dataset.editorId === 'end-b-w1')[0];
  endB.events.click();
  const restored = palette(storage).context.renderWireRoutes(definition);
  assert.equal(descendants(restored, (node) => node.id === 'end-a-w1')[0].hidden, true);
  assert.equal(descendants(restored, (node) => node.id === 'end-b-w1')[0].hidden, false);
  assert.equal(descendants(restored, (node) => node.id === 'end-a-w2')[0].hidden, true);
});

test('pointer dragging marks exact insertion and commits on release', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.connections[0].members = Array.from({length: 4}, (_, index) => ({index, hasLinkedGeometry: true}));
  const rendered = context.renderWireRoutes(definition);
  const editor = descendants(rendered, (node) => node.id === 'end-a-w1')[0];
  const rows = descendants(editor, (node) => node.dataset.reorder === 'true');
  rows[0].parentElement.getBoundingClientRect = () => ({left: 0, right: 300, top: 0, bottom: 160, x: 0, y: 0, width: 300, height: 160, toJSON() { return {}; }});
  rows.forEach((row, index) => {
    row.getBoundingClientRect = () => ({top: index * 40, height: 40});
    row.setPointerCapture = () => {};
    row.hasPointerCapture = () => true;
    row.releasePointerCapture = () => {};
  });
  const event = (y, x = 50) => ({button: 0, pointerId: 1, clientX: x, clientY: y,
    target: {closest: () => null}, preventDefault() {}});
  rows[3].events.pointerdown(event(140));
  rows[3].events.pointermove(event(55));
  assert.equal(rows[1].dataset.drop, 'before');
  rows[3].events.pointerup(event(55));
  assert.equal(calls.at(-1).action, 'move_end_member');
  assert.equal(calls.at(-1).payload.memberIndex, 3);
  assert.equal(calls.at(-1).payload.targetIndex, 1);
  assert.equal(rows[1].dataset.drop, undefined);
  rows[0].events.pointerdown(event(20));
  rows[0].events.pointermove(event(159));
  assert.equal(rows[3].dataset.drop, 'after');
  rows[0].events.pointerup(event(159));
  assert.equal(calls.at(-1).payload.targetIndex, 3);
  rows[0].events.pointerdown(event(20));
  rows[0].events.pointermove(event(55, 400));
  rows[0].events.pointerup(event(55, 400));
  assert.equal(calls.length, 2);
  rows[0].events.pointerdown(event(20));
  rows[0].events.pointermove(event(55));
  rows[0].events.pointercancel();
  rows[0].events.pointerup(event(55));
  assert.equal(calls.length, 2);
  assert.equal(rows[1].dataset.drop, undefined);
  rows[0].events.pointerdown(event(20));
  rows[0].events.pointerup(event(20));
  assert.equal(calls.length, 2);
});

test('member labels follow persistent identity instead of row position', () => {
  const { context } = palette();
  const definition = harness();
  const members = [
    { memberId: 'abcd1234-0000-0000-0000-000000000001', hasLinkedGeometry: true },
    { memberId: 'dcba4321-0000-0000-0000-000000000002', hasLinkedGeometry: true },
  ];
  definition.connections[0].members = members;
  let editor = descendants(context.renderWireRoutes(definition), (node) => node.id === 'end-a-w1')[0];
  const labels = (node) => descendants(node, (child) => child.className === 'member-reference').map((child) => child.textContent);
  assert.deepEqual(labels(editor), ['#abcd1234', '#dcba4321']);
  definition.connections[0].members = [...members].reverse();
  editor = descendants(context.renderWireRoutes(definition), (node) => node.id === 'end-a-w1')[0];
  assert.deepEqual(labels(editor), ['#dcba4321', '#abcd1234']);
});

test('gate stacks share drag placement and both stacks have a left position column', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.controls = [1, 2, 3].map((index) => ({controlId: `gate000${index}`, name: `Gate ${index}`, hasLinkedGeometry: true}));
  definition.pathways[0].orderedControlIds = definition.controls.map((gate) => gate.controlId);
  const gateRows = descendants(context.renderPathways(definition), (node) => node.dataset.reorder === 'true');
  assert.deepEqual(gateRows.map((row) => row.children[0].textContent), ['1', '2', '3']);
  assert.equal(gateRows[0].children[1].textContent, 'Gate 1 #gate0001');
  assert.equal(descendants(gateRows[0], (node) => ['↑', '↓'].includes(node.textContent)).length, 0);
  const endRows = descendants(context.renderWireRoutes(definition), (node) => node.dataset.reorder === 'true');
  assert.equal(endRows[0].children[0].className, 'sequence-position');
  assert.equal(endRows[0].children[0].textContent, '1');
  gateRows[0].parentElement.getBoundingClientRect = () => ({left: 0, right: 300, top: 0, bottom: 120, x: 0, y: 0, width: 300, height: 120, toJSON() { return {}; }});
  gateRows.forEach((row, index) => {
    row.getBoundingClientRect = () => ({top: index * 40, height: 40});
    row.setPointerCapture = () => {};
    row.hasPointerCapture = () => true;
    row.releasePointerCapture = () => {};
  });
  const event = (y) => ({button: 0, pointerId: 1, clientX: 50, clientY: y, target: {closest: () => null}, preventDefault() {}});
  gateRows[0].events.pointerdown(event(20));
  gateRows[0].events.pointermove(event(115));
  assert.equal(gateRows[2].dataset.drop, 'after');
  gateRows[0].events.pointerup(event(115));
  assert.equal(calls.at(-1).action, 'move_pathway_gate');
  assert.equal(calls.at(-1).payload.controlId, 'gate0001');
  assert.equal(calls.at(-1).payload.offset, 2);
  definition.pathways[0].orderedControlIds = ['gate0002', 'gate0003', 'gate0001'];
  const updated = descendants(context.renderPathways(definition), (node) => node.dataset.reorder === 'true');
  assert.deepEqual(updated.map((row) => row.children[0].textContent), ['1', '2', '3']);
  assert.equal(updated[2].children[1].textContent, 'Gate 1 #gate0001');
});

test('junction-related pathway boundary stays locked while interior gates remain draggable', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.controls = [1, 2, 3].map((index) => ({
    controlId: `gate000${index}`, name: `Gate ${index}`, hasLinkedGeometry: true,
  }));
  definition.pathways[0].orderedControlIds = definition.controls.map((gate) => gate.controlId);
  definition.junctions = [{
    junctionId: 'j1', name: 'Junction 01', controlId: 'junction-gate',
    pathwayRelationships: [{ pathwayId: 'p', endpoint: 'start' }],
  }];

  const rendered = context.renderPathways(definition);
  const locked = descendants(rendered, (node) => node.dataset.reorder === 'locked');
  const movable = descendants(rendered, (node) => node.dataset.reorder === 'true');

  assert.equal(locked.length, 1);
  assert.match(locked[0].title, /preserved by a junction/);
  assert.equal(descendants(locked[0], (node) => node.title === 'Remove gate')[0].disabled, true);
  assert.equal(movable.length, 2);
  assert.equal(calls.length, 0);

  definition.junctions = [];
  definition.standaloneEnds = [{
    connectionId: 'loose', pathwayId: 'p', endpoint: 'end',
  }];
  const standaloneRendered = context.renderPathways(definition);
  const standaloneLocked = descendants(
    standaloneRendered, (node) => node.dataset.reorder === 'locked',
  );
  assert.equal(standaloneLocked.length, 1);
  assert.match(standaloneLocked[0].title, /standalone end/);
});

test('pathway popup replaces its traversal stack before a delayed close event', () => {
  const { context } = palette();
  const definition = harness();
  definition.controls = [1, 2].map((index) => ({
    controlId: `gate000${index}`, name: `Gate ${index}`, kind: 'gate', hasLinkedGeometry: true,
  }));
  definition.pathways[0].orderedControlIds = ['gate0001', 'gate0002'];
  context.openPathwayPopup(definition, 'p');
  const stalePopup = context.document.body.querySelector('.pathway-popup');
  stalePopup.close = () => { stalePopup.open = false; };

  const updated = JSON.parse(JSON.stringify(definition));
  updated.controls = updated.controls.slice(1);
  updated.pathways[0].orderedControlIds = ['gate0002'];
  context.renderEditor(updated);

  const refreshedPopup = context.document.body.querySelector('.pathway-popup');
  const gateRows = descendants(refreshedPopup, (node) => node.dataset.reorder === 'true');
  assert.notEqual(refreshedPopup, stalePopup);
  assert.equal(context.document.body.children.includes(stalePopup), false);
  assert.equal(gateRows.length, 1);
  assert.equal(gateRows[0].children[1].textContent, 'Gate 2 #gate0002');
});

asyncTest('pathway popup opens interactive refine placement', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  context.send = async (action, payload) => {
    requests.push({ action, payload });
    return { ok: true };
  };
  const paths = context.renderPathways(definition);
  const button = descendants(paths, (node) => node.textContent === '+ Add Refine Point')[0];

  button.events.click();
  await Promise.resolve();

  assert.equal(requests[0].action, 'add_pathway_refine');
  assert.equal(requests[0].payload.harnessId, 'h');
  assert.equal(requests[0].payload.pathwayId, 'p');
});

asyncTest('refine stack row highlights its marker and opens transform editing', async () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.controls = [{
    controlId: 'refine-001', name: 'Refine Point 01', kind: 'refine', hasLinkedGeometry: true,
    interpolation: { approach_mm: null, departure_mm: null }, usesDefaults: true,
  }];
  definition.pathways[0].orderedControlIds = ['refine-001'];
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });
  const requests = [];
  context.send = async (action, payload) => {
    requests.push({ action, payload });
    return { ok: true };
  };
  const paths = context.renderPathways(definition);
  const row = descendants(paths, (node) => node.className === 'member-row')[0];

  row.events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'control', id: 'refine-001' });
  descendants(row, (node) => node.title === 'Move, rotate, or resize refine point')[0]
    .events.click();
  await Promise.resolve();

  assert.equal(requests[0].action, 'edit_pathway_refine');
  assert.equal(requests[0].payload.controlId, 'refine-001');
});

test('interpolation popups target native gates and ends without changing expansion state', () => {
  const storage = new Map([['wireBundler.expandedSections', '["end:h:w1:start"]']]);
  const { context } = palette(storage);
  const definition = harness();
  definition.connections.forEach((connection) => {
    connection.members = [{ memberId: `member-${connection.connectionId}`, index: 0, hasLinkedGeometry: true }];
  });
  definition.controls = [{ controlId: 'gate-001', name: 'Gate 1', hasLinkedGeometry: true,
    interpolation: { approach_mm: 3, departure_mm: null } }];
  definition.pathways[0].orderedControlIds = ['gate-001'];
  const requests = [];
  context.send = async (action, payload) => { requests.push({ action, payload }); return { ok: true }; };
  const paths = context.renderPathways(definition);
  descendants(paths, (item) => item.title === 'Gate interpolation options')[0].events.click();
  let dialog = context.document.body.children.at(-1);
  let inputs = descendants(dialog, (item) => item.tag === 'input');
  assert.equal(inputs[0].value, '3');
  assert.equal(inputs[1].value, '');
  inputs[1].value = '7';
  inputs[1].events.input();
  dialog.children[0].events.submit({ preventDefault() {} });
  assert.equal(requests[0].payload.targetId, 'gate-001');
  assert.equal(requests[0].payload.settings.departure_mm, 7);
  assert.equal(requests[0].payload.useDefaults, false);
  const wires = context.renderWireRoutes(definition);
  descendants(wires, (item) => item.title === 'End member interpolation options')[1].events.click();
  dialog = context.document.body.children.at(-1);
  inputs = descendants(dialog, (item) => item.tag === 'input');
  assert.ok(inputs[0].attributes['aria-label'].startsWith('Terminal-side'));
  dialog.children[0].events.submit({ preventDefault() {} });
  assert.equal(requests[1].payload.target, 'end');
  assert.equal(requests[1].payload.targetId, 'b1');
  assert.equal(requests[1].payload.memberId, 'member-b1');
  assert.equal(storage.get('wireBundler.expandedSections'), '["end:h:w1:start"]');
});

test('defaults popup saves both presets together and rejects invalid distances', () => {
  const { context } = palette();
  const requests = [];
  context.send = async (action, payload) => { requests.push({ action, payload }); return { ok: true }; };
  context.openInterpolationOptions(harness(), 'defaults');
  const dialog = context.document.body.children.at(-1);
  const inputs = descendants(dialog, (item) => item.tag === 'input' && item.type === 'number');
  assert.equal(inputs.length, 4);
  inputs[0].value = '-1';
  dialog.children[0].events.submit({ preventDefault() {} });
  assert.equal(requests.length, 0);
  inputs[0].value = '2.5';
  inputs[3].value = '6';
  dialog.children[0].events.submit({ preventDefault() {} });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].action, 'set_interpolation');
  assert.equal(requests[0].payload.settings.approach_mm, 2.5);
  assert.equal(requests[0].payload.settings.departure_mm, null);
  assert.equal(requests[0].payload.endDefaults.departure_mm, 6);
  assert.equal(requests[0].payload.applyExisting, true);
});

test('member popup can restore inheritance without changing other members', () => {
  const { context } = palette();
  const definition = harness();
  definition.endDefaults = { approach_mm: 2, departure_mm: 5 };
  definition.connections[0].members = [
    { index: 0, memberId: 'terminal-001', interpolation: { approach_mm: 1, departure_mm: 9 }, usesDefaults: false },
    { index: 1, memberId: 'guide-002', interpolation: { approach_mm: 3, departure_mm: 7 }, usesDefaults: false },
  ];
  const requests = [];
  context.send = async (action, payload) => { requests.push({ action, payload }); return { ok: true }; };
  const wires = context.renderWireRoutes(definition);
  const buttons = descendants(wires, (item) => item.title === 'End member interpolation options');
  buttons[1].events.click();
  const dialog = context.document.body.children.at(-1);
  const inputs = descendants(dialog, (item) => item.type === 'number');
  assert.equal(inputs[1].value, '7');
  descendants(dialog, (item) => item.textContent === 'Use harness defaults')[0].events.click();
  assert.equal(inputs[1].value, '5');
  dialog.children[0].events.submit({ preventDefault() {} });
  assert.equal(requests[0].payload.memberId, 'guide-002');
  assert.equal(requests[0].payload.useDefaults, true);
});
