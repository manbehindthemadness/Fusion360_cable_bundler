/* global require */
const { assert, descendants, harness, palette, test } = require('./support.cjs');

test('master diagram displays standalone Interface cards without pathways', () => {
  const { context } = palette();
  const highlights = [];
  const clears = [];
  context.highlightMember = (_harness, memberType, memberId) => {
    highlights.push([memberType, memberId]);
  };
  context.send = (action) => {
    if (action === 'clear_highlight') clears.push(action);
    return Promise.resolve({ ok: true });
  };
  const definition = harness();
  definition.pathways = [];
  definition.junctions = [];
  definition.interfaces = [{
    interfaceId: 'interface-1', name: 'Socket A',
    targets: [{ kind: 'occurrence', hasLinkedGeometry: true }],
  }];
  const diagram = context.renderRelationshipMap(definition);
  const cards = descendants(diagram, (node) => node.className === 'relationship-interface-card');
  assert.equal(cards.length, 1);
  assert.equal(cards[0].children[0].textContent, 'Socket A');
  assert.equal(cards[0].children[1].textContent, 'occurrence · linked');
  cards[0].events.click();
  assert.deepEqual(highlights, []);
  const contacts = context.document.body.querySelector('.interface-contacts-popup');
  assert.equal(contacts.open, true);
  assert.equal(contacts.children[0].textContent, 'Contacts Editor · Socket A');
  cards[0].events.mouseenter();
  assert.deepEqual(highlights, [['interface', 'interface-1']]);
  cards[0].events.mouseleave();
  assert.deepEqual(clears, ['clear_highlight']);
});

test('master diagram routes connected Interfaces to their pathway end lists', () => {
  const { context } = palette();
  const definition = harness();
  definition.interfaces = [{
    interfaceId: 'connected', name: 'Socket A', connectedConnectionIds: ['a1'],
    targets: [{ kind: 'occurrence', hasLinkedGeometry: true }], contacts: [],
  }, {
    interfaceId: 'reference', name: 'Unwired Socket', connectedConnectionIds: [],
    targets: [{ kind: 'body', hasLinkedGeometry: true }], contacts: [],
  }, {
    interfaceId: 'orphan', name: 'Unrouted Socket', connectedConnectionIds: ['missing'],
    targets: [{ kind: 'body', hasLinkedGeometry: true }], contacts: [],
  }];

  const diagram = context.renderRelationshipMap(definition);

  const graphNode = descendants(diagram, (node) => (
    node.dataset.nodeId === 'interface:connected'
      && node.className?.includes('relationship-topology-interface')
  ))[0];
  assert.equal(graphNode.className.includes('relationship-topology-interface'), true);
  assert.equal(graphNode.querySelector('.relationship-interface-card').children[0].textContent,
    'Socket A');
  const edges = descendants(diagram, (node) => (
    node.className === 'relationship-topology-edge'
      && node.dataset.sourceId === 'interface:connected'
  ));
  assert.equal(edges.length, 1);
  assert.equal(edges[0].dataset.targetId, 'pathway:p');
  assert.equal(edges[0].dataset.cableGroupIds, 'g1');
  assert.equal(edges[0].children[0].dataset.interfaceId, 'connected');
  const reference = descendants(diagram, (node) => (
    node.className === 'relationship-interfaces'
  ))[0];
  assert.deepEqual(descendants(reference, (node) => node.dataset.interfaceId)
    .map((node) => node.dataset.interfaceId), ['reference', 'orphan']);
});

test('Interface graph links follow saved end identity, not matching pin labels', () => {
  const { context } = palette();
  const definition = harness();
  definition.interfaces = [{
    interfaceId: 'board', name: 'Board', connectedConnectionIds: ['a1', 'b2', 'missing'],
    contacts: [{ pin: '1', name: 'Power' }], targets: [],
  }];
  const components = [...context.relationshipTopology(definition)];
  const edges = components.flatMap((component) => component.edges)
    .filter((edge) => edge.kind === 'interface');
  assert.equal(edges.length, 2);
  assert.deepEqual(edges.map((edge) => [edge.sourceId, edge.targetId,
    edge.relationship.endpoint]), [
    ['interface:board', 'pathway:p', 'start'],
    ['pathway:p', 'interface:board', 'end'],
  ]);
});

