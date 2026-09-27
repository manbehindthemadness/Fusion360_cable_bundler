/** Auto Pin ordering and popup regressions. */
const { assert, asyncTest, palette, test } = require('./support.cjs');

test('Auto Pin follows visual rows or columns, direction, and selected contacts', () => {
  const { context } = palette();
  const items = [
    { id: 'bottom-right', loops: [[[20, 20], [30, 20], [30, 30]]] },
    { id: 'top-left', loops: [[[0, 0], [10, 0], [10, 10]]] },
    { id: 'bottom-left', loops: [[[0, 20], [10, 20], [10, 30]]] },
    { id: 'top-right', loops: [[[20, 0], [30, 0], [30, 10]]] },
  ];
  const ids = (direction, selected = new Set(), pattern = 'linear') => (
    Array.from(context.orderedInterfaceContactIds(items, selected, direction, pattern))
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
  assert.deepEqual(ids('LRTB', new Set(), 'zigzag'),
    ['top-left', 'top-right', 'bottom-right', 'bottom-left']);
  assert.deepEqual(ids('RLTB', new Set(), 'zigzag'),
    ['top-right', 'top-left', 'bottom-left', 'bottom-right']);
  assert.deepEqual(ids('TBLR', new Set(), 'zigzag'),
    ['top-left', 'bottom-left', 'bottom-right', 'top-right']);
});

test('Zigzag reverses every second visual row in the Auto Pin sequence', () => {
  const { context } = palette();
  const items = [2, 0, 1].flatMap((row) => [2, 0, 1].map((column) => ({
    id: `${row}-${column}`,
    loops: [[
      [column * 10, row * 10], [column * 10 + 2, row * 10],
      [column * 10 + 2, row * 10 + 2],
    ]],
  })));
  const ordered = Array.from(context.orderedInterfaceContactIds(items, new Set(), 'LRTB', 'zigzag'));
  assert.deepEqual(ordered, [
    '0-0', '0-1', '0-2',
    '1-2', '1-1', '1-0',
    '2-0', '2-1', '2-2',
  ]);
});

test('Spiral starts at the selected corner and winds inward for every order', () => {
  const { context } = palette();
  const items = [2, 0, 1].flatMap((row) => [2, 0, 1].map((column) => ({
    id: `${row}-${column}`,
    loops: [[[column * 10, row * 10], [column * 10 + 2, row * 10],
      [column * 10 + 2, row * 10 + 2]]],
  })));
  const expected = {
    LRTB: ['0-0', '0-1', '0-2', '1-2', '2-2', '2-1', '2-0', '1-0', '1-1'],
    RLTB: ['0-2', '0-1', '0-0', '1-0', '2-0', '2-1', '2-2', '1-2', '1-1'],
    LRBT: ['2-0', '2-1', '2-2', '1-2', '0-2', '0-1', '0-0', '1-0', '1-1'],
    RLBT: ['2-2', '2-1', '2-0', '1-0', '0-0', '0-1', '0-2', '1-2', '1-1'],
    TBLR: ['0-0', '1-0', '2-0', '2-1', '2-2', '1-2', '0-2', '0-1', '1-1'],
    BTLR: ['2-0', '1-0', '0-0', '0-1', '0-2', '1-2', '2-2', '2-1', '1-1'],
    TBRL: ['0-2', '1-2', '2-2', '2-1', '2-0', '1-0', '0-0', '0-1', '1-1'],
    BTRL: ['2-2', '1-2', '0-2', '0-1', '0-0', '1-0', '2-0', '2-1', '1-1'],
  };
  Object.entries(expected).forEach(([direction, order]) => {
    assert.deepEqual(Array.from(context.orderedInterfaceContactIds(
      items, new Set(), direction, 'spiral',
    )), order);
  });
  assert.deepEqual(Array.from(context.orderedInterfaceContactIds(
    items, new Set(expected.LRTB.filter((id) => id !== '0-1')), 'LRTB', 'spiral',
  )), ['0-0', '0-2', '1-2', '2-2', '2-1', '2-0', '1-0', '1-1']);
});

test('Auto Pin popup sends zigzagged contact order when enabled', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const diagram = dialog.children[2];
  diagram.contactState.items = [1, 0].flatMap((row) => [2, 0, 1].map((column) => ({
    id: `${row}-${column}`,
    loops: [[[column * 10, row * 10], [column * 10 + 2, row * 10],
      [column * 10 + 2, row * 10 + 2]]],
  })));
  const naming = dialog.children[1].children[1];
  naming.children[0].events.click();
  const form = naming.querySelector('.interface-contact-auto-pin');
  const zigzag = form.children[3].children[0];
  assert.equal(zigzag.checked, false);
  zigzag.checked = true;
  form.events.submit({ preventDefault() {} });
  assert.deepEqual(Array.from(launches[0].payload.contactIds), [
    '0-0', '0-1', '0-2', '1-2', '1-1', '1-0',
  ]);
});

