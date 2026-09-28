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
    ['Edit', '', 'Delete']);
  const clear = menu.children[1];
  assert.equal(clear.children[0].textContent, 'Clear');
  assert.equal(clear.children[0].attributes['aria-haspopup'], 'menu');
  assert.deepEqual(clear.children[1].children.map((button) => button.textContent),
    ['Pins', 'Values']);
  assert.equal(menu.children[0].disabled, true);
  const background = contactPointer(state.svg, 0, 0);
  viewport.events.pointerdown(background);
  assert.equal(menu.hidden, true);
  viewport.events.pointercancel({ ...background, type: 'pointercancel' });
  rightClick('a');
  menu.children[1].children[1].children[0].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[0].action, 'clear_interface_contact_pins');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['a', 'b']);
  assert.equal(Object.hasOwn(launches[0].payload, 'value'), false);
  rightClick('a');
  menu.children[1].children[1].children[1].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[1].action, 'clear_interface_contact_values');
  assert.deepEqual(Array.from(launches[1].payload.contactIds), ['a', 'b']);
  assert.equal(Object.hasOwn(launches[1].payload, 'pin'), false);
  rightClick('b');
  menu.children[2].events.click();
  await Promise.resolve();
  assert.equal(launches[2].action, 'remove_interface_contacts');
  assert.deepEqual(Array.from(launches[2].payload.contactIds), ['a', 'b']);
  rightClick('c');
  assert.deepEqual([...state.selectedIds], ['c']);
  assert.equal(menu.children[0].disabled, false);
  menu.children[0].events.click();
  assert.equal(diagram.querySelector('.interface-contact-details-editor').dataset.contactId, 'c');
});

asyncTest('orientation backdrop menu targets the selection or every contact in its orientation', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contacts = [
    { contactId: 'a', normal: [0, 0, 1] },
    { contactId: 'b', normal: [0, 0, 1] },
    { contactId: 'c', normal: [0, 0, -1] },
  ].map((contact, index) => ({ ...contact, name: contact.contactId,
    assignedName: `Value ${contact.contactId}`, pin: `${index + 1}`, linked: true,
    loops: [[[index * 4, 0, 0], [index * 4 + 2, 0, 0], [index * 4 + 2, 2, 0]]],
  }));
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  const state = diagram.contactState;
  const backdrop = state.svg.children[0].children[0];
  const rightClick = () => state.workspace.viewport.events.contextmenu({
    target: backdrop, clientX: 50, clientY: 60, preventDefault() {}, stopPropagation() {},
  });
  const menu = diagram.querySelector('.relationship-map-context-menu');

  state.selectedIds.add('a');
  state.selectedIds.add('c');
  rightClick();
  assert.equal(menu.hidden, false);
  assert.equal(menu.children[0].disabled, true);
  menu.children[1].children[1].children[0].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[0].action, 'clear_interface_contact_pins');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['a', 'c']);
  rightClick();
  menu.children[2].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[1].action, 'remove_interface_contacts');
  assert.deepEqual(Array.from(launches[1].payload.contactIds), ['a', 'c']);

  state.selectedIds.clear();
  rightClick();
  assert.equal(menu.children[0].disabled, false);
  menu.children[0].events.click();
  const editor = diagram.querySelector('.interface-contact-orientation-editor');
  assert.equal(editor.children[0].children[0].value, 'Orientation 1');
  editor.children[0].children[0].value = 'Power side';
  editor.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches[2].action, 'rename_interface_contact_orientation');
  assert.deepEqual(Array.from(launches[2].payload.contactIds), ['a', 'b']);
  assert.equal(launches[2].payload.name, 'Power side');

  context.updateInterfaceContactData(dialog, contacts.map((contact) => ({
    ...contact, orientationName: contact.contactId === 'c' ? '' : 'Power side',
  })));
  assert.equal(state.svg.children[0].children[1].textContent, 'Power side · 2 contacts');
  const renamedBackdrop = state.svg.children[0].children[0];
  state.workspace.viewport.events.contextmenu({
    target: renamedBackdrop, clientX: 50, clientY: 60,
    preventDefault() {}, stopPropagation() {},
  });
  menu.children[1].children[1].children[1].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[3].action, 'clear_interface_contact_values');
  assert.deepEqual(Array.from(launches[3].payload.contactIds), ['a', 'b']);
  state.workspace.viewport.events.contextmenu({
    target: renamedBackdrop, clientX: 50, clientY: 60,
    preventDefault() {}, stopPropagation() {},
  });
  menu.children[2].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(launches[4].action, 'remove_interface_contacts');
  assert.deepEqual(Array.from(launches[4].payload.contactIds), ['a', 'b']);
});

