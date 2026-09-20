/** Developer-only relationship-diagram observation and QA bridge. */

function qaHasReadableBox(node) {
  if (!node?.getBoundingClientRect) return false;
  if (node.getClientRects && node.getClientRects().length === 0) return false;
  const rect = node.getBoundingClientRect();
  return [rect.left, rect.top, rect.right, rect.bottom, rect.width, rect.height]
    .every(Number.isFinite) && rect.width >= 16 && rect.height >= 12;
}

function qaRelationshipEdgeGap(edge) {
  const siblings = Array.from(edge.parentElement?.children || [])
    .filter((candidate) => typeof candidate?.getBoundingClientRect === "function");
  const edgeIndex = siblings.indexOf(edge);
  if (edgeIndex <= 0 || edgeIndex >= siblings.length - 1) return Number.POSITIVE_INFINITY;
  const previousRect = siblings[edgeIndex - 1].getBoundingClientRect();
  const edgeRect = edge.getBoundingClientRect();
  const nextRect = siblings[edgeIndex + 1].getBoundingClientRect();
  return Math.max(
    0,
    edgeRect.left - previousRect.right,
    nextRect.left - edgeRect.right,
  );
}

function qaTopologyEdgeGap(edge, diagram) {
  if (typeof edge.getTotalLength !== "function"
      || typeof edge.getPointAtLength !== "function"
      || typeof edge.getScreenCTM !== "function") return Number.POSITIVE_INFINITY;
  const endpoint = edge.dataset.endpoint;
  const pathway = diagram.querySelector(
    `.relationship-topology-pathway[data-pathway-id="${edge.dataset.pathwayId}"]`,
  );
  const junction = diagram.querySelector(
    `.relationship-topology-junction[data-junction-id="${edge.dataset.junctionId}"]`,
  );
  if (!pathway || !junction) return Number.POSITIVE_INFINITY;
  const pathwayEnd = pathway?.querySelector?.(
    `.relationship-end-list[data-endpoint="${endpoint === "end" ? "end" : "start"}"]`,
  ) || pathway;
  const source = endpoint === "end" ? pathwayEnd : junction;
  const target = endpoint === "end" ? junction : pathwayEnd;
  const matrix = edge.getScreenCTM();
  if (!matrix) return Number.POSITIVE_INFINITY;
  const project = (point) => ({
    x: matrix.a * point.x + matrix.c * point.y + matrix.e,
    y: matrix.b * point.x + matrix.d * point.y + matrix.f,
  });
  const start = project(edge.getPointAtLength(0));
  const finish = project(edge.getPointAtLength(edge.getTotalLength()));
  const sourceRect = source.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const sideGap = (point, rectangle, side) => {
    if (!["left", "right", "top", "bottom"].includes(side)) {
      return Number.POSITIVE_INFINITY;
    }
    if (["left", "right"].includes(side)) {
      const sideX = side === "left" ? rectangle.left : rectangle.right;
      return Math.max(
        Math.abs(point.x - sideX),
        Math.max(0, rectangle.top - point.y, point.y - rectangle.bottom),
      );
    }
    const sideY = side === "top" ? rectangle.top : rectangle.bottom;
    return Math.max(
      Math.abs(point.y - sideY),
      Math.max(0, rectangle.left - point.x, point.x - rectangle.right),
    );
  };
  return Math.max(
    sideGap(start, sourceRect, edge.parentElement?.dataset.sourceSide),
    sideGap(finish, targetRect, edge.parentElement?.dataset.targetSide),
  );
}