test('Auto Pin popup keeps Spiral exclusive with Zigzag and submits an inward order', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  dialog.children[2].contactState.items = [2, 0, 1].flatMap((row) => [2, 0, 1].map((column) => ({
    id: `${row}-${column}`,
    loops: [[[column * 10, row * 10], [column * 10 + 2, row * 10],
      [column * 10 + 2, row * 10 + 2]]],
  })));
  const naming = dialog.children[1].children[1];
  naming.children[0].events.click();
  const form = naming.querySelector('.interface-contact-auto-pin');
  const zigzag = form.children[3].children[0];
  const spiral = form.children[4].children[0];
  assert.equal(spiral.checked, false);
  zigzag.checked = true;
  zigzag.events.change();
  spiral.checked = true;
  spiral.events.change();
  assert.equal(zigzag.checked, false);
  zigzag.checked = true;
  zigzag.events.change();
  assert.equal(spiral.checked, false);
  spiral.checked = true;
  spiral.events.change();
  form.events.submit({ preventDefault() {} });
  assert.deepEqual(Array.from(launches[0].payload.contactIds), [
    '0-0', '0-1', '0-2', '1-2', '2-2', '2-1', '2-0', '1-0', '1-1',
  ]);
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
  assert.equal(naming.children[1].textContent, 'Name Locals');
  assert.equal(naming.children[2].textContent, 'Geo Import');
  assert.equal(naming.children[3].textContent, 'Pos Import');
  button.events.click();
  const form = naming.querySelector('.interface-contact-auto-pin');
  const direction = form.children[0].children[0];
  const start = form.children[1].children[0];
  const hopscotch = form.children[2].children[0];
  const zigzag = form.children[3].children[0];
  const spiral = form.children[4].children[0];
  const overwrite = form.children[5].children[0];
  assert.deepEqual(Array.from(direction.children, (option) => option.value),
    ['LRTB', 'RLTB', 'LRBT', 'RLBT', 'TBLR', 'BTLR', 'TBRL', 'BTRL']);
  assert.equal(direction.value, 'LRTB');
  assert.equal(start.value, '0');
  assert.equal(hopscotch.checked, true);
  assert.equal(zigzag.checked, false);
  assert.equal(spiral.checked, false);
  assert.equal(overwrite.checked, false);
  dialog.children[2].contactState.selectedIds.add('pad-1');
  start.value = '7';
  overwrite.checked = true;
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches.length, 1);
  assert.equal(launches[0].action, 'auto_pin_interface_contacts');
  assert.deepEqual(Array.from(launches[0].payload.contactIds), ['pad-1']);
  assert.equal(launches[0].payload.start, 7);
  assert.equal(launches[0].payload.hopscotch, true);
  assert.equal(launches[0].payload.overwrite, true);
  assert.equal(Object.hasOwn(launches[0].payload, 'value'), false);
});

test('Auto Pin without Hopscotch counts occupied contacts and disables Overwrite', () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [{
      contactId: 'pad-1', kind: 'face', name: 'Pad', assignedName: 'VCC', pin: '20',
      linked: true, normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]],
    }],
  });
  const naming = context.document.body.querySelector('.interface-contacts-popup').children[1].children[1];
  naming.children[0].events.click();
  const form = naming.querySelector('.interface-contact-auto-pin');
  const hopscotch = form.children[2].children[0];
  const overwrite = form.children[5].children[0];
  overwrite.checked = true;
  hopscotch.checked = false;
  hopscotch.events.change();
  assert.equal(overwrite.checked, false);
  assert.equal(overwrite.disabled, true);
  form.events.submit({ preventDefault() {} });
  assert.equal(launches[0].payload.hopscotch, false);
  assert.equal(launches[0].payload.overwrite, false);
});

