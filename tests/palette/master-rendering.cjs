/** Focused palette regression suite. */
/* global require, __dirname */
const { Element, assert, descendants, harness, join, palette, readFileSync, test } = require('./support.cjs');

test('multi-junction chains retain pathway ends and continuous procedural traces', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways = [
    definition.pathways[0],
    { pathwayId: 'p2', name: 'path ext 1', startName: '', endName: '', orderedControlIds: [] },
    { pathwayId: 'p3', name: 'path ext 2', startName: '', endName: 'finish', orderedControlIds: [] },
  ];
  definition.junctions = [
    { junctionId: 'j1', name: 'Junction 01', controlId: 'c1',
      pathwayRelationships: [
        { pathwayId: 'p', endpoint: 'end' },
        { pathwayId: 'p2', endpoint: 'start' },
      ] },
    { junctionId: 'j2', name: 'Junction 02', controlId: 'c2',
      pathwayRelationships: [
        { pathwayId: 'p2', endpoint: 'end' },
        { pathwayId: 'p3', endpoint: 'start' },
      ] },
  ];
  definition.wires.forEach((wire) => { wire.orderedPathwayIds = ['p', 'p2', 'p3']; });

  const rendered = context.renderRelationshipMap(definition, []);
  const endLists = descendants(
    rendered, (node) => node.className?.startsWith('relationship-end-list'),
  );
  const junctionLinks = descendants(
    rendered, (node) => node.className === 'relationship-topology-edges',
  );

  assert.equal(endLists.length, 6);
  assert.deepEqual(endLists.map((list) => descendants(
    list, (node) => node.className === 'relationship-end-entry',
  ).length), [3, 0, 0, 0, 0, 3]);
  assert.equal(junctionLinks.length, 1);
  assert.equal(descendants(
    junctionLinks[0], (node) => node.className === 'structural-trace',
  ).length, 4);
  assert.equal(descendants(
    junctionLinks[0], (node) => node.className?.split(' ').includes('wire-trace'),
  ).length, 12);
  const topologyNodes = descendants(
    rendered, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  );
  const lefts = topologyNodes.map((node) => Number.parseFloat(node.style.left));
  assert.ok(lefts.every(Number.isFinite));
  assert.ok([...new Set(lefts)].sort((left, right) => left - right)
    .every((left, index, ordered) => index === 0 || left - ordered[index - 1] <= 200));
  const structuralPaths = descendants(
    junctionLinks[0], (node) => node.className === 'structural-trace',
  );
  assert.ok(structuralPaths.every((path) => {
    const points = JSON.parse(path.attributes['data-route-points']);
    return !path.attributes.d.includes(' C ')
      && points.slice(1).every((point, index) => (
        point.x === points[index].x || point.y === points[index].y
      ));
  }));
  const topologyPorts = descendants(
    junctionLinks[0], (node) => node.className === 'relationship-topology-port',
  );
  assert.equal(topologyPorts.length, 8);
  assert.equal(new Set(topologyPorts.map((port) => port.dataset.portId)).size, 8);

  definition.wires = [];
  const unoccupied = context.renderRelationshipMap(definition, []);
  const structuralLinks = descendants(
    unoccupied, (node) => node.className === 'relationship-topology-edges',
  );
  assert.equal(descendants(
    structuralLinks[0], (node) => node.className === 'structural-trace',
  ).length, 4);

  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-pathway-group \{[^}]*gap: 0;[^}]*width: max-content;/s);
  assert.match(styles, /\.relationship-chain-link \{[^}]*margin-inline: -1px;/s);
  assert.match(styles, /\.relationship-connector \{[^}]*margin-inline: -1px;/s);
});

