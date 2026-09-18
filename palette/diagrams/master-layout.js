/** Route, render, and position the master diagram's topology edges and nodes. */

const TOPOLOGY_TRACE_CLEARANCE = 14;
const TOPOLOGY_TRACE_CORNER_RADIUS = 8;
const TOPOLOGY_LANE_LIMIT = 5;
const TOPOLOGY_LANE_SPACING = 4;
const TOPOLOGY_PORT_SPACING = 22;
const TOPOLOGY_PORT_CORNER_INSET = 14;
const TOPOLOGY_ESCAPE_LENGTH = 14;
const TOPOLOGY_ROUTE_CHANNEL_SPACING = 10;
const TOPOLOGY_SIDES = ["right", "bottom", "top", "left"];

function relationshipEndpointGroups(harness, junction, relationship) {
  return (harness.wireGroups || []).filter((group) => (group.routeLegs || []).some((leg) => (
    (leg.pathwayIds || []).includes(relationship.pathwayId)
      && (leg.controlSteps || []).some((step) => step.controlId === junction.controlId)
  )));
}

/** Count inversions between edges joining the same pair of topology layers. */
function relationshipEdgeCrossingCount(component, positions) {
  let crossings = 0;
  component.edges.forEach((edge, index) => {
    const source = component.nodes.find((node) => node.id === edge.sourceId);
    const target = component.nodes.find((node) => node.id === edge.targetId);
    component.edges.slice(index + 1).forEach((other) => {
      const otherSource = component.nodes.find((node) => node.id === other.sourceId);
      const otherTarget = component.nodes.find((node) => node.id === other.targetId);
      if (!source || !target || !otherSource || !otherTarget) return;
      if (source.depth !== otherSource.depth || target.depth !== otherTarget.depth) return;
      if (source.id === otherSource.id || target.id === otherTarget.id) return;
      const sourceOrder = positions.get(source.id) - positions.get(otherSource.id);
      const targetOrder = positions.get(target.id) - positions.get(otherTarget.id);
      if (sourceOrder * targetOrder < 0) crossings += 1;
    });
  });
  return crossings;
}

/** Return a stable layer order when median sweeps reduce relationship crossings. */
function optimizeRelationshipNodeOrder(component) {
  const layers = new Map();
  component.nodes.forEach((node) => {
    if (!layers.has(node.depth)) layers.set(node.depth, []);
    layers.get(node.depth).push(node);
  });
  const depths = [...layers.keys()].sort((left, right) => left - right);
  const originalPositions = new Map();
  depths.forEach((depth) => layers.get(depth).forEach((node, index) => {
    originalPositions.set(node.id, index);
  }));
  const positions = new Map(originalPositions);
  const neighbors = (node, forward) => component.edges.flatMap((edge) => {
    if (forward && edge.targetId === node.id) return [edge.sourceId];
    if (!forward && edge.sourceId === node.id) return [edge.targetId];
    return [];
  });
  const sweep = (forward) => {
    const orderedDepths = forward ? depths : depths.slice().reverse();
    orderedDepths.forEach((depth) => {
      const nodes = layers.get(depth);
      const scores = new Map(nodes.map((node) => {
        const adjacent = neighbors(node, forward)
          .map((id) => positions.get(id))
          .filter((position) => position !== undefined);
        const score = adjacent.length
          ? adjacent.reduce((total, position) => total + position, 0) / adjacent.length
          : positions.get(node.id);
        return [node.id, score];
      }));
      nodes.sort((left, right) => (
        scores.get(left.id) - scores.get(right.id)
        || originalPositions.get(left.id) - originalPositions.get(right.id)
      ));
      nodes.forEach((node, index) => positions.set(node.id, index));
    });
  };
  for (let iteration = 0; iteration < 4; iteration += 1) {
    sweep(true);
    sweep(false);
  }
  const originalCrossings = relationshipEdgeCrossingCount(component, originalPositions);
  const optimizedCrossings = relationshipEdgeCrossingCount(component, positions);
  if (optimizedCrossings >= originalCrossings) return component.nodes;
  return component.nodes.slice().sort((left, right) => (
    left.depth - right.depth || positions.get(left.id) - positions.get(right.id)
  ));
}

