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

asyncTest('Association Editor initially maps cross-side groups and links same-side groups', async () => {
  const { context, calls } = palette();
  context.send = async (action, payload) => {
    calls.push({ action, payload });
    return { ok: true };
  };
  const items = (side, ids) => ids.map((attachmentId) => ({
    attachmentId, connectionId: side, connectionName: side, label: attachmentId,
  }));
  const definition = { harnessId: 'h1', attachmentAssociations: [
    { associationId: 'left-group', attachmentIds: ['l1', 'l2'] },
    { associationId: 'right-group', attachmentIds: ['r1', 'r2'] },
    { associationId: 'cross-group', attachmentIds: ['l4', 'r3', 'hidden'] },
  ] };
  context.openConnectionAssociationPanel(
    definition, { connectionId: 'left' }, { connectionId: 'right' },
    items('left', ['l1', 'l3', 'l2', 'l4']), items('right', ['r1', 'r2', 'r3']),
    'Left', 'Right',
  );
  const dialog = context.document.body.querySelector('.connection-associations-popup');
  const poolLists = dialog.querySelectorAll('.create-association-list');
  const cards = (list) => descendants(list, (node) => node.dataset.attachmentId !== undefined);
  assert.deepEqual(cards(poolLists[0]).map((card) => card.dataset.attachmentId), ['l1', 'l2', 'l3']);
  assert.deepEqual(cards(poolLists[1]).map((card) => card.dataset.attachmentId), ['r1', 'r2']);
  for (const list of poolLists) {
    const [first, second] = cards(list);
    assert.equal(first.dataset.grouped, 'true');
    assert.equal(first.dataset.groupContinues, 'true');
    assert.equal(second.dataset.grouped, 'true');
    assert.equal(second.dataset.groupContinuation, 'true');
  }
  assert.equal(cards(poolLists[0])[2].dataset.grouped, undefined);
  const rows = dialog.querySelectorAll('.create-cables-assignment-row');
  assert.equal(rows.length, 1);
  assert.equal(rows[0].children[0].children[0].dataset.attachmentId, 'l4');
  assert.equal(rows[0].children[2].children[0].dataset.attachmentId, 'r3');

  descendants(dialog, (node) => node.tag === 'button' && node.textContent === 'Save')[0]
    .dispatchEvent({ type: 'click' });
  await Promise.resolve();
  const payload = calls.find((call) => call.action === 'save_attachment_associations').payload;
  assert.equal(payload.associations.length, 1);
  assert.equal(payload.associations[0].associationId, 'cross-group');
  assert.deepEqual([...payload.associations[0].attachmentIds], ['l4', 'r3', 'hidden']);
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

asyncTest('Cable Details divides an attachment and its owner across the cable group', async () => {
  for (const reverse of [false, true]) {
    const { context, calls } = palette();
    const definition = harness();
    const group = definition.cableGroups[0];
    group.name = 'Ground';
    group.connectionIds = ['a1', 'b1', 'a2'];
    definition.attachmentAssociations = [{
      associationId: 'ground-link', attachmentIds: ['strap-1', 'leaf-a1'],
    }];
    const owner = definition.connections.find((connection) => connection.connectionId === 'b1');
    owner.name = 'Chassis ground';
    owner.attachments = [
      { attachmentId: 'split', name: 'Gnd split 1', parentAttachmentId: null },
      { attachmentId: 'strap-1', name: 'Ground strap 1', parentAttachmentId: 'split' },
      { attachmentId: 'strap-2', name: 'Ground strap 2', parentAttachmentId: 'split' },
    ];
    owner.attachment = owner.attachments[0];
    for (const connectionId of ['a1', 'a2']) {
      const connection = definition.connections.find((item) => item.connectionId === connectionId);
      connection.attachments = [{ attachmentId: `leaf-${connectionId}`, name: connectionId }];
      connection.attachment = connection.attachments[0];
    }
    context.send = async (action, payload) => {
      calls.push({ action, payload });
      return { ok: true };
    };
    context.openCableGroupDetails(definition, 'g1', 'b1');
    const details = context.document.body.querySelector('.cable-group-details-popup');
    const nodes = details.querySelectorAll('.cable-group-details-node');
    const attachment = nodes.find((node) => node.dataset.nodeId === 'attachment:b1:split');
    const connection = nodes.find((node) => node.dataset.nodeId === 'connection:b1');
    const source = reverse ? connection : attachment;
    const target = reverse ? attachment : connection;
    source.events.contextmenu({
      target: source, clientX: 20, clientY: 20, preventDefault() {}, stopPropagation() {},
    });
    details.querySelector('.relationship-map-context-menu').children
      .find((item) => item.textContent === 'Associate').events.click();
    assert.equal(target.classList.contains('connection-association-target'), true);
    context.document.dispatchEvent({
      type: 'click', target: { closest: () => target },
      preventDefault() {}, stopPropagation() {}, stopImmediatePropagation() {},
    });
    const editor = context.document.body.querySelector('.connection-associations-popup');
    assert.equal(editor?.open, true);
    const members = ['left', 'right'].map((side) => descendants(editor, (node) => (
      node.dataset.attachmentId !== undefined && node.dataset.assignmentSide === side
    )).map((node) => node.dataset.attachmentId));
    const expected = reverse
      ? [['leaf-a1', 'leaf-a2'], ['strap-1', 'strap-2']]
      : [['strap-1', 'strap-2'], ['leaf-a1', 'leaf-a2']];
    expected.forEach((ids, index) => {
      assert.deepEqual(new Set(members[index]), new Set(ids));
    });
    const mapped = editor.querySelectorAll('.create-cables-assignment-row');
    assert.equal(mapped.length, 1);
    assert.deepEqual(
      [mapped[0].children[0].children[0].dataset.attachmentId,
        mapped[0].children[2].children[0].dataset.attachmentId],
      reverse ? ['leaf-a1', 'strap-1'] : ['strap-1', 'leaf-a1'],
    );
    await descendants(editor, (node) => node.tag === 'button' && node.textContent === 'Save')[0]
      .events.click();
    const payload = calls.find((call) => call.action === 'save_attachment_associations').payload;
    const remainder = reverse ? payload.leftAnchor : payload.rightAnchor;
    assert.equal(remainder.nodeKind, 'cableGroupRemainder');
    assert.equal(remainder.nodeId, 'g1');
    assert.equal(remainder.connectionId, 'b1');
    assert.deepEqual([...remainder.candidateAttachmentIds], ['leaf-a1', 'leaf-a2']);
    assert.equal(payload.associations[0].associationId, 'ground-link');
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
