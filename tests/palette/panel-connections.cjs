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
    targetKind: null, connected: false, metadata: [],
  };
  const secondAttachment = {
    attachmentId: 'connection-2', name: 'Connection 2', nameOverride: '',
    targetKind: null, connected: false, metadata: [],
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
  menu.children.find((item) => item.textContent === 'Connect').events.click();
  assert.deepEqual(nativeActions, [['a1', 'connection-2']]);

  const connectedAttachment = {
    attachmentId: 'connection-2',
    name: 'J1 socket', nameOverride: '', targetKind: 'joint_origin', connected: true,
    metadata: [{ key: 'connector', value: 'J1' }],
  };
  connection.attachments[1] = connectedAttachment;
  context.openCableGroupDetails(definition, 'g1', 'a1');
  details = context.document.body.querySelector('.cable-group-details-popup');
  attachmentNode = descendants(details, (node) => (
    node.dataset.nodeId === 'attachment:a1:connection-2'
  ))[0];
  const labels = descendants(attachmentNode, (node) => node.tag === 'text');
  assert.equal(labels.some((node) => node.textContent === 'J1 socket'), true);
  assert.equal(labels.some((node) => node.textContent === 'Connected'), true);
  assert.equal(attachmentNode.dataset.connected, 'true');
  menu = details.querySelector('.relationship-map-context-menu');
  attachmentNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: attachmentNode,
  });
  menu.children.find((item) => item.textContent === 'Refine').events.click();
  assert.equal(calls[2].action, 'add_connection_refine');
  assert.equal(calls[2].payload.connectionId, 'a1');
  assert.equal(calls[2].payload.attachmentId, 'connection-2');
  connectedAttachment.connected = false;
  context.openCableGroupDetails(definition, 'g1', 'a1');
  details = context.document.body.querySelector('.cable-group-details-popup');
  const disconnectedNode = descendants(details, (node) => (
    node.dataset.nodeId === 'attachment:a1:connection-2'
  ))[0];
  assert.equal(
    descendants(disconnectedNode, (node) => node.tag === 'text')
      .some((node) => node.textContent === 'Disconnected'),
    true,
  );
  assert.equal(disconnectedNode.dataset.connected, 'false');
  menu = details.querySelector('.relationship-map-context-menu');
  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  assert.equal(menu.children.some((item) => item.textContent === 'Refine'), false);
  menu.children.find((item) => item.textContent === 'Rename').events.click();
  const renameDialog = context.document.body.querySelector('.connection-name-popup');
  const input = renameDialog.querySelector('input');
  assert.equal(input.placeholder, 'J1 socket');
  input.value = 'Bulkhead pin';
  renameDialog.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls[3].action, 'rename_cable_end_attachment');
  assert.equal(calls[3].payload.connectionId, 'a1');
  assert.equal(calls[3].payload.attachmentId, 'connection-2');
  assert.equal(calls[3].payload.name, 'Bulkhead pin');

  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  assert.equal(menu.children.at(-1).textContent, 'Properties');
  menu.children.at(-1).events.click();
  const properties = context.document.body.querySelector('.connection-properties');
  assert.equal(properties.open, true);
  const metadataFields = descendants(properties, (node) => node.tag === 'input');
  assert.equal(metadataFields.length, 2);
  metadataFields[1].value = 'J2';
  await properties.querySelector('form').events.submit({ preventDefault() {} });
  assert.equal(calls[4].action, 'set_cable_end_attachment_properties');
  assert.equal(calls[4].payload.connectionId, 'a1');
  assert.equal(calls[4].payload.attachmentId, 'connection-2');
  assert.equal(JSON.stringify(calls[4].payload.metadata), JSON.stringify([
    { key: 'connector', value: 'J2' },
  ]));

  disconnectedNode.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {}, target: disconnectedNode,
  });
  menu.children.find((item) => item.textContent === 'Delete').events.click();
  assert.equal(calls[5].action, 'remove_cable_end_attachment');
  assert.equal(calls[5].payload.connectionId, 'a1');
  assert.equal(calls[5].payload.attachmentId, 'connection-2');
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
  const addBranch = menu.children[0];
  assert.equal(addBranch.className, 'context-menu-branch');
  assert.equal(addBranch.children[0].textContent, 'Add');
  assert.deepEqual(menu.children.slice(1).map((item) => item.textContent), [
    'Segment', 'Delete', 'Properties',
  ]);
  assert.deepEqual(
    addBranch.children[1].children.map((item) => item.textContent),
    ['Refine'],
  );
  addBranch.children[1].children[0].events.click();
  invokeContextMenu(node('junction:j1'));
  assert.deepEqual(menu.children.map((item) => item.textContent), [
    'Open junction configuration', 'Delete', 'Properties',
  ]);
  menu.children[1].events.click();

  assert.deepEqual(actions, [
    ['open-pathway', 'p'],
    ['open-junction', 'j1'],
    ['refine', 'p'],
    ['delete-junction', 'j1'],
  ]);
});
