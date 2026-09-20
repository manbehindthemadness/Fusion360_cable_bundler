/** Candidate routing, selection, state restoration, and layout orchestration. */

const RELATIONSHIP_ROUTE_CACHE_LIMIT = TOPOLOGY_ROUTED_CANDIDATE_LIMIT * 3;

function applyRelationshipLayoutGeometry(components, layout) {
  const geometryById = new Map(layout.geometryComponents.flatMap(
    (component) => component.nodes.map((node) => [node.id, node]),
  ));
  components.forEach((component) => component.nodes.forEach((node) => {
    const geometry = geometryById.get(node.id);
    node.width = geometry.width;
    node.height = geometry.height;
    node.dockPoints = geometry.dockPoints;
    node.hubCenter = geometry.hubCenter;
    node.left = geometry.left;
    node.top = geometry.top;
    if (node.kind === "pathway") {
      node.dockSides = geometry.dockSides;
      configureRelationshipPathwayDocking(
        relationshipPathwayGroup(node), node.dockSides.start, node.dockSides.end,
        node.intrinsicEndpointSizes,
      );
    }
    node.element.style.left = `${node.left}px`;
    node.element.style.top = `${node.top}px`;
    node.element.style.width = `${node.width}px`;
    node.element.style.height = `${node.height}px`;
  }));
}

function relationshipLayoutRouteSets(components, harness) {
  return components.map((component) => {
    const routingContext = createRelationshipRoutingContext(component.nodes);
    const edgeGroups = relationshipLayoutEdgeGroups(component, harness);
    const candidates = [
      { reverseOrder: false, portMode: "fan" },
      { reverseOrder: true, portMode: "fan" },
      { reverseOrder: false, portMode: "spread" },
      { reverseOrder: true, portMode: "spread" },
      { reverseOrder: false, portMode: "aligned" },
      { reverseOrder: true, portMode: "aligned" },
    ].map(({ reverseOrder, portMode }) => {
      const ports = allocateRelationshipPorts(component, reverseOrder, portMode);
      const routes = routeRelationshipEdges(component, ports, edgeGroups, routingContext);
      return { component, ports, edgeGroups, routes,
        quality: topologyRouteSetQuality(routes) };
    }).sort((left, right) => (
      compareTopologyRouteQuality(left.quality, right.quality)
    ));
    return candidates[0];
  });
}

function relationshipLayoutEdgeGroups(component, harness) {
  return new Map(component.edges.map((edge) => [
    relationshipEdgeId(edge),
    relationshipEndpointGroups(harness, edge.junction, edge.relationship),
  ]));
}

/** Describe every routing input that can change the exact path geometry. */
function relationshipLayoutRouteFingerprint(components, harness, layoutKey) {
  return JSON.stringify({
    layoutKey,
    components: components.map((component) => ({
      nodes: component.nodes.map((node) => ({
        id: node.id,
        left: node.left,
        top: node.top,
        width: node.width,
        height: node.height,
        dockSides: node.dockSides || null,
      })),
      edges: component.edges.map((edge) => {
        const edgeId = relationshipEdgeId(edge);
        return [
          edgeId,
          relationshipEndpointGroups(harness, edge.junction, edge.relationship)
            .map((group) => group.cableGroupId).sort(),
        ];
      }),
    })),
  });
}

/** Return exact route geometry from the per-view session cache when inputs match. */
function cachedRelationshipLayoutRouteSets(cacheKey, components, harness, layoutKey) {
  if (!cacheKey) return null;
  const cache = relationshipLayoutRouteCache.get(cacheKey);
  const fingerprint = relationshipLayoutRouteFingerprint(components, harness, layoutKey);
  const cached = cache?.get(fingerprint);
  if (!cached) return null;
  cache.delete(fingerprint);
  cache.set(fingerprint, cached);
  return components.map((component, index) => ({
    component,
    edgeGroups: relationshipLayoutEdgeGroups(component, harness),
    ports: cached.routeSets[index].ports,
    routes: cached.routeSets[index].routes,
    quality: cached.routeSets[index].quality,
  }));
}

