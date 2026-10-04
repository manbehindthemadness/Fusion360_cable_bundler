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
    (field) => descendants(field, (node) => node.textContent === 'Insulation Pullback').length,
  );
  const weld = descendants(dialog, (node) => node.className === 'material-field').find(
    (field) => descendants(field, (node) => node.textContent === 'Weld').length,
  );
  const mode = descendants(pullback, (node) => node.tag === 'select')[0];
  const amount = descendants(pullback, (node) => node.type === 'number')[0];
  const color = descendants(pullback, (node) => node.type === 'color')[0];
  const weldAmount = descendants(weld, (node) => node.type === 'number')[0];
  const weldColor = descendants(weld, (node) => node.type === 'color')[0];
  assert.equal(descendants(pullback, (node) => node.textContent === 'Measurement').length, 1);
  assert.equal(mode.value, 'percent');
  assert.equal(amount.value, '200');
  assert.equal(amount.className, 'filter');
  assert.equal(color.value, '#B87333');
  assert.equal(descendants(weld, (node) => node.textContent === 'Measurement').length, 0);
  assert.equal(weldAmount.value, '150');
  assert.equal(weldColor.value, '#C0C0C0');

  mode.value = 'distance';
  amount.value = '7.5';
  color.value = '#102030';
  weldAmount.value = '175';
  weldColor.value = '#a0b0c0';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const save = calls.find((call) => call.action === 'set_harness_material_defaults');
  assert.equal(save.payload.materials.pullback.mode, 'distance');
  assert.equal(save.payload.materials.pullback.value, 7.5);
  assert.equal(save.payload.materials.pullback.color.red, 16);
  assert.equal(save.payload.materials.pullback.color.green, 32);
  assert.equal(save.payload.materials.pullback.color.blue, 48);
  assert.equal(save.payload.materials.pullback.appearance, null);
  assert.equal(save.payload.materials.weld.value, 175);
  assert.equal(save.payload.materials.weld.color.red, 160);
  assert.equal(save.payload.materials.weld.color.green, 176);
  assert.equal(save.payload.materials.weld.color.blue, 192);
  assert.equal(save.payload.materials.weld.appearance, null);
});

asyncTest('material measurements use the active design length units', async () => {
  const { context } = palette();
  const definition = harness();
  definition.lengthUnits = { symbol: 'in', millimetersPerUnit: 25.4 };
  definition.materialDefaults.stripes = [{
    color: { name: 'White', hex: '#f5f5f5' },
    widthMm: 25.4,
    pattern: 'dashed',
    angleDeg: 45,
    repeatMm: 50.8,
  }];
  definition.materialDefaults.pullback = {
    mode: 'distance', value: 76.2,
    color: { name: 'Copper', hex: '#B87333' }, appearance: null,
  };
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    return { ok: true };
  };

  context.openMaterialOptions(definition);

  const dialog = context.document.body.querySelector('.material-options');
  const stripes = descendants(
    dialog, (node) => node.className?.split(' ').includes('stripe-row'),
  )[0];
  const width = descendants(
    stripes, (node) => node.tag === 'label' && node.textContent === 'Width (in)',
  )[0].querySelector('input');
  const repeat = descendants(
    stripes, (node) => node.tag === 'label' && node.textContent === 'Repeat (in)',
  )[0].querySelector('input');
  const angle = descendants(
    stripes, (node) => node.tag === 'label' && node.textContent === 'Angle (deg)',
  )[0].querySelector('input');
  const pullback = descendants(dialog, (node) => node.className === 'material-field').find(
    (field) => descendants(field, (node) => node.textContent === 'Insulation Pullback').length,
  );
  const distanceLabel = descendants(
    pullback, (node) => node.tag === 'span' && node.textContent === 'Distance (in)',
  )[0];
  const distance = distanceLabel.parentElement.querySelector('input');
  assert.equal(width.value, '1');
  assert.equal(repeat.value, '2');
  assert.equal(angle.value, '45');
  assert.equal(distance.value, '3');

  width.value = '1.5';
  repeat.value = '2.5';
  distance.value = '3.5';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const save = calls.find((call) => call.action === 'set_harness_material_defaults');
  assert.ok(Math.abs(save.payload.materials.stripes[0].widthMm - 38.1) < 1e-12);
  assert.equal(save.payload.materials.stripes[0].repeatMm, 63.5);
  assert.ok(Math.abs(save.payload.materials.pullback.value - 88.9) < 1e-12);
});