function pointInsideRectangle(point, rectangle) {
  return point.x > rectangle.left && point.x < rectangle.right
    && point.y > rectangle.top && point.y < rectangle.bottom;
}

function relationshipEdgeId(edge) {
  return [
    edge.junction.junctionId,
    edge.relationship.pathwayId,
    edge.relationship.endpoint,
  ].join(":");
}

function topologyNodeCenter(node) {
  return {
    x: node.left + node.width / 2,
    y: node.top + node.height / 2,
  };
}

function topologySideVector(side) {
  return {
    left: { x: -1, y: 0 },
    right: { x: 1, y: 0 },
    top: { x: 0, y: -1 },
    bottom: { x: 0, y: 1 },
  }[side];
}

/** Return the four visually consistent ports initially available on one node. */
function relationshipCanonicalPorts(node) {
  const center = topologyNodeCenter(node);
  return {
    left: { x: node.left, y: center.y },
    right: { x: node.left + node.width, y: center.y },
    top: { x: center.x, y: node.top },
    bottom: { x: center.x, y: node.top + node.height },
  };
}

function topologySideCapacity(node, side) {
  const length = ["left", "right"].includes(side) ? node.height : node.width;
  const usable = Math.max(0, length - 2 * TOPOLOGY_PORT_CORNER_INSET);
  return Math.max(1, Math.floor(usable / TOPOLOGY_PORT_SPACING) + 1);
}

function chooseRelationshipPortSide(node, other, sideCounts) {
  const center = topologyNodeCenter(node);
  const otherCenter = topologyNodeCenter(other);
  const difference = {
    x: otherCenter.x - center.x,
    y: otherCenter.y - center.y,
  };
  const length = Math.hypot(difference.x, difference.y) || 1;
  const assignedCount = [...sideCounts.values()].reduce((total, count) => total + count, 0);
  const candidates = assignedCount < TOPOLOGY_SIDES.length
    ? TOPOLOGY_SIDES.filter((side) => !sideCounts.get(side))
    : TOPOLOGY_SIDES.slice();
  return candidates.sort((left, right) => {
    const score = (side) => {
      const vector = topologySideVector(side);
      const alignment = (difference.x * vector.x + difference.y * vector.y) / length;
      const count = sideCounts.get(side) || 0;
      const overflow = count >= topologySideCapacity(node, side) ? 1000 : 0;
      return (1 - alignment) * 100 + count * 34 + overflow;
    };
    return score(left) - score(right)
      || TOPOLOGY_SIDES.indexOf(left) - TOPOLOGY_SIDES.indexOf(right);
  })[0];
}

function positionRelationshipPorts(node, side, ports) {
  const canonical = relationshipCanonicalPorts(node)[side];
  if (ports.length === 1) {
    ports[0].point = canonical;
    return;
  }
  const vertical = ["left", "right"].includes(side);
  const length = vertical ? node.height : node.width;
  const usable = Math.max(0, length - 2 * TOPOLOGY_PORT_CORNER_INSET);
  const spacing = Math.min(TOPOLOGY_PORT_SPACING, usable / Math.max(1, ports.length - 1));
  ports.sort((left, right) => (
    left.otherPosition - right.otherPosition
    || left.edgeId.localeCompare(right.edgeId)
    || left.role.localeCompare(right.role)
  ));
  ports.forEach((port, index) => {
    const offset = (index - (ports.length - 1) / 2) * spacing;
    port.point = vertical
      ? { x: canonical.x, y: canonical.y + offset }
      : { x: canonical.x + offset, y: canonical.y };
  });
}