/** Retain an exact routed candidate in a small per-view least-recently-used cache. */
function rememberRelationshipLayoutRoutes(cacheKey, layout, harness) {
  if (!cacheKey) return;
  if (!relationshipLayoutRouteCache.has(cacheKey)) {
    relationshipLayoutRouteCache.set(cacheKey, new Map());
  }
  const cache = relationshipLayoutRouteCache.get(cacheKey);
  const fingerprint = relationshipLayoutRouteFingerprint(
    layout.geometryComponents, harness, layout.layoutKey,
  );
  cache.delete(fingerprint);
  cache.set(fingerprint, {
    routeSets: layout.routeSets.map(({ ports, routes, quality }) => ({
      ports, routes, quality,
    })),
  });
  while (cache.size > RELATIONSHIP_ROUTE_CACHE_LIMIT) {
    cache.delete(cache.keys().next().value);
  }
}

function compareRelationshipLayouts(left, right) {
  return compareTopologyRouteSafety(left.routeQuality, right.routeQuality)
    || right.fitScale - left.fitScale
    || left.width * left.height - right.width * right.height
    || (left.width + left.height) - (right.width + right.height)
    || left.routeQuality.shortSegments - right.routeQuality.shortSegments
    || left.routeQuality.excessLength - right.routeQuality.excessLength
    || left.routeQuality.bends - right.routeQuality.bends
    || left.routeQuality.totalLength - right.routeQuality.totalLength
    || left.edgeLength - right.edgeLength
    || left.layoutKey.localeCompare(right.layoutKey);
}

function compareRelationshipLayoutGeometry(left, right) {
  return left.crossings - right.crossings
    || right.fitScale - left.fitScale
    || left.width * left.height - right.width * right.height
    || (left.width + left.height) - (right.width + right.height)
    || left.edgeLength - right.edgeLength
    || left.layoutKey.localeCompare(right.layoutKey);
}

function relationshipLayoutIsSafe(candidate) {
  return candidate
    && candidate.routeQuality.overlaps === 0
    && candidate.routeQuality.parallelConflicts === 0
    && candidate.routeQuality.crossings === 0;
}

/** Route a requested committed layout without exploring unrelated alternatives. */
function preferredRelationshipLayoutCandidate(layouts, routeLayout, preferredKey) {
  if (!preferredKey) return null;
  const preferred = layouts.find((layout) => layout.layoutKey === preferredKey);
  if (!preferred) return null;
  const candidate = routeLayout(preferred);
  return relationshipLayoutIsSafe(candidate) ? candidate : null;
}

/** Route the compact shortlist plus any requested previously committed layout. */
function routeRelationshipLayoutPool(layouts, routeLayout, shortlistSize, preferredKey = "") {
  const candidates = [];
  const attempt = (items) => items.forEach((layout) => {
    const candidate = routeLayout(layout);
    if (candidate) candidates.push(candidate);
  });
  const preliminary = layouts.slice(0, shortlistSize);
  const preferred = layouts.find((layout) => layout.layoutKey === preferredKey);
  if (preferred && !preliminary.includes(preferred)) preliminary.push(preferred);
  attempt(preliminary);
  if (!candidates.length && preliminary.length < layouts.length) {
    attempt(layouts.filter((layout) => !preliminary.includes(layout)));
  }
  return candidates;
}

