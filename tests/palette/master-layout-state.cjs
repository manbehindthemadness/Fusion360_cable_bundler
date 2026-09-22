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

/** Return two connected hubs with four terminal pathway branches. */
function twinHubHarness() {
  const definition = harness();
  definition.pathways.push(
    { pathwayId: 'p2', name: 'Chassis ground path', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Battery ground path', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p4', name: 'Dallas controller path', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p5', name: 'Temp sensor path', startName: 'A', endName: 'B',
      orderedControlIds: [] },
  );
  definition.junctions.push(
    {
      junctionId: 'j1', controlId: 'c1', name: 'Ground junction',
      pathwayRelationships: [
        { pathwayId: 'p', endpoint: 'start' },
        { pathwayId: 'p2', endpoint: 'start' },
        { pathwayId: 'p3', endpoint: 'start' },
      ],
    },
    {
      junctionId: 'j2', controlId: 'c2', name: 'Controller junction',
      pathwayRelationships: [
        { pathwayId: 'p', endpoint: 'end' },
        { pathwayId: 'p4', endpoint: 'start' },
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

  assert.equal(definition.schemaVersion, 22);
  assert.equal(Object.hasOwn(definition, 'cables'), false);
  assert.equal(Object.hasOwn(definition, 'profiles'), false);
  assert.deepEqual(
    Array.from(context.relationshipPathwayGroups(definition, 'p'), (group) => group.cableGroupId),
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

  assert.deepEqual(Array.from(ends, (end) => end.cableGroupId), ['g1', 'g2', 'g3']);
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
  const refreshedStack = descendants(
    context.ui.editor, (node) => node.className === 'relationship-pathway-stack',
  )[0];
  assert.equal(descendants(
    context.ui.editor,
    (node) => node.className === 'relationship-topology-edges',
  ).length, 1);
  assert.equal(refreshedStack.dataset.diagramRouteCacheHit, 'false');
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
  const overlay = descendants(
    stack, (node) => node.className === 'relationship-topology-edges',
  )[0];
  assert.equal(overlay.style.width, stack.style.width);
  assert.equal(overlay.style.height, stack.style.height);
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
  const organizedRoutes = descendants(
    stack, (node) => node.className === 'structural-trace',
  ).map((route) => [route.attributes.d, route.dataset.routePoints]);
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
  assert.equal(refreshedStack.dataset.diagramLayoutCandidateCount, '1');
  assert.equal(refreshedStack.dataset.diagramRouteCacheHit, 'true');
  assert.deepEqual(descendants(
    refreshedStack, (node) => node.className === 'structural-trace',
  ).map((route) => [route.attributes.d, route.dataset.routePoints]), organizedRoutes);
  assert.equal(refreshedStage.style.transform, organizedTransform);
});

test('master diagram restores its complete view across palette reopen', () => {
  const storage = new Map();
  const definition = harness();
  for (let index = 2; index <= 6; index += 1) {
    definition.pathways.push({
      pathwayId: `p${index}`, name: `Pathway ${index}`, startName: 'A', endName: 'B',
      orderedControlIds: [],
    });
  }
  const first = palette(storage).context;
  const diagram = first.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { workspace, toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);
  viewport.clientWidth = 420;
  viewport.clientHeight = 1800;
  toolbar.children[0].events.click();
  toolbar.children[3].events.click();
  const layoutKey = stack.dataset.diagramLayoutKey;
  const transform = workspace.children[1].children[0].style.transform;
  assert.match(layoutKey, /^horizontal\|/);

  const second = palette(storage).context;
  const reopened = second.renderRelationshipMap(definition);
  const reopenedParts = relationshipWorkspaceParts(reopened);

  assert.equal(reopened.dataset.hasSavedDiagramView, 'true');
  assert.equal(reopenedParts.stack.dataset.diagramLayoutKey, layoutKey);
  assert.equal(reopenedParts.workspace.children[1].children[0].style.transform, transform);
  reopenedParts.toolbar.children[0].events.click();
  assert.match(reopenedParts.stack.dataset.diagramLayoutKey, /^vertical\|/);
  assert.equal(reopenedParts.stack.dataset.diagramLayoutCandidateIndex, '0');
  assert.equal(
    [...storage.keys()].filter((key) => key.startsWith(
      'cableBundler.relationshipDiagramView:',
    )).length,
    1,
  );

  const otherDefinition = { ...harness(), harnessId: 'other-harness' };
  const otherDiagram = second.renderRelationshipMap(otherDefinition);
  assert.equal(otherDiagram.dataset.hasSavedDiagramView, 'false');
  assert.equal(
    [...storage.keys()].filter((key) => key.startsWith(
      'cableBundler.relationshipDiagramView:',
    )).length,
    2,
  );
});

test('master diagram rejects malformed or obsolete session views', () => {
  const definition = harness();
  const diagramViewKey = definition.harnessId;
  const storageKey = `cableBundler.relationshipDiagramView:${encodeURIComponent(diagramViewKey)}`;
  const invalidViews = [
    '{broken',
    JSON.stringify({
      contractVersion: '9', layoutKey: 'old', scale: 1, offsetX: 12, offsetY: 12,
    }),
    JSON.stringify({
      contractVersion: '10', layoutKey: 'partial', scale: 1, offsetX: 12,
    }),
  ];

  invalidViews.forEach((stored) => {
    const storage = new Map([[storageKey, stored]]);
    const { context } = palette(storage);
    assert.equal(context.readRelationshipDiagramView(diagramViewKey), undefined);
    assert.equal(storage.has(storageKey), false);
  });
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

test('master diagram redraw selects the deterministic best fit instead of cycling', () => {
  const { context } = palette();
  const definition = branchingHarness();
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);

  viewport.clientWidth = 1900;
  viewport.clientHeight = 850;
  toolbar.children[0].events.click();
  const layoutKey = stack.dataset.diagramLayoutKey;
  const geometry = descendants(
    stack, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).map((node) => [node.dataset.nodeId, node.style.left, node.style.top]);

  assert.ok(Number(stack.dataset.diagramLayoutCandidateCount) >= 1);
  assert.equal(stack.dataset.diagramLayoutCandidateIndex, '0');
  toolbar.children[0].events.click();
  assert.equal(stack.dataset.diagramLayoutKey, layoutKey);
  assert.deepEqual(descendants(
    stack, (node) => node.className?.split(' ').includes('relationship-topology-node'),
  ).map((node) => [node.dataset.nodeId, node.style.left, node.style.top]), geometry);
});

test('master diagram redraw adapts to viewport aspect and maximizes contained zoom', () => {
  const { context } = palette();
  const definition = harness();
  definition.pathways.push(
    { pathwayId: 'p2', name: 'Pathway 002', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p3', name: 'Pathway 003', startName: 'A', endName: 'B',
      orderedControlIds: [] },
    { pathwayId: 'p4', name: 'Pathway 004', startName: 'A', endName: 'B',
      orderedControlIds: [] },
  );
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { workspace, toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);
  const stage = workspace.children[1].children[0];

  viewport.clientWidth = 1300;
  viewport.clientHeight = 300;
  toolbar.children[0].events.click();
  const wideLayoutKey = stack.dataset.diagramLayoutKey;
  const wideAspect = Number.parseFloat(stack.style.width)
    / Number.parseFloat(stack.style.height);

  viewport.clientWidth = 300;
  viewport.clientHeight = 1300;
  toolbar.children[0].events.click();
  const tallLayoutKey = stack.dataset.diagramLayoutKey;
  const tallAspect = Number.parseFloat(stack.style.width)
    / Number.parseFloat(stack.style.height);
  assert.ok(wideAspect > tallAspect, JSON.stringify({
    wideAspect, tallAspect, wideLayoutKey, tallLayoutKey,
  }));
  assert.notEqual(tallLayoutKey, wideLayoutKey);
  assert.equal(stack.dataset.diagramLayoutCandidateIndex, '0');

  stage.scrollWidth = Number.parseFloat(stack.style.width);
  stage.scrollHeight = Number.parseFloat(stack.style.height);
  toolbar.children[0].events.click();
  const expectedScale = Math.min(
    1,
    (viewport.clientWidth - 24) / stage.scrollWidth,
    (viewport.clientHeight - 24) / stage.scrollHeight,
  );
  const transform = stage.style.transform;
  const match = transform.match(/translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\)/);
  assert.ok(match);
  assert.equal(Number(match[3]), expectedScale);
  assert.equal(Number(match[1]), Math.max(
    12, (viewport.clientWidth - stage.scrollWidth * expectedScale) / 2,
  ));
  assert.equal(Number(match[2]), Math.max(
    12, (viewport.clientHeight - stage.scrollHeight * expectedScale) / 2,
  ));

  viewport.clientWidth = 4000;
  viewport.clientHeight = 3000;
  toolbar.children[0].events.click();
  stage.scrollWidth = Number.parseFloat(stack.style.width);
  stage.scrollHeight = Number.parseFloat(stack.style.height);
  toolbar.children[0].events.click();
  assert.match(stage.style.transform, /scale\(1\)$/);
  assert.equal(toolbar.children[2].textContent, '100%');
});

test('master diagram maximizes zoom for a near-square twin-hub topology', () => {
  const { context } = palette();
  const definition = twinHubHarness();
  const diagram = context.renderRelationshipMap(definition);
  sizeRelationshipNodes(diagram);
  const { toolbar, viewport, stack } = relationshipWorkspaceParts(diagram);

  viewport.clientWidth = 1500;
  viewport.clientHeight = 1400;
  toolbar.children[0].events.click();

  assert.match(stack.dataset.diagramLayoutKey, /^vertical\|/);
  assert.equal(stack.relationshipLayoutCandidates[0].fitScale, 1);
  assert.ok(Number.parseFloat(stack.style.width) <= viewport.clientWidth - 24);
  assert.ok(Number.parseFloat(stack.style.height) <= viewport.clientHeight - 24);
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
      Number(path.parentElement.dataset.cableGroupCount),
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
