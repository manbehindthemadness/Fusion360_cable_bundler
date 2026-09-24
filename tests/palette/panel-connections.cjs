/* global require */
const {
  assert, asyncTest, descendants, harness, palette, runInNewContext, test,
} = require('./support.cjs');

asyncTest('Association cards offer Details, Rename, and Delete in pools and rows', async () => {
  const { context, calls } = palette();
  const definition = harness();
  const left = ['a1', 'a2'].map((connectionId) => ({
    attachmentId: `leaf-${connectionId}`, connectionId,
    connectionName: connectionId, label: `Target ${connectionId}`,
  }));
  const right = [{
    attachmentId: 'leaf-b1', connectionId: 'b1', connectionName: 'b1', label: 'Target b1',
  }];
  definition.attachmentAssociations = [{
    associationId: 'linked', attachmentIds: ['leaf-a1', 'leaf-b1'],
  }];
  for (const item of [...left, ...right]) {
    const connection = definition.connections.find((candidate) => (
      candidate.connectionId === item.connectionId
    ));
    connection.attachments = [{
      attachmentId: item.attachmentId, name: item.label, nameOverride: '',
    }];
  }
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'rename_cable_end_attachment') context.renderEditor(definition);
    return { ok: true };
  };
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.cable-group-details-popup');
  context.openConnectionAssociationPanel(
    definition, { connectionId: 'a1' }, { connectionId: 'b1' },
    left, right, 'Left', 'Right',
  );
  const dialog = context.document.body.querySelector('.connection-associations-popup');
  const menu = dialog.querySelector('.relationship-map-context-menu');
  const card = (attachmentId) => descendants(dialog, (node) => (
    node.dataset.attachmentId === attachmentId && node.dataset.assignmentLocation
  ))[0];
  const openMenu = (element) => {
    let prevented = false;
    element.events.contextmenu({
      target: element, clientX: 20, clientY: 20,
      preventDefault() { prevented = true; }, stopPropagation() {},
    });
    assert.equal(prevented, true);
    assert.deepEqual(menu.children.map((child) => child.textContent), [
      'Details', 'Rename', 'Delete',
    ]);
    assert.equal(menu.children[0].disabled, true);
  };
  openMenu(card('leaf-a1'));
  openMenu(card('leaf-a2'));
  menu.children[1].events.click();
  const rename = context.document.body.querySelector('.connection-name-popup');
  assert.equal(rename.open, true);
  const input = rename.querySelector('input');
  assert.equal(input.placeholder, 'Target a2');
  input.value = 'Renamed terminal';
  rename.querySelector('form').events.submit({ preventDefault() {} });
  await Promise.resolve();
  assert.equal(rename.open, false);
  assert.equal(calls[0].action, 'rename_cable_end_attachment');
  assert.equal(calls[0].payload.attachmentId, 'leaf-a2');
  assert.equal(calls[0].payload.name, 'Renamed terminal');
  assert.equal(card('leaf-a2').querySelector('strong').textContent, 'Renamed terminal');
  assert.equal(dialog.open, true);
  assert.deepEqual(dialog.querySelectorAll('.create-cables-assignment-row').map((row) => (
    row.children[0].children[0]?.dataset.attachmentId
  )), ['leaf-a1']);
  assert.equal(context.document.body.querySelector('.cable-group-details-popup'), details);
  openMenu(card('leaf-b1'));
  menu.children[2].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls[1].action, 'remove_cable_end_attachment');
  assert.equal(calls[1].payload.connectionId, 'b1');
  assert.equal(calls[1].payload.attachmentId, 'leaf-b1');
  assert.equal(dialog.open, false);
});

