/* global require, __dirname */
const {
  Element, assert, descendants, harness, join, palette, readFileSync, test,
} = require('./support.cjs');

/** Return a branching topology with three full-width pathways at its root depth. */
function branchingHarness() {
  const definition = harness();
  definition.pathways.push(
    { pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Pathway 003', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p4', name: 'Pathway 004', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p5', name: 'Pathway 005', startName: 'A', endName: 'B',
      orderedControlIds: [] },
  );
  definition.junctions.push(
    {
      junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
      pathwayRelationships: [
        { pathwayId: 'p', endpoint: 'end' },
        { pathwayId: 'p2', endpoint: 'end' },
        { pathwayId: 'p3', endpoint: 'end' },
        { pathwayId: 'p4', endpoint: 'start' },
      ],
    },
    {
      junctionId: 'j2', controlId: 'c2', name: 'Junction 002',
      pathwayRelationships: [
        { pathwayId: 'p4', endpoint: 'end' },
        { pathwayId: 'p5', endpoint: 'start' },
      ],
    },
  );
  return definition;
}

/** Give topology wrappers dimensions representative of their rendered cards. */
function sizeRelationshipNodes(diagram) {
  descendants(
    diagram, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).forEach((node) => {
    const pathway = node.className.split(' ').includes('relationship-topology-pathway');
    node.scrollWidth = pathway ? 638 : 154;
    node.scrollHeight = pathway ? 160 : 76;
  });
}

/** Return the positioned rectangle recorded by the topology layout. */
function relationshipNodeRectangle(node) {
  const left = Number.parseFloat(node.style.left);
  const top = Number.parseFloat(node.style.top);
  const width = Number.parseFloat(node.style.width);
  const height = Number.parseFloat(node.style.height);
  return { left, top, right: left + width, bottom: top + height };
}

/** Return whether two positioned topology nodes overlap. */
function relationshipNodesOverlap(first, second) {
  const left = relationshipNodeRectangle(first);
  const right = relationshipNodeRectangle(second);
  return left.left < right.right && left.right > right.left
    && left.top < right.bottom && left.bottom > right.top;
}

/** Return the shared master-diagram elements used by organization regressions. */
function relationshipWorkspaceParts(diagram) {
  const workspace = descendants(
    diagram, (node) => node.className === 'block-diagram-workspace',
  )[0];
  return {
    workspace,
    toolbar: descendants(
      workspace, (node) => node.className === 'block-diagram-toolbar',
    )[0],
    viewport: descendants(
      workspace, (node) => node.className === 'block-diagram-viewport',
    )[0],
    stack: descendants(
      workspace, (node) => node.className === 'relationship-pathway-stack',
    )[0],
  };
}

test('group-only palette state drives pathway occupancy', () => {
  const { context } = palette();
  const definition = harness();

  assert.equal(definition.schemaVersion, 14);
  assert.equal(Object.hasOwn(definition, 'wires'), false);
  assert.equal(Object.hasOwn(definition, 'profiles'), false);
  assert.deepEqual(
    Array.from(context.relationshipPathwayGroups(definition, 'p'), (group) => group.wireGroupId),
    ['g1', 'g2', 'g3'],
  );
});

test('group-only palette resolves standalone ends to their groups', () => {
  const { context } = palette();
  const definition = harness();
  const connections = new Map(
    definition.connections.map((connection) => [connection.connectionId, connection]),
  );

  const ends = context.relationshipEndGroups(definition, 'p', 'start', connections);

  assert.deepEqual(Array.from(ends, (end) => end.wireGroupId), ['g1', 'g2', 'g3']);
  assert.ok(ends.every((end) => end.groups.length === 1));
});

test('master diagram survives a host refresh that adds a pathway', () => {
  const { context } = palette();
  const definition = harness();

  context.renderEditor(definition);
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).length, 1);

  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  context.renderEditor(definition);

  assert.equal(context.ui.editor.children.length, 1);
  assert.equal(context.ui.editor.children[0].dataset.section, 'master-relationship-graphic');
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).length, 2);
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className === 'relationship-topology-edges',
  ).length, 1);
});