asyncTest('connection material overrides populate again when reopened', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  const attachment = {
    attachmentId: 'connection-1', connectionId: 'a1', parentAttachmentId: null,
    visualOverrides: {
      mainColor: { name: 'Red', hex: '#ff0000' }, appearance: null,
      stripes: [{
        color: { name: 'Blue', hex: '#0000ff' }, widthMm: 0.3,
        pattern: 'longitudinal', angleDeg: 0, repeatMm: null,
      }],
      pullback: {
        mode: 'distance', value: 6.25,
        color: { name: 'Green', hex: '#00ff00' }, appearance: null,
      },
    },
  };
  connection.attachments = [attachment, {
    attachmentId: 'connection-2', connectionId: 'a1', parentAttachmentId: null,
    visualOverrides: {},
  }];
  context.send = async (action) => (
    action === 'get_appearance_libraries'
      ? { ok: true, libraries: [] }
      : { ok: true }
  );

  context.openMaterialOptions(definition, group, attachment);

  const dialog = context.document.body.querySelector('.material-options');
  const swatches = descendants(dialog, (node) => node.type === 'color');
  const pullback = descendants(dialog, (node) => node.className === 'material-field').find(
    (field) => descendants(field, (node) => node.textContent === 'Insulation Pullback').length,
  );
  const pullbackMode = descendants(pullback, (node) => node.tag === 'select')[0];
  const pullbackAmount = descendants(pullback, (node) => node.type === 'number')[0];

  assert.equal(swatches[0].value, '#ff0000');
  assert.equal(swatches[1].value, '#0000ff');
  assert.equal(swatches[2].value, '#00ff00');
  assert.equal(pullbackMode.value, 'distance');
  assert.equal(pullbackAmount.value, '6.25');
});

asyncTest('single connection materials expose only pullback and weld overrides', async () => {
  const { context, calls } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  const attachment = {
    attachmentId: 'connection-1', connectionId: 'a1', parentAttachmentId: null,
    visualOverrides: {},
  };
  connection.attachment = attachment;
  connection.attachments = [attachment];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return action === 'get_appearance_libraries'
      ? { ok: true, libraries: [] }
      : { ok: true };
  };

  context.openMaterialOptions(definition, group, attachment);

  const dialog = context.document.body.querySelector('.material-options');
  const materialFields = descendants(
    dialog, (node) => node.className === 'material-field',
  );
  const titles = materialFields.map((field) => field.querySelector('strong').textContent);
  assert.equal(JSON.stringify(titles), JSON.stringify(['Insulation Pullback', 'Weld']));
  materialFields.forEach((field) => {
    const toggle = descendants(field, (node) => node.type === 'checkbox')[0];
    toggle.checked = true;
    toggle.events.change();
  });
  descendants(materialFields[0], (node) => node.type === 'number')[0].value = '7.5';
  descendants(materialFields[1], (node) => node.type === 'number')[0].value = '180';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const save = calls.find(
    (call) => call.action === 'set_cable_end_attachment_visual_overrides',
  );
  assert.equal(save.payload.overrides.mainColor, null);
  assert.equal(save.payload.overrides.stripes, null);
  assert.equal(save.payload.overrides.pullback.value, 7.5);
  assert.equal(save.payload.overrides.weld.value, 180);
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

asyncTest('ribbon properties save explicit Lines and geometry style without line colors', async () => {
  const { context } = palette();
  const definition = harness();
  const cableGroup = definition.cableGroups[0];
  cableGroup.groupType = 'ribbon';
  cableGroup.ribbonLines = 3;
  cableGroup.ribbonGeometry = 'discrete';
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableGroupProperties(definition, cableGroup);

  const dialog = context.document.body.querySelector('.cable-group-properties');
  const lines = descendants(dialog, (node) => node.tag === 'input' && node.value === '3')[0];
  const geometry = descendants(dialog, (node) => node.tag === 'select'
    && node.value === 'discrete')[0];
  assert.equal(lines.min, '1');
  assert.equal(geometry.children.length, 2);
  assert.equal(descendants(lines.parentElement, (node) => node.type === 'checkbox').length, 0);
  assert.equal(descendants(geometry.parentElement, (node) => node.type === 'checkbox').length, 0);
  lines.value = '6';
  geometry.value = 'ffc';
  assert.equal(dialog.querySelector('.ribbon-line-colors'), undefined);
  assert.equal(descendants(dialog, (node) => node.textContent === 'Body type').length, 0);
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_group_properties');
  assert.equal(calls[0].payload.ribbonLines, 6);
  assert.equal(calls[0].payload.ribbonGeometry, 'ffc');
  assert.equal('ribbonLineColors' in calls[0].payload, false);
  assert.equal(calls[0].payload.ribbonBodyType, 'solid');
});

asyncTest('FFC properties accept one antenna trace', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  group.groupType = 'ribbon';
  group.ribbonLines = 1;
  group.ribbonGeometry = 'ffc';
  group.ribbonBodyType = 'solid';
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  context.openCableGroupProperties(definition, group);
  const dialog = context.document.body.querySelector('.cable-group-properties');
  await dialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls[0].payload.ribbonLines, 1);
  assert.equal(calls[0].payload.ribbonGeometry, 'ffc');
});

