/** Contact selection, loading, and projection regressions. */
const { assert, asyncTest, contactItem, descendants, harness, palette, readPaletteStyles, test } = require('./support.cjs');

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
    'Manual', 'Row', 'Plane', 'Delete',
  ]);
  const naming = dialog.children[1].children[1].children;
  assert.deepEqual(naming.map((button) => button.textContent), ['Pos Import', 'Load brd']);
  assert.deepEqual(modes.slice(0, 3).map((button) => button.attributes['aria-pressed']), [
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
  assert.equal(launches[1].action, 'select_interface_contacts');
  assert.equal(launches[1].payload.mode, 'row');
  assert.equal(launches[0].payload.mode, 'manual');
  modes[2].events.click();
  assert.equal(launches[2].payload.mode, 'plane');
  naming[0].events.click();
  naming[1].events.click();
  assert.deepEqual(launches.slice(3).map((item) => item.action), [
    'pos_import_interface_contacts', 'load_brd_interface_contacts',
  ]);
  assert.deepEqual(modes.slice(0, 3).map((button) => button.attributes['aria-pressed']), [
    'false', 'false', 'true',
  ]);
  dialog.children[3].children[0].events.click();
  assert.equal(context.document.body.querySelector('.interface-contacts-popup'), undefined);
});

test('Contact hover highlights its Fusion target and clears on leave, refresh, and close', () => {
  const { context } = palette();
  const highlights = [];
  const clears = [];
  context.highlightMember = (_harness, type, id, extra) => {
    highlights.push([type, id, extra.interfaceId]);
  };
  context.send = (action) => {
    if (action === 'clear_highlight') clears.push(action);
    return Promise.resolve({ ok: true });
  };
  const contacts = [{
    contactId: 'pad-a', name: 'Pad A', linked: true, geometryRevision: 1,
    normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
  }];
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  let item = contactItem(dialog.children[2], 'pad-a');
  item.events.mouseenter();
  assert.deepEqual(highlights, [['interface_contact', 'pad-a', 'i']]);
  item.events.mouseleave();
  assert.equal(clears.length, 1);
  item.events.mouseenter();
  context.renderInterfaceContacts(dialog.children[2], contacts);
  assert.equal(clears.length, 2);
  item = contactItem(dialog.children[2], 'pad-a');
  item.events.mouseenter();
  dialog.close();
  assert.equal(clears.length, 3);
});

