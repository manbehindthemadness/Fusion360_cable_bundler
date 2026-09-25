/* global require */
const {
  assert, asyncTest, descendants, harness, palette, runInNewContext, test,
} = require('./support.cjs');

/** Return the named submenu branch from a rendered context menu. */
function contextMenuBranch(menu, label) {
  return menu.children.find(
    (item) => item.className === 'context-menu-branch'
      && item.children[0].textContent === label,
  );
}

/** Build a cable-details fixture whose selected cable inherits shielding. */
function shieldingConnectionFixture() {
  const { context, calls } = palette();
  const definition = harness();
  const group = definition.cableGroups[0];
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  group.materials = { ...group.materials, shielding: 'Foil' };
  return { context, calls, definition, group, connection };
}

asyncTest('Cable Details connects detached ends and manages diagram-only connection nodes', async () => {
  const { context, calls } = palette();
  const definition = harness();
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  const nativeActions = [];
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  context.connectCableEnd = (_harness, connectionId, attachmentId) => (
    nativeActions.push([connectionId, attachmentId])
  );
  context.openCableGroupDetails(definition, 'g1', 'a1');
  let details = context.document.body.querySelector('.cable-group-details-popup');
  let endNode = descendants(details, (node) => (
    node.dataset.connectionId === 'a1'
      && node.className?.split(' ').includes('cable-group-details-node')
  ))[0];
  let menu = details.querySelector('.relationship-map-context-menu');
  endNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: endNode,
  });
  contextMenuBranch(menu, 'Add').children[1].children
    .find((item) => item.textContent === 'Connection').events.click();
  assert.equal(calls[0].action, 'add_cable_end_connection');
  assert.equal(calls[0].payload.connectionId, 'a1');

  const firstAttachment = {
    attachmentId: 'connection-1', name: 'Connection 1', nameOverride: '',
    targetKind: /** @type {string|null} */ (null), connected: false, metadata: [],
    visualOverrides: { mainColor: null, appearance: null, stripes: null },
  };
  const secondAttachment = {
    attachmentId: 'connection-2', name: 'Connection 2', nameOverride: '',
    targetKind: null, connected: false, metadata: [],
    visualOverrides: { mainColor: null, appearance: null, stripes: null },
  };
  connection.attachment = firstAttachment;
  connection.attachments = [firstAttachment];
  context.openCableGroupDetails(definition, 'g1', 'a1');
  details = context.document.body.querySelector('.cable-group-details-popup');
  menu = details.querySelector('.relationship-map-context-menu');
  endNode = descendants(details, (node) => node.dataset.nodeId === 'connection:a1')[0];
  endNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: endNode,
  });
  const addConnection = contextMenuBranch(menu, 'Add').children[1].children
    .find((item) => item.textContent === 'Connection');
  assert.equal(addConnection.disabled, false);
  addConnection.events.click();
  assert.equal(calls[1].action, 'add_cable_end_connection');
  assert.equal(
    context.cableGroupAttachmentContextItems(
      definition, definition.cableGroups[0], firstAttachment,
    ).some((item) => item.label === 'Materials'),
    true,
  );

  connection.attachments.push(secondAttachment);
  context.openCableGroupDetails(definition, 'g1', 'a1');
  details = context.document.body.querySelector('.cable-group-details-popup');
  const connectionNodes = descendants(details, (node) => (
    node.dataset.nodeId?.startsWith('attachment:a1:')
  ));
  assert.equal(connectionNodes.length, 2);
  let attachmentNode = connectionNodes.find(
    (node) => node.dataset.nodeId.endsWith(':connection-2'),
  );
  menu = details.querySelector('.relationship-map-context-menu');
  attachmentNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: attachmentNode,
  });
  let addAttachmentAction = contextMenuBranch(menu, 'Add');
  assert.deepEqual(
    addAttachmentAction.children[1].children.map((item) => item.textContent),
    ['Connection'],
  );
  assert.equal(addAttachmentAction.children[1].children[0].disabled, true);
  menu.children.find((item) => item.textContent === 'Connect').events.click();
  assert.deepEqual(nativeActions, [['a1', 'connection-2']]);
  assert.equal(menu.children.some((item) => item.textContent === 'Materials'), true);

  const connectedAttachment = {
    attachmentId: 'connection-2',
    name: 'J1 socket', nameOverride: '', targetKind: 'joint_origin', connected: true,
    metadata: [{ key: 'connector', value: 'J1' }],
    visualOverrides: { mainColor: null, appearance: null, stripes: null },
  };
  const openSecondAttachmentMenu = () => {
    context.openCableGroupDetails(definition, 'g1', 'a1');
    details = context.document.body.querySelector('.cable-group-details-popup');
    attachmentNode = descendants(details, (node) => (
      node.dataset.nodeId === 'attachment:a1:connection-2'
    ))[0];
    menu = details.querySelector('.relationship-map-context-menu');
    attachmentNode.events.contextmenu({
      clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: attachmentNode,
    });
    return contextMenuBranch(menu, 'Add');
  };
  connection.attachments[1] = connectedAttachment;
  addAttachmentAction = openSecondAttachmentMenu();
  const labels = descendants(attachmentNode, (node) => node.tag === 'text');
  assert.equal(labels.some((node) => node.textContent === 'J1 socket'), true);
  assert.equal(labels.some((node) => node.textContent === 'Connected'), true);
  assert.equal(attachmentNode.dataset.connected, 'true');
  assert.deepEqual(
    addAttachmentAction.children[1].children.map((item) => item.textContent),
    ['Connection', 'Refine'],
  );
  assert.equal(menu.children.find((item) => item.textContent === 'Connect').disabled, true);
  assert.equal(addAttachmentAction.children[1].children[0].disabled, true);
  addAttachmentAction.children[1].children[1].events.click();
  assert.equal(calls[2].action, 'add_connection_refine');
  assert.equal(calls[2].payload.connectionId, 'a1');
  assert.equal(calls[2].payload.attachmentId, 'connection-2');

  for (const targetKind of [
    'face', 'joint_origin', 'circular_edge', 'construction_point', 'sketch_point',
  ]) {
    connectedAttachment.targetKind = targetKind;
    addAttachmentAction = openSecondAttachmentMenu();
    assert.equal(addAttachmentAction.children[1].children[0].disabled, true, targetKind);
  }

  connectedAttachment.targetKind = 'profile';
  addAttachmentAction = openSecondAttachmentMenu();
  assert.equal(addAttachmentAction.children[1].children[0].disabled, false);
  addAttachmentAction.children[1].children[0].events.click();
  assert.equal(calls[3].action, 'add_cable_end_connection');
  assert.equal(calls[3].payload.connectionId, 'a1');
  assert.equal(calls[3].payload.parentAttachmentId, 'connection-2');

  connectedAttachment.connected = false;
  addAttachmentAction = openSecondAttachmentMenu();
  const disconnectedNode = attachmentNode;
  assert.equal(
    descendants(disconnectedNode, (node) => node.tag === 'text')
      .some((node) => node.textContent === 'Disconnected'),
    true,
  );
  assert.equal(disconnectedNode.dataset.connected, 'false');
  assert.deepEqual(
    addAttachmentAction.children[1].children.map((item) => item.textContent),
    ['Connection'],
  );
  assert.equal(menu.children.find((item) => item.textContent === 'Connect').disabled, false);
  assert.equal(addAttachmentAction.children[1].children[0].disabled, true);
  menu.children.find((item) => item.textContent === 'Rename').events.click();
  const renameDialog = context.document.body.querySelector('.connection-name-popup');
  const input = renameDialog.querySelector('input');
  assert.equal(input.placeholder, 'J1 socket');
  input.value = 'Bulkhead pin';
  renameDialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls[4].action, 'rename_cable_end_attachment');
  assert.equal(calls[4].payload.connectionId, 'a1');
  assert.equal(calls[4].payload.attachmentId, 'connection-2');
  assert.equal(calls[4].payload.name, 'Bulkhead pin');

  definition.lengthUnits = { symbol: 'cm', millimetersPerUnit: 10 };
  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  assert.equal(menu.children.at(-1).textContent, 'Properties');
  menu.children.at(-1).events.click();
  const properties = context.document.body.querySelector('.connection-properties');
  assert.equal(properties.open, true);
  const propertyFields = descendants(properties, (node) => node.tag === 'input');
  assert.equal(propertyFields.length, 16);
  assert.equal(propertyFields[0].value, '0.075');
  propertyFields[0].value = '0.06';
  propertyFields[1].checked = true;
  propertyFields[1].events.change();
  propertyFields[2].value = 'ETFE';
  assert.equal(propertyFields[5].value, 'auto');
  propertyFields[5].value = '0.04';
  propertyFields[6].checked = true;
  propertyFields[6].events.change();
  propertyFields[7].value = 'Foil';
  propertyFields[7].events.input();
  propertyFields[8].checked = true;
  propertyFields[8].events.change();
  propertyFields[9].value = 'FEP';
  propertyFields[10].checked = true;
  propertyFields[10].events.change();
  propertyFields[11].value = 'Branch maker';
  propertyFields[12].checked = true;
  propertyFields[12].events.change();
  propertyFields[13].value = 'BR-01';
  propertyFields[15].value = 'J2';
  await properties.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls.length, 6,
    descendants(properties, (node) => node.attributes.role === 'alert')[0].textContent);
  assert.equal(calls[5].action, 'set_cable_end_attachment_properties');
  assert.equal(calls[5].payload.connectionId, 'a1');
  assert.equal(calls[5].payload.attachmentId, 'connection-2');
  assert.equal(calls[5].payload.diameterMm, 0.6);
  assert.equal(calls[5].payload.conductorDiameterMm, 0.4);
  assert.equal(calls[5].payload.insulationMaterial, 'ETFE');
  assert.equal(calls[5].payload.conductorMaterial, null);
  assert.equal(calls[5].payload.shielding, 'Foil');
  assert.equal(calls[5].payload.dielectricMaterial, 'FEP');
  assert.equal(calls[5].payload.manufacturer, 'Branch maker');
  assert.equal(calls[5].payload.partNumber, 'BR-01');
  assert.equal(JSON.stringify(calls[5].payload.metadata), JSON.stringify([
    { key: 'connector', value: 'J2' },
  ]));

  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  menu.children.find((item) => item.textContent === 'Delete').events.click();
  assert.equal(calls[6].action, 'remove_cable_end_attachment');
  assert.equal(calls[6].payload.connectionId, 'a1');
  assert.equal(calls[6].payload.attachmentId, 'connection-2');

  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  menu.children.find((item) => item.textContent === 'Materials').events.click();
  const materials = context.document.body.querySelector('.material-options');
  assert.equal(materials.open, true);
  assert.equal(materials.querySelector('h2').textContent, 'Connection Materials');
});