/** Allocate stable, adaptive perimeter ports for every edge in one component. */
function allocateRelationshipPorts(component) {
  const nodes = new Map(component.nodes.map((node) => [node.id, node]));
  const counts = new Map(component.nodes.map((node) => [
    node.id, new Map(TOPOLOGY_SIDES.map((side) => [side, 0])),
  ]));
  const ports = [];
  component.edges.slice().sort((left, right) => (
    relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))
  )).forEach((edge) => {
    const edgeId = relationshipEdgeId(edge);
    [["source", edge.sourceId, edge.targetId], ["target", edge.targetId, edge.sourceId]]
      .forEach(([role, nodeId, otherId]) => {
        const node = nodes.get(nodeId);
        const other = nodes.get(otherId);
        if (!node || !other) return;
        const side = node.kind === "pathway"
          ? (edge.relationship.endpoint === "start" ? "left" : "right")
          : chooseRelationshipPortSide(node, other, counts.get(nodeId));
        counts.get(nodeId).set(side, counts.get(nodeId).get(side) + 1);
        const otherCenter = topologyNodeCenter(other);
        ports.push({
          id: `${edgeId}:${role}`,
          edgeId,
          role,
          nodeId,
          side,
          otherPosition: ["left", "right"].includes(side) ? otherCenter.y : otherCenter.x,
        });
      });
  });
  component.nodes.forEach((node) => {
    TOPOLOGY_SIDES.forEach((side) => positionRelationshipPorts(
      node,
      side,
      ports.filter((port) => port.nodeId === node.id && port.side === side),
    ));
  });
  return ports;
}

function orthogonalSegmentClearsRectangles(start, end, rectangles) {
  return rectangles.every((rectangle) => {
    if (start.x === end.x) {
      const minimumY = Math.min(start.y, end.y);
      const maximumY = Math.max(start.y, end.y);
      return start.x <= rectangle.left || start.x >= rectangle.right
        || maximumY <= rectangle.top || minimumY >= rectangle.bottom;
    }
    const minimumX = Math.min(start.x, end.x);
    const maximumX = Math.max(start.x, end.x);
    return start.y <= rectangle.top || start.y >= rectangle.bottom
      || maximumX <= rectangle.left || minimumX >= rectangle.right;
  });
}

function simplifyTopologyRoute(points) {
  return points.filter((point, index) => {
    if (!index || index === points.length - 1) return true;
    const prior = points[index - 1];
    const next = points[index + 1];
    return !(prior.x === point.x && point.x === next.x)
      && !(prior.y === point.y && point.y === next.y);
  });
}

function topologyRouteSegments(points) {
  return points.slice(1).map((end, index) => ({ start: points[index], end }));
}

function offsetTopologyRoute(points, offset) {
  if (!offset || points.length < 2) return points;
  const normals = topologyRouteSegments(points).map((segment) => {
    const horizontal = segment.start.y === segment.end.y;
    if (horizontal) {
      return { x: 0, y: Math.sign(segment.end.x - segment.start.x) * offset };
    }
    return { x: -Math.sign(segment.end.y - segment.start.y) * offset, y: 0 };
  });
  return points.map((point, index) => {
    if (!index) return { x: point.x + normals[0].x, y: point.y + normals[0].y };
    if (index === points.length - 1) {
      const normal = normals[normals.length - 1];
      return { x: point.x + normal.x, y: point.y + normal.y };
    }
    const prior = normals[index - 1];
    const next = normals[index];
    return { x: point.x + prior.x + next.x, y: point.y + prior.y + next.y };
  });
}

