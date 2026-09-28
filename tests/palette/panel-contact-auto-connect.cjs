/** Auto Connect dialog and grouped-end picker request regressions. */
const { assert, asyncTest, descendants, palette } = require('./support.cjs');

/** Complete one mocked Fusion ending picker without saving an Auto Connect edit. */
function finishEndingPick(context, calls, connectionId) {
  const request = calls.at(-1).payload;
  context.window.fusionJavaScriptHandler.handle('auto_connect_ending_selected', JSON.stringify({
    harnessId: request.harnessId, side: request.side, requestId: request.requestId,
    cancelled: false, connectionId, parentAttachmentId: null, name: connectionId,
  }));
}

asyncTest('Auto Connect sends selected contacts with checked options and converted size', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({
    harnessId: 'harness-1', lengthUnits: { symbol: 'cm', millimetersPerUnit: 10 },
  }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const naming = dialog.children[1].children[1];
  const state = dialog.children[2].contactState;
  state.items = [{ id: 'a' }, { id: 'b' }];
  state.workspace.root.hidden = false;
  state.selectedIds.add('b');
  naming.children[1].events.click();
  const panel = naming.querySelector('.interface-contact-auto-connect');
  assert.equal(panel.attributes['aria-label'], 'Auto Connect options');
  assert.equal(descendants(panel, (item) => item.tag === 'button'
    && item.textContent === 'Select Ending').length, 2);
  const inputs = descendants(panel, (item) => item.tag === 'input');
  assert.equal(inputs[0].checked, true);
  assert.equal(inputs[1].checked, true);
  assert.equal(inputs[2].parentElement.textContent, 'Connection diameter (cm)');
  assert.equal(inputs[3].checked, true);
  assert.equal(inputs[4].checked, true);
  inputs[1].checked = false;
  inputs[2].value = '0.25';
  const apply = descendants(panel, (item) => item.tag === 'button'
    && item.textContent === 'Apply')[0];
  assert.equal(apply.disabled, true);
  panel.querySelector('button').events.click();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'auto_connect_interface_contacts');
  assert.equal(calls.at(-1).payload.side, 'source');
  assert.equal(calls.length, 1);
  finishEndingPick(context, calls, 'ending-1');
  assert.equal(apply.disabled, false);
  apply.events.click();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'apply_auto_connect_interface_contacts');
  assert.equal(calls.at(-1).payload.connectionId, 'ending-1');
  assert.deepEqual(Array.from(calls.at(-1).payload.contactIds), ['b']);
  assert.equal(calls.at(-1).payload.includePins, true);
  assert.equal(calls.at(-1).payload.includeValues, false);
  assert.equal(calls.at(-1).payload.diameterMm, 2.5);
  assert.equal(dialog.open, true);
  assert.equal(naming.querySelector('.interface-contact-auto-connect'), undefined);
});