/** Return every routable packing in deterministic visual-quality order. */
function relationshipLayoutCandidates(components, harness, options = {}) {
  const specifications = relationshipLayoutSpecifications(components);
  const layouts = specifications.map((specification) => {
    const layout = relationshipTopologyLayoutCandidate(components, specification, options);
    layout.fitScale = Math.min(1,
      Math.max(1, (options.width || layout.width) - 24) / layout.width,
      Math.max(1, (options.height || layout.height) - 24) / layout.height);
    return layout;
  }).sort(compareRelationshipLayoutGeometry);
  const shortlistSize = Math.min(TOPOLOGY_ROUTED_CANDIDATE_LIMIT, layouts.length);
  const routeLayout = (layout) => {
    layout.geometryComponents = materializeRelationshipLayout(components, layout);
    const cachedRouteSets = cachedRelationshipLayoutRouteSets(
      options.routeCacheKey, layout.geometryComponents, harness, layout.layoutKey,
    );
    try {
      layout.routeSets = cachedRouteSets
        || relationshipLayoutRouteSets(layout.geometryComponents, harness);
    } catch (_error) {
      return null;
    }
    layout.routeCacheHit = Boolean(cachedRouteSets);
    if (!cachedRouteSets) {
      rememberRelationshipLayoutRoutes(options.routeCacheKey, layout, harness);
    }
    const routes = new Map(layout.routeSets.flatMap((routeSet) => [...routeSet.routes]));
    layout.routeQuality = topologyRouteSetQuality(routes);
    return layout;
  };
  const preferredCandidate = preferredRelationshipLayoutCandidate(
    layouts, routeLayout, options.layoutKey,
  );
  if (preferredCandidate) return [preferredCandidate];
  const candidates = routeRelationshipLayoutPool(
    layouts, routeLayout, shortlistSize, options.layoutKey,
  );
  if (!candidates.length) throw new Error("Unable to produce a routed relationship layout.");
  const safe = candidates.filter(relationshipLayoutIsSafe).sort(compareRelationshipLayouts);
  if (!safe.length) {
    const bestUnsafe = candidates.sort(compareRelationshipLayouts)[0];
    throw new Error(`No relationship layout satisfies trace safety rules (${JSON.stringify(
      bestUnsafe?.routeQuality || {},
    )}).`);
  }
  const best = safe[0];
  const maximumArea = best.width * best.height * 1.15;
  const minimumFitScale = best.fitScale * 0.95;
  const signatures = new Set();
  const preferred = safe.find((candidate) => candidate.layoutKey === options.layoutKey);
  const filtered = safe.filter((candidate) => {
    if (candidate.width * candidate.height > maximumArea
      || candidate.fitScale < minimumFitScale) return false;
    const signature = components.flatMap((component) => component.nodes.map((node) => {
      const point = candidate.positions.get(node.id);
      const sides = candidate.dockSides.get(node.id);
      return `${node.id}:${Math.round(point.x)}:${Math.round(point.y)}:${
        sides ? `${sides.start}-${sides.end}` : "hub"
      }`;
    })).join("|");
    if (signatures.has(signature)) return false;
    signatures.add(signature);
    return true;
  });
  if (preferred && !filtered.includes(preferred)) filtered.push(preferred);
  return filtered;
}

/** Select the best routed packing from genuinely different deterministic layouts. */
function bestRelationshipLayout(components, harness, options = {}) {
  return relationshipLayoutCandidates(components, harness, options)[0];
}

/** Capture mutable geometry so a failed redraw cannot damage the visible diagram. */
function captureRelationshipLayoutState(stack, components) {
  return {
    stackStyle: { width: stack.style.width, height: stack.style.height },
    stackDataset: {
      diagramRotation: stack.dataset.diagramRotation,
      diagramLayoutKey: stack.dataset.diagramLayoutKey,
      minimumParallelTraceGap: stack.dataset.minimumParallelTraceGap,
      overlappingTracePairCount: stack.dataset.overlappingTracePairCount,
      diagramLayoutRevision: stack.dataset.diagramLayoutRevision,
      diagramLayoutError: stack.dataset.diagramLayoutError,
      diagramLayoutCandidateCount: stack.dataset.diagramLayoutCandidateCount,
      diagramLayoutCandidateIndex: stack.dataset.diagramLayoutCandidateIndex,
      diagramRouteCacheHit: stack.dataset.diagramRouteCacheHit,
    },
    nodes: components.flatMap((component) => component.nodes).map((node) => ({
      node,
      geometry: {
        width: node.width,
        height: node.height,
        left: node.left,
        top: node.top,
        hubCenter: node.hubCenter,
        dockPoints: node.dockPoints,
        dockSides: node.dockSides,
      },
      style: {
        left: node.element.style.left,
        top: node.element.style.top,
        width: node.element.style.width,
        height: node.element.style.height,
      },
    })),
  };
}

