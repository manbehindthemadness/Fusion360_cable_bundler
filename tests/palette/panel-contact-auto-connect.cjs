/** Auto Connect dialog and grouped-end picker request regressions. */
const { assert, asyncTest, descendants, palette } = require('./support.cjs');

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
  assert.equal(panel.querySelector('.interface-contact-auto-connect-future').textContent,
    'Second action · Coming later');
  const inputs = descendants(panel, (item) => item.tag === 'input');
  assert.equal(inputs[0].checked, true);
  assert.equal(inputs[1].checked, true);
  assert.equal(inputs[2].parentElement.textContent, 'Connection diameter (cm)');
  inputs[1].checked = false;
  inputs[2].value = '0.25';
  panel.querySelector('button').events.click();
  await Promise.resolve();
  assert.equal(calls.at(-1).action, 'auto_connect_interface_contacts');
  assert.deepEqual(Array.from(calls.at(-1).payload.contactIds), ['b']);
  assert.equal(calls.at(-1).payload.includePins, true);
  assert.equal(calls.at(-1).payload.includeValues, false);
  assert.equal(calls.at(-1).payload.diameterMm, 2.5);
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
  await Promise.resolve();
  assert.deepEqual(Array.from(calls.at(-1).payload.contactIds), ['a', 'b']);
  assert.equal(calls.at(-1).payload.diameterMm, null);
});