test('relationship diagrams zoom and pan exclusively with middle mouse dragging', () => {
  const { context } = palette();
  const definition = harness();
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(
    styles,
    /\.block-diagram-workspace \.block-diagram-viewport \{[^}]*cursor: default;/s,
  );
  assert.match(
    styles,
    /\.block-diagram-workspace \.block-diagram-viewport\.panning,[^{]*\.block-diagram-workspace \.block-diagram-viewport\.panning \* \{[^}]*cursor: grabbing;/s,
  );
  const perWire = context.renderWireRelationshipGraphic(
    definition, definition.wires[0], new Map(), new Map(), new Element('div'), new Element('div'),
  );
  const master = context.renderRelationshipMap(definition, []);
  for (const diagram of [perWire, master]) {
    assert.equal(descendants(
      diagram, (node) => node.className === 'block-diagram-workspace',
    ).length, 1);
    const viewport = descendants(
      diagram, (node) => node.className === 'block-diagram-viewport',
    )[0];
    const stage = descendants(
      diagram, (node) => node.className === 'block-diagram-stage',
    )[0];
    const zoom = descendants(
      diagram, (node) => node.className === 'block-diagram-zoom',
    )[0];
    const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
    const initialZoom = zoom.textContent;
    zoomIn.events.click();
    assert.notEqual(zoom.textContent, initialZoom);
    let prevented = false;
    viewport.events.wheel({
      deltaY: -1, clientX: 50, clientY: 40,
      preventDefault: () => { prevented = true; },
    });
    assert.equal(prevented, true);
    const beforePan = stage.style.transform;
    viewport.events.pointerdown({
      button: 0, pointerId: 6, clientX: 30, clientY: 30, target: viewport,
      preventDefault: () => { throw new Error('left drag must not be consumed'); },
    });
    viewport.events.pointermove({ pointerId: 6, clientX: 50, clientY: 60 });
    viewport.events.pointerup({ pointerId: 6 });
    assert.equal(stage.style.transform, beforePan);
    const interactiveTarget = descendants(diagram, (node) => (
      node.className?.split(' ').includes('wire-relationship-node')
      || node.className === 'relationship-pathway-hub'
    ))[0];
    let panPrevented = false;
    let capturedPointer = null;
    let releasedPointer = null;
    viewport.setPointerCapture = (pointerId) => { capturedPointer = pointerId; };
    viewport.releasePointerCapture = (pointerId) => { releasedPointer = pointerId; };
    viewport.events.pointerdown({
      button: 1, pointerId: 7, clientX: 30, clientY: 30, target: interactiveTarget,
      preventDefault: () => { panPrevented = true; },
    });
    assert.equal(panPrevented, true);
    assert.equal(capturedPointer, 7);
    assert.equal(viewport.className.includes('panning'), true);
    viewport.events.pointermove({ pointerId: 8, clientX: 90, clientY: 90 });
    assert.equal(stage.style.transform, beforePan);
    viewport.events.pointermove({ pointerId: 7, clientX: 50, clientY: 60 });
    const afterPan = stage.style.transform;
    assert.notEqual(afterPan, beforePan);
    viewport.events.pointerup({ pointerId: 8 });
    assert.equal(viewport.className.includes('panning'), true);
    viewport.events.pointerup({ pointerId: 7 });
    assert.equal(releasedPointer, 7);
    assert.equal(viewport.className.includes('panning'), false);
    viewport.events.pointerdown({
      button: 1, pointerId: 9, clientX: 50, clientY: 60, target: viewport,
      preventDefault() {},
    });
    viewport.events.pointercancel({ pointerId: 9 });
    viewport.events.pointermove({ pointerId: 9, clientX: 70, clientY: 80 });
    assert.equal(stage.style.transform, afterPan);
    assert.equal(viewport.className.includes('panning'), false);
  }
});

test('diagram Fit honors explicit content bounds below the default zoom floor', () => {
  const { context } = palette();
  const workspace = context.createBlockDiagramWorkspace('Large route', {
    contentSize: { width: 6000, height: 3000 },
    minScale: 0.01,
  });
  workspace.viewport.clientWidth = 600;
  workspace.viewport.clientHeight = 300;

  workspace.fit();

  const scale = Number.parseFloat(
    workspace.stage.style.transform.match(/scale\(([^)]+)\)/)[1],
  );
  assert.ok(scale < 0.3);
  assert.ok(6000 * scale <= workspace.viewport.clientWidth - 24);
  assert.ok(3000 * scale <= workspace.viewport.clientHeight - 24);
  assert.equal(workspace.zoomValue.textContent, `${Math.round(scale * 100)}%`);
});

