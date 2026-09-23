/* global require */
const {
  assert, asyncTest, descendants, harness, palette, test,
} = require('./support.cjs');

test('material color context menus copy and paste between swatches', () => {
  const { context } = palette();
  const definition = harness();
  definition.materialDefaults.stripes = [
    {
      color: { name: 'Red', hex: '#ff0000' }, widthMm: 0.4,
      pattern: 'dashed', angleDeg: 0, repeatMm: 6,
    },
    {
      color: { name: 'Gray', hex: '#c0c0c0' }, widthMm: 0.4,
      pattern: 'dashed', angleDeg: 90, repeatMm: 6,
    },
  ];
  context.openMaterialOptions(definition);
  const dialog = context.document.body.querySelector('.material-options');
  const swatches = descendants(dialog, (node) => node.type === 'color');
  const contextMenu = (swatch) => descendants(
    swatch.parentElement,
    (node) => node.className?.split(' ').includes('relationship-map-context-menu'),
  )[0];

  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  assert.equal(
    contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste').disabled,
    true,
  );
  swatches[0].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[0],
  });
  contextMenu(swatches[0]).children.find((item) => item.textContent === 'Copy').events.click();
  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste').events.click();
  assert.equal(swatches[2].value, '#202020');

  swatches[1].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[1],
  });
  contextMenu(swatches[1]).children.find((item) => item.textContent === 'Copy').events.click();

  swatches[2].events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: swatches[2],
  });
  const paste = contextMenu(swatches[2]).children.find((item) => item.textContent === 'Paste');
  assert.equal(paste.disabled, false);
  paste.events.click();

  assert.equal(swatches[2].value, '#ff0000');
});

asyncTest('pullback defaults to 200 percent and saves distance and appearance data', async () => {
  const { context } = palette();
  const definition = harness();
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    return { ok: true };
  };

  context.openMaterialOptions(definition);

  const dialog = context.document.body.querySelector('.material-options');
  const pullback = descendants(dialog, (node) => node.className === 'material-field').find(
    (field) => descendants(field, (node) => node.textContent === 'Pullback').length,
  );
  const mode = descendants(pullback, (node) => node.tag === 'select')[0];
  const amount = descendants(pullback, (node) => node.type === 'number')[0];
  const color = descendants(pullback, (node) => node.type === 'color')[0];
  assert.equal(descendants(pullback, (node) => node.textContent === 'Measurement').length, 1);
  assert.equal(mode.value, 'percent');
  assert.equal(amount.value, '200');
  assert.equal(amount.className, 'filter');
  assert.equal(color.value, '#B87333');

  mode.value = 'distance';
  amount.value = '7.5';
  color.value = '#102030';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const save = calls.find((call) => call.action === 'set_harness_material_defaults');
  assert.equal(save.payload.materials.pullback.mode, 'distance');
  assert.equal(save.payload.materials.pullback.value, 7.5);
  assert.equal(save.payload.materials.pullback.color.red, 16);
  assert.equal(save.payload.materials.pullback.color.green, 32);
  assert.equal(save.payload.materials.pullback.color.blue, 48);
  assert.equal(save.payload.materials.pullback.appearance, null);
});

asyncTest('dielectric material appears only while shielding is enabled', async () => {
  const { context } = palette();
  const definition = harness();
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openHarnessProperties(definition);

  const dialog = context.document.body.querySelector('.harness-properties');
  const materialFields = descendants(
    dialog, (node) => node.className === 'material-field',
  );
  const shielding = materialFields.find(
    (field) => descendants(field, (node) => node.textContent === 'Shielding').length,
  );
  const dielectric = materialFields.find(
    (field) => descendants(field, (node) => node.textContent === 'Dielectric Material').length,
  );
  assert.equal(dielectric.hidden, true);
  shielding.querySelector('input').value = 'Foil';
  shielding.querySelector('input').events.input();
  assert.equal(dielectric.hidden, false);
  dielectric.querySelector('input').value = 'FEP';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_harness_properties');
  assert.equal(calls[0].payload.shielding, 'Foil');
  assert.equal(calls[0].payload.dielectricMaterial, 'FEP');
});

