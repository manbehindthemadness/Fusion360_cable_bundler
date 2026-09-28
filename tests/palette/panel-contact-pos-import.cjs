/** PCB contact import regressions. */
const { assert, asyncTest, palette } = require('./support.cjs');

asyncTest('Pos Import reviews skipped contacts before saving selected, custom, and blank names', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    if (action === 'get_pos_import_boards') {
      return Promise.resolve({ ok: true, boards: [
        { name: 'Linked PCB', versionId: 'pcb-version' },
      ] });
    }
    if (action === 'preview_pos_import_interface_contacts') {
      return Promise.resolve({ ok: true,
        autoNames: [{ contactId: 'auto', name: 'J1.1' }],
        unresolved: [
          { contactId: 'choice', label: 'Contact 2', currentName: '', suggestions: ['J1.2', 'J2.2'] },
          { contactId: 'custom', label: 'Contact 3', currentName: '', suggestions: ['J1.3'] },
          { contactId: 'blank', label: 'Contact 4', currentName: 'old', suggestions: ['J1.4', 'J2.4'] },
          { contactId: 'no-match', label: 'Contact 5', currentName: 'saved', suggestions: [] },
        ],
      });
    }
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const dialog = context.document.body.querySelector('.interface-contacts-popup');
  const naming = dialog.children[1].children[1];
  naming.children[4].events.click();
  await Promise.resolve();
  const form = naming.querySelector('.interface-contact-pos-import');
  assert.equal(form.children[0].textContent, 'Choose the linked 2D PCB to read pad names from:');
  assert.equal(form.children[1].children[0].textContent, 'Linked PCB');
  assert.equal(form.children[2].children[0].type, 'checkbox');
  assert.equal(form.children[2].children[0].checked, true);
  assert.equal(form.children[5].disabled, false);
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  await Promise.resolve();
  assert.deepEqual(launches.map((item) => item.action), [
    'get_pos_import_boards', 'preview_pos_import_interface_contacts',
  ]);
  assert.equal(launches[1].payload.boardVersionId, 'pcb-version');
  assert.equal(launches[1].payload.project, true);
  const rows = form.children[4].children;
  assert.equal(rows.length, 3);
  rows[0].children[1].value = '1';
  rows[1].children[1].value = 'custom';
  rows[1].children[1].events.change();
  rows[1].children[2].value = 'My pad';
  rows[2].children[1].value = 'blank';
  assert.equal(rows[1].children[2].hidden, false);
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches[2].action, 'pos_import_interface_contacts');
  assert.deepEqual(JSON.parse(JSON.stringify(launches[2].payload.contactNames)), [
    { contactId: 'auto', name: 'J1.1' },
    { contactId: 'choice', name: 'J2.2' },
    { contactId: 'custom', name: 'My pad' },
    { contactId: 'blank', name: '' },
  ]);
});

asyncTest('Load board reviews file matches with the Pos Import naming choices', async () => {
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
  naming.children[4].events.click();
  await Promise.resolve();
  const form = naming.querySelector('.interface-contact-pos-import');
  assert.equal(form.attributes['aria-label'], 'Choose PCB for Pos Import');
  assert.equal(form.children[2].children[0].checked, true);
  form.children[2].children[0].checked = false;
  form.children[3].events.click();
  await Promise.resolve();
  assert.equal(launches[1].action, 'load_brd_interface_contacts');
  assert.equal(launches[1].payload.project, false);
  assert.equal(form.children[5].disabled, true);
  context.window.fusionJavaScriptHandler.handle('board_file_preview', JSON.stringify({
    harnessId: 'harness-1', interfaceId: 'interface-1',
    autoNames: [{ contactId: 'auto', name: 'J1.1 (GND)' }],
    unresolved: [{ contactId: 'choice', label: 'Contact 2', currentName: '',
      suggestions: ['J1.2 (NC)', 'J2.2 (GND)'] }],
  }));
  assert.equal(launches.length, 2);
  assert.equal(form.children[4].children.length, 1);
  form.children[4].children[0].children[1].value = '0';
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(launches[2].action, 'pos_import_interface_contacts');
  assert.deepEqual(JSON.parse(JSON.stringify(launches[2].payload.contactNames)), [
    { contactId: 'auto', name: 'J1.1 (GND)' },
    { contactId: 'choice', name: 'J1.2 (NC)' },
  ]);
});

asyncTest('Pos Import skips review when no contacts have conflicting PCB candidates', async () => {
  const { context } = palette();
  const launches = [];
  context.send = (action, payload) => {
    launches.push({ action, payload });
    if (action === 'get_pos_import_boards') return Promise.resolve({
      ok: true, boards: [{ name: 'PCB', versionId: 'version-1' }],
    });
    if (action === 'preview_pos_import_interface_contacts') return Promise.resolve({
      ok: true, autoNames: [{ contactId: 'matched', name: 'J1.1' }],
      unresolved: [{ contactId: 'no-match', label: 'Contact 2', suggestions: [] }],
    });
    return Promise.resolve({ ok: true });
  };
  context.openInterfaceContacts({ harnessId: 'harness-1' }, {
    interfaceId: 'interface-1', name: 'Socket', contacts: [],
  });
  const naming = context.document.body.querySelector('.interface-contacts-popup').children[1].children[1];
  naming.children[4].events.click();
  await Promise.resolve();
  const form = naming.querySelector('.interface-contact-pos-import');
  form.events.submit({ preventDefault() {} });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(form.children[4].children.length, 0);
  assert.equal(launches[2].action, 'pos_import_interface_contacts');
  assert.deepEqual(JSON.parse(JSON.stringify(launches[2].payload.contactNames)), [
    { contactId: 'matched', name: 'J1.1' },
  ]);
});