asyncTest('Cable Details associates upstream route nodes in either selection order', async () => {
  const definition = harness();
  const group = definition.cableGroups[0];
  group.connectionIds = ['a1', 'b1', 'a2'];
  definition.pathways = ['power', 'controller', 'sensor'].map((pathwayId) => ({
    pathwayId, name: pathwayId, orderedControlIds: [], metadata: [],
  }));
  definition.junctions = [{
    junctionId: 'junction', controlId: 'junction-control', name: 'Controller junction',
    pathwayRelationships: definition.pathways.map(({ pathwayId }) => ({
      pathwayId, endpoint: pathwayId === 'power' ? 'end' : 'start',
    })),
  }];
  definition.standaloneEnds = group.connectionIds.map((connectionId, index) => ({
    connectionId, pathwayId: definition.pathways[index].pathwayId,
    endpoint: index === 0 ? 'start' : 'end', orderedControlIds: [],
  }));
  group.routeLegs = [{
    pathwayIds: definition.pathways.map(({ pathwayId }) => pathwayId),
    controlSteps: [{ controlId: 'junction-control' }],
  }];
  definition.connections.forEach((connection) => {
    connection.attachments = [{
      attachmentId: `leaf-${connection.connectionId}`, name: connection.name,
      connected: true, targetKind: 'face',
    }];
    connection.attachment = connection.attachments[0];
  });
  for (const routeId of ['pathway:power', 'junction:junction']) {
    for (const peerId of ['connection:a1', 'connection:b1', 'pathway:controller',
      routeId === 'pathway:power' ? 'junction:junction' : 'pathway:power']) {
      for (const reverse of [false, true]) {
        const { context, calls } = palette();
        context.send = async (action, payload) => {
          calls.push({ action, payload });
          return { ok: true };
        };
        context.openCableGroupDetails(definition, group.cableGroupId, 'a1');
        const details = context.document.body.querySelector('.cable-group-details-popup');
        const nodes = details.querySelectorAll('.cable-group-details-node');
        const source = nodes.find((node) => node.dataset.nodeId === (reverse ? peerId : routeId));
        const target = nodes.find((node) => node.dataset.nodeId === (reverse ? routeId : peerId));
        source.events.contextmenu({
          target: source, clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {},
        });
        const associate = details.querySelector('.relationship-map-context-menu').children
          .find((item) => item.textContent === 'Associate');
        assert.equal(associate.disabled, false);
        associate.events.click();
        assert.equal(target.classList.contains('connection-association-target'), true,
          `${source.dataset.nodeId} -> ${target.dataset.nodeId}`);
        context.document.dispatchEvent({
          type: 'click', target: { closest: () => target },
          preventDefault() {}, stopPropagation() {}, stopImmediatePropagation() {},
        });
        const editor = context.document.body.querySelector('.connection-associations-popup');
        assert.equal(editor?.open, true);
        assert.equal(context.document.events.click, undefined);
        const pools = editor.querySelectorAll('.create-cables-end-pool');
        const members = pools.map((pool) => descendants(pool, (node) => (
          node.dataset.attachmentId !== undefined
        )).map((node) => node.dataset.attachmentId));
        assert.ok(members[0].length > 0 && members[1].length > 0);
        assert.equal(members[0].some((id) => members[1].includes(id)), false);
        const expected = routeId === 'pathway:power'
          && ['connection:b1', 'pathway:controller'].includes(peerId)
          ? ['leaf-a1', 'leaf-b1'] : ['leaf-a1', 'leaf-b1', 'leaf-a2'];
        assert.deepEqual(new Set(members.flat()), new Set(expected));
        await descendants(editor, (node) => node.tag === 'button' && node.textContent === 'Save')[0]
          .events.click();
        const payload = calls.find((call) => call.action === 'save_attachment_associations').payload;
        [payload.leftAnchor, payload.rightAnchor].forEach((anchor, index) => {
          if (anchor.nodeKind) {
            assert.deepEqual(new Set(anchor.candidateAttachmentIds), new Set(members[index]));
          }
        });
      }
    }
  }
});

