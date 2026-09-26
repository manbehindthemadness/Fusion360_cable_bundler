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

asyncTest('single click selects and double click edits one contact', async () => {
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
  state.workspace.viewport.events.pointerup({ ...pointer, type: 'pointerup', timeStamp: 1000 });
  assert.equal(item.dataset.selected, 'true');
  assert.equal(diagram.querySelector('.interface-contact-details-editor'), undefined);
  state.workspace.viewport.events.pointerdown(pointer);
  state.workspace.viewport.events.pointerup({ ...pointer, type: 'pointerup', timeStamp: 1200 });
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

asyncTest('contact context menu closes on left press and acts on the selected group', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contacts = ['a', 'b', 'c'].map((contactId, index) => ({
    contactId, name: contactId, assignedName: `Value ${contactId}`, pin: `${index + 1}`,
    linked: true, normal: [0, 0, 1],
    loops: [[[index * 4, 0, 0], [index * 4 + 2, 0, 0], [index * 4 + 2, 2, 0]]],
  }));
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const diagram = context.document.body.querySelector('.interface-contacts-popup').children[2];
  const state = diagram.contactState;
  const viewport = state.workspace.viewport;
  state.selectedIds.add('a');
  state.selectedIds.add('b');
  context.paintInterfaceContactSelection(state);
  const rightClick = (id) => viewport.events.contextmenu({
    target: contactItem(diagram, id), clientX: 50, clientY: 60,
    preventDefault() {}, stopPropagation() {},
  });
  rightClick('a');
  const menu = diagram.querySelector('.relationship-map-context-menu');
  assert.equal(menu.hidden, false);
  assert.deepEqual(menu.children.map((button) => button.textContent),
    ['Edit', 'Clear', 'Delete']);
  assert.equal(menu.children[0].disabled, true);
  const background = contactPointer(state.svg, 0, 0);
  viewport.events.pointerdown(background);
  assert.equal(menu.hidden, true);
  viewport.events.pointercancel({ ...background, type: 'pointercancel' });
  rightClick('a');
  menu.children[1].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[0].action, 'clear_interface_contact_pins');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['a', 'b']);
  assert.equal(Object.hasOwn(launches[0].payload, 'value'), false);
  rightClick('b');
  menu.children[2].events.click();
  await Promise.resolve();
  assert.equal(launches[1].action, 'remove_interface_contacts');
  assert.deepEqual(Array.from(launches[1].payload.contactIds), ['a', 'b']);
  rightClick('c');
  assert.deepEqual([...state.selectedIds], ['c']);
  assert.equal(menu.children[0].disabled, false);
  menu.children[0].events.click();
  assert.equal(diagram.querySelector('.interface-contact-details-editor').dataset.contactId, 'c');
});

test('Auto Pin follows visual rows or columns, direction, and selected contacts', () => {
  const { context } = palette();
  const items = [
    { id: 'bottom-right', loops: [[[20, 20], [30, 20], [30, 30]]] },
    { id: 'top-left', loops: [[[0, 0], [10, 0], [10, 10]]] },
    { id: 'bottom-left', loops: [[[0, 20], [10, 20], [10, 30]]] },
    { id: 'top-right', loops: [[[20, 0], [30, 0], [30, 10]]] },
  ];
  const ids = (direction, selected = new Set()) => (
    Array.from(context.orderedInterfaceContactIds(items, selected, direction))
  );
  assert.deepEqual(ids('LRTB'), ['top-left', 'top-right', 'bottom-left', 'bottom-right']);
  assert.deepEqual(ids('RLTB'), ['top-right', 'top-left', 'bottom-right', 'bottom-left']);
  assert.deepEqual(ids('LRBT'), ['bottom-left', 'bottom-right', 'top-left', 'top-right']);
  assert.deepEqual(ids('RLBT'), ['bottom-right', 'bottom-left', 'top-right', 'top-left']);
  assert.deepEqual(ids('TBLR'), ['top-left', 'bottom-left', 'top-right', 'bottom-right']);
  assert.deepEqual(ids('BTLR'), ['bottom-left', 'top-left', 'bottom-right', 'top-right']);
  assert.deepEqual(ids('TBRL'), ['top-right', 'bottom-right', 'top-left', 'bottom-left']);
  assert.deepEqual(ids('BTRL'), ['bottom-right', 'top-right', 'bottom-left', 'top-left']);
  assert.deepEqual(ids('LRTB', new Set(['top-right', 'bottom-left'])), ['top-right', 'bottom-left']);
});