test('a shared Interface keeps separate links to both pathway boundaries', () => {
  const { context } = palette();
  const definition = harness();
  definition.interfaces = [{
    interfaceId: 'board', name: 'Board', connectedConnectionIds: ['a1', 'b1'],
    contacts: [], targets: [],
  }];

  const diagram = context.renderRelationshipMap(definition);

  const edges = descendants(diagram, (node) => (
    node.className === 'relationship-topology-edge'
      && node.children[0]?.dataset.interfaceId === 'board'
  ));
  assert.equal(edges.length, 2);
  assert.deepEqual(new Set(edges.map((edge) => edge.children[0].dataset.endpoint)),
    new Set(['start', 'end']));
  const stack = diagram.querySelector('.relationship-pathway-stack');
  assert.equal(stack.dataset.diagramLayoutError, undefined);
});

test('diagram QA measures Interface links against their own nodes', () => {
  const { context } = palette();
  const rectangle = (left, right) => ({
    left, right, top: 0, bottom: 100,
  });
  const interfaceNode = {
    dataset: { nodeId: 'interface:board' },
    getBoundingClientRect: () => rectangle(0, 100),
  };
  const pathwayNode = {
    dataset: { nodeId: 'pathway:p' },
    getBoundingClientRect: () => rectangle(150, 250),
    querySelector: () => ({ getBoundingClientRect: () => rectangle(150, 250) }),
  };
  const unrelatedNode = {
    dataset: { nodeId: 'junction:far' },
    getBoundingClientRect: () => rectangle(300, 350),
  };
  const diagram = {
    querySelector: (selector) => (selector.includes('topology-interface')
      ? interfaceNode : pathwayNode),
    querySelectorAll: () => [interfaceNode, pathwayNode, unrelatedNode],
  };
  const edge = {
    dataset: { interfaceId: 'board', pathwayId: 'p', endpoint: 'start' },
    parentElement: {
      dataset: {
        sourceId: 'interface:board', targetId: 'pathway:p',
        sourceSide: 'right', targetSide: 'left',
      },
      querySelectorAll: () => [],
    },
    getTotalLength: () => 50,
    getPointAtLength: (length) => ({ x: 100 + length, y: 50 }),
    getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
  };

  assert.equal(context.qaTopologyEdgeGap(edge, diagram), 0);
  assert.ok(context.qaTopologyTraceClearance(edge, diagram) > 100);
});

test('Cable Details Materials action opens group materials', () => {
  const { context } = palette();
  const definition = harness();
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');

  details.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: details,
  });
  const menu = details.querySelector('.relationship-map-context-menu');
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(
    materialDialog.children[0].children[0].textContent,
    'Connected Cable Group Materials',
  );
});

test('Cable Details header shows and renames its cable group', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.cableGroups[0].name = 'Engine loom';

  context.openCableGroupDetails(definition, 'g1', 'a1');

  const details = context.document.body.querySelector('.cable-group-details-popup');
  const heading = details.querySelector('.cable-group-details-heading');
  const title = descendants(heading, (node) => node.tag === 'h2')[0];
  const rename = descendants(
    heading, (node) => node.tag === 'button' && node.textContent === 'Rename',
  )[0];
  assert.equal(title.textContent, 'Engine loom');
  assert.equal(descendants(heading, (node) => node.tag === 'p')[0].textContent, '2 assigned ends');
  assert.equal(descendants(details, (node) => node.tag === 'h3')[0].textContent, 'Assigned Ends');
  assert.equal(descendants(heading, (node) => node.textContent === 'Cable Details').length, 0);

  rename.events.click();
  const input = heading.querySelector('input');
  assert.equal(input.value, 'Engine loom');
  assert.equal(input.attributes['aria-label'], 'Cable group name');
  input.value = 'Cabin data';
  input.events.keydown({ key: 'Enter', stopPropagation() {}, preventDefault() {} });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'rename_cable_group');
  assert.equal(calls[0].payload.harnessId, 'h');
  assert.equal(calls[0].payload.cableGroupId, 'g1');
  assert.equal(calls[0].payload.name, 'Cabin data');
});