asyncTest('Name Locals chooses saved fields and selected contacts in a popup', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [{
      contactId: 'pad-1', kind: 'face', name: 'Pad', assignedName: 'VCC', pin: '1',
      linked: true, normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  dialog.children[2].contactState.selectedIds.add('pad-1');
  const naming = dialog.children[1].children[1];
  naming.children[2].events.click();
  const form = naming.querySelector('.interface-contact-name-locals');
  assert.equal(form.attributes['aria-label'], 'Name Locals options');
  const values = form.children[1].children[0];
  const pins = form.children[2].children[0];
  const apply = form.children[3];
  assert.equal(values.checked, true);
  assert.equal(pins.checked, true);
  assert.equal(form.children[1].children[1], 'Values');
  assert.equal(form.children[2].children[1], 'Pins');
  assert.equal(launches.length, 0);
  values.checked = false;
  values.events.change();
  pins.checked = false;
  pins.events.change();
  assert.equal(apply.disabled, true);
  values.checked = true;
  values.events.change();
  assert.equal(apply.disabled, false);
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'name_interface_contact_locals');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['pad-1']);
  assert.equal(launches[0].payload.includeValues, true);
  assert.equal(launches[0].payload.includePins, false);
});

test('Auto Pin remembers order, Start, and checkbox choices within the palette session', () => {
  const storage = new Map();
  const { context } = palette(storage);
  const naming = context.document.createElement('div');
  const diagram = context.document.createElement('div');
  context.openInterfaceAutoPin(naming, diagram, 'harness-1', 'interface-1');
  const first = naming.querySelector('.interface-contact-auto-pin');
  const order = first.children[0].children[0];
  const start = first.children[1].children[0];
  const hopscotch = first.children[2].children[0];
  const zigzag = first.children[3].children[0];
  const spiral = first.children[4].children[0];
  const overwrite = first.children[5].children[0];
  assert.equal(order.value, 'LRTB');
  assert.equal(start.value, '0');
  assert.equal(hopscotch.checked, true);
  assert.equal(zigzag.checked, false);
  assert.equal(spiral.checked, false);
  assert.equal(overwrite.checked, false);
  order.value = 'BTRL';
  order.events.change();
  start.value = '42';
  start.events.change();
  zigzag.checked = true;
  zigzag.events.change();
  spiral.checked = true;
  spiral.events.change();
  hopscotch.checked = false;
  hopscotch.events.change();
  first.remove();
  context.openInterfaceAutoPin(naming, diagram, 'harness-1', 'interface-1');
  const second = naming.querySelector('.interface-contact-auto-pin');
  assert.equal(second.children[0].children[0].value, 'BTRL');
  assert.equal(second.children[1].children[0].value, '42');
  assert.equal(second.children[2].children[0].checked, false);
  assert.equal(second.children[3].children[0].checked, false);
  assert.equal(second.children[4].children[0].checked, true);
  assert.equal(second.children[5].children[0].checked, false);
  assert.equal(second.children[5].children[0].disabled, true);
  second.children[2].children[0].checked = true;
  second.children[2].children[0].events.change();
  second.children[5].children[0].checked = true;
  second.children[5].children[0].events.change();
  second.children[3].children[0].checked = true;
  second.children[3].children[0].events.change();
  const anotherPalette = palette(storage).context;
  const anotherNaming = anotherPalette.document.createElement('div');
  const anotherDiagram = anotherPalette.document.createElement('div');
  anotherPalette.openInterfaceAutoPin(anotherNaming, anotherDiagram, 'harness-1', 'interface-1');
  const anotherForm = anotherNaming.querySelector('.interface-contact-auto-pin');
  assert.equal(anotherForm.children[0].children[0].value, 'BTRL');
  assert.equal(anotherForm.children[1].children[0].value, '42');
  assert.equal(anotherForm.children[2].children[0].checked, true);
  assert.equal(anotherForm.children[3].children[0].checked, true);
  assert.equal(anotherForm.children[4].children[0].checked, false);
  assert.equal(anotherForm.children[5].children[0].checked, true);
  assert.equal(anotherForm.children[5].children[0].disabled, false);
  storage.set('cableBundler.autoPinOrder', 'invalid');
  storage.set('cableBundler.autoPinStart', '-1');
  storage.set('cableBundler.autoPinHopscotch', 'bad');
  storage.set('cableBundler.autoPinZigzag', 'true');
  storage.set('cableBundler.autoPinSpiral', 'true');
  storage.set('cableBundler.autoPinOverwrite', 'bad');
  const invalidNaming = anotherPalette.document.createElement('div');
  anotherPalette.openInterfaceAutoPin(invalidNaming, anotherDiagram, 'harness-1', 'interface-1');
  assert.equal(invalidNaming.querySelector('.interface-contact-auto-pin').children[0].children[0].value,
    'LRTB');
  assert.equal(invalidNaming.querySelector('.interface-contact-auto-pin').children[1].children[0].value,
    '0');
  const invalidForm = invalidNaming.querySelector('.interface-contact-auto-pin');
  assert.equal(invalidForm.children[2].children[0].checked, true);
  assert.equal(invalidForm.children[3].children[0].checked, false);
  assert.equal(invalidForm.children[4].children[0].checked, true);
  assert.equal(invalidForm.children[5].children[0].checked, false);
});