/** Restore the last committed geometry after an unsuccessful layout attempt. */
function restoreRelationshipLayoutState(stack, state) {
  Object.assign(stack.style, state.stackStyle);
  Object.entries(state.stackDataset).forEach(([key, value]) => {
    if (value === undefined) delete stack.dataset[key];
    else stack.dataset[key] = value;
  });
  state.nodes.forEach(({ node, geometry, style }) => {
    Object.assign(node, geometry);
    Object.assign(node.element.style, style);
    if (node.kind === "pathway" && geometry.dockSides) {
      configureRelationshipPathwayDocking(
        relationshipPathwayGroup(node), geometry.dockSides.start, geometry.dockSides.end,
        node.intrinsicEndpointSizes,
      );
    }
  });
}

/** Copy routed geometry before a local interaction mutates its visible endpoint. */
function cloneRelationshipRouteSet(routeSet) {
  const ports = routeSet.ports.map((port) => ({
    ...port,
    point: { ...port.point },
  }));
  const portsById = new Map(ports.map((port) => [port.id, port]));
  const routes = new Map([...routeSet.routes].map(([edgeId, route]) => [edgeId, {
    ...route,
    points: route.points.map((point) => ({ ...point })),
    sourcePort: portsById.get(route.sourcePort.id),
    targetPort: portsById.get(route.targetPort.id),
  }]));
  return {
    ...routeSet,
    ports,
    routes,
    edgeElements: new Map(),
    portElements: new Map(),
  };
}

/** Reroute only traces attached to one end list after its visible size changes. */
function updateRelationshipEndpointTraces(stack, pathwayId, endpoint) {
  const pathwayNodeId = `pathway:${pathwayId}`;
  (stack.relationshipRenderedRouteSets || []).forEach((routeSet) => {
    const pathwayNode = routeSet.component.nodes.find((node) => node.id === pathwayNodeId);
    if (!pathwayNode) return;
    const affectedEdges = routeSet.component.edges.filter((edge) => (
      edge.relationship.pathwayId === pathwayId
        && edge.relationship.endpoint === endpoint
    ));
    if (!affectedEdges.length) return;
    const metrics = relationshipPathwayDimensions(pathwayNode, pathwayNode.dockSides);
    const dockPoint = relationshipRenderedDockPoint(pathwayNode, endpoint, metrics);
    const affectedEdgeIds = new Set(affectedEdges.map(relationshipEdgeId));
    const affectedPorts = routeSet.ports.filter((port) => (
      port.nodeId === pathwayNodeId && affectedEdgeIds.has(port.edgeId)
    ));
    const priorPortPoints = new Map(affectedPorts.map((port) => [port.id, port.point]));
    affectedPorts.forEach((port) => {
      port.point = { ...dockPoint };
    });
    const routingContext = createRelationshipRoutingContext(routeSet.component.nodes);
    affectedEdges.forEach((edge) => {
      const edgeId = relationshipEdgeId(edge);
      const priorRoute = routeSet.routes.get(edgeId);
      const occupied = [...routeSet.routes]
        .filter(([otherEdgeId]) => otherEdgeId !== edgeId)
        .flatMap(([, route]) => topologyRouteSegments(route.points).map((segment) => ({
          ...segment,
          halfExtent: route.traceHalfExtent,
        })));
      const route = routeRelationshipEdge(
        priorRoute.sourcePort,
        priorRoute.targetPort,
        routeSet.component.nodes,
        occupied,
        priorRoute.traceHalfExtent,
        routingContext,
      );
      const edgePorts = affectedPorts.filter((port) => port.edgeId === edgeId);
      if (!route) {
        edgePorts.forEach((port) => {
          port.point = priorPortPoints.get(port.id);
        });
        return;
      }
      routeSet.routes.set(edgeId, route);
      edgePorts.forEach((port) => {
        updateRenderedTopologyPort(port, routeSet.portElements.get(port.id));
      });
      const rendered = renderTopologyEdge(
        edge, route, routeSet.edgeGroups.get(edgeId) || [],
      );
      routeSet.edgeElements.get(edgeId).replaceChildren(...rendered.children);
    });
  });
}

