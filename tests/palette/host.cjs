/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, asyncTest, harness, join, palette, readFileSync, runInNewContext, test } = require('./support.cjs');

test('solid generation requires confirmation and targets the selected harness', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.wires = [];
  definition.wireGroups = [{ wireGroupId: 'g1', connectionIds: ['a1', 'b1'] }];
  runInNewContext('currentState = { harnesses: [definition] }; selectedHarnessKey = harnessKey(definition);',
    Object.assign(context, { definition }));
  context.window.confirm = () => false;
  context.generateSolids();
  assert.equal(calls.length, 0);
  context.window.confirm = (message) => message.includes('manual edits');
  context.generateSolids();
  assert.equal(calls[0].action, 'generate_solids');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.replaceExisting, true);
});

test('clear solids requires confirmation and targets the selected harness', () => {
  const { context, calls } = palette();
  runInNewContext('currentState = { harnesses: [definition] }; selectedHarnessKey = harnessKey(definition);',
    Object.assign(context, { definition: harness() }));
  context.window.confirm = () => false;
  context.clearSolids();
  assert.equal(calls.length, 0);
  context.window.confirm = (message) => message.includes('manual edits');
  context.clearSolids();
  assert.equal(calls[0].action, 'clear_solids');
  assert.equal(calls[0].payload.harnessId, 'h');
});

test('event console retains messages and marks failures', () => {
  const { context } = palette();
  context.appendNotice('Solving route preview…');
  context.appendNotice('Wire 001: dynamically adjusted transitions.');
  context.appendNotice('Wire 001: dynamically adjusted transitions.');
  context.appendNotice('Sweep failed', true);
  const entries = runInNewContext('ui.notice.children', context);
  assert.deepEqual(
    entries.map((entry) => entry.textContent),
    ['Solving route preview…', 'Wire 001: dynamically adjusted transitions.', 'Sweep failed'],
  );
  assert.equal(entries[2].className, 'notice-entry error');
});

test('event console hides diagnostics until verbose output is enabled', () => {
  const storage = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(storage);
  const message = 'Wire 001 failed. Routing diagnostic: points_mm=[(1, 2, 3)]';
  context.appendNotice(message, true);
  const entry = runInNewContext('ui.notice.children[0]', context);
  assert.equal(entry.textContent, 'Wire 001 failed.');
  runInNewContext('ui.verboseDiagnostics.checked = true; ui.verboseDiagnostics.events.change();', context);
  assert.equal(entry.textContent, message);
  assert.equal(storage.get('wireBundler.verboseDiagnostics'), 'true');
});

test('developer mode defaults off and gates verbose diagnostics', () => {
  const storage = new Map([['wireBundler.verboseDiagnostics', 'true']]);
  const { context } = palette(storage);

  assert.equal(context.ui.developerMode.checked, false);
  assert.equal(context.ui.verboseDiagnostics.disabled, true);
  assert.equal(context.ui.verboseDiagnostics.checked, false);

  context.ui.verboseDiagnostics.checked = true;
  context.ui.verboseDiagnostics.events.change();
  assert.equal(context.ui.verboseDiagnostics.checked, false);
  assert.equal(storage.get('wireBundler.verboseDiagnostics'), 'false');
});

test('developer mode requires disclosure agreement before activation', () => {
  const storage = new Map();
  const { context } = palette(storage);

  context.ui.developerMode.checked = true;
  context.ui.developerMode.events.change();
  assert.equal(context.ui.developerConsent.open, true);
  assert.equal(context.ui.developerMode.checked, false);
  assert.equal(context.ui.developerConsentEnable.disabled, true);

  context.ui.developerConsentForm.events.submit({ preventDefault() {} });
  assert.equal(context.ui.developerConsent.open, true);
  assert.equal(storage.get('wireBundler.developerMode'), 'false');

  context.ui.developerConsentAgreement.checked = true;
  context.ui.developerConsentAgreement.events.change();
  assert.equal(context.ui.developerConsentEnable.disabled, false);
  context.ui.developerConsentForm.events.submit({ preventDefault() {} });

  assert.equal(context.ui.developerConsent.open, false);
  assert.equal(context.ui.developerMode.checked, true);
  assert.equal(context.ui.verboseDiagnostics.disabled, false);
  assert.equal(storage.get('wireBundler.developerMode'), 'true');
  assert.equal(storage.get('wireBundler.developerConsentVersion'), '1');

  context.ui.developerMode.checked = false;
  context.ui.developerMode.events.change();
  assert.equal(context.ui.developerMode.checked, false);
  assert.equal(context.ui.verboseDiagnostics.disabled, true);
  assert.equal(storage.get('wireBundler.developerMode'), 'false');
});

