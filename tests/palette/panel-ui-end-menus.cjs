/* global require */
const { assert, descendants, harness, palette, test } = require('./support.cjs');

/** Return the named submenu branch from a rendered context menu. */
function contextMenuBranch(menu, label) {
  return menu.children.find(
    (item) => item.className === 'context-menu-branch'
      && item.children[0].textContent === label,
  );
}

test('master end menu groups connection and routing actions under Add', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways[0].orderedControlIds = ['c1'];
  const actions = [];
  context.appendEndGuides = (_harness, connectionId) => actions.push(['guides', connectionId]);
  context.addEndRefine = (_harness, connectionId) => actions.push(['refine', connectionId]);
  const diagram = context.renderRelationshipMap(definition);
  const end = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];

  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  const menu = descendants(
    diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
  )[0];
  let addBranch = contextMenuBranch(menu, 'Add');
  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Connection', 'Guides', 'Refine'],
  );
  addBranch.children[1].children[1].events.click();
  end.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
  });
  addBranch = contextMenuBranch(menu, 'Add');
  addBranch.children[1].children[2].events.click();

  assert.deepEqual(actions, [['guides', 'a1'], ['refine', 'a1']]);
});

test('master end menu switches only unassigned ends immediately above Rename', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.cableGroups = definition.cableGroups.slice(1);
  const diagram = context.renderRelationshipMap(definition);
  const unassigned = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a1',
  )[0];
  const assigned = descendants(
    diagram,
    (node) => node.className === 'relationship-end-entry' && node.dataset.connectionId === 'a2',
  )[0];
  const openMenu = (end) => {
    end.events.contextmenu({
      clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: end,
    });
    return descendants(
      diagram, (node) => node.className === 'relationship-map-context-menu' && !node.hidden,
    )[0];
  };

  assert.equal(unassigned.children[1].textContent, 'Unassigned');
  assert.equal(unassigned.attributes['aria-label'], 'a1, unassigned end');
  assert.equal(assigned.children[1].textContent, 'Assigned');
  assert.equal(assigned.attributes['aria-label'], 'a2, assigned end');

  let menu = openMenu(unassigned);
  const labels = menu.children.map((item) => item.textContent);
  assert.equal(labels.indexOf('Switch'), labels.indexOf('Rename') - 1);
  assert.equal(labels.at(-1), 'Properties');
  menu.children.find((item) => item.textContent === 'Switch').events.click();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'switch_standalone_end');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.connectionId, 'a1');

  menu = openMenu(assigned);
  assert.equal(menu.children.some((item) => item.textContent === 'Switch'), false);
});