asyncTest('Association Editor extends one pair to three and five members by dropping on either card', async () => {
  const { context, calls } = palette();
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  const left = ['l1', 'l2', 'l3'].map((attachmentId) => ({
    attachmentId, connectionId: 'left', connectionName: 'Left', label: attachmentId,
  }));
  const right = ['r1', 'r2'].map((attachmentId) => ({
    attachmentId, connectionId: 'right', connectionName: 'Right', label: attachmentId,
  }));
  const open = runInNewContext('openConnectionAssociationPanel', context);
  open(
    { harnessId: 'h1', attachmentAssociations: [
      { associationId: 'existing', attachmentIds: ['l1', 'r1'] },
    ] },
    { connectionId: 'left' }, { connectionId: 'right' },
    left, right, 'Left', 'Right',
  );
  const dialog = context.document.body.querySelector('.connection-associations-popup');

  const dropOn = (attachmentId, targetId) => {
    const source = descendants(dialog, (element) => element.dataset.attachmentId === attachmentId
      && element.dataset.assignmentLocation === 'pool')[0];
    const target = descendants(dialog, (element) => element.dataset.attachmentId === targetId
      && element.dataset.assignmentLocation === 'row')[0];
    if (targetId.startsWith('r')) target.style.left = '150';
    const bounds = target.getBoundingClientRect();
    const clientX = bounds.left + bounds.width / 2;
    const clientY = bounds.top + bounds.height / 2;
    source.setPointerCapture = () => {};
    source.hasPointerCapture = () => false;
    source.dispatchEvent({
      type: 'pointerdown', button: 0, pointerId: 1, target: { closest: () => null },
      clientX: 0, clientY: 0,
    });
    source.dispatchEvent({
      type: 'pointermove', pointerId: 1, clientX, clientY, preventDefault() {},
    });
    source.dispatchEvent({ type: 'pointerup', pointerId: 1 });
  };

  dropOn('l2', 'r1');
  let rows = dialog.querySelectorAll('.create-cables-assignment-row');
  assert.equal(rows.length, 2);
  assert.equal(rows[1].children[2].children.length, 0);
  assert.equal(rows[1].dataset.grouped, 'true');
  assert.equal(rows[0].dataset.groupContinues, 'true');
  assert.equal(rows[1].dataset.groupContinuation, 'true');
  assert.equal(rows[1].dataset.groupSingleSide, 'left');

  dropOn('r2', 'l1');
  dropOn('l3', 'r1');
  rows = dialog.querySelectorAll('.create-cables-assignment-row');
  assert.equal(rows.length, 3);
  assert.equal(rows[2].children[2].children.length, 0);
  assert.equal(rows[1].dataset.groupContinues, 'true');
  assert.equal(rows[2].dataset.groupSingleSide, 'left');

  const save = descendants(dialog, (element) => element.tag === 'button'
    && element.textContent === 'Save')[0];
  save.dispatchEvent({ type: 'click' });
  await Promise.resolve();
  const payload = calls.find((call) => call.action === 'save_attachment_associations').payload;
  assert.equal(payload.associations.length, 1);
  assert.equal(payload.associations[0].associationId, 'existing');
  assert.deepEqual([...payload.associations[0].attachmentIds], ['l1', 'r1', 'l2', 'r2', 'l3']);
});

test('Association Editor joins complete center pairs under one identity', () => {
  const { context } = palette();
  const initial = runInNewContext('initialConnectionAssociationAssignments', context);
  const join = runInNewContext('joinConnectionAssociationGroups', context);
  const left = ['l1', 'l2'].map((attachmentId) => ({ attachmentId }));
  const right = ['r1', 'r2'].map((attachmentId) => ({ attachmentId }));
  const assignments = initial({ attachmentAssociations: [
    { associationId: 'first', attachmentIds: ['l1', 'r1'] },
    { associationId: 'second', attachmentIds: ['l2', 'r2'] },
  ] }, left, right);

  join(assignments, 1, 0);

  assert.equal(assignments.rows.length, 2);
  assert.equal(assignments.rows[0].groupId, 'first');
  assert.equal(assignments.rows[1].groupId, 'first');
  assert.deepEqual(
    [...assignments.rows.flatMap((row) => [row.left.connectionId, row.right.connectionId])],
    ['l1', 'r1', 'l2', 'r2'],
  );
});