test('developer mode and verbose diagnostics survive palette context recreation', () => {
  const preferences = new Map();
  const first = palette(new Map(), preferences).context;
  first.ui.developerMode.checked = true;
  first.ui.developerMode.events.change();
  first.ui.developerConsentAgreement.checked = true;
  first.ui.developerConsentAgreement.events.change();
  first.ui.developerConsentForm.events.submit({ preventDefault() {} });
  first.ui.verboseDiagnostics.checked = true;
  first.ui.verboseDiagnostics.events.change();

  const second = palette(new Map(), preferences).context;

  assert.equal(second.ui.developerMode.checked, true);
  assert.equal(second.ui.verboseDiagnostics.disabled, false);
  assert.equal(second.ui.verboseDiagnostics.checked, true);
});

asyncTest('developer mode QA probe observes a detached wire card through a fixed target', async () => {
  const preferences = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const definition = harness();
  const sent = [];
  context.send = async (action, payload) => sent.push({ action, payload });
  runInNewContext(
    'currentState = { harnesses: [definition], notice: "" };',
    Object.assign(context, { definition }),
  );

  const result = context.window.fusionJavaScriptHandler.handle('qa_probe', JSON.stringify({
    operation: 'observe_wire',
    harnessId: 'h',
    wireId: 'w1',
    expectedLabel: 'Wire #001',
  }));
  await Promise.resolve();

  assert.equal(result, 'OK');
  assert.deepEqual(sent, [{ action: 'clear_highlight', payload: undefined }]);
  assert.equal(context.ui.libraryView.hidden, true);
  assert.equal(context.ui.editorView.hidden, false);
  assert.equal(context.ui.editor.querySelector('.wire-route'), undefined);
});

asyncTest('developer visual QA probe verifies the relationship-diagram structure', async () => {
  const preferences = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'lower fuse box path ext 1', startName: '', endName: '',
    orderedControlIds: [],
  });
  definition.junctions = [{
    junctionId: 'j1', name: 'Junction 01', controlId: 'c1',
    pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  }];
  definition.wires.forEach((wire) => { wire.orderedPathwayIds = ['p', 'p2']; });
  const sent = [];
  context.window.scrollTo = () => {};
  context.send = async (action, payload) => sent.push({ action, payload });
  runInNewContext(
    'currentState = { harnesses: [definition], notice: "" };',
    Object.assign(context, { definition }),
  );

  const result = context.window.fusionJavaScriptHandler.handle(
    'qa_probe', JSON.stringify({ operation: 'observe_relationship_diagram' }),
  );
  await Promise.resolve();

  assert.equal(result, 'OK');
  assert.equal(JSON.stringify(sent), JSON.stringify([{
    action: 'qa_diagram_observation',
    payload: {
      status: 'passed',
      connectorCount: 20,
      maximumEndpointGap: 0,
      obstructedTraceCount: 0,
      portCount: 4,
      invalidTraceGroupCount: 0,
      contractVersion: '4',
      layout: 'endpoint-junction-forest',
    },
  }]));
});