function qaTopologyTraceClearance(edge, diagram) {
  const nodes = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-node") || [],
  ).filter((node) => {
    if (node.dataset.pathwayId === edge.dataset.pathwayId) return false;
    return node.dataset.junctionId !== edge.dataset.junctionId;
  });
  const cableTraces = Array.from(
    edge.parentElement?.querySelectorAll?.(".cable-trace") || [],
  );
  const renderedPaths = cableTraces.length ? cableTraces : [edge];
  let minimumClearance = Number.POSITIVE_INFINITY;
  renderedPaths.forEach((path) => {
    if (typeof path.getTotalLength !== "function"
        || typeof path.getPointAtLength !== "function"
        || typeof path.getScreenCTM !== "function") return;
    const matrix = path.getScreenCTM();
    if (!matrix) return;
    const length = path.getTotalLength();
    const sampleCount = Math.max(2, Math.ceil(length / 4));
    const scale = Math.max(Math.hypot(matrix.a, matrix.b), Number.EPSILON);
    const isBundle = path.className?.baseVal?.split(" ").includes(
      "relationship-cable-bundle",
    ) || path.className?.split?.(" ").includes("relationship-cable-bundle");
    const traceHalfExtent = isBundle ? 5 : 3;
    for (let index = 0; index <= sampleCount; index += 1) {
      const point = path.getPointAtLength(length * index / sampleCount);
      const projected = {
        x: matrix.a * point.x + matrix.c * point.y + matrix.e,
        y: matrix.b * point.x + matrix.d * point.y + matrix.f,
      };
      nodes.forEach((node) => {
        const rectangle = node.getBoundingClientRect();
        const horizontalDistance = Math.max(
          rectangle.left - projected.x,
          0,
          projected.x - rectangle.right,
        );
        const verticalDistance = Math.max(
          rectangle.top - projected.y,
          0,
          projected.y - rectangle.bottom,
        );
        const clearance = Math.hypot(horizontalDistance, verticalDistance) / scale
          - traceHalfExtent;
        minimumClearance = Math.min(minimumClearance, clearance);
      });
    }
  });
  return minimumClearance;
}

function qaTopologyTraceObstructed(edge, diagram) {
  return qaTopologyTraceClearance(edge, diagram) < RELATIONSHIP_DIAGRAM_SPACING - 1;
}

function qaRelationshipVisualBounds(node) {
  const descendants = [
    ".relationship-pathway-hub", ".relationship-end-list", ".relationship-junction-hub",
  ].flatMap((selector) => Array.from(node.querySelectorAll?.(selector) || []));
  return [node, ...descendants].reduce((bounds, element) => {
    const rectangle = element.getBoundingClientRect();
    if (!rectangle.width || !rectangle.height) return bounds;
    return {
      left: Math.min(bounds.left, rectangle.left),
      right: Math.max(bounds.right, rectangle.right),
      top: Math.min(bounds.top, rectangle.top),
      bottom: Math.max(bounds.bottom, rectangle.bottom),
    };
  }, { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity });
}

function qaRelationshipVisualOverlapCount(nodes) {
  const bounds = nodes.map(qaRelationshipVisualBounds);
  return bounds.reduce((count, rectangle, index) => count + bounds.slice(index + 1)
    .filter((other) => (
      rectangle.left < other.right - 1
      && rectangle.right > other.left + 1
      && rectangle.top < other.bottom - 1
      && rectangle.bottom > other.top + 1
    )).length, 0);
}

function qaRelationshipVisibleOverflowCount(nodes) {
  return nodes.filter((node) => {
    const wrapper = node.getBoundingClientRect();
    const visible = qaRelationshipVisualBounds(node);
    return visible.left < wrapper.left - 1 || visible.right > wrapper.right + 1
      || visible.top < wrapper.top - 1 || visible.bottom > wrapper.bottom + 1;
  }).length;
}