test('Wire Details deterministically reduces avoidable route crossings', () => {
  const { context } = palette();
  const topology = (reverse = false) => {
    const specifications = [
      ['connection:root', 'connection', 'Root'],
      ['pathway:a', 'pathway', 'Alpha'],
      ['pathway:b', 'pathway', 'Beta'],
      ['junction:c', 'junction', 'Charlie'],
      ['junction:d', 'junction', 'Delta'],
    ];
    if (reverse) specifications.reverse();
    const nodes = specifications.map(([id, kind, label]) => ({
      id, kind, label, item: {}, neighbors: new Set(),
    }));
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const pairs = [
      ['connection:root', 'pathway:a'],
      ['connection:root', 'pathway:b'],
      ['pathway:a', 'junction:d'],
      ['pathway:b', 'junction:c'],
    ];
    const edges = (reverse ? pairs.slice().reverse() : pairs).map(([leftId, rightId]) => {
      nodesById.get(leftId).neighbors.add(rightId);
      nodesById.get(rightId).neighbors.add(leftId);
      return { id: [leftId, rightId].sort().join('|'), leftId, rightId };
    });
    return { nodes, edges };
  };

  const first = context.layoutWireGroupDetailsTopology(topology(), 'root');
  const second = context.layoutWireGroupDetailsTopology(topology(true), 'root');
  const rows = (layout) => Object.fromEntries(
    layout.nodes.map((node) => [node.id, [node.depth, node.row]]),
  );

  assert.equal(first.orderingScore.crossings, 0);
  assert.deepEqual(rows(first), rows(second));
  assert.ok(first.nodes.find((node) => node.id === 'junction:d').row
    < first.nodes.find((node) => node.id === 'junction:c').row);
});

test('Wire Details expands full labels and sorts separated route ports', () => {
  const { context } = palette();
  const definition = harness();
  const longLabel = 'Path to the battery ground distribution block';
  definition.wires = [];
  definition.pathways = ['p1', 'p2', 'p3'].map((pathwayId, index) => ({
    pathwayId,
    name: index === 0 ? longLabel : `Path ${index + 1}`,
    startName: '',
    endName: '',
    orderedControlIds: [],
  }));
  definition.connections = ['a', 'b', 'c'].map((connectionId) => ({
    connectionId, name: `End ${connectionId.toUpperCase()}`, hasLinkedGeometry: true,
  }));
  definition.standaloneEnds = [
    { connectionId: 'a', pathwayId: 'p1', endpoint: 'start' },
    { connectionId: 'b', pathwayId: 'p2', endpoint: 'end' },
    { connectionId: 'c', pathwayId: 'p3', endpoint: 'end' },
  ];
  definition.junctions = [{
    junctionId: 'j1', name: 'Shared junction', controlId: 'junction-control',
    pathwayRelationships: ['p1', 'p2', 'p3'].map((pathwayId, index) => ({
      pathwayId, endpoint: index ? 'start' : 'end',
    })),
  }];
  const group = {
    wireGroupId: 'g1', connectionIds: ['a', 'b', 'c'], routeLegs: [{
      routeId: 'leg-1', startConnectionId: 'a', endConnectionId: 'b',
      pathwayIds: ['p1', 'p2'], controlSteps: [{ controlId: 'junction-control' }],
    }, {
      routeId: 'leg-2', startConnectionId: null, endConnectionId: 'c',
      pathwayIds: ['p3'], controlSteps: [{ controlId: 'junction-control' }],
    }],
  };

  const workspace = context.renderWireGroupDetailsGraphic(definition, group, 'a');
  const svg = descendants(workspace.root, (node) => node.className === 'wire-group-details-svg')[0];
  const pathwayNode = descendants(svg, (node) => node.dataset.nodeId === 'pathway:p1')[0];
  const label = descendants(
    pathwayNode, (node) => node.className === 'relationship-node-label',
  )[0];
  const rectangle = descendants(
    pathwayNode, (node) => node.className?.split(' ').includes('relationship-node'),
  )[0];
  const junctionLinks = descendants(svg, (node) => (
    node.className === 'wire-group-route-link'
      && (node.attributes['data-start-node-id'] === 'junction:j1'
        || node.attributes['data-end-node-id'] === 'junction:j1')
  ));
  const junctionPorts = junctionLinks.map((link) => (
    link.attributes['data-start-node-id'] === 'junction:j1'
      ? link.attributes['data-start-y'] : link.attributes['data-end-y']
  ));

  assert.equal(label.textContent, longLabel);
  const rectangleX = Number(rectangle.attributes.x);
  const rectangleWidth = Number(rectangle.attributes.width);
  assert.ok(rectangleWidth > 150);
  assert.ok(rectangleX >= 0);
  assert.ok(rectangleX + rectangleWidth <= Number(svg.attributes.width));
  assert.equal(junctionLinks.every((link) => link.tag === 'path'), true);
  assert.equal(new Set(junctionPorts).size, junctionPorts.length);
});

