/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, asyncTest, descendants, harness, join, palette, readFileSync, runInNewContext, test } = require('./support.cjs');

/** Install the deterministic material catalog shared by dialog tests. */
function configureMaterialCatalog(context) {
  runInNewContext('currentState = { catalog };', Object.assign(context, { catalog: {
    insulationMaterials: ['PVC', 'ETFE'], conductorMaterials: ['Copper', 'Tinned Copper'],
    colors: [{ name: 'Black', hex: '#202020' }], stripePatterns: [],
  } }));
}

test('property text fields use controlled autocomplete instead of native datalists', () => {
  const { context } = palette();
  const definition = harness();
  configureMaterialCatalog(context);
  context.send = async (action) => action === 'get_appearance_libraries'
    ? { ok: true, libraries: [] } : { ok: true, appearances: [] };

  context.openHarnessProperties(definition);

  const dialog = context.document.body.children.at(-1);
  assert.equal(descendants(dialog, (item) => item.tag === 'datalist').length, 0);
  const insulation = descendants(dialog, (item) => item.type === 'text')[0];
  const choices = descendants(dialog, (item) => item.className === 'autocomplete-suggestions')[0];
  assert.equal(choices.hidden, true);
  insulation.events.click();
  assert.equal(choices.hidden, false);
  assert.deepEqual(choices.children.map((item) => item.textContent), ['PVC']);
  insulation.value = '';
  insulation.events.input();
  assert.deepEqual(choices.children.map((item) => item.textContent), ['PVC', 'ETFE']);
});

asyncTest('harness properties are separate from visual materials', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  configureMaterialCatalog(context);
  context.send = async (action, payload) => {
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    requests.push({ action, payload });
    return { ok: true };
  };

  context.openMaterialOptions(definition);
  const materials = context.document.body.children.at(-1);
  const materialLabels = descendants(materials, (item) => item.tag === 'strong')
    .map((item) => item.textContent);
  assert.deepEqual(materialLabels, ['Main insulation appearance', 'Procedural stripes']);
  assert.equal(descendants(materials, (item) => item.type === 'checkbox').length, 0);
  descendants(materials, (item) => item.tag === 'form')[0]
    .events.submit({ preventDefault() {} });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(requests[0].action, 'set_harness_material_defaults');
  assert.equal(requests[0].payload.materials.insulationMaterial, 'PVC');
  assert.equal(requests[0].payload.materials.conductorMaterial, 'Copper');
  assert.equal(requests[0].payload.materials.manufacturer, '');
  assert.equal(requests[0].payload.materials.partNumber, '');
  assert.equal(requests[0].payload.materials.notes, '');

  context.openHarnessProperties(definition);
  const properties = context.document.body.children.at(-1);
  const form = descendants(properties, (item) => item.tag === 'form')[0];
  const fields = descendants(properties, (item) => item.className?.split(' ')
    .includes('material-field'));
  assert.deepEqual(
    descendants(properties, (item) => item.tag === 'strong').map((item) => item.textContent),
    ['Insulation Material', 'Conductor Material', 'Manufacturer', 'Part Number', 'Notes'],
  );
  assert.equal(descendants(properties, (item) => item.type === 'checkbox').length, 0);
  assert.equal(descendants(properties, (item) => item.type === 'number').length, 0);
  descendants(fields[0], (item) => item.type === 'text')[0].value = 'ETFE';
  descendants(fields[1], (item) => item.type === 'text')[0].value = 'Tinned Copper';
  descendants(fields[2], (item) => item.type === 'text')[0].value = 'Acme';
  descendants(fields[3], (item) => item.type === 'text')[0].value = 'WB-42';
  descendants(fields[4], (item) => item.tag === 'textarea')[0].value = 'Matched stock';
  await form.events.submit({ preventDefault() {} });

  assert.equal(requests.length, 2);
  assert.equal(requests[1].action, 'set_harness_properties');
  assert.equal(JSON.stringify(requests[1].payload), JSON.stringify({
    harnessId: 'h', insulationMaterial: 'ETFE', conductorMaterial: 'Tinned Copper',
    manufacturer: 'Acme', partNumber: 'WB-42', notes: 'Matched stock',
  }));
  assert.equal(properties.open, false);
});