asyncTest('Delete button and Del key remove only selected Interface contacts', async () => {
  const { context } = palette();
  const requests = [];
  context.send = (action, payload) => {
    requests.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const contacts = ['a', 'b', 'c'].map((contactId, index) => ({
    contactId, name: contactId, linked: true, geometryRevision: 1,
    loops: [[[index, 0, 0], [index + 0.5, 0, 0], [index, 0.5, 0]]],
  }));
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  const state = diagram.contactState;
  const remove = dialog.children[1].children[0].children[3];
  assert.equal(remove.disabled, true);
  state.workspace.viewport.events.keydown({
    key: 'Enter', target: contactItem(diagram, 'a'), preventDefault() {},
  });
  state.workspace.viewport.events.keydown({
    key: 'Enter', target: contactItem(diagram, 'c'), shiftKey: true, preventDefault() {},
  });
  assert.equal(remove.disabled, false);
  remove.events.click();
  remove.events.click();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].action, 'remove_interface_contacts');
  assert.equal(requests[0].payload.harnessId, 'h');
  assert.equal(requests[0].payload.interfaceId, 'i');
  assert.deepEqual([...requests[0].payload.contactIds], ['a', 'c']);
  await new Promise((resolve) => setImmediate(resolve));
  context.updateInterfaceContactData(dialog, [contacts[1]]);
  assert.equal(state.selectedIds.size, 0);
  assert.equal(remove.disabled, true);
  state.workspace.viewport.events.keydown({
    key: 'Enter', target: contactItem(diagram, 'b'), preventDefault() {},
  });
  let prevented = false;
  state.workspace.viewport.events.keydown({
    key: 'Delete', target: state.workspace.viewport, preventDefault() { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.equal(requests[1].action, 'remove_interface_contacts');
  assert.deepEqual([...requests[1].payload.contactIds], ['b']);
  dialog.close();
});

asyncTest('Contact geometry requests coalesce, reuse names, and release closed diagrams', async () => {
  const { context } = palette();
  const requests = [];
  context.send = (action) => new Promise((resolve) => requests.push({ action, resolve }));
  const metadata = [{ contactId: 'a', name: 'face', assignedName: '', geometryRevision: 1 }];
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: metadata });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  assert.equal(diagram.contactState.items.length, 0);
  assert.equal(diagram.contactState.workspace.root.hidden, true);
  assert.equal(diagram.attributes['aria-busy'], 'true');
  assert.equal(diagram.querySelector('.interface-contact-loading').children[0].textContent,
    'Loading contacts… 0 / 1');
  context.updateInterfaceContactData(dialog, metadata);
  assert.equal(requests.length, 1);
  const geometry = { contactId: 'a', linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]] };
  requests[0].resolve({ ok: true, contacts: [geometry] });
  await new Promise((resolve) => setImmediate(resolve));
  const svg = diagram.contactState.svg;
  assert.equal(diagram.contactState.workspace.root.hidden, false);
  assert.equal(diagram.querySelector('.interface-contact-loading'), undefined);
  assert.equal(diagram.attributes['aria-busy'], 'false');
  context.updateInterfaceContactData(dialog, metadata);
  assert.equal(diagram.contactState.svg, svg);
  context.updateInterfaceContactData(dialog, [{ ...metadata[0], name: 'J1.1', assignedName: 'J1.1' }]);
  assert.equal(requests.length, 1);
  assert.equal(diagram.contactState.contacts[0].assignedName, 'J1.1');
  assert.equal(diagram.contactState.contacts[0].loops.length, 1);
  context.updateInterfaceContactData(dialog, [{ ...metadata[0], geometryRevision: 2 }]);
  context.updateInterfaceContactData(dialog, [{ ...metadata[0], geometryRevision: 3 }]);
  assert.equal(requests.length, 2);
  requests[1].resolve({ ok: true, contacts: [] });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 3);
  dialog.close();
  requests[2].resolve({ ok: true, contacts: [geometry] });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(diagram.contactState, null);
  assert.equal(diagram.children.length, 0);
  assert.equal(dialog.contactMetadata.length, 0);
  assert.equal(context.document.body.querySelector('.interface-contacts-popup'), undefined);
});

asyncTest('Unchanged contact sources keep the diagram across model revisions', async () => {
  const { context } = palette();
  const actions = [];
  let signature = 'same-source';
  context.send = async (action) => {
    actions.push(action);
    if (action === 'get_interface_contact_signatures') {
      return { ok: true, signatures: { a: signature } };
    }
    return { ok: true, contacts: [{
      contactId: 'a', name: 'A', sourceSignature: signature, linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }] };
  };
  const contact = { contactId: 'a', name: 'A', geometryRevision: 1 };
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts: [contact],
  });
  await new Promise((resolve) => setImmediate(resolve));
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const svg = dialog.children[2].contactState.svg;
  for (const revision of [2, 3, 4]) {
    context.updateInterfaceContactData(dialog, [{ ...contact, geometryRevision: revision }]);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(dialog.children[2].contactState.svg, svg);
  }
  assert.deepEqual(actions, [
    'get_interface_contacts',
    'get_interface_contact_signatures',
    'get_interface_contact_signatures',
    'get_interface_contact_signatures',
  ]);
  dialog.close();
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts: [{ ...contact, geometryRevision: 5 }],
  });
  await new Promise((resolve) => setImmediate(resolve));
  const reopened = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(reopened.children[2].contactState.svg, svg);
  signature = 'changed-source';
  context.updateInterfaceContactData(reopened, [{ ...contact, geometryRevision: 6 }]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.notEqual(reopened.children[2].contactState.svg, svg);
  assert.equal(actions.at(-1), 'get_interface_contacts');
  reopened.close();
});