asyncTest('Association Editor merges associations brought in from elsewhere', async () => {
  const { context, calls } = palette();
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  const items = (side) => ['1', '2'].map((suffix) => ({
    attachmentId: `${side}${suffix}`, connectionId: side,
    connectionName: side, label: `${side}${suffix}`,
  }));
  runInNewContext('openConnectionAssociationPanel', context)(
    { harnessId: 'h1', attachmentAssociations: [
      { associationId: 'center', attachmentIds: ['l2', 'r2'] },
      { associationId: 'elsewhere-left', attachmentIds: ['l1', 'hidden-left'] },
      { associationId: 'elsewhere-right', attachmentIds: ['r1', 'hidden-right'] },
    ] },
    { connectionId: 'l' }, { connectionId: 'r' },
    items('l'), items('r'), 'Left', 'Right',
  );
  const dialog = context.document.body.querySelector('.connection-associations-popup');
  const dragOnto = (attachmentId, targetId) => {
    const source = descendants(dialog, (element) => element.dataset.attachmentId === attachmentId
      && element.dataset.assignmentLocation === 'pool')[0];
    const target = descendants(dialog, (element) => element.dataset.attachmentId === targetId
      && element.dataset.assignmentLocation === 'row')[0];
    assert.equal(source.children[1].textContent.includes('Associated elsewhere'), true);
    if (targetId.startsWith('r')) target.style.left = '150';
    const bounds = target.getBoundingClientRect();
    source.setPointerCapture = () => {};
    source.hasPointerCapture = () => false;
    source.dispatchEvent({
      type: 'pointerdown', button: 0, pointerId: 1, target: { closest: () => null },
      clientX: 0, clientY: 0,
    });
    source.dispatchEvent({
      type: 'pointermove', pointerId: 1,
      clientX: bounds.left + bounds.width / 2,
      clientY: bounds.top + bounds.height / 2,
      preventDefault() {},
    });
    source.dispatchEvent({ type: 'pointerup', pointerId: 1 });
  };

  dragOnto('l1', 'r2');
  dragOnto('r1', 'l2');
  const rows = dialog.querySelectorAll('.create-cables-assignment-row');
  assert.equal(rows.length, 3);
  assert.equal(descendants(dialog, (element) => element.dataset.assignmentLocation === 'pool'
    && ['l1', 'r1'].includes(element.dataset.attachmentId)).length, 0);

  const save = descendants(dialog, (element) => element.tag === 'button'
    && element.textContent === 'Save')[0];
  save.dispatchEvent({ type: 'click' });
  await Promise.resolve();
  const payload = calls.find((call) => call.action === 'save_attachment_associations').payload;
  assert.equal(payload.associations.length, 1);
  assert.equal(payload.associations[0].associationId, 'center');
  assert.deepEqual(new Set(payload.associations[0].attachmentIds),
    new Set(['l1', 'l2', 'r1', 'r2', 'hidden-left', 'hidden-right']));
});

test('Association Editor can return an imported outside group to its pool', () => {
  const { context } = palette();
  const initial = runInNewContext('initialConnectionAssociationAssignments', context);
  const assign = runInNewContext('assignConnectionAssociationItem', context);
  const unassign = runInNewContext('unassignConnectionAssociationItem', context);
  const assignments = initial({ attachmentAssociations: [
    { associationId: 'center', attachmentIds: ['l2', 'r2'] },
    { associationId: 'elsewhere', attachmentIds: ['l1', 'hidden'] },
  ] }, [{ attachmentId: 'l1' }, { attachmentId: 'l2' }], [{ attachmentId: 'r2' }]);

  assign(assignments, 'left', 'l1', { location: 'extend', rowIndex: 0 });
  assert.equal(assignments.rows.length, 2);
  assert.equal(assignments.groupSources.get('center').has('elsewhere'), true);

  unassign(assignments, 'left', 1, 0);
  assert.equal(assignments.rows.length, 1);
  assert.deepEqual([...assignments.pools.left], ['l1']);
  assert.equal(assignments.groupSources.get('center').has('elsewhere'), false);
});

test('Association Editor moves all visible members of an outside group into an empty center', () => {
  const { context } = palette();
  const initial = runInNewContext('initialConnectionAssociationAssignments', context);
  const assign = runInNewContext('assignConnectionAssociationItem', context);
  const assignments = initial({ attachmentAssociations: [
    { associationId: 'elsewhere', attachmentIds: ['l1', 'l2', 'hidden'] },
  ] }, [{ attachmentId: 'l1' }, { attachmentId: 'l2' }], [{ attachmentId: 'r1' }]);

  assign(assignments, 'left', 'l2', { location: 'center', rowIndex: 0 });

  assert.equal(assignments.rows.length, 2);
  assert.deepEqual([...assignments.rows.map((row) => row.left.connectionId)], ['l1', 'l2']);
  assert.equal(assignments.rows.every((row) => row.groupId === 'elsewhere'), true);
  assert.equal(assignments.pools.left.length, 0);
});

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