test('developer visual QA detects a topology trace inside an unrelated node', () => {
  const { context } = palette();
  const unrelated = {
    dataset: { pathwayId: 'middle' },
    getBoundingClientRect: () => ({ left: 40, right: 60, top: 40, bottom: 60 }),
  };
  const diagram = { querySelectorAll: () => [unrelated] };
  const edge = {
    dataset: { pathwayId: 'source', junctionId: 'target' },
    getTotalLength: () => 100,
    getPointAtLength: (distance) => ({ x: distance, y: 50 }),
    getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
  };

  assert.equal(context.qaTopologyTraceObstructed(edge, diagram), true);
  edge.getPointAtLength = (distance) => ({ x: distance, y: 30 });
  assert.equal(context.qaTopologyTraceObstructed(edge, diagram), false);
});

test('developer visual QA measures topology endpoints against dynamic port sides', () => {
  const { context } = palette();
  const junction = {
    getBoundingClientRect: () => ({ left: 0, right: 100, top: 0, bottom: 60 }),
  };
  const pathway = {
    getBoundingClientRect: () => ({ left: 200, right: 300, top: 200, bottom: 260 }),
  };
  const diagram = {
    querySelector: (selector) => (selector.includes('junction') ? junction : pathway),
  };
  const edge = {
    dataset: { endpoint: 'start', pathwayId: 'p', junctionId: 'j' },
    parentElement: { dataset: { sourceSide: 'bottom', targetSide: 'top' } },
    getTotalLength: () => 100,
    getPointAtLength: (distance) => (distance ? { x: 250, y: 200 } : { x: 50, y: 60 }),
    getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
  };

  assert.equal(context.qaTopologyEdgeGap(edge, diagram), 0);
  edge.getPointAtLength = (distance) => (
    distance ? { x: 250, y: 200 } : { x: 50, y: 65 }
  );
  assert.equal(context.qaTopologyEdgeGap(edge, diagram), 5);
});

test('palette QA probe is denied without current developer consent', () => {
  const { context } = palette();
  const result = context.window.fusionJavaScriptHandler.handle('qa_probe', JSON.stringify({
    operation: 'observe_wire',
    harnessId: 'h',
    wireId: 'w1',
    expectedLabel: 'Wire #001',
  }));

  assert.equal(result, 'DENIED');
});

test('developer QA probe verifies the fixed wire-options dialog geometry', () => {
  const preferences = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const definition = harness();
  const sent = [];
  context.window.scrollTo = () => {};
  context.send = async (action, payload) => {
    sent.push({ action, payload });
    return action === 'get_appearance_libraries' ? { ok: true, libraries: [] } : { ok: true };
  };
  runInNewContext(
    'currentState = { harnesses: [definition], notice: "", catalog: null };',
    Object.assign(context, { definition }),
  );

  const result = context.window.fusionJavaScriptHandler.handle('qa_probe', JSON.stringify({
    operation: 'observe_wire_dialog', harnessId: 'h', wireId: 'w1',
  }));

  assert.equal(result, 'OK');
  assert.equal(context.document.body.children.some((child) => child.tag === 'dialog'), false);
  assert.deepEqual(sent[0], { action: 'get_appearance_libraries', payload: undefined });
});

test('developer QA dialog probe rejects horizontal overflow', () => {
  const preferences = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const definition = harness();
  const createElement = context.document.createElement;
  context.document.createElement = (tag) => {
    const element = createElement(tag);
    if (tag === 'dialog') element.scrollWidth = element.clientWidth + 20;
    return element;
  };
  context.window.scrollTo = () => {};
  context.send = async (action) => (
    action === 'get_appearance_libraries' ? { ok: true, libraries: [] } : { ok: true }
  );
  runInNewContext(
    'currentState = { harnesses: [definition], notice: "", catalog: null };',
    Object.assign(context, { definition }),
  );

  const result = context.window.fusionJavaScriptHandler.handle('qa_probe', JSON.stringify({
    operation: 'observe_wire_dialog', harnessId: 'h', wireId: 'w1',
  }));

  assert.equal(result, 'MISMATCH');
  assert.equal(context.document.body.children.some((child) => child.tag === 'dialog'), false);
});