test('master relationship graphic is last and independently cross-checked', () => {
  const { context } = palette();
  const definition = harness();
  context.renderEditor(definition);
  const sections = Array.from(context.ui.editor.children).filter((node) => node.tag === 'details');
  assert.deepEqual(
    sections.map((section) => section.dataset.section),
    ['wire-routes', 'validation', 'master-relationship-graphic'],
  );
  const audit = descendants(sections[1], (node) => node.className === 'relationship-audit')[0];
  assert.match(audit.textContent, /agrees with wire routes/);
  const pathwayCards = descendants(
    sections[2], (node) => node.className === 'relationship-pathway-group',
  );
  assert.equal(pathwayCards.length, 1);
  const endLists = descendants(pathwayCards[0], (node) => node.className === 'relationship-end-list');
  assert.equal(endLists.length, 2);
  assert.ok(endLists.every((list) => list.open));
  const wireGraphics = descendants(sections[0], (node) => node.className === 'wire-relationship-graphic');
  assert.equal(wireGraphics.length, 3);
  const pathwayBubble = descendants(wireGraphics[0], (node) => (
    node.className === 'relationship-node pathway'
  ))[0];
  assert.equal(pathwayBubble.attributes.width, '150');
  assert.equal(pathwayBubble.attributes.transform, undefined);
  const graphicLabels = descendants(wireGraphics[0], (node) => node.tag === 'text')
    .map((node) => node.textContent);
  assert.ok(graphicLabels.includes('Data input'));
  assert.ok(graphicLabels.includes('lower fuse box path'));
  assert.ok(graphicLabels.includes('Data output'));
  const connectors = descendants(sections[2], (node) => node.className === 'relationship-connector');
  assert.equal(connectors.length, 2);
  assert.ok(connectors.every((connector) => (
    descendants(connector, (node) => node.tag === 'path').length === 3
  )));
  endLists[0].open = false;
  endLists[0].events.toggle();
  assert.equal(descendants(connectors[0], (node) => node.tag === 'path').length, 1);
  assert.equal(sections[2].open, true);
});

