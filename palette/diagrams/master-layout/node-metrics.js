/** Rendered node measurement and pathway docking for the master diagram. */

function relationshipPathwayGroup(node) {
  return node.element.children[0];
}

function relationshipEndpointSize(node, endpoint) {
  if (node.intrinsicEndpointSizes) return node.intrinsicEndpointSizes[endpoint];
  const list = relationshipPathwayGroup(node).relationshipEndpointLists[endpoint];
  return relationshipEndListSize(list);
}

/** Return the rendered card footprint for one pair of distinct endpoint docks. */
function relationshipPathwayDimensions(node, dockSides) {
  const metrics = relationshipPathwayDockMetrics(
    relationshipPathwayGroup(node), dockSides.start, dockSides.end,
    node.intrinsicEndpointSizes,
  );
  return {
    ...metrics,
    leftExtent: metrics.columns[0] + metrics.columns[1],
    rightExtent: metrics.columns[3] + metrics.columns[4],
    topExtent: metrics.rows[0] + metrics.rows[1],
    bottomExtent: metrics.rows[3] + metrics.rows[4],
  };
}

function relationshipFallbackDockPoint(node, endpoint, metrics) {
  const point = metrics.docks[endpoint];
  return { x: node.left + point.x, y: node.top + point.y };
}

/** Return the actual outer edge of one rendered endpoint list in diagram coordinates. */
function relationshipRenderedDockPoint(node, endpoint, metrics) {
  const fallback = relationshipFallbackDockPoint(node, endpoint, metrics);
  const list = relationshipPathwayGroup(node).relationshipEndpointLists[endpoint];
  if (typeof node.element.getBoundingClientRect !== "function"
      || typeof list.getBoundingClientRect !== "function") return fallback;
  const nodeRect = node.element.getBoundingClientRect();
  const listRect = list.getBoundingClientRect();
  if (!nodeRect.width || !nodeRect.height || !listRect.width || !listRect.height) {
    return fallback;
  }
  if (nodeRect.width === listRect.width && nodeRect.height === listRect.height) return fallback;
  const scaleX = node.width / nodeRect.width;
  const scaleY = node.height / nodeRect.height;
  const side = node.dockSides[endpoint];
  const screenPoint = {
    left: { x: listRect.left, y: (listRect.top + listRect.bottom) / 2 },
    right: { x: listRect.right, y: (listRect.top + listRect.bottom) / 2 },
    top: { x: (listRect.left + listRect.right) / 2, y: listRect.top },
    bottom: { x: (listRect.left + listRect.right) / 2, y: listRect.bottom },
  }[side];
  return {
    x: node.left + (screenPoint.x - nodeRect.left) * scaleX,
    y: node.top + (screenPoint.y - nodeRect.top) * scaleY,
  };
}

function relationshipNodeDimensions(node, dockSides = null) {
  if (node.kind === "pathway") {
    return relationshipPathwayDimensions(node, dockSides || { start: "left", end: "right" });
  }
  return {
    width: Math.max(154, node.intrinsicNodeSize?.width || node.element.scrollWidth || 0),
    height: Math.max(92, node.intrinsicNodeSize?.height || node.element.scrollHeight || 0),
  };
}

/** Freeze intrinsic visible sizes before candidate orientation can influence the DOM. */
function captureRelationshipIntrinsicSizes(components) {
  components.forEach((component) => component.nodes.forEach((node) => {
    if (node.kind === "pathway") {
      if (node.intrinsicEndpointSizes) return;
      const group = relationshipPathwayGroup(node);
      node.intrinsicEndpointSizes = {
        start: relationshipEndListSize(group.relationshipEndpointLists.start),
        end: relationshipEndListSize(group.relationshipEndpointLists.end),
      };
      return;
    }
    if (node.intrinsicNodeSize) return;
    node.intrinsicNodeSize = {
      width: Math.max(154, node.element.scrollWidth || 0),
      height: Math.max(92, node.element.scrollHeight || 0),
    };
  }));
}

function relationshipPreferredSide(difference, fallback) {
  if (!difference || (!difference.x && !difference.y)) return fallback;
  if (Math.abs(difference.x) >= Math.abs(difference.y)) {
    return difference.x < 0 ? "left" : "right";
  }
  return difference.y < 0 ? "top" : "bottom";
}

/** Choose two distinct endpoint sides that face their connected junctions. */
function relationshipPathwayDockSides(component, node, positions) {
  const differences = { start: [], end: [] };
  component.edges.forEach((edge) => {
    if (edge.relationship.pathwayId !== node.item.pathwayId) return;
    const otherId = edge.sourceId === node.id ? edge.targetId : edge.sourceId;
    const own = positions.get(node.id);
    const other = positions.get(otherId);
    if (!own || !other) return;
    differences[edge.relationship.endpoint].push({
      x: other.x - own.x,
      y: other.y - own.y,
    });
  });
  const average = (values) => values.length ? {
    x: values.reduce((total, value) => total + value.x, 0) / values.length,
    y: values.reduce((total, value) => total + value.y, 0) / values.length,
  } : null;
  const preferred = {
    start: relationshipPreferredSide(average(differences.start), "left"),
    end: relationshipPreferredSide(average(differences.end), "right"),
  };
  const pairs = TOPOLOGY_SIDES.flatMap((start) => TOPOLOGY_SIDES
    .filter((end) => end !== start)
    .map((end) => ({ start, end })));
  const scoreSide = (side, endpoint) => {
    const values = differences[endpoint];
    if (!values.length) return side === preferred[endpoint] ? 0 : 28;
    const vector = topologySideVector(side);
    return values.reduce((total, difference) => {
      const length = Math.hypot(difference.x, difference.y) || 1;
      const alignment = (difference.x * vector.x + difference.y * vector.y) / length;
      return total + (1 - alignment) * 100;
    }, 0);
  };
  return pairs.sort((left, right) => {
    const pairScore = (pair) => scoreSide(pair.start, "start")
      + scoreSide(pair.end, "end")
      + (topologySideVector(pair.start).x === -topologySideVector(pair.end).x
        && topologySideVector(pair.start).y === -topologySideVector(pair.end).y ? 0 : 6);
    return pairScore(left) - pairScore(right)
      || TOPOLOGY_SIDES.indexOf(left.start) - TOPOLOGY_SIDES.indexOf(right.start)
      || TOPOLOGY_SIDES.indexOf(left.end) - TOPOLOGY_SIDES.indexOf(right.end);
  })[0];
}