asyncTest('Auto Pin popup sends one selected-only pin edit without Value changes', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contact = { contactId: 'pad-1', kind: 'face', name: 'Pad', assignedName: 'VCC',
    pin: 'old', linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0]]] };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [contact],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const naming = dialog.children[1].children[1];
  const button = naming.children[0];
  assert.equal(button.textContent, 'Auto Pin');
  assert.equal(naming.children[1].textContent, 'Geo Import');
  assert.equal(naming.children[2].textContent, 'Pos Import');
  button.events.click();
  const form = naming.querySelector('.interface-contact-auto-pin');
  const direction = form.children[0].children[0];
  const start = form.children[1].children[0];
  const overwrite = form.children[2].children[0];
  assert.deepEqual(Array.from(direction.children, (option) => option.value),
    ['LRTB', 'RLTB', 'LRBT', 'RLBT', 'TBLR', 'BTLR', 'TBRL', 'BTRL']);
  assert.equal(direction.value, 'LRTB');
  assert.equal(start.value, '0');
  assert.equal(overwrite.checked, undefined);
  dialog.children[2].contactState.selectedIds.add('pad-1');
  start.value = '7';
  overwrite.checked = true;
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'auto_pin_interface_contacts');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['pad-1']);
  assert.equal(launches[0].payload.start, 7);
  assert.equal(launches[0].payload.overwrite, true);
  assert.equal(Object.hasOwn(launches[0].payload, 'value'), false);
});

test('Auto Pin remembers order within the palette session', () => {
  const storage = new Map();
  const { context } = palette(storage);
  const naming = context.document.createElement('div');
  const diagram = context.document.createElement('div');
  context.openInterfaceAutoPin(naming, diagram, 'harness-1', 'interface-1');
  const first = naming.querySelector('.interface-contact-auto-pin');
  const order = first.children[0].children[0];
  assert.equal(order.value, 'LRTB');
  order.value = 'BTRL';
  order.events.change();
  first.remove();
  context.openInterfaceAutoPin(naming, diagram, 'harness-1', 'interface-1');
  assert.equal(naming.querySelector('.interface-contact-auto-pin').children[0].children[0].value,
    'BTRL');
  const anotherPalette = palette(storage).context;
  const anotherNaming = anotherPalette.document.createElement('div');
  const anotherDiagram = anotherPalette.document.createElement('div');
  anotherPalette.openInterfaceAutoPin(anotherNaming, anotherDiagram, 'harness-1', 'interface-1');
  assert.equal(anotherNaming.querySelector('.interface-contact-auto-pin').children[0].children[0].value,
    'BTRL');
  storage.set('cableBundler.autoPinOrder', 'invalid');
  const invalidNaming = anotherPalette.document.createElement('div');
  anotherPalette.openInterfaceAutoPin(invalidNaming, anotherDiagram, 'harness-1', 'interface-1');
  assert.equal(invalidNaming.querySelector('.interface-contact-auto-pin').children[0].children[0].value,
    'LRTB');
});

test('Geo Import sends only selected contact IDs when a selection exists', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contacts = ['a', 'b'].map((contactId, index) => ({
    contactId, kind: 'face', name: contactId, linked: true, normal: [0, 0, 1],
    loops: [[[index * 10, 0, 0], [index * 10 + 2, 0, 0], [index * 10 + 2, 2, 0]]],
  }));
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  dialog.children[2].contactState.selectedIds.add('b');
  dialog.children[1].children[1].children[1].events.click();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'geo_import_interface_contacts');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['b']);
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