asyncTest('shielded final connections split Connect into main and shielding targets', async () => {
  const { context, calls, definition, group, connection } = shieldingConnectionFixture();
  const leaf = {
    attachmentId: 'shielded-leaf', parentAttachmentId: null, connectionId: 'a1',
    name: 'Shielded leaf', nameOverride: '', targetKind: null, connected: false,
    shieldingTarget: null, metadata: [], visualOverrides: {},
  };
  connection.attachment = leaf;
  connection.attachments = /** @type {Array<*>} */ ([leaf]);

  const items = context.cableGroupAttachmentContextItems(definition, group, leaf);
  const connect = items.find((item) => item.label === 'Connect');

  assert.equal(
    JSON.stringify(connect.items.map((item) => item.label)),
    JSON.stringify(['Main', 'Shielding']),
  );
  await connect.items[1].action();
  assert.equal(calls[0].action, 'connect_cable_end');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.attachmentId, 'shielded-leaf');
  assert.equal(calls[0].payload.relationship, 'shielding');

  connection.attachments.push({
    attachmentId: 'child', parentAttachmentId: leaf.attachmentId, connectionId: 'a1',
    name: 'Child', nameOverride: '', targetKind: null, connected: false,
    shieldingTarget: null, metadata: [], visualOverrides: {},
  });
  const parentConnect = context.cableGroupAttachmentContextItems(
    definition, group, leaf,
  ).find((item) => item.label === 'Connect');
  assert.equal(parentConnect.items, undefined);
});