function qaInvalidTraceGroupCount(diagram) {
  const edges = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-edge") || [],
  );
  const ports = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-port") || [],
  );
  const attribute = (node, name) => (
    node?.getAttribute?.(name) ?? node?.attributes?.[name] ?? ""
  );
  const portFor = (portId) => ports.find((port) => port.dataset.portId === portId);
  const invalidEdges = edges.filter((edge) => {
    const groupCount = Number.parseInt(edge.dataset.cableGroupCount, 10);
    const mode = edge.dataset.renderMode;
    const lanes = Array.from(edge.querySelectorAll?.(".relationship-cable-lane") || []);
    const bundles = Array.from(edge.querySelectorAll?.(".relationship-cable-bundle") || []);
    const badges = Array.from(edge.querySelectorAll?.(".relationship-cable-count") || []);
    const groupIds = relationshipElementGroupIds(edge);
    const expectedMode = groupCount === 0
      ? "structure" : groupCount <= TOPOLOGY_LANE_LIMIT ? "lanes" : "bundle";
    if (!Number.isInteger(groupCount) || groupCount < 0 || groupIds.size !== groupCount
        || mode !== expectedMode) return true;
    if (mode === "structure" && (lanes.length || bundles.length || badges.length)) return true;
    if (mode === "lanes") {
      const offsets = lanes.map((lane) => Number.parseFloat(lane.dataset.laneOffset));
      const expectedOffsets = lanes.map((_lane, index) => (
        (index - (groupCount - 1) / 2) * TOPOLOGY_LANE_SPACING
      ));
      if (lanes.length !== groupCount || bundles.length || badges.length
          || offsets.some((offset) => !Number.isFinite(offset))
          || offsets.some((offset, index) => offset !== expectedOffsets[index])) return true;
    }
    if (mode === "bundle" && (lanes.length || bundles.length !== 1 || badges.length !== 1)) {
      return true;
    }
    const sourcePort = portFor(edge.dataset.sourcePortId);
    const targetPort = portFor(edge.dataset.targetPortId);
    if (!sourcePort || !targetPort) return true;
    if (sourcePort.dataset.nodeId !== edge.dataset.sourceId
        || targetPort.dataset.nodeId !== edge.dataset.targetId
        || sourcePort.dataset.side !== edge.dataset.sourceSide
        || targetPort.dataset.side !== edge.dataset.targetSide) return true;
    if (mode !== "lanes") return false;
    return lanes.some((lane) => {
      const endpoints = [{
        x: Number.parseFloat(attribute(lane, "data-source-x")),
        y: Number.parseFloat(attribute(lane, "data-source-y")),
      }, {
        x: Number.parseFloat(attribute(lane, "data-target-x")),
        y: Number.parseFloat(attribute(lane, "data-target-y")),
      }];
      return [sourcePort, targetPort].some((port, index) => {
        const portLeft = Number.parseFloat(attribute(port, "x"));
        const portTop = Number.parseFloat(attribute(port, "y"));
        const portWidth = Number.parseFloat(attribute(port, "width"));
        const portHeight = Number.parseFloat(attribute(port, "height"));
        const laneX = endpoints[index].x;
        const laneY = endpoints[index].y;
        return laneX < portLeft || laneX > portLeft + portWidth
          || laneY < portTop || laneY > portTop + portHeight;
      });
    });
  });
  return Number(invalidEdges.length);
}

/** Parse a nonnegative QA dataset number, using a reload-safe fallback. */
function qaNonnegativeNumber(value, fallback) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