test('master topology traces leave adaptive ports normally and avoid measured nodes', () => {
  const { context } = palette();
  const source = { id: 'pathway:source', left: 20, top: 120, width: 120, height: 60 };
  const obstacle = { id: 'pathway:obstacle', left: 240, top: 90, width: 140, height: 120 };
  const target = { id: 'junction:target', left: 500, top: 120, width: 120, height: 60 };
  const sourcePort = {
    id: 'edge:source', nodeId: source.id, side: 'right', point: { x: 140, y: 150 },
  };
  const targetPort = {
    id: 'edge:target', nodeId: target.id, side: 'left', point: { x: 500, y: 150 },
  };

  const routed = context.routeRelationshipEdge(
    sourcePort, targetPort, [source, obstacle, target],
  );

  assert.equal(routed.kind, 'orthogonal');
  assert.ok(routed.points.length >= 4);
  assert.equal(routed.points[0].x, 140);
  assert.equal(routed.points[0].y, 150);
  assert.equal(routed.points[routed.points.length - 1].x, 500);
  assert.equal(routed.points[routed.points.length - 1].y, 150);
  assert.ok(routed.points.some((point) => point.y <= obstacle.top - 14
    || point.y >= obstacle.top + obstacle.height + 14));
  assert.match(routed.d, / Q /);
  assert.ok(routed.points.slice(1).every((point, index) => (
    point.x === routed.points[index].x || point.y === routed.points[index].y
  )));
  assert.equal(routed.points[1].y, routed.points[0].y);
  assert.ok(routed.points[1].x > routed.points[0].x);

  const clearTarget = { ...target, top: 280 };
  const clearTargetPort = {
    ...targetPort,
    point: { x: clearTarget.left, y: clearTarget.top + clearTarget.height / 2 },
  };
  const clearRoute = context.routeRelationshipEdge(
    sourcePort, clearTargetPort, [source, clearTarget],
  );
  assert.equal(clearRoute.kind, 'orthogonal');
  assert.doesNotMatch(clearRoute.d, / C /);
});

test('master topology starts with four centered ports and expands sides symmetrically', () => {
  const { context } = palette();
  const center = {
    id: 'junction:center', left: 100, top: 100, width: 120, height: 100,
  };
  const neighbors = [
    { id: 'pathway:p0', left: 400, top: 110, width: 100, height: 80 },
    { id: 'pathway:p1', left: -200, top: 110, width: 100, height: 80 },
    { id: 'pathway:p2', left: 110, top: -200, width: 100, height: 80 },
    { id: 'pathway:p3', left: 110, top: 400, width: 100, height: 80 },
    { id: 'pathway:p4', left: 400, top: 70, width: 100, height: 80 },
    { id: 'pathway:p5', left: 400, top: 150, width: 100, height: 80 },
  ];
  const edges = neighbors.map((neighbor, index) => ({
    sourceId: center.id,
    targetId: neighbor.id,
    junction: { junctionId: `j${index}` },
    relationship: { pathwayId: `p${index}`, endpoint: 'start' },
  }));
  const component = { nodes: [center, ...neighbors], edges };

  assert.equal(JSON.stringify(context.relationshipCanonicalPorts(center)), JSON.stringify({
    left: { x: 100, y: 150 },
    right: { x: 220, y: 150 },
    top: { x: 160, y: 100 },
    bottom: { x: 160, y: 200 },
  }));
  const ports = context.allocateRelationshipPorts(component);
  const centerPorts = ports.filter((port) => port.nodeId === center.id);
  const repeatedRight = centerPorts.filter((port) => port.side === 'right');
  assert.equal(centerPorts.length, 6);
  assert.equal(
    [...new Set(centerPorts.map((port) => port.side))].sort().join(','),
    'bottom,left,right,top',
  );
  assert.equal(repeatedRight.length, 3);
  assert.equal(
    repeatedRight.map((port) => port.point.y).sort((left, right) => left - right).join(','),
    '128,150,172',
  );
  assert.equal(
    JSON.stringify(context.allocateRelationshipPorts({
      nodes: component.nodes, edges: edges.slice().reverse(),
    })),
    JSON.stringify(ports),
  );

  const rightOnly = {
    nodes: [center, ...neighbors.slice(0, 5).map((neighbor, index) => ({
      ...neighbor, id: `pathway:right-${index}`, left: 400, top: 110 + index * 10,
    }))],
    edges: edges.slice(0, 5).map((edge, index) => ({
      ...edge,
      targetId: `pathway:right-${index}`,
      junction: { junctionId: `right-${index}` },
    })),
  };
  const rightOnlyCenterPorts = context.allocateRelationshipPorts(rightOnly)
    .filter((port) => port.nodeId === center.id);
  assert.equal(
    new Set(rightOnlyCenterPorts.slice(0, 4).map((port) => port.side)).size,
    4,
  );
  assert.equal(rightOnlyCenterPorts[4].side, 'right');
});