test('master diagram can redraw and fit for its resized viewport', () => {
  const { context } = palette();
  const definition = branchingHarness();

  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { workspace, toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);
  const redraw = toolbar.children[0];

  assert.equal(redraw.textContent, 'Redraw');
  assert.equal(redraw.title, 'Redraw and fit diagram');
  assert.equal(redraw.attributes['aria-label'], 'Redraw and fit diagram');
  const initialRevision = Number(stack.dataset.diagramLayoutRevision);
  assert.ok(initialRevision > 0);
  viewport.clientWidth = 900;
  viewport.clientHeight = 1600;
  redraw.events.click();

  assert.equal(Number(stack.dataset.diagramLayoutRevision), initialRevision + 1);
  assert.equal(stack.dataset.diagramLayoutError, undefined);
  assert.ok([0, 1, 2, 3].includes(Number(stack.dataset.diagramRotation)));
  assert.ok(stack.dataset.diagramLayoutKey.split('|').length >= 3);
  assert.ok(Number.parseFloat(stack.style.width) > 0);
  assert.ok(Number.parseFloat(stack.style.height) > 0);
  viewport.clientWidth = 2200;
  viewport.clientHeight = 500;
  redraw.events.click();
  const rootPathways = ['p', 'p2', 'p3'].map((pathwayId) => descendants(
    stack, (node) => node.className?.split(' ').includes('relationship-topology-node')
      && node.dataset.nodeId === `pathway:${pathwayId}`,
  )[0]);
  assert.ok(new Set(rootPathways.map((node) => node.style.top)).size >= 2);
  const firstJunction = descendants(
    stack, (node) => node.className?.split(' ').includes('relationship-topology-node')
      && node.dataset.nodeId === 'junction:j1',
  )[0];
  assert.ok(rootPathways.every((node) => node.style.left && node.style.top));
  assert.ok(firstJunction.style.left && firstJunction.style.top);
  const organizedTransform = workspace.children[1].children[0].style.transform;
  assert.match(organizedTransform, /scale\(/);

  context.renderEditor(definition);
  const refreshedStack = descendants(
    context.ui.editor, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  const refreshedStage = descendants(
    context.ui.editor, (node) => node.className === 'block-diagram-stage',
  )[0];
  assert.equal(refreshedStack.dataset.diagramRotation, stack.dataset.diagramRotation);
  assert.equal(refreshedStack.dataset.diagramLayoutKey, stack.dataset.diagramLayoutKey);
  assert.equal(refreshedStage.style.transform, organizedTransform);
});

test('disconnected component packing remains compact and deterministic', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);
  const geometry = () => ({
    canvas: [stack.style.width, stack.style.height, stack.dataset.diagramRotation],
    nodes: descendants(
      stack, (node) => node.className?.split(' ').includes('relationship-topology-node'),
    ).map((node) => [node.dataset.nodeId, node.style.left, node.style.top]),
  });

  viewport.clientWidth = 1800;
  viewport.clientHeight = 420;
  toolbar.children[0].events.click();
  const wide = geometry();
  toolbar.children[0].events.click();
  assert.deepEqual(geometry(), wide);
  viewport.clientWidth = 420;
  viewport.clientHeight = 1800;
  toolbar.children[0].events.click();
  const tall = geometry();
  toolbar.children[0].events.click();
  assert.deepEqual(geometry(), tall);
  descendants(
    stack, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).forEach((node, index, nodes) => nodes.slice(index + 1).forEach((other) => {
    assert.equal(relationshipNodesOverlap(node, other), false);
  }));
});

test('master diagram cycles deterministic compact layouts and wraps', () => {
  const { context } = palette();
  const definition = branchingHarness();
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { toolbar, stack } = relationshipWorkspaceParts(diagram);

  const layoutKey = stack.dataset.diagramLayoutKey;
  const candidateCount = Number(stack.dataset.diagramLayoutCandidateCount);
  assert.ok(candidateCount >= 1);
  toolbar.children[0].events.click();
  if (candidateCount > 1) assert.notEqual(stack.dataset.diagramLayoutKey, layoutKey);
  for (let index = 1; index < candidateCount; index += 1) {
    toolbar.children[0].events.click();
  }
  assert.equal(stack.dataset.diagramLayoutKey, layoutKey);
});