function topologySegmentConflictScore(candidate, occupied) {
  const candidateHorizontal = candidate.start.y === candidate.end.y;
  return occupied.reduce((score, segment) => {
    const occupiedHorizontal = segment.start.y === segment.end.y;
    if (candidateHorizontal === occupiedHorizontal) {
      const sameLine = candidateHorizontal
        ? candidate.start.y === segment.start.y
        : candidate.start.x === segment.start.x;
      if (!sameLine) return score;
      const candidateRange = candidateHorizontal
        ? [candidate.start.x, candidate.end.x] : [candidate.start.y, candidate.end.y];
      const occupiedRange = occupiedHorizontal
        ? [segment.start.x, segment.end.x] : [segment.start.y, segment.end.y];
      const overlap = Math.min(Math.max(...candidateRange), Math.max(...occupiedRange))
        - Math.max(Math.min(...candidateRange), Math.min(...occupiedRange));
      if (overlap > 0) return score + 800 + overlap * 8;
      return score + (overlap === 0 ? 180 : 0);
    }
    const horizontal = candidateHorizontal ? candidate : segment;
    const vertical = candidateHorizontal ? segment : candidate;
    const crossing = vertical.start.x >= Math.min(horizontal.start.x, horizontal.end.x)
      && vertical.start.x <= Math.max(horizontal.start.x, horizontal.end.x)
      && horizontal.start.y >= Math.min(vertical.start.y, vertical.end.y)
      && horizontal.start.y <= Math.max(vertical.start.y, vertical.end.y);
    return score + (crossing ? 360 : 0);
  }, 0);
}

function roundedTopologyRoute(points) {
  let path = `M ${points[0].x} ${points[0].y}`;
  points.slice(1, -1).forEach((point, index) => {
    const prior = points[index];
    const next = points[index + 2];
    const incoming = Math.abs(point.x - prior.x) + Math.abs(point.y - prior.y);
    const outgoing = Math.abs(next.x - point.x) + Math.abs(next.y - point.y);
    const radius = Math.min(TOPOLOGY_TRACE_CORNER_RADIUS, incoming / 2, outgoing / 2);
    const before = {
      x: point.x + Math.sign(prior.x - point.x) * radius,
      y: point.y + Math.sign(prior.y - point.y) * radius,
    };
    const after = {
      x: point.x + Math.sign(next.x - point.x) * radius,
      y: point.y + Math.sign(next.y - point.y) * radius,
    };
    path += ` L ${before.x} ${before.y} Q ${point.x} ${point.y}, ${after.x} ${after.y}`;
  });
  const end = points[points.length - 1];
  return `${path} L ${end.x} ${end.y}`;
}