asyncTest('connection nodes disconnect main and shielding relationships independently', async () => {
  const { context, calls, definition, group, connection } = shieldingConnectionFixture();
  const node = {
    attachmentId: 'connected-node', parentAttachmentId: null, connectionId: 'a1',
    name: 'Connected node', nameOverride: '', targetKind: 'construction_point',
    connected: false, metadata: [], visualOverrides: {},
    shieldingTarget: {
      targetKind: 'construction_point', name: 'Shield stud', connected: false,
    },
  };
  connection.attachment = node;
  connection.attachments = /** @type {Array<*>} */ ([node]);

  let items = context.cableGroupAttachmentContextItems(definition, group, node);
  let disconnect = items.find((item) => item.label === 'Disconnect');
  assert.equal(
    JSON.stringify(disconnect.items.map((item) => item.label)),
    JSON.stringify(['Main', 'Shielding']),
  );
  assert.equal(disconnect.items[0].disabled, false);
  assert.equal(disconnect.items[1].disabled, false);
  await disconnect.items[1].action();
  await disconnect.items[0].action();
  assert.equal(calls[0].action, 'disconnect_cable_end_relationship');
  assert.equal(calls[0].payload.relationship, 'shielding');
  assert.equal(calls[1].payload.relationship, 'main');

  connection.attachments.push({
    attachmentId: 'child', parentAttachmentId: node.attachmentId, connectionId: 'a1',
    name: 'Child', nameOverride: '', targetKind: null, connected: false,
    shieldingTarget: null, metadata: [], visualOverrides: {},
  });
  items = context.cableGroupAttachmentContextItems(definition, group, node);
  disconnect = items.find((item) => item.label === 'Disconnect');
  assert.equal(disconnect.items[0].disabled, true);
  assert.equal(
    disconnect.items[0].title,
    'Disconnect child connection nodes before their parent profile',
  );
});