asyncTest('connected cable metadata inherits until explicitly overridden', async () => {
  const { context } = palette();
  const definition = harness();
  const cableGroup = definition.cableGroups[0];
  definition.metadata = [{ key: 'project', value: 'Orion' }];
  cableGroup.metadata = [{ key: 'project', value: 'Orion' }];
  cableGroup.metadataOverrides = [];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableGroupProperties(definition, cableGroup);

  const dialog = context.document.body.querySelector('.cable-group-properties');
  const row = dialog.querySelector('.metadata-row');
  const value = row.querySelector('.metadata-value');
  const override = descendants(row, (node) => node.type === 'checkbox')[0];
  const conductorDiameter = dialog.querySelector('.conductor-diameter-field').querySelector('input');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Shielding').length, 1);
  assert.equal(value.value, 'Orion');
  assert.equal(value.disabled, true);
  assert.equal(conductorDiameter.value, 'auto');
  override.checked = true;
  override.events.change();
  value.value = 'Apollo';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_group_properties');
  assert.equal(calls[0].payload.shielding, null);
  assert.equal(calls[0].payload.dielectricMaterial, null);
  assert.equal(calls[0].payload.conductorDiameterMm, null);
  assert.equal(JSON.stringify(calls[0].payload.metadataOverrides), JSON.stringify([
    { key: 'project', value: 'Apollo' },
  ]));
  assert.equal(descendants(dialog, (node) => node.textContent === 'Notes').length, 0);
});

asyncTest('pathway Properties edits only pathway metadata', async () => {
  const { context } = palette();
  const definition = harness();
  const pathway = definition.pathways[0];
  pathway.metadata = [{ key: 'zone', value: 'forward' }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openPathwayProperties(definition, pathway);

  const dialog = context.document.body.querySelector('.pathway-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  assert.equal(fields[0].value, 'zone');
  assert.equal(fields[1].value, 'forward');
  fields[1].value = 'aft';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_pathway_properties');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'zone', value: 'aft' },
  ]));
});

asyncTest('pathway-end Properties edits only the selected boundary metadata', async () => {
  const { context } = palette();
  const definition = harness();
  const pathway = definition.pathways[0];
  pathway.startMetadata = [{ key: 'station', value: 'left' }];
  pathway.endMetadata = [{ key: 'station', value: 'right' }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openPathwayEndProperties(definition, pathway, 'start');

  const dialog = context.document.body.querySelector('.pathway-end-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  assert.equal(fields[0].value, 'station');
  assert.equal(fields[1].value, 'left');
  fields[1].value = 'forward-left';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_pathway_end_properties');
  assert.equal(calls[0].payload.pathwayId, 'p');
  assert.equal(calls[0].payload.endpoint, 'start');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'station', value: 'forward-left' },
  ]));
});

asyncTest('junction Properties edits only junction metadata', async () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'cj', name: 'Branch',
    pathwayRelationships: [], metadata: [{ key: 'panel', value: 'P2' }],
  };
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openJunctionProperties(definition, junction);

  const dialog = context.document.body.querySelector('.junction-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  fields[1].value = 'P3';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_junction_properties');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'panel', value: 'P3' },
  ]));
});

asyncTest('cable-end Properties edits only the selected end metadata', async () => {
  const { context } = palette();
  const definition = harness();
  definition.connections[0].metadata = [{ key: 'connector', value: 'J1' }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableEndProperties(definition, 'a1');

  const dialog = context.document.body.querySelector('.cable-end-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  assert.equal(fields.length, 2);
  fields[1].value = 'J2';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_end_properties');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([
    { key: 'connector', value: 'J2' },
  ]));
});