test('route-aware redraw packs branching topology without trace blips or crossovers', () => {
  const { context } = palette();
  const definition = branchingHarness();
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);
  viewport.clientWidth = 1900;
  viewport.clientHeight = 850;
  toolbar.children[0].events.click();

  const routes = descendants(
    stack, (node) => node.className === 'structural-trace',
  ).map((path) => ({
    points: JSON.parse(path.dataset.routePoints),
    traceHalfExtent: context.topologyTraceHalfExtent(
      Number(path.parentElement.dataset.wireGroupCount),
    ),
  }));
  const quality = context.topologyRouteSetQuality(new Map(
    routes.map((route, index) => [`route-${index}`, route]),
  ));

  assert.equal(routes.length, 6);
  assert.equal(Number(stack.dataset.diagramLayoutRevision), 2);
  assert.equal(stack.dataset.diagramLayoutError, undefined);
  assert.equal(quality.overlaps, 0);
  assert.equal(quality.parallelConflicts, 0);
  assert.ok(quality.minimumParallelGap >= 10);
  assert.equal(quality.crossings, 0);
  assert.equal(quality.shortSegments, 0);
  assert.ok(Number.parseFloat(stack.style.width) / Number.parseFloat(stack.style.height) > 0.7);
  assert.ok(stack.dataset.diagramLayoutKey.includes('|'));
  assert.ok(Number(stack.dataset.minimumParallelTraceGap) >= 10);
  assert.equal(stack.dataset.overlappingTracePairCount, '0');
});

test('layout search widens when every compact routing candidate fails', () => {
  const { context } = palette();
  let attempts = 0;
  const layouts = Array.from({ length: 30 }, (_unused, index) => index);
  const candidates = context.routeRelationshipLayoutPool(layouts, (layout) => {
    attempts += 1;
    return layout < 24 ? null : layout;
  }, 24);

  assert.equal(attempts, 30);
  assert.equal(JSON.stringify(candidates), JSON.stringify([24, 25, 26, 27, 28, 29]));
});

test('failed layout attempts can restore the last committed node geometry', () => {
  const { context } = palette();
  const stack = new Element('div');
  const element = new Element('div');
  const node = {
    id: 'junction:j1', kind: 'junction', element,
    width: 154, height: 92, left: 40, top: 60,
    hubCenter: { x: 117, y: 106 }, dockPoints: null, dockSides: null,
  };
  Object.assign(element.style, {
    left: '40px', top: '60px', width: '154px', height: '92px',
  });
  stack.style.width = '400px';
  stack.style.height = '300px';
  stack.dataset.diagramLayoutRevision = '3';
  const state = context.captureRelationshipLayoutState(
    stack, [{ nodes: [node] }],
  );

  node.left = 900;
  element.style.left = '900px';
  stack.style.width = '1200px';
  stack.dataset.diagramLayoutRevision = '4';
  context.restoreRelationshipLayoutState(stack, state);

  assert.equal(node.left, 40);
  assert.equal(element.style.left, '40px');
  assert.equal(stack.style.width, '400px');
  assert.equal(stack.dataset.diagramLayoutRevision, '3');
});

test('layout freezes minimum junction size and QA checks visible descendant bounds', () => {
  const { context } = palette();
  const junctionElement = new Element('div');
  junctionElement.scrollWidth = 120;
  junctionElement.scrollHeight = 24;
  const junction = { kind: 'junction', element: junctionElement };
  context.captureRelationshipIntrinsicSizes([{ nodes: [junction] }]);
  junctionElement.scrollWidth = 900;
  junctionElement.scrollHeight = 900;
  const frozenSize = context.relationshipNodeDimensions(junction);
  assert.equal(frozenSize.width, 154);
  assert.equal(frozenSize.height, 92);

  const first = new Element('div');
  first.style.width = '100px';
  first.style.height = '100px';
  const overflowingList = new Element('div');
  overflowingList.className = 'relationship-end-list';
  overflowingList.style.left = '80px';
  overflowingList.style.width = '40px';
  overflowingList.style.height = '40px';
  first.append(overflowingList);
  const second = new Element('div');
  second.style.left = '110px';
  second.style.width = '100px';
  second.style.height = '100px';

  assert.equal(context.qaRelationshipVisualOverlapCount([first, second]), 1);
  assert.equal(context.qaRelationshipVisibleOverflowCount([first, second]), 1);
});