test('contact naming and import checkboxes remember session choices', () => {
  const storage = new Map();
  const { context } = palette(storage);
  context.send = () => Promise.resolve({ ok: true, boards: [] });
  const naming = context.document.createElement('div');
  const diagram = context.document.createElement('div');
  diagram.contactState = { selectedIds: new Set() };
  context.openInterfaceGeoImport(naming, diagram, 'harness-1', 'interface-1');
  const geo = naming.querySelector('.interface-contact-geo-import');
  geo.children[3].children[0].checked = false;
  geo.children[3].children[0].events.change();
  geo.children[4].children[0].checked = true;
  geo.children[4].children[0].events.change();
  geo.remove();
  context.openInterfaceNameLocals(naming, diagram, 'harness-1', 'interface-1');
  const locals = naming.querySelector('.interface-contact-name-locals');
  locals.children[1].children[0].checked = false;
  locals.children[1].children[0].events.change();
  locals.remove();
  context.openInterfacePosImport(naming, 'harness-1', 'interface-1');
  const pos = naming.querySelector('.interface-contact-pos-import');
  pos.children[2].children[0].checked = false;
  pos.children[2].children[0].events.change();
  pos.remove();

  const another = palette(storage).context;
  another.send = () => Promise.resolve({ ok: true, boards: [] });
  const anotherNaming = another.document.createElement('div');
  const anotherDiagram = another.document.createElement('div');
  anotherDiagram.contactState = { selectedIds: new Set() };
  another.openInterfaceGeoImport(anotherNaming, anotherDiagram, 'harness-1', 'interface-1');
  const restoredGeo = anotherNaming.querySelector('.interface-contact-geo-import');
  assert.equal(restoredGeo.children[3].children[0].checked, false);
  assert.equal(restoredGeo.children[4].children[0].checked, true);
  restoredGeo.remove();
  another.openInterfaceNameLocals(anotherNaming, anotherDiagram, 'harness-1', 'interface-1');
  const restoredLocals = anotherNaming.querySelector('.interface-contact-name-locals');
  assert.equal(restoredLocals.children[1].children[0].checked, false);
  assert.equal(restoredLocals.children[2].children[0].checked, true);
  restoredLocals.remove();
  another.openInterfacePosImport(anotherNaming, 'harness-1', 'interface-1');
  assert.equal(anotherNaming.querySelector('.interface-contact-pos-import')
    .children[2].children[0].checked, false);
});