/** Find a deterministic, bend-aware orthogonal route through measured node bounds. */
function topologyVisibilityRoute(start, end, rectangles, occupiedSegments = []) {
  const channelCoordinates = (values) => values.flatMap((value) => [
    value - TOPOLOGY_ROUTE_CHANNEL_SPACING,
    value + TOPOLOGY_ROUTE_CHANNEL_SPACING,
  ]);
  const occupiedVerticalXs = occupiedSegments.filter(
    (segment) => segment.start.x === segment.end.x,
  ).map((segment) => segment.start.x);
  const occupiedHorizontalYs = occupiedSegments.filter(
    (segment) => segment.start.y === segment.end.y,
  ).map((segment) => segment.start.y);
  const xs = [...new Set([
    start.x,
    end.x,
    ...rectangles.flatMap((rectangle) => [rectangle.left, rectangle.right]),
    ...channelCoordinates(occupiedVerticalXs),
  ])].sort((left, right) => left - right);
  const ys = [...new Set([
    start.y,
    end.y,
    ...rectangles.flatMap((rectangle) => [rectangle.top, rectangle.bottom]),
    ...channelCoordinates(occupiedHorizontalYs),
  ])].sort((left, right) => left - right);
  const points = [];
  const pointIndexes = new Map();
  xs.forEach((x) => ys.forEach((y) => {
    const point = { x, y };
    if (rectangles.some((rectangle) => pointInsideRectangle(point, rectangle))) return;
    pointIndexes.set(`${x}:${y}`, points.length);
    points.push(point);
  }));
  const neighbors = new Map(points.map((_point, index) => [index, []]));
  const connectLine = (indexes, horizontal) => {
    indexes.sort((left, right) => {
      const first = points[left];
      const second = points[right];
      return horizontal ? first.x - second.x : first.y - second.y;
    });
    indexes.slice(0, -1).forEach((index, offset) => {
      const nextIndex = indexes[offset + 1];
      const first = points[index];
      const second = points[nextIndex];
      if (!orthogonalSegmentClearsRectangles(first, second, rectangles)) return;
      const distance = Math.abs(second.x - first.x) + Math.abs(second.y - first.y);
      const direction = horizontal ? "h" : "v";
      const conflict = topologySegmentConflictScore({ start: first, end: second }, occupiedSegments);
      neighbors.get(index).push({ index: nextIndex, direction, distance, conflict });
      neighbors.get(nextIndex).push({ index, direction, distance, conflict });
    });
  };
  ys.forEach((y) => connectLine(
    xs.map((x) => pointIndexes.get(`${x}:${y}`)).filter((index) => index !== undefined),
    true,
  ));
  xs.forEach((x) => connectLine(
    ys.map((y) => pointIndexes.get(`${x}:${y}`)).filter((index) => index !== undefined),
    false,
  ));
  const startIndex = pointIndexes.get(`${start.x}:${start.y}`);
  const endIndex = pointIndexes.get(`${end.x}:${end.y}`);
  if (startIndex === undefined || endIndex === undefined) return null;
  const queue = [{ cost: 0, index: startIndex, direction: "", route: [startIndex] }];
  const best = new Map([[`${startIndex}:`, 0]]);
  while (queue.length) {
    queue.sort((left, right) => (
      left.cost - right.cost || left.index - right.index || left.direction.localeCompare(right.direction)
    ));
    const current = queue.shift();
    if (current.index === endIndex) {
      return simplifyTopologyRoute(current.route.map((index) => points[index]));
    }
    (neighbors.get(current.index) || []).forEach((neighbor) => {
      const bendCost = current.direction && current.direction !== neighbor.direction ? 24 : 0;
      const cost = current.cost + neighbor.distance + bendCost + neighbor.conflict;
      const key = `${neighbor.index}:${neighbor.direction}`;
      if (cost >= (best.get(key) ?? Number.POSITIVE_INFINITY)) return;
      best.set(key, cost);
      queue.push({
        cost,
        index: neighbor.index,
        direction: neighbor.direction,
        route: [...current.route, neighbor.index],
      });
    });
  }
  return null;
}

function topologyPortEscape(port) {
  const vector = topologySideVector(port.side);
  return {
    x: port.point.x + vector.x * TOPOLOGY_ESCAPE_LENGTH,
    y: port.point.y + vector.y * TOPOLOGY_ESCAPE_LENGTH,
  };
}

/** Route one edge orthogonally through its assigned perimeter ports. */
function routeRelationshipEdge(sourcePort, targetPort, nodes, occupiedSegments = []) {
  const start = topologyPortEscape(sourcePort);
  const end = topologyPortEscape(targetPort);
  const rectangles = nodes.map((node) => ({
    left: node.left - TOPOLOGY_TRACE_CLEARANCE,
    right: node.left + node.width + TOPOLOGY_TRACE_CLEARANCE,
    top: node.top - TOPOLOGY_TRACE_CLEARANCE,
    bottom: node.top + node.height + TOPOLOGY_TRACE_CLEARANCE,
  }));
  const middle = topologyVisibilityRoute(start, end, rectangles, occupiedSegments);
  const points = simplifyTopologyRoute([
    sourcePort.point,
    start,
    ...(middle || [start, { x: start.x, y: end.y }, end]).slice(1, -1),
    end,
    targetPort.point,
  ]);
  return {
    d: roundedTopologyRoute(points),
    kind: middle ? "orthogonal" : "fallback",
    points,
    sourcePort,
    targetPort,
  };
}