test('parallel route quality includes visible trace envelopes', () => {
  const { context } = palette();
  const route = (y) => ({
    points: [{ x: 0, y }, { x: 100, y }], traceHalfExtent: 4.5,
  });
  const crowded = context.topologyRouteSetQuality(new Map([
    ['first', route(0)], ['second', route(18)],
  ]));
  const separated = context.topologyRouteSetQuality(new Map([
    ['first', route(0)], ['second', route(19)],
  ]));

  assert.equal(crowded.minimumParallelGap, 9);
  assert.equal(crowded.parallelConflicts, 1);
  assert.equal(separated.minimumParallelGap, 10);
  assert.equal(separated.parallelConflicts, 0);
});

test('populated topology edges suppress their structural centerline', () => {
  const styles = readFileSync(join(__dirname, '../../palette/styles.css'), 'utf8');

  assert.match(styles, /not\(\[data-render-mode="structure"]\) \.structural-trace/);
  assert.match(styles, /stroke: none/);
});

test('route simplification removes duplicate, reversal, and clear dogleg points', () => {
  const { context } = palette();
  const points = context.simplifyTopologyDoglegs([
    { x: 0, y: 0 }, { x: 0, y: 0 }, { x: 20, y: 0 },
    { x: 20, y: 8 }, { x: 40, y: 8 }, { x: 40, y: 0 }, { x: 60, y: 0 },
  ], []);

  assert.equal(JSON.stringify(points), JSON.stringify([{ x: 0, y: 0 }, { x: 60, y: 0 }]));
});

test('master relationship traces attach to distinct cardinal pathway ends', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });
  definition.junctions.push({
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
    pathwayRelationships: [
      { pathwayId: 'p', endpoint: 'end' },
      { pathwayId: 'p2', endpoint: 'start' },
    ],
  });
  definition.wireGroups.forEach((group) => {
    group.routeLegs[0].controlSteps = [{ controlId: 'c1' }];
  });
  definition.wireGroups.push(...[4, 5].map((index) => ({
    ...definition.wireGroups[0],
    wireGroupId: `g${index}`,
    connectionIds: [`extra-a${index}`, `extra-b${index}`],
    routeLegs: [{
      routeId: `r${index}`, label: `Group ${index} Leg 1`,
      startConnectionId: `extra-a${index}`, endConnectionId: `extra-b${index}`,
      pathwayIds: ['p'], controlSteps: [{ controlId: 'c1' }],
    }],
  })));

  const diagram = context.renderRelationshipMap(definition);
  const ports = descendants(
    diagram, (node) => node.className === 'relationship-topology-port',
  );
  const pathwayPorts = ports.filter((port) => port.dataset.nodeId.startsWith('pathway:'));

  pathwayPorts.forEach((port) => {
    const node = descendants(
      diagram, (candidate) => candidate.className?.split(' ').includes(
        'relationship-topology-node',
      ) && candidate.dataset.nodeId === port.dataset.nodeId,
    )[0];
    const pathwayGroup = node.children[0];
    const endpoint = port.dataset.portId.split(':')[2];
    assert.equal(port.dataset.side, endpoint === 'start'
      ? pathwayGroup.dataset.startSide : pathwayGroup.dataset.endSide);
    assert.notEqual(pathwayGroup.dataset.startSide, pathwayGroup.dataset.endSide);
  });
  const fiveLaneEdge = descendants(
    diagram, (node) => node.className === 'relationship-topology-edge'
      && node.dataset.wireGroupCount === '5',
  )[0];
  const fiveLanePort = pathwayPorts.find((port) => port.dataset.nodeId === 'pathway:p');
  assert.equal(fiveLaneEdge.dataset.renderMode, 'lanes');
  assert.equal(descendants(
    fiveLaneEdge, (node) => node.className === 'wire-trace relationship-wire-lane',
  ).length, 5);
  assert.ok(Number(fiveLanePort.attributes.width) >= 24);
});