asyncTest('Closing contacts stops additional geometry batches', async () => {
  const { context } = palette();
  const requests = [];
  context.send = (_action, payload) => new Promise((resolve) => requests.push({ payload, resolve }));
  const contacts = Array.from({ length: 30 }, (_, index) => ({ contactId: `${index}`, geometryRevision: 1 }));
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].payload.contactIds.length, 30);
  requests[0].resolve({ ok: true, cacheComplete: false, contacts: [] });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[1].payload.contactIds.length, 8);
  context.document.body.querySelector('.interface-contacts-popup').close();
  requests[1].resolve({ ok: true, contacts: [] });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 2);
});

asyncTest('A complete warm cache loads many contacts in one request', async () => {
  const { context } = palette();
  const actions = [];
  const contacts = Array.from({ length: 255 }, (_, index) => ({ contactId: `${index}`, geometryRevision: 0 }));
  context.send = async (action, payload) => {
    actions.push({ action, payload });
    return { ok: true, cacheComplete: true, contacts: contacts.map((item, index) => ({
      contactId: item.contactId, linked: true, normal: [0, 0, 1],
      loops: [[[index, 0, 0], [index + 0.5, 0, 0], [index + 0.5, 0.5, 0]]],
    })) };
  };
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts });
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(actions.map((item) => item.action), ['get_interface_contacts_cached']);
  assert.equal(actions[0].payload.contactIds.length, 255);
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(dialog.children[2].contactState.items.length, 255);
  const diagram = dialog.children[2];
  dialog.close();
  assert.equal(diagram.contactState, null);
  assert.equal(diagram.children.length, 0);
});

asyncTest('Reopening unchanged contacts reuses bounded geometry and current names', async () => {
  const { context } = palette();
  const requests = [];
  context.send = (action) => {
    requests.push(action);
    return Promise.resolve({ ok: true, contacts: [{
      contactId: 'a', linked: true, normal: [0, 0, 1],
      loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }] });
  };
  const original = [{ contactId: 'a', name: 'face', assignedName: '', geometryRevision: 4 }];
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: original });
  await new Promise((resolve) => setImmediate(resolve));
  const firstSvg = context.document.body.querySelector('.interface-contacts-popup')
    .children[2].contactState.svg;
  const firstStage = context.document.body.querySelector('.interface-contacts-popup')
    .children[2].contactState.workspace.stage;
  context.document.body.querySelector('.interface-contacts-popup').close();
  assert.equal(firstStage.children.length, 0);
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: original });
  let dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(dialog.children[2].contactState.svg, firstSvg);
  assert.equal(requests.length, 1);
  const reusedItem = dialog.children[2].contactState.items[0].node;
  dialog.children[2].contactState.workspace.viewport.events.keydown({
    key: 'Enter', target: reusedItem, preventDefault() {},
  });
  assert.equal(reusedItem.attributes['aria-selected'], 'true');
  dialog.close();
  const renamed = [{ ...original[0], name: 'J1.1', assignedName: 'J1.1' }];
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: renamed });
  dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(requests.length, 1);
  assert.notEqual(dialog.children[2].contactState.svg, firstSvg);
  assert.equal(dialog.children[2].contactState.contacts[0].assignedName, 'J1.1');
  assert.equal(dialog.children[2].contactState.items.length, 1);
  assert.equal(dialog.querySelector('.interface-contact-loading'), undefined);
  dialog.close();
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket',
    contacts: [{ ...renamed[0], geometryRevision: 5 }] });
  dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(requests.length, 2);
  assert.ok(dialog.querySelector('.interface-contact-loading'));
  dialog.close();
});