asyncTest('ribbon Body type appears only with Interfaces at both ends', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  group.groupType = 'ribbon';
  group.ribbonLines = 3;
  definition.interfaces = [{ interfaceId: 'i1', connectedConnectionIds: ['a1'] }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableGroupProperties(definition, group);
  let dialog = context.document.body.querySelector('.cable-group-properties');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Body type').length, 0);
  dialog.close();

  definition.interfaces.push({ interfaceId: 'i2', connectedConnectionIds: ['b1'] });
  context.openCableGroupProperties(definition, group);
  dialog = context.document.body.querySelector('.cable-group-properties');
  const label = descendants(dialog, (node) => node.textContent === 'Body type')[0];
  const select = label.querySelector('select');
  assert.equal(select.value, 'split');
  assert.deepEqual(select.children.map((option) => option.textContent), ['Split', 'Solid']);
  select.value = 'solid';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_group_properties');
  assert.equal(calls[0].payload.ribbonBodyType, 'solid');

  group.ribbonBodyType = 'solid';
  definition.interfaces.pop();
  context.openCableGroupProperties(definition, group);
  dialog = context.document.body.querySelector('.cable-group-properties');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Body type').length, 0);
  await dialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal('ribbonBodyType' in calls[1].payload, false);
});

asyncTest('FFC properties show flat sizing and reject dimensions outside contact pitch', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  group.groupType = 'ribbon';
  group.ribbonLines = 3;
  group.ribbonGeometry = 'discrete';
  group.ffcPitchMm = 1;
  group.ffcAutoTraceWidthMm = 0.8;
  definition.interfaces = [
    { interfaceId: 'i1', connectedConnectionIds: ['a1'] },
    { interfaceId: 'i2', connectedConnectionIds: ['b1'] },
  ];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  context.openCableGroupProperties(definition, group);
  const dialog = context.document.body.querySelector('.cable-group-properties');
  const geometry = descendants(dialog, (node) => node.tag === 'select'
    && node.value === 'discrete')[0];
  const bodyType = descendants(dialog, (node) => node.textContent === 'Body type')[0];
  const width = descendants(dialog, (node) => node.textContent === 'Trace Width (mm)')[0];
  const spacing = descendants(dialog, (node) => node.textContent === 'Spacing (mm)')[0];
  const thickness = descendants(dialog, (node) => node.textContent === 'Diameter (mm)')[0];
  assert.equal(width.hidden, true);
  geometry.value = 'ffc';
  geometry.events.change();
  assert.equal(bodyType.hidden, true);
  assert.equal(width.hidden, false);
  assert.equal(spacing.hidden, false);
  assert.equal(thickness.textContent, 'Thickness (mm)');
  assert.equal(dialog.querySelector('.conductor-diameter-field').hidden, true);
  width.querySelector('input').value = '1.2';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls.length, 0);
  width.querySelector('input').value = '0.6';
  spacing.querySelector('input').value = '0.3';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls.length, 0);
  spacing.querySelector('input').value = 'auto';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls[0].payload.ribbonBodyType, 'solid');
  assert.equal(calls[0].payload.traceWidthMm, 0.6);
  assert.equal(calls[0].payload.traceSpacingMm, null);
});

asyncTest('ribbon materials collapse and save individual line colors', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  group.groupType = 'ribbon';
  group.ribbonLines = 3;
  group.ribbonLineColors = [
    null, { name: 'Blue', red: 0, green: 0, blue: 255, hex: '#0000ff' }, null,
  ];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return action === 'get_appearance_libraries'
      ? { ok: true, libraries: [] } : { ok: true };
  };

  context.openMaterialOptions(definition, group);
  const dialog = context.document.body.querySelector('.material-options');
  const colors = dialog.querySelector('.ribbon-line-colors');
  const rows = descendants(colors, (node) => node.tag === 'label');
  assert.equal(colors.tag, 'details');
  assert.equal(colors.open, undefined);
  assert.equal(colors.querySelector('summary').textContent, 'Individual line colors');
  assert.equal(rows.length, 3);
  assert.equal(rows[1].querySelector('input').checked, true);
  const toggle = descendants(rows[0], (node) => node.type === 'checkbox')[0];
  const picker = descendants(rows[0], (node) => node.type === 'color')[0];
  toggle.checked = true;
  toggle.events.change();
  picker.value = '#ff0000';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const saved = calls.find((call) => call.action === 'set_cable_group_material_overrides');
  assert.equal(saved.payload.ribbonLineColors.length, 3);
  assert.equal(saved.payload.ribbonLineColors[0].red, 255);
  assert.equal(saved.payload.ribbonLineColors[1].blue, 255);
  assert.equal(saved.payload.ribbonLineColors[1].name, 'Blue');
  assert.equal(saved.payload.ribbonLineColors[2], null);
});

