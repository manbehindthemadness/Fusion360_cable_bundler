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
  assert.equal(descendants(dialog, (node) => node.textContent === 'Shielding').length, 1);
  assert.equal(value.value, 'Orion');
  assert.equal(value.disabled, true);
  override.checked = true;
  override.events.change();
  value.value = 'Apollo';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_group_properties');
  assert.equal(calls[0].payload.shielding, null);
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