/** Parse a nonnegative QA dataset integer, using a reload-safe fallback. */
function qaNonnegativeInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function qaObserveRelationshipDiagram() {
  const selectedHarness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  const hasDiagramNode = (candidate) => (
    candidate?.pathways?.length || candidate?.junctions?.length
  );
  const harness = hasDiagramNode(selectedHarness)
    ? selectedHarness : currentState.harnesses.find(hasDiagramNode);
  if (!harness) {
    void send("qa_diagram_observation", {
      status: "skipped",
      connectorCount: 0,
      maximumEndpointGap: 0,
      minimumUnrelatedTraceGap: RELATIONSHIP_DIAGRAM_SPACING,
      minimumParallelTraceGap: TOPOLOGY_ROUTE_CHANNEL_SPACING,
      overlappingTracePairCount: 0,
      obstructedTraceCount: 0,
      portCount: 0,
      topologyEdgeCount: 0,
      expectedTopologyEdgeCount: 0,
      invalidTraceGroupCount: 0,
      layoutRevision: 0,
      layoutError: false,
      redrawCompleted: true,
      layoutChanged: true,
      layoutCandidateCount: 0,
      layoutCandidateIndex: 0,
      visualOverlapCount: 0,
      visibleOverflowCount: 0,
      contractVersion: RELATIONSHIP_DIAGRAM_CONTRACT_VERSION,
      layout: RELATIONSHIP_DIAGRAM_LAYOUT,
    }).catch(() => {});
    return "OK";
  }
  openHarness(harnessKey(harness));
  const section = ui.editor.querySelector('[data-section="master-relationship-graphic"]');
  if (section) section.open = true;
  const filter = Array.from(section?.querySelectorAll("input") || []).find(
    (candidate) => candidate.getAttribute?.("aria-label") === "Filter master relationship graphic"
      || candidate.attributes?.["aria-label"] === "Filter master relationship graphic",
  );
  if (filter?.value) {
    filter.value = "";
    filter.dispatchEvent(new window.Event("input"));
  }
  const stackBeforeRedraw = section?.querySelector?.(".relationship-pathway-stack");
  const revisionBeforeRedraw = Number.parseInt(
    stackBeforeRedraw?.dataset.diagramLayoutRevision || "0", 10,
  );
  const layoutKeyBeforeRedraw = stackBeforeRedraw?.dataset.diagramLayoutKey || "";
  const redrawButton = Array.from(
    section?.querySelectorAll?.(".block-diagram-toolbar button") || [],
  ).find((candidate) => candidate.textContent === "Redraw");
  redrawButton?.click();
  window.requestAnimationFrame(() => {
    const diagram = ui.editor.querySelector(".relationship-map");
    const workspace = diagram?.querySelector?.(".block-diagram-workspace");
    const pathwayGroups = Array.from(
      diagram?.querySelectorAll?.(".relationship-pathway-group") || [],
    );
    const pathwayHubs = Array.from(
      diagram?.querySelectorAll?.(".relationship-pathway-hub") || [],
    );
    const junctionHubs = Array.from(
      diagram?.querySelectorAll?.(".relationship-junction-hub") || [],
    );
    const connectorEdges = [
      ...Array.from(diagram?.querySelectorAll?.(".relationship-connector") || []),
      ...Array.from(diagram?.querySelectorAll?.(".relationship-chain-link") || []),
    ];
    const topologyEdges = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-edges .structural-trace") || [],
    );
    const topologyNodes = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-node") || [],
    );
    const topologyPorts = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-port") || [],
    );
    const topologyStack = diagram?.querySelector?.(".relationship-pathway-stack");
    const expectedTopologyEdgeCount = (harness.junctions || []).reduce(
      (count, junction) => count + (junction.pathwayRelationships || []).length,
      0,
    );
    const topologyEdgeCount = topologyEdges.length;
    const layoutRevision = Number.parseInt(
      topologyStack?.dataset.diagramLayoutRevision || "0", 10,
    );
    const layoutError = Boolean(topologyStack?.dataset.diagramLayoutError);
    const redrawCompleted = Boolean(redrawButton) && layoutRevision > revisionBeforeRedraw;
    const layoutCandidateCount = Number.parseInt(
      topologyStack?.dataset.diagramLayoutCandidateCount || "0", 10,
    );
    const layoutCandidateIndex = Number.parseInt(
      topologyStack?.dataset.diagramLayoutCandidateIndex || "0", 10,
    );
    const layoutChanged = layoutCandidateCount <= 1
      || topologyStack?.dataset.diagramLayoutKey !== layoutKeyBeforeRedraw;
    const paths = Array.from(diagram?.querySelectorAll?.("path") || []);
    const connectorCount = paths.length;
    const endpointGaps = [
      ...connectorEdges.map(qaRelationshipEdgeGap),
      ...topologyEdges.map((edge) => qaTopologyEdgeGap(edge, diagram)),
    ];
    const maximumEndpointGap = endpointGaps.length ? Math.max(...endpointGaps) : 0;
    const traceClearances = topologyEdges
      .map((edge) => qaTopologyTraceClearance(edge, diagram))
      .filter(Number.isFinite);
    const minimumUnrelatedTraceGap = traceClearances.length
      ? Math.max(0, Math.min(...traceClearances))
      : RELATIONSHIP_DIAGRAM_SPACING;
    const obstructedTraceCount = traceClearances.filter(
      (clearance) => clearance < RELATIONSHIP_DIAGRAM_SPACING - 1,
    ).length;
    const minimumParallelTraceGap = qaNonnegativeNumber(
      topologyStack?.dataset.minimumParallelTraceGap,
      TOPOLOGY_ROUTE_CHANNEL_SPACING,
    );
    const overlappingTracePairCount = qaNonnegativeInteger(
      topologyStack?.dataset.overlappingTracePairCount,
      0,
    );
    const invalidTraceGroupCount = qaInvalidTraceGroupCount(diagram);
    const visualOverlapCount = qaRelationshipVisualOverlapCount(topologyNodes);
    const visibleOverflowCount = qaRelationshipVisibleOverflowCount(topologyNodes);
    const contractVersion = diagram?.dataset.diagramContractVersion || "";
    const layout = diagram?.dataset.diagramLayout || "";
    const passed = Boolean(workspace)
      && pathwayGroups.length === harness.pathways.length
      && pathwayHubs.length === harness.pathways.length
      && junctionHubs.length === (harness.junctions || []).length
      && (harness.pathways.length === 0 || connectorEdges.length > 0)
      && maximumEndpointGap <= 1
      && obstructedTraceCount === 0
      && minimumParallelTraceGap >= TOPOLOGY_ROUTE_CHANNEL_SPACING - 1
      && overlappingTracePairCount === 0
      && topologyEdgeCount === expectedTopologyEdgeCount
      && topologyPorts.length === topologyEdgeCount * 2
      && invalidTraceGroupCount === 0
      && Number.isFinite(layoutRevision)
      && layoutRevision > 0
      && !layoutError
      && redrawCompleted
      && visualOverlapCount === 0
      && visibleOverflowCount === 0
      && contractVersion === RELATIONSHIP_DIAGRAM_CONTRACT_VERSION
      && layout === RELATIONSHIP_DIAGRAM_LAYOUT
      && paths.every((path) => Boolean(path.getAttribute?.("d") || path.attributes?.d));
    section?.scrollIntoView({ block: "center" });
    void send("qa_diagram_observation", {
      status: passed ? "passed" : "failed",
      connectorCount,
      maximumEndpointGap,
      minimumUnrelatedTraceGap,
      minimumParallelTraceGap,
      overlappingTracePairCount,
      obstructedTraceCount,
      portCount: topologyPorts.length,
      topologyEdgeCount,
      expectedTopologyEdgeCount,
      invalidTraceGroupCount,
      layoutRevision,
      layoutError,
      redrawCompleted,
      layoutChanged,
      layoutCandidateCount,
      layoutCandidateIndex,
      visualOverlapCount,
      visibleOverflowCount,
      contractVersion,
      layout,
    }).catch(() => {});
  });
  return "OK";
}
function handleQaProbe(data) {
  if (!developerModeEnabled) return "DENIED";
  let payload;
  try {
    payload = JSON.parse(data);
  } catch (_error) {
    return "INVALID";
  }
  if (payload?.operation === "observe_relationship_diagram") {
    return qaObserveRelationshipDiagram();
  }
  return "INVALID";
}