asyncTest('wire options Cancel restores the values rendered by Apply', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  configureMaterialCatalog(context);
  context.send = async (action, payload) => {
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    requests.push({ action, payload });
    return { ok: true };
  };

  context.openMaterialOptions(definition, definition.wires[0]);
  const dialog = context.document.body.children.at(-1);
  const diameter = descendants(dialog, (item) => item.type === 'number')[0];
  const insulation = descendants(dialog, (item) => item.type === 'text')[0];
  const override = descendants(dialog, (item) => item.type === 'checkbox')[0];
  const apply = descendants(dialog, (item) => item.textContent === 'Apply')[0];
  diameter.value = '2';
  override.checked = true;
  override.events.change();
  insulation.value = 'ETFE';

  await apply.events.click();
  assert.deepEqual(requests.map((request) => request.action), [
    'set_wire_diameter', 'set_wire_material_overrides',
  ]);
  assert.equal(requests[0].payload.diameterMm, 2);
  assert.equal(requests[1].payload.overrides.insulationMaterial, 'ETFE');

  await dialog.cancelOptions();
  assert.deepEqual(requests.map((request) => request.action), [
    'set_wire_diameter', 'set_wire_material_overrides',
    'set_wire_diameter', 'set_wire_material_overrides',
  ]);
  assert.equal(requests[2].payload.diameterMm, 1.5);
  assert.equal(
    JSON.stringify(requests[3].payload.overrides),
    JSON.stringify(definition.wires[0].materialOverrides),
  );
  assert.equal(dialog.open, false);
});

asyncTest('connected wire materials reuse overrides without exposing diameter', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  const wireGroup = {
    wireGroupId: 'group-1', diameterMm: 2.4,
    materials: {
      ...definition.materialDefaults,
      insulationMaterial: 'ETFE', conductorMaterial: 'Tinned Copper',
      manufacturer: 'Acme', partNumber: 'WB-42', notes: 'Use matched stock',
    },
    materialOverrides: {
      insulationMaterial: 'ETFE', conductorMaterial: 'Tinned Copper', mainColor: null,
      appearance: null, stripes: null, manufacturer: 'Acme', partNumber: 'WB-42',
      notes: 'Use matched stock',
    },
  };
  configureMaterialCatalog(context);
  context.send = async (action, payload) => {
    if (action === 'get_appearance_libraries') return { ok: true, libraries: [] };
    requests.push({ action, payload });
    return { ok: true };
  };

  context.openMaterialOptions(definition, null, wireGroup);
  const dialog = context.document.body.children.at(-1);
  assert.equal(descendants(dialog, (item) => item.type === 'number').length, 0);
  assert.equal(descendants(dialog, (item) => item.tag === 'h2')[0].textContent,
    'Connected Wire Materials');
  const labels = descendants(dialog, (item) => item.tag === 'strong')
    .map((item) => item.textContent);
  assert.equal(labels.includes('Insulation material'), false);
  assert.equal(labels.includes('Conductor material'), false);
  assert.equal(labels.includes('Manufacturer'), false);
  assert.equal(labels.includes('Part number'), false);
  assert.equal(labels.includes('Notes'), false);
  const colorOverride = descendants(dialog, (item) => item.type === 'checkbox')[0];
  colorOverride.checked = true;
  colorOverride.events.change();
  await descendants(dialog, (item) => item.textContent === 'Apply')[0].events.click();

  assert.equal(requests[0].action, 'set_wire_group_material_overrides');
  assert.equal(requests[0].payload.wireGroupId, 'group-1');
  assert.equal(requests[0].payload.overrides.insulationMaterial, 'ETFE');
  assert.equal(requests[0].payload.overrides.conductorMaterial, 'Tinned Copper');
  assert.equal(requests[0].payload.overrides.manufacturer, 'Acme');
  assert.equal(requests[0].payload.overrides.partNumber, 'WB-42');
  assert.equal(requests[0].payload.overrides.notes, 'Use matched stock');
  await dialog.cancelOptions();
  assert.equal(requests[1].action, 'set_wire_group_material_overrides');
  assert.equal(requests[1].payload.overrides.insulationMaterial, 'ETFE');
  assert.equal(requests[1].payload.overrides.conductorMaterial, 'Tinned Copper');
  assert.equal(requests[1].payload.overrides.manufacturer, 'Acme');
  assert.equal(requests[1].payload.overrides.partNumber, 'WB-42');
  assert.equal(requests[1].payload.overrides.notes, 'Use matched stock');
});

