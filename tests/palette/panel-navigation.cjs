/* global require */
const {
  assert, asyncTest, descendants, harness, palette, test,
} = require('./support.cjs');

/** Return the named submenu branch from a rendered context menu. */
function contextMenuBranch(menu, label) {
  return menu.children.find(
    (item) => item.className === 'context-menu-branch'
      && item.children[0].textContent === label,
  );
}

test('diagram hover requires a fresh panel interaction after the pointer leaves', () => {
  const { context } = palette();
  const highlights = [];
  context.highlightMember = (_harness, memberType, memberId) => {
    highlights.push([memberType, memberId]);
  };
  const diagram = context.renderRelationshipMap(harness());
  const end = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];

  context.document.documentElement.dispatchEvent({ type: 'mouseleave' });
  end.events.mouseenter();
  assert.deepEqual(highlights, []);
  assert.equal(diagram.className.includes('relationship-focus-active'), false);

  context.document.dispatchEvent({ type: 'pointerdown' });
  end.events.mouseenter();
  assert.deepEqual(highlights, [['connection', 'a1']]);
  assert.equal(diagram.className.includes('relationship-focus-active'), true);
});

test('Route Editor opens Details only for assigned cable ends', () => {
  const { context } = palette();
  const definition = harness();
  definition.cableGroups = definition.cableGroups.slice(1);
  const left = context.resolveCableCreationBoundary(
    definition, { pathwayId: 'p', endpoint: 'start' },
  );
  const right = context.resolveCableCreationBoundary(
    definition, { pathwayId: 'p', endpoint: 'end' },
  );
  context.openCreateCablesPopup(definition, left, right);
  const editor = context.document.body.querySelector('.create-cables-popup');
  const cards = descendants(
    editor, (node) => node.className?.split(' ').includes('create-cables-end-card'),
  );
  const assigned = cards.find((candidate) => candidate.dataset.connectionId === 'a2');
  const unassigned = cards.find((candidate) => candidate.dataset.connectionId === 'a1');
  const openMenu = (connectionId) => {
    const card = cards.find((candidate) => candidate.dataset.connectionId === connectionId);
    card.events.contextmenu({
      clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: card,
    });
    return editor.querySelector('.relationship-map-context-menu');
  };

  let menu = openMenu('a2');
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Details', 'Rename', 'Delete',
  ]);
  menu.children[0].events.click();
  assert.equal(editor.open, true);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup').open, true);

  context.closeCableGroupDetails();
  assigned.closest = () => null;
  assigned.setPointerCapture = () => {};
  assigned.hasPointerCapture = () => false;
  assigned.events.pointerdown({
    button: 0, clientX: 20, clientY: 20, pointerId: 1, target: assigned,
  });
  assigned.events.pointermove({
    clientX: 1000, clientY: 1000, preventDefault() {}, target: assigned,
  });
  assigned.events.pointerup({ pointerId: 1, target: assigned });
  assigned.events.click({
    preventDefault() {}, stopPropagation() {}, target: assigned,
  });
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);

  assigned.events.pointerdown({
    button: 0, clientX: 20, clientY: 20, pointerId: 2, target: assigned,
  });
  assigned.events.pointerup({ pointerId: 2, target: assigned });
  assigned.events.click({ target: assigned });
  assert.equal(editor.open, true);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup').open, true);

  context.closeCableGroupDetails();
  menu = openMenu('a1');
  assert.deepEqual(menu.children.map((item) => item.textContent), ['Rename', 'Delete']);
  unassigned.events.click?.({ target: unassigned });
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
});

asyncTest('editing a master end isolates keyboard and pointer events until saved', async () => {
  const { context, calls } = palette();
  const definition = harness();
  const highlights = [];
  let finishSave;
  context.highlightMember = (_harness, memberType, memberId) => {
    highlights.push([memberType, memberId]);
  };
  context.mutate = (action, payload) => {
    calls.push({ action, payload });
    return new Promise((resolve) => { finishSave = resolve; });
  };
  const diagram = context.renderRelationshipMap(definition);
  const end = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];
  const otherEnd = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a2',
  )[0];

  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  const menu = descendants(
    diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  menu.children.find((item) => item.textContent === 'Rename').events.click();
  const input = end.querySelector('input');
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, []);
  assert.equal(diagram.className.includes('relationship-focus-active'), false);
  ['mousedown', 'click'].forEach((eventName) => {
    let pointerPropagationStopped = false;
    input.events[eventName]({
      stopPropagation() { pointerPropagationStopped = true; },
    });
    if (!pointerPropagationStopped && eventName === 'click') end.events.click();
    assert.equal(pointerPropagationStopped, true);
  });
  let contextPropagationStopped = false;
  let contextDefaultPrevented = false;
  input.events.contextmenu({
    stopPropagation() { contextPropagationStopped = true; },
    preventDefault() { contextDefaultPrevented = true; },
  });
  assert.equal(contextPropagationStopped, true);
  assert.equal(contextDefaultPrevented, false);
  assert.equal(menu.hidden, true);
  let propagationStopped = false;
  let defaultPrevented = false;
  input.events.keydown({
    key: ' ',
    stopPropagation() { propagationStopped = true; },
    preventDefault() { defaultPrevented = true; },
  });
  if (!propagationStopped) end.events.keydown({ key: ' ', preventDefault() {} });

  assert.equal(propagationStopped, true);
  assert.equal(defaultPrevented, false);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), undefined);
  assert.equal(end.querySelector('input'), input);
  input.value = 'Engine Bay End';
  input.events.blur();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.name, 'Engine Bay End');
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, []);
  assert.equal(diagram.className.includes('relationship-focus-active'), false);

  finishSave();
  await new Promise((resolve) => setTimeout(resolve, 0));
  otherEnd.events.mouseenter();
  assert.deepEqual(highlights, [['connection', 'a2']]);
  assert.equal(diagram.className.includes('relationship-focus-active'), true);
});

test('Cable Details end nodes and rows share Add routing submenus', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways[0].orderedControlIds = ['c1'];
  const actions = [];
  context.appendEndGuides = (_harness, connectionId) => actions.push(['guides', connectionId]);
  context.addEndRefine = (_harness, connectionId) => actions.push(['refine', connectionId]);
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const graphicEnd = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-node')
      && node.dataset.connectionId === 'a1',
  )[0];
  const member = descendants(
    details,
    (node) => node.className?.split(' ').includes('cable-group-details-member')
      && node.dataset.connectionId === 'a1',
  )[0];
  const menu = details.querySelector('.relationship-map-context-menu');

  graphicEnd.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: graphicEnd,
  });
  let addBranch = contextMenuBranch(menu, 'Add');
  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Connection', 'Guides', 'Refine'],
  );
  addBranch.children[1].children[1].events.click();
  member.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: member,
  });
  addBranch = contextMenuBranch(menu, 'Add');
  addBranch.children[1].children[2].events.click();

  assert.deepEqual(actions, [['guides', 'a1'], ['refine', 'a1']]);
  assert.equal(menu.children.at(-1).textContent, 'Properties');
});