asyncTest('Auto Connect selects a target Interface and sends both contact sets', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  const source = { interfaceId: 'interface-1', name: 'Source', contacts: [] };
  const target = { interfaceId: 'interface-2', name: 'Target', contacts: [] };
  const harness = { harnessId: 'harness-1', interfaces: [source, target] };
  const master = context.document.createElement('div');
  const toolbar = context.document.createElement('div');
  const filter = context.document.createElement('input');
  master.className = 'relationship-map';
  toolbar.className = 'relationship-map-toolbar';
  filter.className = 'filter';
  filter.value = 'Source';
  toolbar.append(filter);
  master.append(toolbar);
  context.document.body.append(master);
  context.openInterfaceContacts(harness, source);
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const state = dialog.children[2].contactState;
  state.items = [{ id: 'a' }, { id: 'b' }];
  state.workspace.root.hidden = false;
  state.selectedIds.add('b');
  const sourceEditContact = state.onEditContact;
  dialog.children[1].children[1].children[1].events.click();
  const panel = dialog.querySelector('.interface-contact-auto-connect');
  const buttons = descendants(panel, (item) => item.tag === 'button');
  const pendingCloseEvents = [];
  dialog.close = () => {
    dialog.open = false;
    pendingCloseEvents.push(() => dialog.events.close());
  };
  buttons[1].events.click();
  assert.equal(dialog.open, false);
  assert.equal(filter.value, '');
  assert.equal(master.dataset.autoConnectSelectingTarget, 'true');
  assert.equal(toolbar.querySelector('.interface-auto-connect-target-prompt')?.tag, 'div');
  state.items = [];
  const card = context.renderRelationshipInterfaceCard(harness, target, () => {});
  card.events.click();
  pendingCloseEvents.shift()();
  assert.equal(dialog.open, true);
  assert.equal(context.document.body.querySelector('.interface-contacts-popup'), dialog);
  assert.equal(toolbar.querySelector('.interface-auto-connect-target-prompt'), undefined);
  assert.equal(dialog.dataset.interfaceId, 'interface-2');
  state.items = [{ id: 'x' }, { id: 'y' }];
  state.workspace.root.hidden = false;
  state.selectedIds.add('y');
  const inputs = descendants(panel, (item) => item.tag === 'input');
  inputs[3].checked = false;
  const apply = descendants(panel, (item) => item.tag === 'button'
    && item.textContent === 'Apply')[0];
  buttons[0].events.click();
  finishEndingPick(context, calls, 'ending-1');
  assert.equal(apply.disabled, true);
  buttons[2].events.click();
  assert.equal(calls.at(-1).payload.side, 'target');
  finishEndingPick(context, calls, 'ending-2');
  assert.equal(apply.disabled, false);
  apply.events.click();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'apply_auto_connect_interface_contacts');
  assert.deepEqual(Array.from(calls.at(-1).payload.contactIds), ['b']);
  assert.equal(calls.at(-1).payload.targetInterfaceId, 'interface-2');
  assert.deepEqual(Array.from(calls.at(-1).payload.targetContactIds), ['y']);
  assert.equal(calls.at(-1).payload.targetIncludePins, false);
  assert.equal(dialog.open, true);
  assert.equal(pendingCloseEvents.length, 0);
  assert.equal(dialog.dataset.interfaceId, 'interface-1');
  assert.equal(dialog.children[0].textContent, 'Contacts Editor · Source');
  assert.equal(state.interfaceId, 'interface-1');
  assert.equal(state.autoConnectTargetPreview, false);
  assert.equal(state.onEditContact, sourceEditContact);
  assert.equal(dialog.querySelector('.interface-contact-auto-connect'), undefined);
  assert.notEqual(dialog.children[1].children[1].children[1].disabled, true);
});

asyncTest('Auto Connect target selection can be cancelled from the master diagram', async () => {
  const { context } = palette();
  const source = { interfaceId: 'interface-1', name: 'Source', contacts: [] };
  const harness = { harnessId: 'harness-1', interfaces: [source] };
  const master = context.document.createElement('div');
  const toolbar = context.document.createElement('div');
  master.className = 'relationship-map';
  toolbar.className = 'relationship-map-toolbar';
  master.append(toolbar);
  context.document.body.append(master);
  context.openInterfaceContacts(harness, source);
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const state = dialog.children[2].contactState;
  state.items = [{ id: 'a' }];
  state.workspace.root.hidden = false;
  dialog.children[1].children[1].children[1].events.click();
  const panel = dialog.querySelector('.interface-contact-auto-connect');
  const selectTarget = descendants(panel, (item) => item.tag === 'button'
    && item.textContent === 'Select Target Contacts')[0];
  selectTarget.events.click();
  toolbar.querySelector('.interface-auto-connect-target-prompt')
    .querySelector('button').events.click();
  assert.equal(dialog.open, true);
  assert.equal(dialog.dataset.interfaceId, 'interface-1');
  assert.equal(master.dataset.autoConnectSelectingTarget, undefined);
  assert.equal(toolbar.querySelector('.interface-auto-connect-target-prompt'), undefined);
});

asyncTest('Auto Connect uses all loaded contacts and automatic diameter by default', async () => {
  const { context, calls } = palette();
  context.send = (action, payload) => {
    calls.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const state = dialog.children[2].contactState;
  state.items = [{ id: 'a' }, { id: 'b' }];
  state.workspace.root.hidden = false;
  dialog.children[1].children[1].children[1].events.click();
  const panel = dialog.querySelector('.interface-contact-auto-connect');
  panel.querySelector('button').events.click();
  finishEndingPick(context, calls, 'ending-1');
  descendants(panel, (item) => item.tag === 'button'
    && item.textContent === 'Apply')[0].events.click();
  await Promise.resolve();
  assert.deepEqual(Array.from(calls.at(-1).payload.contactIds), ['a', 'b']);
  assert.equal(calls.at(-1).payload.diameterMm, null);
});