function topologyRouteMidpoint(route) {
  const segments = route.points.slice(1).map((point, index) => {
    const prior = route.points[index];
    return {
      prior,
      point,
      length: Math.abs(point.x - prior.x) + Math.abs(point.y - prior.y),
    };
  });
  const halfLength = segments.reduce((total, segment) => total + segment.length, 0) / 2;
  let traversed = 0;
  for (const segment of segments) {
    if (traversed + segment.length >= halfLength) {
      const progress = segment.length
        ? (halfLength - traversed) / segment.length
        : 0;
      return {
        x: segment.prior.x + (segment.point.x - segment.prior.x) * progress,
        y: segment.prior.y + (segment.point.y - segment.prior.y) * progress,
      };
    }
    traversed += segment.length;
  }
  return route.points[route.points.length - 1];
}

function topologyRouteSetScore(routes) {
  const routeList = [...routes.values()];
  let score = 0;
  routeList.forEach((route, index) => {
    const segments = topologyRouteSegments(route.points);
    score += segments.reduce((total, segment) => (
      total + Math.abs(segment.end.x - segment.start.x)
      + Math.abs(segment.end.y - segment.start.y)
    ), 0) + Math.max(0, segments.length - 1) * 24;
    routeList.slice(index + 1).forEach((other) => {
      segments.forEach((segment) => {
        score += topologySegmentConflictScore(segment, topologyRouteSegments(other.points));
      });
    });
  });
  return score;
}

function routeRelationshipEdges(component, ports) {
  const portsById = new Map(ports.map((port) => [port.id, port]));
  const stableEdges = component.edges.slice().sort((left, right) => (
    relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))
  ));
  const orders = [stableEdges, stableEdges.slice().reverse()];
  let best = null;
  orders.forEach((edges) => {
    const routes = new Map();
    const occupied = [];
    edges.forEach((edge) => {
      const edgeId = relationshipEdgeId(edge);
      const route = routeRelationshipEdge(
        portsById.get(`${edgeId}:source`),
        portsById.get(`${edgeId}:target`),
        component.nodes,
        occupied,
      );
      routes.set(edgeId, route);
      occupied.push(...topologyRouteSegments(route.points));
    });
    const score = topologyRouteSetScore(routes);
    if (!best || score < best.score) best = { routes, score };
  });
  return best?.routes || new Map();
}

function topologyGroupMode(groups) {
  if (!groups.length) return "structure";
  return groups.length <= TOPOLOGY_LANE_LIMIT ? "lanes" : "bundle";
}

/** Render one routed topology edge using bounded, deterministic group detail. */
function renderTopologyEdge(edge, route, groups) {
  const group = svgElement("g", {
    class: "relationship-topology-edge",
    "data-source-id": edge.sourceId,
    "data-target-id": edge.targetId,
    "data-wire-group-ids": groups.map((wireGroup) => wireGroup.wireGroupId).join(" "),
    "data-wire-group-count": groups.length,
    "data-render-mode": topologyGroupMode(groups),
    "data-source-port-id": route.sourcePort.id,
    "data-target-port-id": route.targetPort.id,
    "data-source-side": route.sourcePort.side,
    "data-target-side": route.targetPort.side,
  });
  const structural = svgElement("path", {
    class: "structural-trace",
    d: route.d,
    "data-junction-id": edge.junction.junctionId,
    "data-pathway-id": edge.relationship.pathwayId,
    "data-endpoint": edge.relationship.endpoint,
    "data-source-x": `${route.points[0].x}`,
    "data-source-y": `${route.points[0].y}`,
    "data-target-x": `${route.points[route.points.length - 1].x}`,
    "data-target-y": `${route.points[route.points.length - 1].y}`,
    "data-route-kind": route.kind,
    "data-route-points": JSON.stringify(route.points),
  });
  group.append(structural);
  if (groups.length <= TOPOLOGY_LANE_LIMIT) {
    groups.forEach((wireGroup, index) => {
      const offset = (index - (groups.length - 1) / 2) * TOPOLOGY_LANE_SPACING;
      const lanePoints = offsetTopologyRoute(route.points, offset);
      group.append(svgElement("path", {
        class: "wire-trace relationship-wire-lane",
        d: roundedTopologyRoute(lanePoints),
        stroke: wireGroup.materials?.mainColor?.hex || "#1777c8",
        "data-lane-offset": `${offset}`,
        "data-source-x": `${lanePoints[0].x}`,
        "data-source-y": `${lanePoints[0].y}`,
        "data-target-x": `${lanePoints[lanePoints.length - 1].x}`,
        "data-target-y": `${lanePoints[lanePoints.length - 1].y}`,
        "data-wire-group-id": wireGroup.wireGroupId,
      }));
    });
  } else {
    const colors = new Set(
      groups.map((wireGroup) => wireGroup.materials?.mainColor?.hex || "#1777c8"),
    );
    const midpoint = topologyRouteMidpoint(route);
    const badge = svgElement("g", {
      class: "relationship-wire-count",
      transform: `translate(${midpoint.x} ${midpoint.y})`,
    });
    badge.append(
      svgElement("rect", { x: -14, y: -9, width: 28, height: 18, rx: 9 }),
      svgElement("text", { x: 0, y: 4, "text-anchor": "middle" }),
    );
    badge.children[1].textContent = `×${groups.length}`;
    group.append(
      svgElement("path", {
        class: "wire-trace relationship-wire-bundle",
        d: route.d,
        stroke: colors.size === 1 ? [...colors][0] : "#526f85",
        "data-wire-group-ids": groups.map((wireGroup) => wireGroup.wireGroupId).join(" "),
      }),
      badge,
    );
  }
  return group;
}