test('master topology route scoring rejects overlaps more strongly than clean crossings', () => {
  const { context } = palette();
  const occupied = [{ start: { x: 0, y: 20 }, end: { x: 100, y: 20 } }];
  const overlap = context.topologySegmentConflictScore(
    { start: { x: 20, y: 20 }, end: { x: 80, y: 20 } }, occupied,
  );
  const crossing = context.topologySegmentConflictScore(
    { start: { x: 50, y: 0 }, end: { x: 50, y: 40 } }, occupied,
  );
  const clear = context.topologySegmentConflictScore(
    { start: { x: 0, y: 40 }, end: { x: 100, y: 40 } }, occupied,
  );

  assert.ok(overlap > crossing);
  assert.ok(crossing > clear);
  assert.equal(clear, 0);
});

test('master topology node ordering changes only when crossings decrease', () => {
  const { context } = palette();
  const nodes = [
    { id: 'a', depth: 0 },
    { id: 'b', depth: 0 },
    { id: 'c', depth: 1 },
    { id: 'd', depth: 1 },
  ];
  const component = {
    nodes,
    edges: [
      { sourceId: 'a', targetId: 'd' },
      { sourceId: 'b', targetId: 'c' },
    ],
  };

  const optimized = context.optimizeRelationshipNodeOrder(component);

  assert.equal(optimized.map((node) => node.id).join(','), 'a,b,d,c');
  assert.equal(
    context.optimizeRelationshipNodeOrder({ nodes, edges: [] })
      .map((node) => node.id).join(','),
    'a,b,c,d',
  );
});

test('palette entry point loads organized local style and script resources', () => {
  const html = readFileSync(join(__dirname, '..', '..', 'palette.html'), 'utf8');
  assert.match(html, /<link rel="stylesheet" href="palette\/styles\.css">/);
  assert.deepEqual(
    [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map((match) => match[1]),
    [
      'palette/foundation.js',
      'palette/route-editors.js',
      'palette/materials.js',
      'palette/relationship-audit.js',
      'palette/diagrams/workspace.js',
      'palette/wire-graphic.js',
      'palette/diagrams/master-model.js',
      'palette/diagrams/master-layout.js',
      'palette/wire-group-details.js',
      'palette/diagrams/create-wires.js',
      'palette/diagrams/master-components.js',
      'palette/master-graphic.js',
      'palette/editor.js',
      'palette/host.js',
    ],
  );
  assert.doesNotMatch(html, /<style>|<script>/);
});

test('master relationship filtering, hover, navigation, and mismatch reporting work', () => {
  const { context, calls } = palette();
  const definition = harness();
  definition.relationshipMap.routes[0].nodeIds.reverse();
  const issues = context.relationshipAuditIssues(definition);
  assert.ok(issues.some((issue) => issue.code === 'palette_wire_route_mismatch'));
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });
  context.renderEditor(definition);
  const graphic = context.ui.editor.children[context.ui.editor.children.length - 1];
  const filter = descendants(graphic, (node) => node.attributes['aria-label'] === 'Filter master relationship graphic')[0];
  filter.value = '002';
  filter.events.input();
  const pathwayCards = descendants(graphic, (node) => node.className === 'relationship-pathway-group');
  assert.equal(pathwayCards.length, 1);
  const entries = descendants(graphic, (node) => node.className === 'relationship-end-entry');
  assert.equal(entries.length, 2);
  entries[0].events.mouseenter();
  assert.deepEqual(calls[calls.length - 1], { type: 'connection', id: 'a2' });
  entries[0].events.click();
  const wireCard = context.ui.editor.querySelector('[data-wire-id="w2"]');
  assert.equal(wireCard.scrolledIntoView, true);
  assert.equal(wireCard.querySelector('.wire-details').hidden, false);
  const validation = context.ui.editor.querySelector('[data-section="validation"]');
  assert.ok(descendants(validation, (node) => node.textContent?.includes('does not match')).length);
});