test('inset endpoint ports retain visible anchors and escape beyond their node', () => {
  const { context } = palette();
  const wrapper = new Element('div');
  const group = new Element('div');
  const startList = new Element('details');
  const endList = new Element('details');
  wrapper.style.left = '100px';
  wrapper.style.top = '80px';
  wrapper.style.width = '300px';
  wrapper.style.height = '200px';
  startList.style.left = '40px';
  group.relationshipEndpointLists = { start: startList, end: endList };
  group.append(startList, endList);
  wrapper.append(group);
  const node = {
    id: 'pathway:p', element: wrapper, left: 100, top: 80, width: 300, height: 200,
    dockSides: { start: 'left', end: 'right' },
  };
  const measured = context.relationshipRenderedDockPoint(
    node, 'start', { docks: { start: { x: 0, y: 100 } } },
  );

  assert.equal(measured.x, 140);
  assert.notEqual(measured.x, node.left);
  [
    ['left', { x: 140, y: 150 }, { x: 68, y: 150 }],
    ['right', { x: 360, y: 150 }, { x: 432, y: 150 }],
    ['top', { x: 250, y: 110 }, { x: 250, y: 48 }],
    ['bottom', { x: 250, y: 240 }, { x: 250, y: 312 }],
  ].forEach(([side, point, expected]) => {
    const escape = context.topologyPortEscape({ side, point }, node);
    assert.equal(escape.x, expected.x);
    assert.equal(escape.y, expected.y);
  });
});

test('layered docking aligns sibling pathway ends toward their junction', () => {
  const { context } = palette();
  assert.equal(context.relationshipNodeDimensions({
    kind: 'junction', element: { scrollWidth: 0, scrollHeight: 0 },
  }).height, 92);
  const definition = harness();
  definition.pathways.push(...[2, 3, 4].map((index) => ({
    pathwayId: `p${index}`, name: `Pathway ${index}`, startName: 'A', endName: 'B',
    orderedControlIds: [],
  })));
  definition.junctions.push({
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
    pathwayRelationships: ['p', 'p2', 'p3', 'p4'].map((pathwayId) => ({
      pathwayId, endpoint: 'start',
    })),
  });

  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const toolbar = descendants(
    diagram, (node) => node.className === 'block-diagram-toolbar',
  )[0];
  toolbar.children[0].events.click();
  const connectedPorts = descendants(
    diagram, (node) => node.className === 'relationship-topology-port'
      && node.dataset.nodeId.startsWith('pathway:'),
  );

  assert.deepEqual(
    [...new Set(connectedPorts.map((port) => port.dataset.side))].sort(),
    ['left'],
  );
  descendants(
    diagram, (node) => node.className === 'relationship-pathway-group',
  ).forEach((group) => {
    assert.notEqual(group.dataset.startSide, group.dataset.endSide);
    ['start', 'end'].forEach((endpoint) => {
      const side = endpoint === 'start' ? group.dataset.startSide : group.dataset.endSide;
      const list = group.relationshipEndpointLists[endpoint];
      const connector = group.relationshipConnectors[endpoint];
      assert.equal(connector.dataset.side, side);
      if (['left', 'right'].includes(side)) {
        assert.ok(Number.parseFloat(connector.style.marginLeft) <= -1);
        assert.equal(list.style.justifySelf, side === 'left' ? 'end' : 'start');
        assert.equal(
          group.relationshipDockMetrics.columns[side === 'left' ? 1 : 3],
          32,
        );
      } else {
        assert.ok(Number.parseFloat(connector.style.marginTop) <= -1);
        assert.ok(['center', 'stretch'].includes(list.style.justifySelf));
        assert.equal(
          group.relationshipDockMetrics.rows[side === 'top' ? 1 : 3],
          32,
        );
      }
    });
  });
  const emptyMetrics = descendants(
    diagram, (node) => node.className === 'relationship-pathway-group'
      && node.dataset.pathwayId === 'p2',
  )[0].relationshipDockMetrics;
  assert.ok(emptyMetrics.sizes.start.width < 210);
  assert.ok(emptyMetrics.sizes.end.width < 210);
  const nodes = descendants(
    diagram, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  );
  let compactUnrelatedPair = false;
  nodes.forEach((node, index) => nodes.slice(index + 1).forEach((other) => {
    assert.equal(relationshipNodesOverlap(node, other), false);
    const first = relationshipNodeRectangle(node);
    const second = relationshipNodeRectangle(other);
    const horizontalGap = Math.max(0, first.left - second.right, second.left - first.right);
    const verticalGap = Math.max(0, first.top - second.bottom, second.top - first.bottom);
    const connected = node.dataset.nodeId === 'junction:j1'
      || other.dataset.nodeId === 'junction:j1';
    const expectedGap = connected ? 83 : 32;
    assert.ok(horizontalGap >= expectedGap - Number.EPSILON
      || verticalGap >= expectedGap - Number.EPSILON);
    if (!connected && Math.max(horizontalGap, verticalGap) < 83) {
      compactUnrelatedPair = true;
    }
  }));
  assert.equal(compactUnrelatedPair, true);
  connectedPorts.forEach((port) => {
    const node = nodes.find((candidate) => candidate.dataset.nodeId === port.dataset.nodeId);
    const rectangle = relationshipNodeRectangle(node);
    const portCenter = {
      x: Number(port.attributes.x) + Number(port.attributes.width) / 2,
      y: Number(port.attributes.y) + Number(port.attributes.height) / 2,
    };
    assert.ok(portCenter.x >= rectangle.left && portCenter.x <= rectangle.right);
    assert.ok(portCenter.y >= rectangle.top && portCenter.y <= rectangle.bottom);
  });
});