asyncTest('Rebuild Cache clears the snapshot and resamples with progress', async () => {
  const { context } = palette();
  const requests = [];
  context.send = (action) => new Promise((resolve) => requests.push({ action, resolve }));
  const contact = { contactId: 'a', name: 'Pad', assignedName: '', geometryRevision: 1 };
  const projection = { contactId: 'a', linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]] };
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: [contact] });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  requests[0].resolve({ ok: true, contacts: [projection] });
  await new Promise((resolve) => setImmediate(resolve));
  const firstSvg = dialog.children[2].contactState.svg;
  const rebuild = dialog.children[3].children[1];
  assert.equal(rebuild.textContent, 'Rebuild Cache');
  rebuild.events.click();
  assert.equal(rebuild.disabled, true);
  assert.equal(requests[1].action, 'rebuild_interface_contacts_cache');
  assert.equal(dialog.children[2].querySelector('.interface-contact-loading').children[1].value, 0);
  requests[1].resolve({ ok: true, diskCacheAvailable: true });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[2].action, 'get_interface_contacts');
  assert.equal(rebuild.disabled, true);
  requests[2].resolve({ ok: true, contacts: [projection] });
  await new Promise((resolve) => setImmediate(resolve));
  assert.notEqual(dialog.children[2].contactState.svg, firstSvg);
  assert.equal(dialog.children[2].querySelector('.interface-contact-loading'), undefined);
  assert.equal(rebuild.disabled, false);
  dialog.close();
});

asyncTest('Developer mode reports contact cache eligibility after loading', async () => {
  const preferences = new Map([
    ['cableBundler.developerMode', 'true'],
    ['cableBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const actions = [];
  context.send = async (action) => {
    actions.push(action);
    if (action === 'get_interface_contact_cache_status') {
      return { ok: true, cache: { reason: 'document has unsaved changes', snapshot: 'unavailable' } };
    }
    return { ok: true, cacheBefore: { reason: 'document has unsaved changes', snapshot: 'unavailable' },
      cacheStats: { hits: 0, misses: 1 }, serverMs: 18,
      contacts: [{ contactId: 'a', linked: true, normal: [0, 0, 1],
      loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]] }] };
  };
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket',
    contacts: [{ contactId: 'a', name: 'Pad', assignedName: '', geometryRevision: 1 }] });
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(actions, ['get_interface_contacts', 'get_interface_contact_cache_status']);
  assert.match(context.ui.notice.children.at(-1).textContent, /before document has unsaved changes/);
  assert.match(context.ui.notice.children.at(-1).textContent, /0 hits \/ 1 misses/);
  assert.match(context.ui.notice.children.at(-1).textContent, /document has unsaved changes/);
  context.document.body.querySelector('.interface-contacts-popup').close();
});

asyncTest('A name arriving during geometry loading is part of the cached image', async () => {
  const { context } = palette();
  const requests = [];
  context.send = () => new Promise((resolve) => requests.push(resolve));
  const contact = { contactId: 'a', name: 'face', assignedName: '', geometryRevision: 1 };
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: [contact] });
  const first = context.document.body.querySelector('.interface-contacts-popup');
  const renamed = { ...contact, name: 'J1.1', assignedName: 'J1.1' };
  context.updateInterfaceContactData(first, [renamed]);
  requests[0]({ ok: true, contacts: [{
    contactId: 'a', linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
  }] });
  await new Promise((resolve) => setImmediate(resolve));
  const svg = first.children[2].contactState.svg;
  first.close();
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: [renamed] });
  const reopened = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(reopened.children[2].contactState.svg, svg);
  assert.equal(requests.length, 1);
  reopened.close();
});

test('Contact geometry cache drops oversized snapshots', () => {
  const { context } = palette();
  const dialog = { dataset: { harnessId: 'h', interfaceId: 'i' } };
  context.rememberContactGeometry(dialog, 'revision-1', [{ blob: 'x'.repeat(2_000_000) }]);
  assert.equal(context.restoredContactGeometry(dialog, 'revision-1'), null);
  context.rememberContactGeometry(dialog, 'revision-2', [{ contactId: 'a', loops: [] }]);
  assert.equal(context.restoredContactGeometry(dialog, 'revision-2').length, 1);
  context.render({ harnesses: [], notice: '', theme: { mode: 'fixed', active: 'dark' } });
  assert.equal(context.restoredContactGeometry(dialog, 'revision-2'), null);
});

