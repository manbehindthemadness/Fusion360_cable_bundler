/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, asyncTest, descendants, harness, join, palette, readFileSync, runInNewContext, test } = require('./support.cjs');

test('material text fields use controlled autocomplete instead of native datalists', () => {
  const { context } = palette();
  const definition = harness();
  runInNewContext('currentState = { catalog };', Object.assign(context, { catalog: {
    insulationMaterials: ['PVC', 'ETFE'], conductorMaterials: ['Copper'],
    colors: [{ name: 'Black', hex: '#202020' }], stripePatterns: [],
  } }));
  context.send = async (action) => action === 'get_appearance_libraries'
    ? { ok: true, libraries: [] } : { ok: true, appearances: [] };

  context.openMaterialOptions(definition);

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

asyncTest('wire options Cancel restores the values rendered by Apply', async () => {
  const { context } = palette();
  const definition = harness();
  const requests = [];
  runInNewContext('currentState = { catalog };', Object.assign(context, { catalog: {
    insulationMaterials: ['PVC', 'ETFE'], conductorMaterials: ['Copper'],
    colors: [{ name: 'Black', hex: '#202020' }], stripePatterns: [],
  } }));
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

test('material dialog constrains library controls to its horizontal bounds', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.material-options \{[^}]*overflow-x: hidden;/);
  assert.match(styles, /\.material-options select, \.material-options textarea \{[^}]*max-width: 100%;/s);
});