test('expanded master traces use wire colors and pathway hubs open their popup', () => {
  const { context } = palette();
  const definition = harness();
  definition.wires[0].materials = {
    ...definition.materialDefaults,
    mainColor: { name: 'Red', hex: '#cc1122' },
    stripes: [
      { color: { name: 'White', hex: '#ffffff' }, pattern: 'solid' },
      { color: { name: 'Blue', hex: '#2255cc' }, pattern: 'dashed' },
    ],
  };
  definition.wires[1].materials = {
    ...definition.materialDefaults,
    mainColor: { name: 'Green', hex: '#228844' },
  };
  definition.wires[2].materials = {
    ...definition.materialDefaults,
    mainColor: { name: 'Yellow', hex: '#e8c51c' },
  };
  definition.wires[1].startConnectionId = 'a1';
  context.renderEditor(definition);
  const master = context.ui.editor.querySelector('[data-section="master-relationship-graphic"]');
  const connectors = descendants(master, (node) => node.className === 'relationship-connector');
  const wireTraces = descendants(connectors[0], (node) => node.className === 'wire-trace');
  assert.deepEqual(wireTraces.map((trace) => trace.attributes.stroke), [
    '#cc1122', '#228844', '#e8c51c',
  ]);
  assert.deepEqual(wireTraces.map((trace) => trace.attributes['data-wire-id']), ['w1', 'w2', 'w3']);
  const stripes = descendants(connectors[0], (node) => node.className === 'stripe-trace');
  assert.deepEqual(stripes.map((stripe) => stripe.attributes.stroke), ['#ffffff', '#2255cc']);
  assert.deepEqual(stripes.map((stripe) => stripe.attributes['stroke-dasharray']), ['none', '8 5']);
  const endList = descendants(master, (node) => node.className === 'relationship-end-list')[0];
  endList.open = false;
  endList.events.toggle();
  const collapsedTraces = descendants(connectors[0], (node) => node.tag === 'path');
  assert.equal(collapsedTraces.length, 1);
  assert.equal(collapsedTraces[0].className, 'aggregate-trace');

  descendants(master, (node) => node.className === 'relationship-pathway-hub')[0].events.click();
  const popup = context.document.body.querySelector('.pathway-popup');
  const pathwaySection = popup.querySelector('[data-section="pathway:p"]');
  assert.equal(context.ui.editor.querySelector('[data-section="pathways"]'), undefined);
  assert.equal(popup.open, true);
  assert.equal(pathwaySection.open, true);
  assert.deepEqual(
    descendants(pathwaySection, (node) => node.tag === 'label').map((node) => node.textContent),
    ['Pathway Name', 'Start Name', 'End Name'],
  );
  definition.pathways[0].name = 'Updated pathway';
  context.renderEditor(definition);
  const refreshedPopup = context.document.body.querySelector('.pathway-popup');
  assert.equal(context.document.body.querySelectorAll('.pathway-popup').length, 1);
  assert.equal(refreshedPopup.querySelector('[data-section="pathway:p"]').children[0]
    .children[0].textContent, 'Updated pathway');
  descendants(refreshedPopup, (node) => node.textContent === 'Close')[0].events.click();
  assert.equal(context.document.body.querySelector('.pathway-popup'), undefined);
});