test('developer QA probe dispatches fixed connection, pathway, and wire hover events', () => {
  const preferences = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '1'],
  ]);
  const { context } = palette(new Map(), preferences);
  const definition = harness();
  const calls = [];
  context.window.scrollTo = () => {};
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });
  context.send = async (action) => calls.push({ action });
  runInNewContext(
    'currentState = { harnesses: [definition], notice: "" };',
    Object.assign(context, { definition }),
  );
  const probe = (payload) => context.window.fusionJavaScriptHandler.handle(
    'qa_probe', JSON.stringify({ harnessId: 'h', wireId: 'w1', ...payload }),
  );

  assert.equal(probe({ operation: 'hover_connection', endpoint: 'start' }), 'OK');
  assert.equal(probe({ operation: 'leave_hover' }), 'OK');
  assert.equal(probe({ operation: 'hover_pathway', pathwayId: 'p' }), 'OK');
  assert.equal(probe({ operation: 'leave_hover' }), 'OK');
  assert.equal(probe({ operation: 'hover_wire' }), 'OK');
  assert.equal(probe({ operation: 'leave_hover' }), 'OK');
  assert.deepEqual(calls, [
    { type: 'connection', id: 'a1' },
    { action: 'clear_highlight' },
    { type: 'pathway_gates', id: 'p' },
    { action: 'clear_highlight' },
    { type: 'preview_wire', id: 'w1' },
    { action: 'clear_highlight' },
  ]);
});

test('developer mode rejects stale consent and remains off after cancel or Escape', () => {
  const storage = new Map([
    ['wireBundler.developerMode', 'true'],
    ['wireBundler.developerConsentVersion', '0'],
  ]);
  const { context } = palette(storage);
  assert.equal(context.ui.developerMode.checked, false);
  assert.equal(storage.get('wireBundler.developerMode'), 'false');

  context.ui.developerMode.checked = true;
  context.ui.developerMode.events.change();
  context.ui.developerConsentCancel.events.click();
  assert.equal(context.ui.developerConsent.open, false);
  assert.equal(context.ui.developerMode.checked, false);

  context.ui.developerMode.checked = true;
  context.ui.developerMode.events.change();
  context.ui.developerConsent.events.cancel({ preventDefault() {} });
  assert.equal(context.ui.developerConsent.open, false);
  assert.equal(context.ui.developerMode.checked, false);
  assert.equal(storage.get('wireBundler.developerMode'), 'false');
});

test('developer disclosure explains capture scope and separate opt-in', () => {
  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  assert.match(html, /Screen Recording or Accessibility permission/);
  assert.match(html, /design names, geometry, paths, and other project/);
  assert.match(html, /Each external QA run remains separately opt-in/);
  assert.match(html, /I have read and understand this disclosure and agree/);
});

test('validation and events share one collapsed bottom panel with a resizable console', () => {
  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  const libraryIndex = html.indexOf('id="library-view"');
  const editorIndex = html.indexOf('id="editor-view"');
  const panelIndex = html.indexOf('class="validation-events"');
  const validationIndex = html.indexOf('id="validation-output"');
  const developerModeIndex = html.indexOf('id="developer-mode"');
  const verboseIndex = html.indexOf('id="verbose-diagnostics"');
  const consoleIndex = html.indexOf('id="notice"');
  assert.ok(panelIndex > libraryIndex && panelIndex > editorIndex);
  assert.ok(validationIndex > panelIndex && developerModeIndex > validationIndex);
  assert.ok(verboseIndex > developerModeIndex && consoleIndex > verboseIndex);
  assert.match(html, /<details class="validation-events">[\s\S]*Validation &amp; Events/);
  assert.doesNotMatch(html, /<details class="validation-events"[^>]*\bopen\b/);
  assert.doesNotMatch(html, /<header\b|class="app-header"|id="refresh"/);
  assert.match(styles, /#notice \{[^}]*min-height: 72px;[^}]*max-height: 60vh;[^}]*resize: vertical;/s);
  assert.match(styles, /body \{[^}]*grid-template-rows: minmax\(0, 1fr\);/s);
  assert.match(styles, /#editor-view:not\(\[hidden\]\) \{[^}]*grid-template-rows: auto minmax\(0, 1fr\);/s);
});
