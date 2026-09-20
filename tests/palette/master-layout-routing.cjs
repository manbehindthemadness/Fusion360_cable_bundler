/* global require, __dirname */
const {
  Element, assert, descendants, harness, palette, readPaletteStyles, test,
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


test('diagram QA metrics use reload-safe nonnegative fallbacks', () => {
  const { context } = palette();

  assert.equal(context.qaNonnegativeNumber(undefined, 10), 10);
  assert.equal(context.qaNonnegativeNumber('-1', 10), 10);
  assert.equal(context.qaNonnegativeNumber('12.5', 10), 12.5);
  assert.equal(context.qaNonnegativeInteger(undefined, 0), 0);
  assert.equal(context.qaNonnegativeInteger('-1', 0), 0);
  assert.equal(context.qaNonnegativeInteger('3', 0), 3);
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

test('layout search routes a requested layout beyond the compact shortlist', () => {
  const { context } = palette();
  const attempts = [];
  const layouts = Array.from({ length: 20 }, (_unused, index) => ({
    layoutKey: `layout-${index}`,
  }));
  const candidates = context.routeRelationshipLayoutPool(layouts, (layout) => {
    attempts.push(layout.layoutKey);
    return layout;
  }, 3, 'layout-17');

  assert.deepEqual(attempts, ['layout-0', 'layout-1', 'layout-2', 'layout-17']);
  assert.equal(candidates.at(-1).layoutKey, 'layout-17');
});

test('saved safe layout bypasses unrelated routing candidates', () => {
  const { context } = palette();
  const attempts = [];
  const layouts = ['first', 'saved', 'last'].map((layoutKey) => ({ layoutKey }));
  const route = (layout) => {
    attempts.push(layout.layoutKey);
    return {
      ...layout,
      routeQuality: { overlaps: 0, parallelConflicts: 0, crossings: 0 },
    };
  };

  const selected = context.preferredRelationshipLayoutCandidate(
    layouts, route, 'saved',
  );

  assert.equal(selected.layoutKey, 'saved');
  assert.deepEqual(attempts, ['saved']);
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
  const styles = readPaletteStyles();

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

test('clear aligned routes bypass visibility search without accepting conflicts', () => {
  const { context } = palette();
  const start = { x: 0, y: 20 };
  const end = { x: 100, y: 20 };

  assert.equal(
    JSON.stringify(context.topologyDirectRoute(start, end, [], [], 3)),
    JSON.stringify([start, end]),
  );
  assert.equal(context.topologyDirectRoute(
    start,
    end,
    [],
    [{ start: { x: 10, y: 20 }, end: { x: 90, y: 20 }, halfExtent: 3 }],
    3,
  ), null);
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
  definition.cableGroups.forEach((group) => {
    group.routeLegs[0].controlSteps = [{ controlId: 'c1' }];
  });
  definition.cableGroups.push(...[4, 5].map((index) => ({
    ...definition.cableGroups[0],
    cableGroupId: `g${index}`,
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
      && node.dataset.cableGroupCount === '5',
  )[0];
  const fiveLanePort = pathwayPorts.find((port) => port.dataset.nodeId === 'pathway:p');
  assert.equal(fiveLaneEdge.dataset.renderMode, 'lanes');
  assert.equal(descendants(
    fiveLaneEdge, (node) => node.className === 'cable-trace relationship-cable-lane',
  ).length, 5);
  assert.ok(Number(fiveLanePort.attributes.width) >= 24);
});

test('endpoint list sizing ignores allocated horizontal track width', () => {
  const { context } = palette();
  const compact = new Element('details');
  compact.className = 'relationship-end-list';
  compact.clientWidth = 82;
  compact.scrollWidth = 210;
  compact.scrollHeight = 58;
  compact.style.width = '210px';
  const expanded = new Element('details');
  expanded.className = 'relationship-end-list';
  expanded.clientWidth = 286;
  expanded.scrollWidth = 286;
  expanded.scrollHeight = 92;

  const compactSize = context.relationshipEndListSize(compact);
  const expandedSize = context.relationshipEndListSize(expanded);

  assert.equal(compactSize.width, 96);
  assert.equal(compactSize.height, 58);
  assert.equal(compact.style.width, '210px');
  assert.equal(expandedSize.width, 286);
});

test('horizontal endpoint lists fill their reserved dock width', () => {
  const { context } = palette();
  const group = new Element('div');
  const startList = new Element('details');
  const endList = new Element('details');
  const startConnector = new Element('svg');
  const endConnector = new Element('svg');
  startList.className = 'relationship-end-list empty';
  endList.className = 'relationship-end-list';
  startConnector.setDockSide = (side) => { startConnector.dataset.side = side; };
  endConnector.setDockSide = (side) => { endConnector.dataset.side = side; };
  group.relationshipEndpointLists = { start: startList, end: endList };
  group.relationshipConnectors = { start: startConnector, end: endConnector };
  group.relationshipHub = new Element('div');
  const sizes = {
    start: { width: 96, height: 34 },
    end: { width: 148, height: 72 },
  };

  context.configureRelationshipPathwayDocking(group, 'left', 'right', sizes);
  assert.equal(startList.style.width, '96px');
  assert.equal(endList.style.width, '148px');

  context.configureRelationshipPathwayDocking(group, 'top', 'bottom', sizes);
  assert.equal(startList.style.width, '');
  assert.equal(endList.style.width, '');
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

test('collapsing an end list locally reconnects its topology trace', () => {
  const { context } = palette();
  const definition = harness();
  definition.junctions.push({
    junctionId: 'j1', controlId: 'c1', name: 'Junction 001',
    pathwayRelationships: [{ pathwayId: 'p', endpoint: 'end' }],
  });
  definition.cableGroups.forEach((group) => {
    group.routeLegs[0].controlSteps = [{ controlId: 'c1' }];
  });

  const diagram = context.renderRelationshipMap(definition);
  const stack = descendants(
    diagram, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  const endList = descendants(
    diagram, (node) => node.className === 'relationship-end-list'
      && node.dataset.pathwayId === 'p' && node.dataset.endpoint === 'end',
  )[0];
  const edge = descendants(
    diagram, (node) => node.className === 'relationship-topology-edge'
      && (node.dataset.sourceId === 'pathway:p' || node.dataset.targetId === 'pathway:p'),
  )[0];
  const pathwayIsSource = edge.dataset.sourceId === 'pathway:p';
  const coordinate = (path) => [
    Number(path.dataset[pathwayIsSource ? 'sourceX' : 'targetX']),
    Number(path.dataset[pathwayIsSource ? 'sourceY' : 'targetY']),
  ];
  const initialPath = descendants(
    edge, (node) => node.className === 'structural-trace',
  )[0];
  const initialEndpoint = coordinate(initialPath);
  const initialRevision = stack.dataset.diagramLayoutRevision;

  endList.style.left = '37px';
  endList.style.top = '29px';
  endList.style.width = '84px';
  endList.style.height = '34px';
  endList.open = false;
  endList.events.toggle();

  const updatedPath = descendants(
    edge, (node) => node.className === 'structural-trace',
  )[0];
  const updatedEndpoint = coordinate(updatedPath);
  const pathwayPort = descendants(
    diagram, (node) => node.className === 'relationship-topology-port'
      && node.dataset.nodeId === 'pathway:p',
  )[0];
  const portCenter = [
    Number(pathwayPort.attributes.x) + Number(pathwayPort.attributes.width) / 2,
    Number(pathwayPort.attributes.y) + Number(pathwayPort.attributes.height) / 2,
  ];

  assert.notDeepEqual(updatedEndpoint, initialEndpoint);
  assert.deepEqual(updatedEndpoint, portCenter);
  assert.equal(stack.dataset.diagramLayoutRevision, initialRevision);
  assert.equal(descendants(
    diagram, (node) => node.className === 'relationship-topology-edge',
  )[0], edge);
});

test('layered docking aligns sibling pathway ends with the selected flow axis', () => {
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
  const stack = descendants(
    diagram, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  const connectedPorts = descendants(
    diagram, (node) => node.className === 'relationship-topology-port'
      && node.dataset.nodeId.startsWith('pathway:'),
  );

  const flowSides = stack.dataset.diagramLayoutKey.startsWith('vertical|')
    ? ['bottom', 'top'] : ['left', 'right'];
  assert.ok(connectedPorts.every((port) => flowSides.includes(port.dataset.side)));
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
  const geometryComponents = context.relationshipTopology(definition);
  const renderedNodes = new Map(nodes.map((node) => [node.dataset.nodeId, node]));
  geometryComponents.forEach((component) => component.nodes.forEach((node) => {
    node.element = renderedNodes.get(node.id);
  }));
  context.captureRelationshipIntrinsicSizes(geometryComponents);
  const verticalSpecification = context.relationshipLayoutSpecifications(geometryComponents)
    .find((specification) => specification.flow === 'vertical'
      && specification.direction === 'forward'
      && specification.orderMode === 'dense'
      && specification.roots[0].id === 'junction:j1');
  const verticalLayout = context.relationshipTopologyLayoutCandidate(
    geometryComponents, verticalSpecification,
  );
  const pathwayRectangles = context.materializeRelationshipLayout(
    geometryComponents, verticalLayout,
  )[0].nodes.filter((node) => node.kind === 'pathway').map((node) => ({
    left: node.left, right: node.left + node.width,
  })).sort((left, right) => left.left - right.left);
  pathwayRectangles.slice(1).forEach((rectangle, index) => {
    assert.equal(rectangle.left - pathwayRectangles[index].right, 32);
  });
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
    className: 'cable-trace relationship-cable-lane',
    parentElement: { dataset: { cableGroupCount: '5' } },
    getTotalLength: () => 40,
    getPointAtLength: (distance) => ({ x: 80 + distance, y: 65 }),
    getScreenCTM: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
  };
  edge.parentElement.querySelectorAll = () => [edge];

  assert.equal(context.topologyTraceHalfExtent(5), 11);
  assert.equal(context.qaTopologyTraceClearance(edge, diagram), 32);
  assert.equal(context.qaTopologyTraceObstructed(edge, diagram), false);
  edge.getPointAtLength = (distance) => ({ x: 80 + distance, y: 66.5 });
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