test('master collapse limit defaults to seven, clamps, persists, and search reveals matches', () => {
  const storage = new Map();
  const definition = harness();
  const template = definition.wires[0];
  definition.connections = Array.from({ length: 8 }, (_, index) => ['a', 'b'].map((end) => ({
    connectionId: `${end}${index + 1}`, name: `${end}${index + 1}`, hasLinkedGeometry: true,
  }))).flat();
  definition.wires = Array.from({ length: 8 }, (_, index) => ({
    ...template,
    wireId: `w${index + 1}`,
    wireNumber: `${index + 1}`.padStart(3, '0'),
    startConnectionId: `a${index + 1}`,
    endConnectionId: `b${index + 1}`,
    startEndName: index === 0 ? 'Data input' : '',
    endEndName: index === 0 ? 'Data output' : '',
  }));
  let { context } = palette(storage);
  let rendered = context.renderRelationshipMap(definition, []);
  let limit = descendants(rendered, (node) => (
    node.attributes['aria-label'] === 'Connections before end lists collapse'
  ))[0];
  assert.equal(limit.value, '7');
  let endLists = descendants(rendered, (node) => node.className === 'relationship-end-list');
  assert.ok(endLists.every((list) => !list.open));
  let connectors = descendants(rendered, (node) => node.className === 'relationship-connector');
  assert.ok(connectors.every((connector) => (
    descendants(connector, (node) => node.tag === 'path').length === 1
  )));
  const sevenConnectionHarness = {
    ...definition,
    connections: definition.connections.filter((connection) => !connection.connectionId.endsWith('8')),
    wires: definition.wires.slice(0, 7),
  };
  const boundary = context.renderRelationshipMap(sevenConnectionHarness, []);
  assert.ok(descendants(boundary, (node) => node.className === 'relationship-end-list')
    .every((list) => list.open));
  limit.value = '20';
  limit.events.change();
  endLists = descendants(rendered, (node) => node.className === 'relationship-end-list');
  assert.ok(endLists.every((list) => list.open));
  assert.equal(storage.get('wireBundler.relationshipCollapseLimit:h'), '20');
  ({ context } = palette(storage));
  rendered = context.renderRelationshipMap(definition, []);
  limit = descendants(rendered, (node) => (
    node.attributes['aria-label'] === 'Connections before end lists collapse'
  ))[0];
  assert.equal(limit.value, '20');
  limit.value = '0';
  limit.events.change();
  assert.equal(limit.value, '1');
  const filter = descendants(rendered, (node) => (
    node.attributes['aria-label'] === 'Filter master relationship graphic'
  ))[0];
  filter.value = 'Data input';
  filter.events.input();
  endLists = descendants(rendered, (node) => node.className === 'relationship-end-list');
  assert.equal(endLists[0].open, true);
  assert.equal(endLists[1].open, false);
  assert.equal(endLists[0].children[0].children[1].textContent, '1 of 8');
  connectors = descendants(rendered, (node) => node.className === 'relationship-connector');
  assert.equal(descendants(connectors[0], (node) => node.tag === 'path').length, 1);
  assert.equal(descendants(connectors[1], (node) => node.tag === 'path').length, 1);
});

test('master and per-wire graphics preserve scoped Fusion highlighting', () => {
  const { context, calls } = palette();
  const definition = harness();
  context.highlightMember = (_harness, type, id) => calls.push({ type, id });
  const master = context.renderRelationshipMap(definition, []);
  descendants(master, (node) => node.className === 'relationship-pathway-hub')[0]
    .events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'pathway_gates', id: 'p' });
  const endList = descendants(master, (node) => node.className === 'relationship-end-list')[0];
  endList.children[0].events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'pathway_wires', id: 'p' });
  descendants(master, (node) => node.className === 'relationship-end-entry')[0]
    .events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'connection', id: 'a1' });
  const wireGraphic = descendants(
    context.renderWireRoutes(definition),
    (node) => node.className === 'wire-relationship-graphic',
  )[0];
  descendants(wireGraphic, (node) => node.dataset.endpoint === 'start')[0]
    .events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'connection', id: 'a1' });
  descendants(wireGraphic, (node) => node.className === 'wire-relationship-route')[0]
    .events.mouseenter();
  assert.deepEqual(calls.pop(), { type: 'preview_wire', id: 'w1' });
});