/**
 * Position acyclic topology components compactly and draw their edges.
 */
function layoutRelationshipGraph(stack, components, harness, options = {}) {
  const priorState = captureRelationshipLayoutState(stack, components);
  captureRelationshipIntrinsicSizes(components);
  let layouts;
  try {
    layouts = relationshipLayoutCandidates(components, harness, options);
  } catch (error) {
    restoreRelationshipLayoutState(stack, priorState);
    stack.dataset.diagramLayoutError = error.message;
    return null;
  }
  const currentIndex = layouts.findIndex((candidate) => candidate.layoutKey === options.layoutKey);
  const selectedIndex = Math.max(0, currentIndex);
  const layout = layouts[selectedIndex];
  stack.relationshipLayoutCandidates = layouts;
  applyRelationshipLayoutGeometry(components, layout);
  const canvasWidth = layout.width;
  const canvasHeight = layout.height;
  const overlay = svgElement("svg", {
    class: "relationship-topology-edges",
    viewBox: `0 0 ${canvasWidth} ${canvasHeight}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  overlay.style.width = `${canvasWidth}px`;
  overlay.style.height = `${canvasHeight}px`;
  const renderedRouteSets = layout.routeSets.map(cloneRelationshipRouteSet);
  renderedRouteSets.forEach((routeSet) => {
    const {
      component, ports, edgeGroups, routes,
    } = routeSet;
    const nodes = new Map(component.nodes.map((node) => [node.id, node]));
    const portsById = new Map(ports.map((port) => [port.id, port]));
    component.edges.forEach((edge) => {
      const source = nodes.get(edge.sourceId);
      const target = nodes.get(edge.targetId);
      if (!source || !target) return;
      const edgeId = relationshipEdgeId(edge);
      const route = routes.get(edgeId);
      if (!route) return;
      const groups = edgeGroups.get(edgeId) || [];
      const edgeElement = renderTopologyEdge(edge, route, groups);
      routeSet.edgeElements.set(edgeId, edgeElement);
      overlay.append(edgeElement);
      portsById.get(`${edgeId}:source`).groups = groups;
      portsById.get(`${edgeId}:target`).groups = groups;
    });
    ports.forEach((port) => {
      const portElement = renderTopologyPort(port);
      routeSet.portElements.set(port.id, portElement);
      overlay.append(portElement);
    });
  });
  stack.querySelector(".relationship-topology-edges")?.remove();
  stack.insertBefore(overlay, stack.children[0] || null);
  stack.relationshipRenderedRouteSets = renderedRouteSets;
  stack.style.width = `${canvasWidth}px`;
  stack.style.height = `${canvasHeight}px`;
  stack.dataset.diagramRotation = `${layout.rotation}`;
  stack.dataset.diagramLayoutKey = layout.layoutKey;
  stack.dataset.minimumParallelTraceGap = `${Math.max(
    0, layout.routeQuality.minimumParallelGap,
  )}`;
  stack.dataset.overlappingTracePairCount = `${layout.routeQuality.parallelConflicts}`;
  stack.dataset.diagramLayoutCandidateCount = `${layouts.length}`;
  stack.dataset.diagramLayoutCandidateIndex = `${selectedIndex}`;
  stack.dataset.diagramRouteCacheHit = `${Boolean(layout.routeCacheHit)}`;
  stack.dataset.diagramLayoutRevision = `${
    Number.parseInt(priorState.stackDataset.diagramLayoutRevision || "0", 10) + 1
  }`;
  delete stack.dataset.diagramLayoutError;
  return {
    layoutKey: layout.layoutKey,
    rotation: layout.rotation,
    candidateCount: layouts.length,
    candidateIndex: selectedIndex,
  };
}