asyncTest('Rendered contact image survives when raw geometry exceeds the memory budget', async () => {
  const { context } = palette();
  const requests = [];
  context.send = () => new Promise((resolve) => requests.push(resolve));
  const geometry = [{
    contactId: 'a', name: 'A', geometryRevision: 1, linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]], blob: 'x'.repeat(2_000_000),
  }];
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: geometry });
  const first = context.document.body.querySelector('.interface-contacts-popup');
  const svg = first.children[2].contactState.svg;
  assert.equal(context.restoredContactGeometry(first, context.contactGeometryKey(geometry)), null);
  first.close();
  const metadata = [{ contactId: 'a', name: 'A', geometryRevision: 1 }];
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts: metadata });
  const reopened = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(reopened.children[2].contactState.svg, svg);
  assert.equal(requests.length, 0);
  context.updateInterfaceContactData(reopened, [{ ...metadata[0], name: 'A1', assignedName: 'A1' }]);
  assert.equal(requests.length, 1);
  reopened.close();
  requests[0]({ ok: true, contacts: [] });
  await new Promise((resolve) => setImmediate(resolve));
});

test('Contact image outlines collapse dense rectangles but preserve curved edges', () => {
  const { context } = palette();
  const rectangle = [
    ...Array.from({ length: 21 }, (_, index) => [index, 0]),
    ...Array.from({ length: 10 }, (_, index) => [20, index + 1]),
    ...Array.from({ length: 20 }, (_, index) => [19 - index, 10]),
    ...Array.from({ length: 9 }, (_, index) => [0, 9 - index]),
    [0, 0],
  ];
  assert.equal(JSON.stringify(context.simplifyContactOutline(rectangle)),
    JSON.stringify([[0, 0], [20, 0], [20, 10], [0, 10]]));
  const circle = Array.from({ length: 32 }, (_, index) => [
    10 * Math.cos(index * Math.PI / 16), 10 * Math.sin(index * Math.PI / 16),
  ]);
  const rounded = context.simplifyContactOutline(circle);
  assert.ok(rounded.length > 4 && rounded.length < circle.length);
});

asyncTest('Contact loading reports progress and failure without unavailable placeholders', async () => {
  const { context } = palette();
  const requests = [];
  context.send = () => new Promise((resolve) => requests.push(resolve));
  const contacts = Array.from({ length: 9 }, (_, index) => ({
    contactId: `${index}`, name: 'face', geometryRevision: 1,
  }));
  context.openInterfaceContacts({ harnessId: 'h' }, { interfaceId: 'i', name: 'Socket', contacts });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  requests[0]({ ok: true, contacts: contacts.slice(0, 8) });
  await new Promise((resolve) => setImmediate(resolve));
  const status = diagram.querySelector('.interface-contact-loading');
  assert.equal(status.children[0].textContent, 'Loading contacts… 8 / 9');
  assert.equal(status.children[1].value, 8);
  assert.equal(status.children[1].max, 9);
  assert.equal(diagram.contactState.items.length, 0);
  requests[1]({ ok: false, error: 'Geometry request failed' });
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(status.children[0].textContent, /Unable to load contacts/);
  assert.equal(status.children[1].hidden, true);
  assert.equal(diagram.contactState.workspace.root.hidden, true);
  assert.equal(diagram.attributes['aria-busy'], 'false');
  dialog.close();
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

test('Value and Pin appear inside a contact with room for two lines', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'pad-1', kind: 'face', name: 'J5.2', assignedName: 'J5.2', pin: 'P7', linked: true,
    normal: [0, 0, 1], loops: [[[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0]]],
  }]);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className === 'interface-contact-label'
  ));
  assert.equal(labels.length, 2);
  assert.equal(labels[0].textContent, 'J5.2');
  assert.equal(labels[1].textContent, 'Pin P7');
  assert.ok(Number(labels[0].attributes.y) < Number(labels[1].attributes.y));
  const zoomOut = descendants(diagram, (node) => node.title === 'Zoom out')[0];
  for (let index = 0; index < 20; index += 1) zoomOut.events.click();
  assert.equal(labels[0].style.display, 'none');
  assert.equal(labels[1].style.display, 'none');
  const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
  for (let index = 0; index < 20; index += 1) zoomIn.events.click();
  assert.equal(labels[0].style.display, '');
  assert.equal(labels[1].style.display, '');
});