test('Cable Details badges only terminal physical connection nodes', () => {
  const { context } = palette();
  const definition = harness();
  const connection = definition.connections.find((item) => item.connectionId === 'a1');
  const parent = {
    attachmentId: 'profile', name: 'Profile', parentAttachmentId: null,
    targetKind: 'profile', connected: true, visualOverrides: {},
  };
  const child = {
    attachmentId: 'terminal', name: 'Terminal', parentAttachmentId: 'profile',
    targetKind: 'joint_origin', connected: true, visualOverrides: {},
  };
  connection.attachment = parent;
  connection.attachments = [parent, child];

  context.openCableGroupDetails(definition, 'g1', 'a1');

  const dialog = context.document.body.querySelector('.cable-group-details-popup');
  const profileNode = descendants(dialog, (element) => (
    element.dataset.nodeId === 'attachment:a1:profile'
  ))[0];
  const terminalNode = descendants(dialog, (element) => (
    element.dataset.nodeId === 'attachment:a1:terminal'
  ))[0];
  assert.equal(profileNode.dataset.physicalConnection, 'false');
  assert.equal(terminalNode.dataset.physicalConnection, 'true');
  assert.equal(descendants(profileNode, (element) => (
    element.className?.split(' ').includes('connection-physical-indicator')
  )).length, 0);
  const badges = descendants(terminalNode, (element) => (
    element.className?.split(' ').includes('connection-physical-indicator')
  ));
  assert.equal(badges.length, 1);
  assert.equal(badges[0].className.split(' ').includes('connected'), true);
  assert.equal(descendants(badges[0], (element) => element.tag === 'path').length, 3);
  assert.equal(descendants(badges[0], (element) => element.tag === 'text').length, 0);

  child.connected = false;
  context.openCableGroupDetails(definition, 'g1', 'a1');
  const refreshed = context.document.body.querySelector('.cable-group-details-popup');
  const disconnected = descendants(refreshed, (element) => (
    element.dataset.nodeId === 'attachment:a1:terminal'
  ))[0];
  const outline = descendants(disconnected, (element) => (
    element.className?.split(' ').includes('connection-physical-indicator')
  ))[0];
  assert.equal(outline.className.split(' ').includes('disconnected'), true);
});

test('Cable Details gives associated terminal nodes matching numbered color badges', () => {
  const { context } = palette();
  const definition = harness();
  const left = definition.connections.find((item) => item.connectionId === 'a1');
  const right = definition.connections.find((item) => item.connectionId === 'b1');
  const attachment = (attachmentId, parentAttachmentId = null) => ({
    attachmentId, name: attachmentId, parentAttachmentId,
    targetKind: 'profile', connected: true, visualOverrides: {},
  });
  left.attachments = [
    attachment('parent'), attachment('left-a', 'parent'), attachment('left-b', 'parent'),
  ];
  left.attachment = left.attachments[0];
  right.attachments = [
    attachment('right-a'), attachment('right-b'),
    attachment('right-extra'), attachment('unassociated'),
  ];
  right.attachment = right.attachments[0];
  definition.attachmentAssociations = [
    { associationId: 'group-b', attachmentIds: ['left-b', 'right-b'] },
    { associationId: 'group-a', attachmentIds: ['left-a', 'right-a', 'right-extra'] },
  ];

  context.openCableGroupDetails(definition, 'g1', 'a1');

  const dialog = context.document.body.querySelector('.cable-group-details-popup');
  const node = (connectionId, attachmentId) => descendants(dialog, (element) => (
    element.dataset.nodeId === `attachment:${connectionId}:${attachmentId}`
  ))[0];
  const badge = (connectionId, attachmentId) => descendants(
    node(connectionId, attachmentId),
    (element) => element.className === 'connection-association-indicator',
  )[0];
  const firstLeft = badge('a1', 'left-a');
  const firstRight = badge('b1', 'right-a');
  const firstExtra = badge('b1', 'right-extra');
  const secondLeft = badge('a1', 'left-b');
  const secondRight = badge('b1', 'right-b');
  assert.equal(firstLeft.dataset.groupNumber, '1');
  assert.equal(firstRight.dataset.groupNumber, '1');
  assert.equal(firstLeft.dataset.associationId, 'group-a');
  assert.equal(firstLeft.children[0].attributes.fill, firstRight.children[0].attributes.fill);
  assert.equal(firstExtra.dataset.groupNumber, '1');
  assert.equal(firstExtra.children[0].attributes.fill, firstLeft.children[0].attributes.fill);
  assert.equal(secondLeft.dataset.groupNumber, '2');
  assert.equal(secondRight.dataset.groupNumber, '2');
  assert.equal(secondLeft.children[0].attributes.fill, secondRight.children[0].attributes.fill);
  assert.notEqual(firstLeft.children[0].attributes.fill, secondLeft.children[0].attributes.fill);
  assert.equal(badge('a1', 'parent'), undefined);
  assert.equal(badge('b1', 'unassociated'), undefined);
});

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