asyncTest('ribbon materials omit procedural stripes without changing their overrides', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  const stripe = {
    color: { name: 'White', hex: '#f5f5f5' }, widthMm: 0.4,
    pattern: 'longitudinal', angleDeg: 0, repeatMm: null,
  };
  group.groupType = 'ribbon';
  group.ribbonLines = 3;
  group.materials = { ...group.materials, stripes: [stripe] };
  group.materialOverrides.stripes = [stripe];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return action === 'get_appearance_libraries'
      ? { ok: true, libraries: [] } : { ok: true };
  };

  context.openMaterialOptions(definition, group);
  const dialog = context.document.body.querySelector('.material-options');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Procedural stripes').length, 0);
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const saved = calls.find((call) => call.action === 'set_cable_group_material_overrides');
  assert.deepEqual(saved.payload.overrides.stripes, [stripe]);
});

asyncTest('ribbon connection materials omit procedural stripes', async () => {
  const { context } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  const connection = definition.connections[0];
  const stripe = {
    color: { name: 'White', hex: '#f5f5f5' }, widthMm: 0.4,
    pattern: 'longitudinal', angleDeg: 0, repeatMm: null,
  };
  group.groupType = 'ribbon';
  const attachment = {
    attachmentId: 'root-1', connectionId: connection.connectionId,
    parentAttachmentId: null, visualOverrides: { stripes: [stripe] },
  };
  connection.attachments = [attachment, {
    attachmentId: 'root-2', connectionId: connection.connectionId,
    parentAttachmentId: null, visualOverrides: {},
  }];
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return action === 'get_appearance_libraries'
      ? { ok: true, libraries: [] } : { ok: true };
  };

  context.openMaterialOptions(definition, group, attachment);
  const dialog = context.document.body.querySelector('.material-options');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Procedural stripes').length, 0);
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  const saved = calls.find((call) => call.action === 'set_cable_end_attachment_visual_overrides');
  assert.deepEqual(saved.payload.overrides.stripes, [stripe]);
});

test('loose cable group materials retain procedural stripes', () => {
  const { context } = palette();
  const definition = harness();
  context.openMaterialOptions(definition, definition.cableGroups[0]);

  const dialog = context.document.body.querySelector('.material-options');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Procedural stripes').length, 1);
});

asyncTest('cable diameter fields use the active design length units', async () => {
  const { context } = palette();
  const definition = harness();
  const cableGroup = definition.cableGroups[0];
  definition.lengthUnits = { symbol: 'in', millimetersPerUnit: 25.4 };
  cableGroup.diameterMm = 25.4;
  cableGroup.conductorDiameterMm = 12.7;
  const calls = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };

  context.openCableGroupProperties(definition, cableGroup);

  const dialog = context.document.body.querySelector('.cable-group-properties');
  const fields = descendants(dialog, (node) => node.tag === 'input');
  const conductorDiameter = dialog.querySelector('.conductor-diameter-field');
  assert.equal(fields[0].value, '1');
  assert.equal(conductorDiameter.querySelector('input').value, '0.5');
  assert.equal(descendants(dialog, (node) => node.textContent === 'Diameter (in)').length, 1);
  assert.equal(
    descendants(dialog, (node) => node.textContent === 'Conductor Diameter (in)').length,
    1,
  );
  fields[0].value = '2';
  fields[0].events.input();
  conductorDiameter.querySelector('input').value = '0.75';
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls.length, 1, descendants(dialog, (node) => node.attributes.role === 'alert')[0]
    .textContent);
  assert.equal(calls[0].payload.diameterMm, 50.8);
  assert.ok(Math.abs(calls[0].payload.conductorDiameterMm - 19.05) < 1e-12);
  assert.equal(conductorDiameter.querySelector('.conductor-diameter-hint').textContent,
    'Auto = 1.5 in (75%)');
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
