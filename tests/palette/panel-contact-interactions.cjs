/** Contact diagram pointer, selection, and editor regressions. */
const { assert, asyncTest, contactItem, descendants, harness, palette, test } = require('./support.cjs');

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

asyncTest('left clicking a contact edits its Value and Pin without losing selection', async () => {
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
  const editor = diagram.querySelector('.interface-contact-details-editor');
  assert.equal(editor.dataset.contactId, 'pad-1');
  assert.equal(editor.children[0].textContent, 'Value');
  assert.equal(editor.children[1].textContent, 'Pin');
  const valueInput = editor.children[0].children[0];
  const pinInput = editor.children[1].children[0];
  assert.equal(valueInput.value, 'J5.2');
  assert.equal(pinInput.value, '');
  valueInput.value = 'J5.4';
  pinInput.value = 'P7';
  editor.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'set_interface_contact_details');
  assert.equal(launches[0].payload.harnessId, 'harness-1');
  assert.equal(launches[0].payload.interfaceId, 'interface-1');
  assert.equal(launches[0].payload.contactId, 'pad-1');
  assert.equal(launches[0].payload.value, 'J5.4');
  assert.equal(launches[0].payload.pin, 'P7');
  assert.equal(diagram.querySelector('.interface-contact-details-editor'), undefined);
  context.updateInterfaceContactData(dialog, [{ ...contact, assignedName: 'J5.4', pin: 'P7' }]);
  diagram.contactState.onEditContact('pad-1', pointer);
  const reopened = diagram.querySelector('.interface-contact-details-editor');
  assert.equal(reopened.children[0].children[0].value, 'J5.4');
  assert.equal(reopened.children[1].children[0].value, 'P7');
  const svg = diagram.contactState.svg;
  reopened.children[1].children[0].value = 'P8';
  reopened.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches[1].payload.value, 'J5.4');
  assert.equal(launches[1].payload.pin, 'P8');
  context.updateInterfaceContactData(dialog, [{ ...contact, assignedName: 'J5.4', pin: 'P8' }]);
  assert.notEqual(diagram.contactState.svg, svg);
  const labels = descendants(contactItem(diagram, 'pad-1'), (node) => (
    node.className?.includes('interface-contact-label')
  ));
  assert.ok(labels.some((label) => label.textContent.includes('P8')));
  diagram.contactState.onEditContact('pad-1', pointer);
  const unchanged = diagram.querySelector('.interface-contact-details-editor');
  assert.equal(unchanged.children[1].children[0].value, 'P8');
  unchanged.events.submit({ preventDefault() {} });
  assert.equal(launches.length, 2);
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

test('Contact drag paths retain bounded history', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, []);
  const state = diagram.contactState;
  const viewport = state.workspace.viewport;
  for (const mode of ['box', 'freeform']) {
    state.mode = mode;
    viewport.events.pointerdown(contactPointer(state.svg, 0, 0));
    for (let index = 0; index < 4100; index += 1) {
      viewport.events.pointermove(contactPointer(state.svg, index + 5, 10));
    }
    assert.ok(state.drag.points.length <= (mode === 'box' ? 2 : 2048));
    viewport.events.pointercancel({ ...contactPointer(state.svg, 0, 0), type: 'pointercancel' });
    assert.equal(state.drag, null);
  }
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
  viewport.events.keydown({ key: 'Enter', target: contactItem(diagram, 'b'), preventDefault() {} });
  assert.equal(contactItem(diagram, 'b').attributes['aria-selected'], 'true');
});