test('Geo Import defaults to names and can launch the source Interface picker', () => {
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
  const naming = dialog.children[1].children[1];
  naming.children[3].events.click();
  const form = naming.querySelector('.interface-contact-geo-import');
  const geometry = form.children[1].children[0];
  const selectInterface = form.children[2].children[0];
  const importValues = form.children[3].children[0];
  const importPins = form.children[4].children[0];
  const apply = form.children[5];
  assert.equal(form.attributes['aria-label'], 'Geo Import options');
  assert.equal(geometry.checked, true);
  assert.equal(importValues.checked, true);
  assert.equal(importPins.checked, false);
  assert.equal(form.children[3].children[1], 'Values');
  assert.equal(form.children[4].children[1], 'Pins');
  assert.equal(selectInterface.value, 'interface');
  assert.equal(launches.length, 0);
  geometry.checked = false;
  selectInterface.checked = true;
  selectInterface.events.change();
  assert.equal(apply.disabled, false);
  assert.equal(form.children.length, 7);
  assert.equal(form.children[3].hidden, false);
  assert.equal(form.children[4].hidden, false);
  assert.equal(apply.textContent, 'Pick Interface');
  importValues.checked = false;
  importValues.events.change();
  assert.equal(apply.disabled, true);
  importPins.checked = true;
  importPins.events.change();
  assert.equal(apply.disabled, false);
  form.events.submit({ preventDefault() {} });
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'copy_projected_interface_contacts');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['b']);
  assert.equal(launches[0].payload.copyValues, false);
  assert.equal(launches[0].payload.copyPins, true);
});

test('Geo Import can restore Pins without importing Values', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const naming = context.document.body.querySelector('.interface-contacts-popup').children[1].children[1];
  naming.children[3].events.click();
  const form = naming.querySelector('.interface-contact-geo-import');
  const importValues = form.children[3].children[0];
  const importPins = form.children[4].children[0];
  const apply = form.children[5];
  importValues.checked = false;
  importValues.events.change();
  assert.equal(apply.disabled, true);
  importPins.checked = true;
  importPins.events.change();
  assert.equal(apply.disabled, false);
  form.events.submit({ preventDefault() {} });
  assert.equal(launches[0].action, 'geo_import_interface_contacts');
  assert.equal(launches[0].payload.importValues, false);
  assert.equal(launches[0].payload.importPins, true);
});

asyncTest('projected Interface conflicts submit chosen saved source contacts', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Connector', contacts: [{
      contactId: 'destination-1', name: 'Pin', assignedName: '', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }],
  });
  context.showInterfaceProjectionConflicts({
    harnessId: 'harness-1', interfaceId: 'interface-1', sourceId: 'source-1',
    contactIds: [], copyValues: false, copyPins: true,
    conflicts: [{ contactId: 'destination-1', currentName: '', suggestions: [
      { sourceContactId: 'pad-a', value: 'NET_A', pin: '1' },
      { sourceContactId: 'pad-b', value: 'NET_B', pin: '2' },
    ] }],
  });
  const form = context.document.body.querySelector('.interface-contact-projection-review');
  assert.ok(form);
  const select = form.children[1].children[0].children[1];
  assert.equal(select.children[1].textContent, 'Pin 1');
  select.value = 'pad-b';
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'resolve_projected_interface_contacts');
  assert.deepEqual(Array.from(launches[0].payload.choices, (choice) => ({ ...choice })), [
    { contactId: 'destination-1', sourceContactId: 'pad-b' },
  ]);
  assert.equal(launches[0].payload.copyValues, false);
  assert.equal(launches[0].payload.copyPins, true);
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