asyncTest('connection Properties place shielding above custom metadata', async () => {
  const { context, calls, definition, group, connection } = shieldingConnectionFixture();
  const node = {
    attachmentId: 'connector', parentAttachmentId: null, connectionId: 'a1',
    name: 'Connector', nameOverride: '', targetKind: null, connected: false,
    shieldingTarget: null, metadata: [], visualOverrides: {},
  };
  connection.attachment = node;
  connection.attachments = [node];

  const items = context.cableGroupAttachmentContextItems(definition, group, node);
  assert.equal(items.some((item) => item.label === 'Shielding Properties'), false);
  assert.equal(items.at(-1).label, 'Properties');
  items.at(-1).action();
  const dialog = context.document.body.querySelector('.connection-properties');
  assert.equal(dialog.querySelector('h2').textContent, 'Connection Properties');
  const fields = descendants(dialog, (item) => item.tag === 'input');
  assert.equal(fields[1].value, 'Foil');
  assert.equal(fields[1].disabled, true);
  assert.equal(fields[3].value, '');
  assert.equal(fields[3].disabled, true);
  fields[0].checked = true;
  fields[0].events.change();
  fields[1].value = '';
  fields[1].events.input();
  const dielectricLabel = descendants(
    dialog, (item) => item.textContent === 'Dielectric Material',
  )[0];
  assert.equal(dielectricLabel.parentElement.parentElement.hidden, true);
  await dialog.querySelector('form').events.submit({ preventDefault() {} });

  assert.equal(calls[0].action, 'set_cable_end_attachment_shielding');
  assert.equal(calls[0].payload.connectionId, 'a1');
  assert.equal(calls[0].payload.attachmentId, 'connector');
  assert.equal(calls[0].payload.shielding, '');
  assert.equal(calls[0].payload.dielectricMaterial, null);
  assert.equal(JSON.stringify(calls[0].payload.metadata), JSON.stringify([]));
});