function renderTopologyPort(port) {
  const groups = port.groups || [];
  const laneCount = groups.length <= TOPOLOGY_LANE_LIMIT ? groups.length : 1;
  const extent = laneCount > 1
    ? (laneCount - 1) * TOPOLOGY_LANE_SPACING + 8
    : 8;
  return svgElement("rect", {
    class: "relationship-topology-port",
    x: port.point.x - extent / 2,
    y: port.point.y - extent / 2,
    width: extent,
    height: extent,
    rx: 4,
    "data-port-id": port.id,
    "data-node-id": port.nodeId,
    "data-side": port.side,
    "data-wire-group-ids": groups.map((wireGroup) => wireGroup.wireGroupId).join(" "),
  });
}

/** Return positions for one flow direction and the resulting canvas dimensions. */
function relationshipLayoutCandidate(components, vertical) {
  const padding = 30;
  const layerGap = 54;
  const rowGap = 40;
  let componentOffset = padding;
  let maximumFlowExtent = 0;
  const positions = new Map();
  components.forEach((component) => {
    const rowsByDepth = new Map();
    const nodesByDepth = new Map();
    component.nodes.forEach((node) => {
      const row = rowsByDepth.get(node.depth) || 0;
      rowsByDepth.set(node.depth, row + 1);
      if (!nodesByDepth.has(node.depth)) nodesByDepth.set(node.depth, []);
      nodesByDepth.get(node.depth).push(node);
      node.row = row;
      node.width = node.element.scrollWidth || (node.kind === "pathway" ? 278 : 154);
      node.height = node.element.scrollHeight || (node.kind === "pathway" ? 92 : 76);
    });
    const rowExtent = Math.max(
      112,
      ...component.nodes.map((node) => vertical ? node.width : node.height),
    );
    const componentRows = Math.max(1, ...rowsByDepth.values());
    const layerExtents = new Map(
      [...nodesByDepth].map(([depth, nodes]) => [
        depth,
        Math.max(...nodes.map((node) => vertical ? node.height : node.width)),
      ]),
    );
    const layerOffsets = new Map();
    let nextLayerOffset = padding;
    [...layerExtents.keys()].sort((left, right) => left - right).forEach((depth) => {
      layerOffsets.set(depth, nextLayerOffset);
      nextLayerOffset += layerExtents.get(depth) + layerGap;
    });
    component.nodes.forEach((node) => {
      const nodesAtDepth = rowsByDepth.get(node.depth);
      const centeredRow = node.row + (componentRows - nodesAtDepth) / 2;
      const flowPosition = layerOffsets.get(node.depth)
        + (layerExtents.get(node.depth) - (vertical ? node.height : node.width)) / 2;
      const rowPosition = componentOffset + centeredRow * (rowExtent + rowGap);
      positions.set(node.id, vertical
        ? { left: rowPosition, top: flowPosition }
        : { left: flowPosition, top: rowPosition });
    });
    maximumFlowExtent = Math.max(maximumFlowExtent, nextLayerOffset - layerGap);
    componentOffset += componentRows * (rowExtent + rowGap) + layerGap;
  });
  const crossExtent = componentOffset - layerGap + padding;
  return {
    positions,
    width: Math.max(vertical ? crossExtent : maximumFlowExtent + padding, 260),
    height: Math.max(vertical ? maximumFlowExtent + padding : crossExtent, 260),
    vertical,
  };
}