test('topology clearance includes the visible trace envelope', () => {
  const { context } = palette();
  const node = {
    dataset: { nodeId: 'unrelated' },
    getBoundingClientRect: () => ({ left: 80, right: 120, top: 100, bottom: 140 }),
  };
  const diagram = { querySelectorAll: () => [node] };
  const edge = {
    dataset: { pathwayId: 'p', junctionId: 'j' },
    className: 'wire-trace relationship-wire-lane',
    parentElement: { dataset: { wireGroupCount: '5' } },
    getTotalLength: () => 40,
    getPointAtLength: (distance) => ({ x: 80 + distance, y: 66.5 }),
    getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
  };
  edge.parentElement.querySelectorAll = () => [edge];

  assert.equal(context.topologyTraceHalfExtent(5), 9.5);
  assert.equal(context.qaTopologyTraceClearance(edge, diagram), 32);
  assert.equal(context.qaTopologyTraceObstructed(edge, diagram), false);
  edge.getPointAtLength = (distance) => ({ x: 80 + distance, y: 68 });
  assert.equal(context.qaTopologyTraceClearance(edge, diagram), 30.5);
  assert.equal(context.qaTopologyTraceObstructed(edge, diagram), true);
});

test('protected layout corridors route around an unrelated junction', () => {
  const { context } = palette();
  const nodes = [
    { id: 'source', left: 0, top: 100, width: 100, height: 100 },
    { id: 'blocker', left: 183, top: 80, width: 100, height: 140 },
    { id: 'target', left: 366, top: 100, width: 100, height: 100 },
  ];
  const route = context.routeRelationshipEdge(
    { nodeId: 'source', side: 'right', point: { x: 100, y: 150 } },
    { nodeId: 'target', side: 'left', point: { x: 366, y: 150 } },
    nodes,
    [],
    1.5,
  );
  const protectedBlocker = {
    left: 149.5, right: 316.5, top: 46.5, bottom: 253.5,
  };

  assert.ok(route);
  assert.notEqual(route.kind, 'fallback');
  assert.equal(route.points.some((point) => point.y <= protectedBlocker.top
    || point.y >= protectedBlocker.bottom), true);
  context.topologyRouteSegments(route.points.slice(1, -1)).forEach((segment) => {
    assert.equal(context.orthogonalSegmentClearsRectangles(
      segment.start, segment.end, [protectedBlocker],
    ), true);
  });
});