test('a contact with only Pin shows its pin in the diagram and accessible name', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'pin-only', kind: 'face', name: 'Pad', assignedName: '', pin: '12',
    linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]],
  }]);
  const item = contactItem(diagram, 'pin-only');
  const label = descendants(item, (node) => node.className?.includes('interface-contact-label'))[0];
  assert.equal(label.textContent, 'Pin 12');
  assert.match(item.attributes['aria-label'], /Pin 12/);
});

test('compact contacts keep Value outside and unnamed contacts have a distinct appearance', () => {
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
    node.className?.includes('interface-contact-label-outside')
  ))[0];
  assert.equal(label.textContent, 'A1');
  assert.equal(label.style.display, undefined);
  const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
  for (let index = 0; index < 20; index += 1) zoomIn.events.click();
  assert.equal(label.style.display, undefined);
  assert.equal(descendants(contactItem(diagram, 'named'), (node) => node.tag === 'title')[0]
    .textContent, 'A1');
  assert.match(descendants(contactItem(diagram, 'unnamed'), (node) => node.tag === 'title')[0]
    .textContent, /Unnamed contact/);
});

test('dense two-column contacts place nonoverlapping Pin and Value labels on outer sides', () => {
  const { context } = palette();
  const contacts = Array.from({ length: 38 }, (_unused, index) => {
    const column = index < 19 ? 0 : 1;
    const row = index % 19;
    const x = column * 20;
    const y = row * 2;
    return {
      contactId: `pad-${index}`, kind: 'face', name: `Pad ${index}`,
      assignedName: `V${index}`, pin: `${index + 1}`, linked: true, normal: [0, 0, 1],
      loops: [[[x, y, 0], [x + 0.5, y, 0], [x + 0.5, y + 0.5, 0], [x, y + 0.5, 0]]],
    };
  });
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, contacts);
  const { svg, items, diagramWidth, diagramHeight } = diagram.contactState;
  const labels = descendants(svg, (node) => node.className?.includes('interface-contact-label-outside'));
  const leaders = descendants(svg, (node) => node.className === 'interface-contact-label-leader');
  assert.equal(labels.length, 38);
  assert.equal(leaders.length, 38);
  assert.equal(labels[0].textContent, 'Pin 1 · V0');
  assert.notEqual(labels[0].attributes['text-anchor'], labels[19].attributes['text-anchor']);
  assert.ok(labels[0].attributes['text-anchor'] === 'end'
    ? Number(labels[0].attributes.x) < items[0].loops[0][0][0]
    : Number(labels[0].attributes.x) > items[0].loops[0][0][0]);
  assert.ok(labels[19].attributes['text-anchor'] === 'end'
    ? Number(labels[19].attributes.x) < items[19].loops[0][0][0]
    : Number(labels[19].attributes.x) > items[19].loops[0][0][0]);
  for (const start of [0, 19]) {
    for (let index = start + 1; index < start + 19; index += 1) {
      assert.ok(Number(labels[index].attributes.y) - Number(labels[index - 1].attributes.y) >= 16);
    }
  }
  assert.ok(labels.every((label) => Number(label.attributes.x) > 0
    && Number(label.attributes.x) < diagramWidth
    && Number(label.attributes.y) < diagramHeight));
});

test('wide contact rows place compact labels above and below the geometry', () => {
  const { context } = palette();
  const contacts = [0, 1].flatMap((row) => Array.from({ length: 3 }, (_unused, column) => ({
    contactId: `${row}-${column}`, kind: 'face', assignedName: `V${row}${column}`,
    linked: true, normal: [0, 0, 1],
    loops: [[[column * 8, row * 2, 0], [column * 8 + 0.5, row * 2, 0],
      [column * 8 + 0.5, row * 2 + 0.5, 0], [column * 8, row * 2 + 0.5, 0]]],
  })));
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, contacts);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className?.includes('interface-contact-label-outside')
  ));
  assert.equal(labels.length, 6);
  assert.equal(labels.slice(0, 3).every((label) => label.attributes['text-anchor'] === 'middle'), true);
  assert.ok(Number(labels[0].attributes.y) < diagram.contactState.items[0].loops[0][0][1]);
  assert.ok(Number(labels[3].attributes.y) > diagram.contactState.items[3].loops[0][0][1]);
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
