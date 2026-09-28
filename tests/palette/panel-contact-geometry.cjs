/** Contact selection, loading, and projection regressions. */
const { assert, asyncTest, contactItem, descendants, harness, palette, test } = require('./support.cjs');

test('Contacts Editor lifecycle logs opening and button close without contact contents', () => {
  const { context } = palette();
  const observations = [];
  context.window.adsk = { fusionSendData(action, data) {
    assert.equal(action, 'log_contact_editor_lifecycle');
    observations.push(JSON.parse(data));
    return Promise.resolve('{}');
  } };
  const contacts = [{ contactId: 'secret-contact', name: 'secret-name', pin: 'secret-pin' }];
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  dialog.children[3].children[0].events.click();

  assert.deepEqual(observations.map((entry) => [entry.event, entry.reason]), [
    ['open-request', 'initial'], ['open-shown', 'initial'], ['close', 'button'],
  ]);
  assert.deepEqual(observations.map((entry) => entry.sequence), [1, 2, 3]);
  assert.equal(observations[0].attached, false);
  assert.equal(observations[1].open, true);
  assert.equal(observations[2].open, false);
  assert.equal(observations[2].contactCount, 1);
  assert.equal(JSON.stringify(observations).includes('secret-'), false);
});

test('Contacts Editor lifecycle records document-change closure', () => {
  const { context } = palette();
  const observations = [];
  context.window.adsk = { fusionSendData(_action, data) {
    observations.push(JSON.parse(data));
    return Promise.resolve('{}');
  } };
  const definition = harness();
  definition.interfaces = [{ interfaceId: 'i', name: 'Socket', contacts: [] }];
  const showDocument = (scope) => context.render({
    contactDocumentScope: scope, harnesses: [definition], notice: '',
    theme: { mode: 'fixed', active: 'dark' },
  });
  showDocument('first');
  context.openInterfaceContacts(definition, definition.interfaces[0]);
  showDocument('second');

  const closure = observations.find((entry) => entry.event === 'close');
  assert.equal(closure.reason, 'document-scope-changed');
  assert.equal(closure.scopeMatches, false);
});

test('Edit Contacts opens the Contacts Editor with Manual, Row, and Plane modes', () => {
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
  assert.equal(menu.children[0].textContent, 'Edit Contacts');
  menu.children[0].events.click();

  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(dialog.open, true);
  assert.equal(dialog.children[0].textContent, 'Contacts Editor · Socket A');
  assert.equal(dialog.attributes['aria-label'], 'Contacts Editor: Socket A');
  const modes = dialog.children[1].children[0].children;
  assert.deepEqual(modes.map((button) => button.textContent), [
    'Manual', 'Row', 'Plane', 'Delete',
  ]);
  const naming = dialog.children[1].children[1].children;
  assert.deepEqual(naming.map((button) => button.textContent),
    ['Auto Pin', 'Auto Connect', 'Name Locals', 'Geo Import', 'Pos Import']);
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
  naming[3].events.click();
  const geoForm = dialog.children[1].children[1].querySelector('.interface-contact-geo-import');
  assert.equal(launches.length, 3);
  geoForm.events.submit({ preventDefault() {} });
  naming[4].events.click();
  const form = dialog.children[1].children[1].querySelector('.interface-contact-pos-import');
  form.children[3].events.click();
  assert.deepEqual(launches.slice(3).map((item) => item.action), [
    'geo_import_interface_contacts', 'get_pos_import_boards', 'load_brd_interface_contacts',
  ]);
  assert.deepEqual(Array.from(launches[3].payload.contactIds), []);
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

asyncTest('A closing document quietly cancels its pending contact signature check', async () => {
  const { context } = palette();
  const actions = [];
  context.send = async (action, payload) => {
    actions.push({ action, payload });
    if (action === 'get_interface_contact_signatures') return { ok: false, stale: true };
    return { ok: true, contacts: [{
      contactId: 'a', sourceSignature: 'source', linked: true, normal: [0, 0, 1],
      loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }] };
  };
  const contact = { contactId: 'a', name: 'Pad', geometryRevision: 1 };
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts: [contact],
  });
  await new Promise((resolve) => setImmediate(resolve));
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  context.updateInterfaceContactData(dialog, [{ ...contact, geometryRevision: 2 }]);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(dialog.open, false);
  assert.deepEqual(actions.map((item) => item.action), [
    'get_interface_contacts', 'get_interface_contact_signatures',
  ]);
  assert.equal(actions[1].payload.contactDocumentScope, '');
  assert.equal(context.document.body.querySelector('.interface-contacts-popup'), undefined);
  assert.equal(context.ui.notice.children.length, 0);
});

asyncTest('A stale warm-cache reply closes the old contact dialog without retrying', async () => {
  const { context } = palette();
  const actions = [];
  context.send = async (action, payload) => {
    actions.push({ action, payload });
    return { ok: false, stale: true };
  };
  const contacts = Array.from({ length: 17 }, (_, index) => ({
    contactId: `${index}`, name: `Pad ${index}`, geometryRevision: 1,
  }));
  context.openInterfaceContacts({ harnessId: 'h' }, {
    interfaceId: 'i', name: 'Socket', contacts,
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(dialog.open, false);
  assert.deepEqual(actions.map((item) => item.action), ['get_interface_contacts_cached']);
  assert.equal(actions[0].payload.contactDocumentScope, '');
  assert.equal(context.ui.notice.children.length, 0);
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

asyncTest('Switching documents restores each Interface image without resampling', async () => {
  const { context } = palette();
  const requests = [];
  let activeDocument = 'first';
  const contacts = [{ contactId: 'a', name: 'Pad', assignedName: '', geometryRevision: 0 }];
  const definition = harness();
  definition.interfaces = [{ interfaceId: 'i', name: 'Socket', contacts }];
  context.send = (action) => {
    requests.push([activeDocument, action]);
    const x = activeDocument === 'first' ? 0 : 10;
    return Promise.resolve({ ok: true, contacts: [{
      contactId: 'a', linked: true, normal: [0, 0, 1],
      loops: [[[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0]]],
    }] });
  };
  const showDocument = (scope) => context.render({
    contactDocumentScope: scope, harnesses: [definition], notice: '',
    theme: { mode: 'fixed', active: 'dark' },
  });

  showDocument('document-first');
  context.openInterfaceContacts(definition, definition.interfaces[0]);
  await new Promise((resolve) => setImmediate(resolve));
  let dialog = context.document.body.querySelector('.interface-contacts-popup');
  const firstSvg = dialog.children[2].contactState.svg;

  activeDocument = 'second';
  showDocument('document-second');
  assert.equal(dialog.open, false);
  context.openInterfaceContacts(definition, definition.interfaces[0]);
  await new Promise((resolve) => setImmediate(resolve));
  dialog = context.document.body.querySelector('.interface-contacts-popup');
  const secondSvg = dialog.children[2].contactState.svg;
  assert.notEqual(secondSvg, firstSvg);
  dialog.close();

  activeDocument = 'first';
  showDocument('document-first');
  context.openInterfaceContacts(definition, definition.interfaces[0]);
  dialog = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(dialog.children[2].contactState.svg, firstSvg);
  assert.deepEqual(requests, [['first', 'get_interface_contacts'], ['second', 'get_interface_contacts']]);
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