test('shielding indicators distinguish connected and disconnected relationships', () => {
  const { context, definition, connection } = shieldingConnectionFixture();
  const node = {
    attachmentId: 'shielded-connector', parentAttachmentId: null, connectionId: 'a1',
    name: 'Shielded connector', nameOverride: '', targetKind: 'construction_point',
    connected: true, metadata: [], visualOverrides: {},
    shieldingTarget: {
      targetKind: 'construction_point', name: 'Shield stud', connected: true,
    },
  };
  connection.attachment = node;
  connection.attachments = [node];

  context.openCableGroupDetails(definition, 'g1', 'a1');
  let details = context.document.body.querySelector('.cable-group-details-popup');
  let rendered = descendants(details, (candidate) => (
    candidate.dataset.nodeId === 'attachment:a1:shielded-connector'
  ))[0];
  assert.equal(rendered.dataset.shielding, 'connected');
  let indicator = descendants(rendered, (candidate) => (
    candidate.className === 'connection-shielding-indicator connected'
  ))[0];
  assert.equal(indicator.attributes['aria-label'], 'Shielding connected');
  assert.equal(indicator.children[1].textContent, 'S+');

  node.shieldingTarget = null;
  context.openCableGroupDetails(definition, 'g1', 'a1');
  details = context.document.body.querySelector('.cable-group-details-popup');
  rendered = descendants(details, (candidate) => (
    candidate.dataset.nodeId === 'attachment:a1:shielded-connector'
  ))[0];
  assert.equal(rendered.dataset.shielding, 'disconnected');
  indicator = descendants(rendered, (candidate) => (
    candidate.className === 'connection-shielding-indicator disconnected'
  ))[0];
  assert.equal(indicator.attributes['aria-label'], 'Shielding disconnected');
  assert.equal(indicator.children[1].textContent, 'S−');
});

test('hovering a connection node highlights its Fusion attachment geometry', () => {
  const { context } = palette();
  const definition = harness();
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  const node = {
    attachmentId: 'connected-node', parentAttachmentId: null, connectionId: 'a1',
    name: 'Connected node', nameOverride: '', targetKind: 'profile',
    connected: true, metadata: [], visualOverrides: {}, shieldingTarget: null,
  };
  connection.attachment = node;
  connection.attachments = [node];
  const highlights = [];
  context.highlightMember = (_harness, memberType, memberId, extra) => {
    highlights.push([memberType, memberId, extra]);
  };

  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const rendered = descendants(details, (candidate) => (
    candidate.dataset.nodeId === 'attachment:a1:connected-node'
  ))[0];
  rendered.events.mouseenter();

  assert.equal(
    JSON.stringify(highlights),
    JSON.stringify([['attachment', 'connected-node', { connectionId: 'a1' }]]),
  );
});

test('Cable Details connection nodes form a parent-child chain', () => {
  const { context } = palette();
  const definition = harness();
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  connection.attachment = {
    attachmentId: 'parent', parentAttachmentId: null, name: 'Parent', nameOverride: '',
    targetKind: 'profile', connected: true, metadata: [], visualOverrides: {},
  };
  connection.attachments = [
    connection.attachment,
    {
      attachmentId: 'child', parentAttachmentId: 'parent', name: 'Child', nameOverride: '',
      targetKind: 'profile', connected: true, metadata: [], visualOverrides: {},
    },
    {
      attachmentId: 'grandchild', parentAttachmentId: 'child', name: 'Grandchild',
      nameOverride: '', targetKind: null, connected: false, metadata: [], visualOverrides: {},
    },
  ];

  const topology = context.cableGroupDetailsTopology(definition, definition.cableGroups[0]);
  const edgeIds = topology.edges.map((edge) => [edge.leftId, edge.rightId].sort().join('|'));

  assert.equal(edgeIds.includes('attachment:a1:parent|connection:a1'), true);
  assert.equal(edgeIds.includes('attachment:a1:child|attachment:a1:parent'), true);
  assert.equal(edgeIds.includes('attachment:a1:child|attachment:a1:grandchild'), true);
  assert.equal(edgeIds.includes('attachment:a1:child|connection:a1'), false);
});