asyncTest('connected wire properties atomically saves diameter and construction materials', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  configureMaterialCatalog(context);
  context.send = async (action, payload) => {
    requests.push({ action, payload });
    return { ok: true };
  };
  context.openWireGroupProperties(definition, {
    wireGroupId: 'group-1', diameterMm: 1.5,
    materials: {
      ...definition.materialDefaults,
      conductorMaterial: 'Tinned Copper', partNumber: 'WB-42',
    },
    materialOverrides: {
      insulationMaterial: null, conductorMaterial: 'Tinned Copper', mainColor: null,
      appearance: null, stripes: null, manufacturer: null, partNumber: 'WB-42', notes: null,
    },
  });
  const dialog = context.document.body.children.at(-1);
  const diameter = descendants(dialog, (item) => item.type === 'number')[0];
  const form = descendants(dialog, (item) => item.tag === 'form')[0];
  const materialFields = descendants(dialog, (item) => item.className?.split(' ')
    .includes('material-field'));
  const insulation = descendants(materialFields[0], (item) => item.type === 'text')[0];
  const insulationOverride = descendants(
    materialFields[0], (item) => item.type === 'checkbox',
  )[0];
  const conductorOverride = descendants(
    materialFields[1], (item) => item.type === 'checkbox',
  )[0];
  const manufacturer = descendants(materialFields[2], (item) => item.type === 'text')[0];
  const manufacturerOverride = descendants(
    materialFields[2], (item) => item.type === 'checkbox',
  )[0];
  const partNumberOverride = descendants(
    materialFields[3], (item) => item.type === 'checkbox',
  )[0];
  const notes = descendants(materialFields[4], (item) => item.tag === 'textarea')[0];
  const notesOverride = descendants(
    materialFields[4], (item) => item.type === 'checkbox',
  )[0];
  assert.equal(materialFields.length, 5);
  assert.equal(insulation.disabled, true);
  assert.equal(conductorOverride.checked, true);
  assert.equal(partNumberOverride.checked, true);
  assert.equal(notes.disabled, true);
  diameter.value = '0';
  await form.events.submit({ preventDefault() {} });
  assert.equal(requests.length, 0);
  assert.match(descendants(dialog, (item) => item.attributes.role === 'alert')[0].textContent,
    /positive diameter/);
  diameter.value = '2.75';
  insulationOverride.checked = true;
  insulationOverride.events.change();
  insulation.value = '';
  await form.events.submit({ preventDefault() {} });
  assert.equal(requests.length, 0);
  assert.match(descendants(dialog, (item) => item.attributes.role === 'alert')[0].textContent,
    /Insulation material/);
  insulation.value = 'ETFE';
  conductorOverride.checked = false;
  conductorOverride.events.change();
  manufacturerOverride.checked = true;
  manufacturerOverride.events.change();
  manufacturer.value = '';
  partNumberOverride.checked = false;
  partNumberOverride.events.change();
  notesOverride.checked = true;
  notesOverride.events.change();
  notes.value = 'Install as matched stock';
  await form.events.submit({ preventDefault() {} });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].action, 'set_wire_group_properties');
  assert.equal(requests[0].payload.harnessId, 'h');
  assert.equal(requests[0].payload.wireGroupId, 'group-1');
  assert.equal(requests[0].payload.diameterMm, 2.75);
  assert.equal(requests[0].payload.insulationMaterial, 'ETFE');
  assert.equal(requests[0].payload.conductorMaterial, null);
  assert.equal(requests[0].payload.manufacturer, '');
  assert.equal(requests[0].payload.partNumber, null);
  assert.equal(requests[0].payload.notes, 'Install as matched stock');
  assert.equal(dialog.open, false);
});

test('material dialog constrains library controls to its horizontal bounds', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.material-options \{[^}]*overflow-x: hidden;/);
  assert.match(styles, /\.material-options select, \.material-options textarea \{[^}]*max-width: 100%;/s);
});