test('current pathway popup retains gate ordering and interpolation controls', () => {
  const { context } = palette();
  const definition = harness();
  definition.gateDefaults = { approach_mm: null, departure_mm: null };
  definition.endDefaults = { approach_mm: null, departure_mm: null };
  definition.controls = [1, 2, 3].map((index) => ({
    controlId: `c${index}`, name: `Gate ${index}`, kind: 'routing_gate',
    interpolation: { approach_mm: null, departure_mm: null },
    usesDefaults: true, hasLinkedGeometry: true,
  }));
  definition.pathways[0].orderedControlIds = ['c1', 'c2', 'c3'];

  context.openPathwayPopup(definition, 'p');

  const popup = context.document.body.querySelector('.pathway-popup');
  const gateRows = descendants(
    popup, (node) => node.className?.split(' ').includes('member-row'),
  );
  const options = descendants(
    popup, (node) => node.className?.split(' ').includes('options-button'),
  )[0];
  assert.equal(popup.open, true);
  assert.ok(gateRows.some((row) => row.dataset.reorder === 'true'));

  options.events.click();
  const interpolation = context.document.body.querySelector('.wire-options');
  assert.equal(interpolation.open, true);
  assert.equal(interpolation.attributes['aria-label'], 'Interpolation · Gate 1');
});

test('generation defaults expose persisted generation preferences', () => {
  const { context } = palette();
  const definition = harness();
  definition.gateDefaults = { approach_mm: null, departure_mm: null };
  definition.endDefaults = { approach_mm: null, departure_mm: null };
  definition.minimumClearanceMm = 0.35;
  definition.autoTransitionPreset = 'relaxed';

  context.openInterpolationOptions(definition, 'defaults');

  const dialog = context.document.body.querySelector('.wire-options');
  const clearance = descendants(
    dialog, (node) => node.attributes?.['aria-label'] === 'Minimum member gap (mm)',
  )[0];
  const relaxation = descendants(
    dialog,
    (node) => node.attributes?.['aria-label'] === 'Automatic transition relaxation',
  )[0];
  const relaxationHeading = descendants(
    dialog, (node) => node.className === 'auto-transition-heading',
  )[0];
  const endpointLabels = descendants(
    dialog, (node) => node.className === 'auto-transition-endpoints',
  );
  assert.equal(dialog.attributes['aria-label'], 'Generation defaults');
  assert.equal(clearance.value, '0.35');
  assert.equal(clearance.min, '0');
  assert.equal(relaxation.type, 'range');
  assert.equal(relaxation.value, '3');
  assert.equal(relaxation.min, '0');
  assert.equal(relaxation.max, '4');
  assert.equal(relaxation.step, '1');
  assert.equal(relaxation.attributes['aria-valuetext'], 'Relaxed');
  assert.equal(relaxationHeading.children[0].textContent, 'Automatic transition relaxation');
  assert.equal(relaxationHeading.children[1].textContent, 'Relaxed');
  assert.equal(endpointLabels.length, 0);
});

test('empty pathway end opens the current pathway popup', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push({
    pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
    orderedControlIds: [],
  });

  const diagram = context.renderRelationshipMap(definition);
  const emptyEnd = descendants(diagram, (node) => (
    node.className?.split(' ').includes('relationship-end-list')
      && node.dataset.pathwayId === 'p2'
  ))[0];
  emptyEnd.children[0].events.click({ preventDefault() {} });

  const popup = context.document.body.querySelector('.pathway-popup');
  assert.equal(popup.open, true);
  assert.equal(popup.attributes['aria-label'], 'Pathway configuration: Pathway 002');
});

test('master diagram Materials action opens harness materials', () => {
  const { context } = palette();
  const definition = harness();
  const diagram = context.renderRelationshipMap(definition);
  const viewport = descendants(
    diagram, (node) => node.className === 'block-diagram-viewport',
  )[0];
  const menu = descendants(
    viewport, (node) => node.className === 'relationship-map-context-menu',
  )[0];

  viewport.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: viewport,
  });
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(materialDialog.children[0].children[0].textContent, 'Harness Materials');
});

test('Wire Details Materials action opens group materials', () => {
  const { context } = palette();
  const definition = harness();
  context.openWireGroupDetails(definition, 'g1', 'a1');
  const details = context.document.body.querySelector('.wire-group-details-popup');

  details.events.contextmenu({
    clientX: 20, clientY: 20, preventDefault() {}, target: details,
  });
  const menu = details.querySelector('.relationship-map-context-menu');
  menu.children.find((item) => item.textContent === 'Materials').events.click();

  const materialDialog = context.document.body.querySelector('.material-options');
  assert.equal(materialDialog.open, true);
  assert.equal(
    materialDialog.children[0].children[0].textContent,
    'Connected Wire Group Materials',
  );
});