test('Cable Details separates interleaved branches from multiple junctions', () => {
  const { context } = palette();
  const makeNode = (id, kind, neighbors) => ({
    id, kind, item: null, label: id, neighbors: new Set(neighbors),
  });
  const topology = {
    nodes: [
      makeNode('connection:root', 'connection', ['pathway:root']),
      makeNode('pathway:root', 'pathway', [
        'connection:root', 'junction:controller', 'junction:ground',
      ]),
      makeNode('junction:controller', 'junction', [
        'pathway:root', 'pathway:dallas', 'pathway:temp',
      ]),
      makeNode('junction:ground', 'junction', [
        'pathway:root', 'pathway:battery', 'pathway:temp', 'pathway:chassis',
      ]),
      makeNode('pathway:battery', 'pathway', ['junction:ground']),
      makeNode('pathway:chassis', 'pathway', ['junction:ground']),
      makeNode('pathway:dallas', 'pathway', ['junction:controller']),
      makeNode('pathway:temp', 'pathway', ['junction:controller', 'junction:ground']),
    ],
    edges: [
      ['connection:root', 'pathway:root'],
      ['pathway:root', 'junction:controller'],
      ['pathway:root', 'junction:ground'],
      ['junction:controller', 'pathway:dallas'],
      ['junction:controller', 'pathway:temp'],
      ['junction:ground', 'pathway:battery'],
      ['junction:ground', 'pathway:temp'],
      ['junction:ground', 'pathway:chassis'],
    ].map(([leftId, rightId]) => ({ id: `${leftId}|${rightId}`, leftId, rightId })),
  };

  const layout = context.layoutCableGroupDetailsTopology(topology, 'root');
  const row = (id) => layout.nodes.find((node) => node.id === id).row;
  const routes = context.routeCableGroupDetailsEdges(layout);
  const depths = new Map(layout.nodes.map((node) => [node.id, node.depth]));
  const initialPositions = new Map();
  [...new Set(depths.values())].forEach((depth) => {
    topology.nodes.filter((node) => depths.get(node.id) === depth)
      .sort((left, right) => left.id.localeCompare(right.id))
      .forEach((node, index) => initialPositions.set(node.id, index));
  });

  assert.ok(context.cableGroupDetailsEdgeCrossingCount(
    topology.edges, initialPositions, depths,
  ) > 0);
  assert.equal(layout.orderingScore.crossings, 0);
  const routedCrossings = routes.flatMap((route, index) => routes.slice(index + 1).map((other) => {
    if (route.start.depth !== other.start.depth
      || route.end.depth !== other.end.depth
      || route.start.id === other.start.id
      || route.end.id === other.end.id) return 0;
    return (route.startY - other.startY) * (route.endY - other.endY) < 0 ? 1 : 0;
  })).reduce((total, crossing) => total + crossing, 0);
  assert.equal(routedCrossings, 0);
  assert.ok(row('pathway:dallas') < row('pathway:temp'));
  assert.ok(row('pathway:temp') < row('pathway:battery'));
  assert.ok(row('pathway:battery') < row('pathway:chassis'));
});

test('Cable Details pathway and junction nodes share master diagram interactions', () => {
  const { context } = palette();
  const definition = harness();
  const junction = {
    junctionId: 'j1', controlId: 'cj', name: 'Branch',
    pathwayRelationships: [{ pathwayId: 'p', endpoint: 'start' }], metadata: [],
  };
  definition.junctions = [junction];
  definition.cableGroups[0].routeLegs[0].controlSteps = [{ controlId: 'cj' }];
  const actions = [];
  context.activatePathwayNode = (_harness, pathway) => (
    actions.push(['open-pathway', pathway.pathwayId])
  );
  context.activateJunctionNode = (_harness, item) => (
    actions.push(['open-junction', item.junctionId])
  );
  context.addPathwayRefine = (_harness, pathway) => (
    actions.push(['refine', pathway.pathwayId])
  );
  context.removeJunction = (_harness, item) => (
    actions.push(['delete-junction', item.junctionId])
  );
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  const node = (nodeId) => descendants(details, (candidate) => (
    candidate.className?.split(' ').includes('cable-group-details-node')
      && candidate.dataset.nodeId === nodeId
  ))[0];
  const menu = details.querySelector('.relationship-map-context-menu');
  const invokeContextMenu = (target) => target.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target,
  });

  node('pathway:p').events.click();
  node('junction:j1').events.click();
  invokeContextMenu(node('pathway:p'));
  assert.equal(menu.children[0].textContent, 'Associate');
  const addBranch = menu.children[1];
  assert.equal(addBranch.className, 'context-menu-branch');
  assert.equal(addBranch.children[0].textContent, 'Add');
  assert.deepEqual(menu.children.slice(2).map((item) => item.textContent), [
    'Segment', 'Delete', 'Properties',
  ]);
  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Refine'],
  );
  addBranch.children[1].children[0].events.click();
  invokeContextMenu(node('junction:j1'));
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Associate', 'Delete', 'Properties',
  ]);
  menu.children[1].events.click();

  assert.deepEqual(actions, [
    ['open-pathway', 'p'],
    ['open-junction', 'j1'],
    ['refine', 'p'],
    ['delete-junction', 'j1'],
  ]);
});