/** Return the layout direction that displays largest in the current viewport. */
function bestRelationshipLayout(components, viewportSize) {
  const candidates = [
    relationshipLayoutCandidate(components, false),
    relationshipLayoutCandidate(components, true),
  ];
  const preferred = candidates.find((candidate) => (
    (candidate.vertical ? "vertical" : "horizontal") === viewportSize?.flow
  ));
  if (preferred) return preferred;
  const availableWidth = Math.max(1, viewportSize?.width || 760);
  const availableHeight = Math.max(1, viewportSize?.height || 430);
  const fitScale = (candidate) => Math.min(
    1,
    availableWidth / candidate.width,
    availableHeight / candidate.height,
  );
  return candidates.sort((left, right) => (
    fitScale(right) - fitScale(left) || Number(left.vertical) - Number(right.vertical)
  ))[0];
}

/**
 * Position acyclic topology components for the viewport and draw their edges.
 */
function layoutRelationshipGraph(stack, components, harness, viewportSize = {}) {
  components.forEach((component) => {
    component.nodes = optimizeRelationshipNodeOrder(component);
  });
  const layout = bestRelationshipLayout(components, viewportSize);
  components.forEach((component) => component.nodes.forEach((node) => {
    const position = layout.positions.get(node.id);
    node.left = position.left;
    node.top = position.top;
    node.element.style.left = `${node.left}px`;
    node.element.style.top = `${node.top}px`;
  }));
  stack.querySelector(".relationship-topology-edges")?.remove();
  const canvasWidth = layout.width;
  const canvasHeight = layout.height;
  const overlay = svgElement("svg", {
    class: "relationship-topology-edges",
    viewBox: `0 0 ${canvasWidth} ${canvasHeight}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  components.forEach((component) => {
    const nodes = new Map(component.nodes.map((node) => [node.id, node]));
    const ports = allocateRelationshipPorts(component);
    const portsById = new Map(ports.map((port) => [port.id, port]));
    const routes = routeRelationshipEdges(component, ports);
    component.edges.forEach((edge) => {
      const source = nodes.get(edge.sourceId);
      const target = nodes.get(edge.targetId);
      if (!source || !target) return;
      const edgeId = relationshipEdgeId(edge);
      const route = routes.get(edgeId);
      if (!route) return;
      const groups = relationshipEndpointGroups(
        harness,
        edge.junction,
        edge.relationship,
      );
      overlay.append(renderTopologyEdge(edge, route, groups));
      portsById.get(`${edgeId}:source`).groups = groups;
      portsById.get(`${edgeId}:target`).groups = groups;
    });
    ports.forEach((port) => overlay.append(renderTopologyPort(port)));
  });
  stack.insertBefore(overlay, stack.children[0] || null);
  stack.style.width = `${canvasWidth}px`;
  stack.style.height = `${canvasHeight}px`;
  const flow = layout.vertical ? "vertical" : "horizontal";
  stack.dataset.diagramFlow = flow;
  return flow;
}
