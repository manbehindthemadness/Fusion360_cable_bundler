/** Route, render, and position the master diagram's topology edges and nodes. */

const RELATIONSHIP_DIAGRAM_SPACING = 32;
const TOPOLOGY_TRACE_CORNER_RADIUS = 8;
const TOPOLOGY_LANE_LIMIT = 5;
const TOPOLOGY_LANE_SPACING = 4;
const TOPOLOGY_PORT_SPACING = 22;
const TOPOLOGY_PORT_CORNER_INSET = 14;
const TOPOLOGY_ROUTE_CHANNEL_SPACING = 10;
const TOPOLOGY_SIDES = ["right", "bottom", "top", "left"];
const TOPOLOGY_LAYOUT_TRACE_HALF_EXTENT = (TOPOLOGY_LANE_LIMIT - 1)
  * TOPOLOGY_LANE_SPACING / 2 + 1.5;
const TOPOLOGY_ROUTING_ENVELOPE = RELATIONSHIP_DIAGRAM_SPACING
  + TOPOLOGY_LAYOUT_TRACE_HALF_EXTENT;
const TOPOLOGY_NODE_GAP = RELATIONSHIP_DIAGRAM_SPACING;
const TOPOLOGY_CONNECTED_GAP = TOPOLOGY_ROUTING_ENVELOPE * 2;
const TOPOLOGY_COMPONENT_GAP = RELATIONSHIP_DIAGRAM_SPACING;
const TOPOLOGY_CANVAS_PADDING = TOPOLOGY_ROUTING_ENVELOPE;
const TOPOLOGY_LAYOUT_CANDIDATE_LIMIT = 128;
const TOPOLOGY_ROUTED_CANDIDATE_LIMIT = 12;
const TOPOLOGY_SHORT_SEGMENT = TOPOLOGY_TRACE_CORNER_RADIUS * 2;

function relationshipEndpointGroups(harness, junction, relationship) {
  return (harness.wireGroups || []).filter((group) => (group.routeLegs || []).some((leg) => (
    (leg.pathwayIds || []).includes(relationship.pathwayId)
      && (leg.controlSteps || []).some((step) => step.controlId === junction.controlId)
  )));
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
  const center = node.hubCenter || topologyNodeCenter(node);
  return {
    left: node.dockPoints?.left || { x: node.left, y: center.y },
    right: node.dockPoints?.right || { x: node.left + node.width, y: center.y },
    top: node.dockPoints?.top || { x: center.x, y: node.top },
    bottom: node.dockPoints?.bottom || { x: center.x, y: node.top + node.height },
  };
}

function topologySideCapacity(node, side) {
  const endpoint = node.kind === "pathway"
    ? Object.entries(node.dockSides || {}).find(([, dockSide]) => dockSide === side)?.[0]
    : null;
  const endpointSize = endpoint ? relationshipEndpointSize(node, endpoint) : null;
  const length = endpointSize
    ? (["left", "right"].includes(side) ? endpointSize.height : endpointSize.width)
    : (["left", "right"].includes(side) ? node.height : node.width);
  const usable = Math.max(0, length - 2 * TOPOLOGY_PORT_CORNER_INSET);
  return Math.max(1, Math.floor(usable / TOPOLOGY_PORT_SPACING) + 1);
}

function chooseRelationshipPortSide(node, other, sideCounts, spreadPorts = true) {
  const center = topologyNodeCenter(node);
  const otherCenter = topologyNodeCenter(other);
  const difference = {
    x: otherCenter.x - center.x,
    y: otherCenter.y - center.y,
  };
  const length = Math.hypot(difference.x, difference.y) || 1;
  const assignedCount = [...sideCounts.values()].reduce((total, count) => total + count, 0);
  const candidates = spreadPorts && assignedCount < TOPOLOGY_SIDES.length
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

function positionRelationshipPorts(node, side, ports, reverseOrder = false) {
  const canonical = relationshipCanonicalPorts(node)[side];
  if (ports.length === 1) {
    ports[0].point = canonical;
    return;
  }
  const vertical = ["left", "right"].includes(side);
  const endpoint = node.kind === "pathway"
    ? Object.entries(node.dockSides || {}).find(([, dockSide]) => dockSide === side)?.[0]
    : null;
  const endpointSize = endpoint ? relationshipEndpointSize(node, endpoint) : null;
  const length = endpointSize
    ? (vertical ? endpointSize.height : endpointSize.width)
    : (vertical ? node.height : node.width);
  const usable = Math.max(0, length - 2 * TOPOLOGY_PORT_CORNER_INSET);
  const spacing = Math.min(TOPOLOGY_PORT_SPACING, usable / Math.max(1, ports.length - 1));
  ports.sort((left, right) => (
    left.otherPosition - right.otherPosition
    || left.edgeId.localeCompare(right.edgeId)
    || left.role.localeCompare(right.role)
  ));
  if (reverseOrder) ports.reverse();
  ports.forEach((port, index) => {
    const offset = (index - (ports.length - 1) / 2) * spacing;
    port.point = vertical
      ? { x: canonical.x, y: canonical.y + offset }
      : { x: canonical.x + offset, y: canonical.y };
  });
}

function relationshipJunctionIncidents(component, node, nodes) {
  return component.edges.flatMap((edge) => {
    if (edge.sourceId === node.id) {
      return [{ key: `${relationshipEdgeId(edge)}:source`, other: nodes.get(edge.targetId) }];
    }
    if (edge.targetId === node.id) {
      return [{ key: `${relationshipEdgeId(edge)}:target`, other: nodes.get(edge.sourceId) }];
    }
    return [];
  }).filter((item) => item.other);
}

/** Assign low-degree junction ports together so their angular order cannot invert. */
function spreadRelationshipJunctionSides(component) {
  const nodes = new Map(component.nodes.map((node) => [node.id, node]));
  const assignments = new Map();
  component.nodes.filter((node) => node.kind === "junction").forEach((node) => {
    const incident = relationshipJunctionIncidents(component, node, nodes)
      .sort((left, right) => left.key.localeCompare(right.key));
    if (!incident.length || incident.length > TOPOLOGY_SIDES.length) return;
    const center = topologyNodeCenter(node);
    let best = null;
    const search = (index, available, selected, score) => {
      if (index === incident.length) {
        const signature = selected.join("|");
        if (!best || score < best.score - 1e-9
          || (Math.abs(score - best.score) <= 1e-9 && signature > best.signature)) {
          best = { score, signature, sides: selected.slice() };
        }
        return;
      }
      const otherCenter = topologyNodeCenter(incident[index].other);
      const dx = otherCenter.x - center.x;
      const dy = otherCenter.y - center.y;
      const length = Math.hypot(dx, dy) || 1;
      available.forEach((side) => {
        const vector = topologySideVector(side);
        const alignment = (dx * vector.x + dy * vector.y) / length;
        search(index + 1, available.filter((candidate) => candidate !== side),
          [...selected, side], score + 1 - alignment);
      });
    };
    search(0, TOPOLOGY_SIDES, [], 0);
    incident.forEach((item, index) => assignments.set(item.key, best.sides[index]));
  });
  return assignments;
}

/** Fan same-direction branches without forcing an inner route behind an outer route. */
function fanRelationshipJunctionSides(component) {
  const nodes = new Map(component.nodes.map((node) => [node.id, node]));
  const assignments = new Map();
  component.nodes.filter((node) => node.kind === "junction").forEach((node) => {
    const center = topologyNodeCenter(node);
    const incident = relationshipJunctionIncidents(component, node, nodes);
    if (incident.length < 3) return;
    const offsets = incident.map((item) => {
      const other = topologyNodeCenter(item.other);
      return { ...item, x: other.x - center.x, y: other.y - center.y };
    });
    const horizontal = offsets.reduce((total, item) => total + Math.abs(item.x), 0)
      >= offsets.reduce((total, item) => total + Math.abs(item.y), 0);
    offsets.sort((left, right) => (
      (horizontal ? left.y - right.y : left.x - right.x)
      || left.key.localeCompare(right.key)
    ));
    const average = offsets.reduce(
      (total, item) => total + (horizontal ? item.x : item.y), 0,
    );
    const facing = horizontal
      ? (average >= 0 ? "right" : "left")
      : (average >= 0 ? "bottom" : "top");
    offsets.forEach((item, index) => {
      let side = facing;
      if (index === 0) side = horizontal ? "top" : "left";
      if (index === offsets.length - 1) side = horizontal ? "bottom" : "right";
      assignments.set(item.key, side);
    });
  });
  return assignments;
}

/** Allocate stable, adaptive perimeter ports for every edge in one component. */
function allocateRelationshipPorts(component, reverseOrder = false, spreadPorts = true) {
  const nodes = new Map(component.nodes.map((node) => [node.id, node]));
  const counts = new Map(component.nodes.map((node) => [
    node.id, new Map(TOPOLOGY_SIDES.map((side) => [side, 0])),
  ]));
  const portMode = spreadPorts === true ? "spread" : spreadPorts === false ? "aligned" : spreadPorts;
  const assignedSides = portMode === "spread"
    ? spreadRelationshipJunctionSides(component)
    : portMode === "fan" ? fanRelationshipJunctionSides(component) : new Map();
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
          ? node.dockSides[edge.relationship.endpoint]
          : assignedSides.get(`${edgeId}:${role}`)
            || chooseRelationshipPortSide(node, other, counts.get(nodeId), false);
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
      ports.filter((port) => port.nodeId === node.id && port.side === side), reverseOrder,
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
  const simplified = [];
  points.forEach((point) => {
    const prior = simplified[simplified.length - 1];
    if (prior && prior.x === point.x && prior.y === point.y) return;
    simplified.push(point);
    let changed = true;
    while (changed && simplified.length >= 3) {
      changed = false;
      const next = simplified[simplified.length - 1];
      const middle = simplified[simplified.length - 2];
      const first = simplified[simplified.length - 3];
      const collinear = first.x === middle.x && middle.x === next.x
        || first.y === middle.y && middle.y === next.y;
      if (collinear) {
        simplified.splice(simplified.length - 2, 1);
        changed = true;
      }
    }
  });
  return simplified;
}

/** Remove clear orthogonal doglegs that return to their original axis. */
function simplifyTopologyDoglegs(points, rectangles) {
  const simplified = simplifyTopologyRoute(points);
  let changed = true;
  while (changed) {
    changed = false;
    for (let index = 0; index + 3 < simplified.length; index += 1) {
      const first = simplified[index];
      const last = simplified[index + 3];
      if (first.x !== last.x && first.y !== last.y) continue;
      if (!orthogonalSegmentClearsRectangles(first, last, rectangles)) continue;
      simplified.splice(index + 1, 2);
      changed = true;
      break;
    }
  }
  return simplifyTopologyRoute(simplified);
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

function topologySegmentConflictScore(candidate, occupied, candidateHalfExtent = 0) {
  const candidateHorizontal = candidate.start.y === candidate.end.y;
  return occupied.reduce((score, segment) => {
    const occupiedHorizontal = segment.start.y === segment.end.y;
    if (candidateHorizontal === occupiedHorizontal) {
      const candidateRange = candidateHorizontal
        ? [candidate.start.x, candidate.end.x] : [candidate.start.y, candidate.end.y];
      const occupiedRange = occupiedHorizontal
        ? [segment.start.x, segment.end.x] : [segment.start.y, segment.end.y];
      const overlap = Math.min(Math.max(...candidateRange), Math.max(...occupiedRange))
        - Math.max(Math.min(...candidateRange), Math.min(...occupiedRange));
      if (overlap < 0) return score;
      const distance = candidateHorizontal
        ? Math.abs(candidate.start.y - segment.start.y)
        : Math.abs(candidate.start.x - segment.start.x);
      const required = candidateHalfExtent + (segment.halfExtent || 0)
        + TOPOLOGY_ROUTE_CHANNEL_SPACING;
      if (overlap > 0 && distance < required) {
        return score + 800 + overlap * 8 + (required - distance) * 40;
      }
      return score + (overlap === 0 && distance < required ? 180 : 0);
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
function topologyVisibilityRoute(
  start, end, rectangles, occupiedSegments = [], traceHalfExtent = 0,
) {
  const occupiedVerticalXs = occupiedSegments.filter(
    (segment) => segment.start.x === segment.end.x,
  ).flatMap((segment) => {
    const offset = (segment.halfExtent || 0) + traceHalfExtent
      + TOPOLOGY_ROUTE_CHANNEL_SPACING;
    return [segment.start.x - offset, segment.start.x + offset];
  });
  const occupiedHorizontalYs = occupiedSegments.filter(
    (segment) => segment.start.y === segment.end.y,
  ).flatMap((segment) => {
    const offset = (segment.halfExtent || 0) + traceHalfExtent
      + TOPOLOGY_ROUTE_CHANNEL_SPACING;
    return [segment.start.y - offset, segment.start.y + offset];
  });
  const xs = [...new Set([
    start.x,
    end.x,
    ...rectangles.flatMap((rectangle) => [rectangle.left, rectangle.right]),
    ...occupiedVerticalXs,
  ])].sort((left, right) => left - right);
  const ys = [...new Set([
    start.y,
    end.y,
    ...rectangles.flatMap((rectangle) => [rectangle.top, rectangle.bottom]),
    ...occupiedHorizontalYs,
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
      const conflict = topologySegmentConflictScore(
        { start: first, end: second }, occupiedSegments, traceHalfExtent,
      );
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

/** Find a validated route around the outside of every protected node envelope. */
function topologyPerimeterRoute(
  start, end, rectangles, occupiedSegments = [], traceHalfExtent = 0,
) {
  const margin = TOPOLOGY_ROUTE_CHANNEL_SPACING;
  const left = Math.min(...rectangles.map((rectangle) => rectangle.left)) - margin;
  const right = Math.max(...rectangles.map((rectangle) => rectangle.right)) + margin;
  const top = Math.min(...rectangles.map((rectangle) => rectangle.top)) - margin;
  const bottom = Math.max(...rectangles.map((rectangle) => rectangle.bottom)) + margin;
  const candidates = [
    [start, { x: start.x, y: top }, { x: end.x, y: top }, end],
    [start, { x: right, y: start.y }, { x: right, y: end.y }, end],
    [start, { x: start.x, y: bottom }, { x: end.x, y: bottom }, end],
    [start, { x: left, y: start.y }, { x: left, y: end.y }, end],
  ].map(simplifyTopologyRoute).filter((points) => topologyRouteSegments(points).every(
    (segment) => orthogonalSegmentClearsRectangles(segment.start, segment.end, rectangles),
  ));
  const score = (points) => topologyRouteSegments(points).reduce((total, segment) => (
    total
      + Math.abs(segment.end.x - segment.start.x)
      + Math.abs(segment.end.y - segment.start.y)
      + topologySegmentConflictScore(segment, occupiedSegments, traceHalfExtent)
  ), Math.max(0, points.length - 2) * 24);
  return candidates.sort((first, second) => score(first) - score(second))[0] || null;
}

function topologyPortEscape(port, node, clearance = RELATIONSHIP_DIAGRAM_SPACING) {
  return {
    left: { x: node.left - clearance, y: port.point.y },
    right: { x: node.left + node.width + clearance, y: port.point.y },
    top: { x: port.point.x, y: node.top - clearance },
    bottom: { x: port.point.x, y: node.top + node.height + clearance },
  }[port.side];
}

/** Return the greatest rendered distance from a route centerline. */
function topologyTraceHalfExtent(groupCount) {
  if (groupCount <= 0) return 1.5;
  if (groupCount <= TOPOLOGY_LANE_LIMIT) {
    return (groupCount - 1) * TOPOLOGY_LANE_SPACING / 2 + 1.5;
  }
  return 4.5;
}

/** Route one edge orthogonally through its assigned perimeter ports. */
function routeRelationshipEdge(
  sourcePort, targetPort, nodes, occupiedSegments = [], traceHalfExtent = 0,
) {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const clearance = RELATIONSHIP_DIAGRAM_SPACING + traceHalfExtent;
  const start = topologyPortEscape(sourcePort, nodesById.get(sourcePort.nodeId), clearance);
  const end = topologyPortEscape(targetPort, nodesById.get(targetPort.nodeId), clearance);
  const rectangles = nodes.map((node) => ({
    left: node.left - clearance,
    right: node.left + node.width + clearance,
    top: node.top - clearance,
    bottom: node.top + node.height + clearance,
  }));
  const visibleMiddle = topologyVisibilityRoute(
    start, end, rectangles, occupiedSegments, traceHalfExtent,
  );
  const routedMiddle = visibleMiddle
    || topologyPerimeterRoute(
      start, end, rectangles, occupiedSegments, traceHalfExtent,
    );
  if (!routedMiddle) return null;
  const middle = simplifyTopologyDoglegs(routedMiddle, rectangles);
  const points = simplifyTopologyRoute([
    sourcePort.point,
    start,
    ...middle.slice(1, -1),
    end,
    targetPort.point,
  ]);
  return {
    d: roundedTopologyRoute(points),
    kind: visibleMiddle ? "orthogonal" : "perimeter",
    points,
    sourcePort,
    targetPort,
    traceHalfExtent,
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
      const occupied = topologyRouteSegments(other.points).map((segment) => ({
        ...segment, halfExtent: other.traceHalfExtent || 0,
      }));
      segments.forEach((segment) => {
        score += topologySegmentConflictScore(
          segment, occupied, route.traceHalfExtent || 0,
        );
      });
    });
  });
  return score;
}

/** Describe visible route defects independently of route discovery order. */
function topologyRouteSetQuality(routes) {
  const routeList = [...routes.values()];
  const quality = {
    overlaps: 0, parallelConflicts: 0, parallelClearanceShortfall: 0,
    minimumParallelGap: Number.POSITIVE_INFINITY, crossings: 0,
    shortSegments: 0, excessLength: 0, bends: 0, totalLength: 0,
  };
  routeList.forEach((route, index) => {
    const segments = topologyRouteSegments(route.points);
    const routeLength = segments.reduce((total, segment) => {
      const length = Math.abs(segment.end.x - segment.start.x)
        + Math.abs(segment.end.y - segment.start.y);
      if (length > 0 && length < TOPOLOGY_SHORT_SEGMENT) quality.shortSegments += 1;
      return total + length;
    }, 0);
    const first = route.points[0];
    const last = route.points[route.points.length - 1];
    quality.totalLength += routeLength;
    quality.excessLength += routeLength
      - Math.abs(last.x - first.x) - Math.abs(last.y - first.y);
    quality.bends += Math.max(0, segments.length - 1);
    routeList.slice(index + 1).forEach((other) => {
      segments.forEach((segment) => topologyRouteSegments(other.points).forEach((candidate) => {
        const horizontal = segment.start.y === segment.end.y;
        const candidateHorizontal = candidate.start.y === candidate.end.y;
        if (horizontal === candidateHorizontal) {
          const firstRange = horizontal
            ? [segment.start.x, segment.end.x] : [segment.start.y, segment.end.y];
          const secondRange = horizontal
            ? [candidate.start.x, candidate.end.x] : [candidate.start.y, candidate.end.y];
          const overlap = Math.min(Math.max(...firstRange), Math.max(...secondRange))
            - Math.max(Math.min(...firstRange), Math.min(...secondRange));
          if (overlap <= 0) return;
          const distance = horizontal
            ? Math.abs(segment.start.y - candidate.start.y)
            : Math.abs(segment.start.x - candidate.start.x);
          const visibleGap = distance
            - (route.traceHalfExtent || 0) - (other.traceHalfExtent || 0);
          quality.minimumParallelGap = Math.min(quality.minimumParallelGap, visibleGap);
          if (distance === 0) quality.overlaps += 1;
          if (visibleGap < TOPOLOGY_ROUTE_CHANNEL_SPACING) {
            quality.parallelConflicts += 1;
            quality.parallelClearanceShortfall += TOPOLOGY_ROUTE_CHANNEL_SPACING - visibleGap;
          }
          return;
        }
        const horizontalSegment = horizontal ? segment : candidate;
        const verticalSegment = horizontal ? candidate : segment;
        const x = verticalSegment.start.x;
        const y = horizontalSegment.start.y;
        if (x > Math.min(horizontalSegment.start.x, horizontalSegment.end.x)
          && x < Math.max(horizontalSegment.start.x, horizontalSegment.end.x)
          && y > Math.min(verticalSegment.start.y, verticalSegment.end.y)
          && y < Math.max(verticalSegment.start.y, verticalSegment.end.y)) {
          quality.crossings += 1;
        }
      }));
    });
  });
  if (!Number.isFinite(quality.minimumParallelGap)) {
    quality.minimumParallelGap = TOPOLOGY_ROUTE_CHANNEL_SPACING;
  }
  return quality;
}

function compareTopologyRouteSafety(left, right) {
  return left.overlaps - right.overlaps
    || left.parallelConflicts - right.parallelConflicts
    || left.parallelClearanceShortfall - right.parallelClearanceShortfall
    || left.crossings - right.crossings;
}

function compareTopologyRouteQuality(left, right) {
  return compareTopologyRouteSafety(left, right)
    || left.shortSegments - right.shortSegments
    || left.excessLength - right.excessLength
    || left.bends - right.bends
    || left.totalLength - right.totalLength;
}

function routeRelationshipEdges(component, ports, edgeGroups) {
  const portsById = new Map(ports.map((port) => [port.id, port]));
  const stableEdges = component.edges.slice().sort((left, right) => (
    relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))
  ));
  const edgeDistance = (edge) => {
    const nodes = new Map(component.nodes.map((node) => [node.id, node]));
    const source = topologyNodeCenter(nodes.get(edge.sourceId));
    const target = topologyNodeCenter(nodes.get(edge.targetId));
    return Math.abs(target.x - source.x) + Math.abs(target.y - source.y);
  };
  const edgeConstraint = (edge) => component.nodes.find(
    (node) => node.id === edge.sourceId,
  ).neighbors.length + component.nodes.find((node) => node.id === edge.targetId).neighbors.length;
  const orders = [
    stableEdges,
    stableEdges.slice().reverse(),
    stableEdges.slice().sort((left, right) => edgeDistance(left) - edgeDistance(right)
      || relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))),
    stableEdges.slice().sort((left, right) => edgeDistance(right) - edgeDistance(left)
      || relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))),
    stableEdges.slice().sort((left, right) => edgeConstraint(right) - edgeConstraint(left)
      || relationshipEdgeId(left).localeCompare(relationshipEdgeId(right))),
  ];
  let best = null;
  orders.forEach((edges) => {
    const routes = new Map();
    const occupied = [];
    let complete = true;
    edges.forEach((edge) => {
      const edgeId = relationshipEdgeId(edge);
      const route = routeRelationshipEdge(
        portsById.get(`${edgeId}:source`),
        portsById.get(`${edgeId}:target`),
        component.nodes,
        occupied,
        topologyTraceHalfExtent(edgeGroups.get(edgeId)?.length || 0),
      );
      if (!route) {
        complete = false;
        return;
      }
      routes.set(edgeId, route);
      occupied.push(...topologyRouteSegments(route.points).map((segment) => ({
        ...segment, halfExtent: route.traceHalfExtent,
      })));
    });
    if (!complete) return;
    const quality = topologyRouteSetQuality(routes);
    const score = topologyRouteSetScore(routes);
    if (!best || compareTopologyRouteQuality(quality, best.quality) < 0
      || (!compareTopologyRouteQuality(quality, best.quality) && score < best.score)) {
      best = { routes, quality, score };
    }
  });
  if (!best) throw new Error("Unable to route relationship edges outside protected nodes.");
  return best.routes;
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

function relationshipRootCandidates(component) {
  const junctions = component.nodes.filter((node) => node.kind === "junction");
  return (junctions.length ? junctions : component.nodes).slice().sort((left, right) => (
    right.neighbors.length - left.neighbors.length
    || left.index - right.index
    || left.id.localeCompare(right.id)
  ));
}

function relationshipLayerCrossingCount(component, positions) {
  let crossings = 0;
  component.edges.forEach((edge, index) => component.edges.slice(index + 1).forEach((other) => {
    const source = component.nodes.find((node) => node.id === edge.sourceId);
    const target = component.nodes.find((node) => node.id === edge.targetId);
    const otherSource = component.nodes.find((node) => node.id === other.sourceId);
    const otherTarget = component.nodes.find((node) => node.id === other.targetId);
    if (!source || !target || !otherSource || !otherTarget) return;
    if (source.depth !== otherSource.depth || target.depth !== otherTarget.depth) return;
    if (source.id === otherSource.id || target.id === otherTarget.id) return;
    const sourceOrder = positions.get(source.id) - positions.get(otherSource.id);
    const targetOrder = positions.get(target.id) - positions.get(otherTarget.id);
    if (sourceOrder * targetOrder < 0) crossings += 1;
  }));
  return crossings;
}

/** Return a stable same-depth order after deterministic median sweeps. */
function optimizeRelationshipNodeOrder(component) {
  const layers = new Map();
  component.nodes.forEach((node) => {
    if (!layers.has(node.depth)) layers.set(node.depth, []);
    layers.get(node.depth).push(node);
  });
  const depths = [...layers.keys()].sort((left, right) => left - right);
  const original = new Map();
  depths.forEach((depth) => layers.get(depth).forEach((node, index) => {
    original.set(node.id, index);
  }));
  const positions = new Map(original);
  const adjacentPositions = (node) => component.edges.flatMap((edge) => {
    if (edge.sourceId === node.id) return [positions.get(edge.targetId)];
    if (edge.targetId === node.id) return [positions.get(edge.sourceId)];
    return [];
  }).filter((position) => position !== undefined);
  for (let pass = 0; pass < 6; pass += 1) {
    const orderedDepths = pass % 2 ? depths.slice().reverse() : depths;
    orderedDepths.forEach((depth) => {
      layers.get(depth).sort((left, right) => {
        const score = (node) => {
          const adjacent = adjacentPositions(node);
          return adjacent.length
            ? adjacent.reduce((total, value) => total + value, 0) / adjacent.length
            : positions.get(node.id);
        };
        return score(left) - score(right)
          || original.get(left.id) - original.get(right.id)
          || left.id.localeCompare(right.id);
      }).forEach((node, index) => positions.set(node.id, index));
    });
  }
  const selected = relationshipLayerCrossingCount(component, positions)
    <= relationshipLayerCrossingCount(component, original) ? positions : original;
  return component.nodes.slice().sort((left, right) => (
    left.depth - right.depth || selected.get(left.id) - selected.get(right.id)
  ));
}

function relationshipOrderedNeighbors(component, node, orderMode) {
  const nodes = new Map(component.nodes.map((candidate) => [candidate.id, candidate]));
  const ordered = node.neighbors.slice().sort((leftId, rightId) => {
    const left = nodes.get(leftId);
    const right = nodes.get(rightId);
    return orderMode === "dense"
      ? right.neighbors.length - left.neighbors.length || left.id.localeCompare(right.id)
      : left.id.localeCompare(right.id);
  });
  return orderMode === "reverse" ? ordered.reverse() : ordered;
}

/** Seed one component in topology rings around a candidate root and branch order. */
function radialRelationshipComponent(component, rotation, dimensions, root, orderMode) {
  const depths = new Map([[root.id, 0]]);
  const queue = [root];
  const traversal = [root];
  while (queue.length) {
    const node = queue.shift();
    relationshipOrderedNeighbors(component, node, orderMode).forEach((neighborId) => {
      if (depths.has(neighborId)) return;
      depths.set(neighborId, depths.get(node.id) + 1);
      const neighbor = component.nodes.find((candidate) => candidate.id === neighborId);
      queue.push(neighbor);
      traversal.push(neighbor);
    });
  }
  const rings = new Map();
  traversal.forEach((node) => {
    const depth = depths.get(node.id) || 0;
    if (!rings.has(depth)) rings.set(depth, []);
    rings.get(depth).push(node);
  });
  const positions = new Map([[root.id, { x: 0, y: 0 }]]);
  let radius = 0;
  let priorDiagonal = Math.hypot(
    dimensions.get(root.id).width,
    dimensions.get(root.id).height,
  );
  [...rings.keys()].sort((left, right) => left - right).slice(1).forEach((depth) => {
    const nodes = rings.get(depth);
    const maximumDiagonal = Math.max(...nodes.map((node) => {
      const size = dimensions.get(node.id);
      return Math.hypot(size.width, size.height);
    }));
    radius += priorDiagonal / 2 + maximumDiagonal / 2 + TOPOLOGY_CONNECTED_GAP;
    priorDiagonal = maximumDiagonal;
    nodes.forEach((node, index) => {
      const angle = rotation * Math.PI / 2 - Math.PI / 2
        + 2 * Math.PI * index / nodes.length;
      positions.set(node.id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
  });
  return positions;
}

function relationshipPairGap(component, firstId, secondId) {
  const connected = component.edges.some((edge) => (
    edge.sourceId === firstId && edge.targetId === secondId
    || edge.sourceId === secondId && edge.targetId === firstId
  ));
  return connected ? TOPOLOGY_CONNECTED_GAP : TOPOLOGY_NODE_GAP;
}

function relationshipNodePositionClears(component, node, point, positions, dimensions) {
  const size = dimensions.get(node.id);
  return component.nodes.every((other) => {
    if (other.id === node.id) return true;
    const otherPoint = positions.get(other.id);
    const otherSize = dimensions.get(other.id);
    const gap = relationshipPairGap(component, node.id, other.id);
    const horizontalClearance = Math.abs(otherPoint.x - point.x)
      - (size.width + otherSize.width) / 2;
    const verticalClearance = Math.abs(otherPoint.y - point.y)
      - (size.height + otherSize.height) / 2;
    return horizontalClearance >= gap || verticalClearance >= gap;
  });
}

/** Resolve rectangular overlap without changing deterministic topology order. */
function separateRelationshipNodes(component, positions, dimensions) {
  for (let iteration = 0; iteration < 80; iteration += 1) {
    let moved = false;
    component.nodes.forEach((node, index) => component.nodes.slice(index + 1).forEach((other) => {
      const first = positions.get(node.id);
      const second = positions.get(other.id);
      const firstSize = dimensions.get(node.id);
      const secondSize = dimensions.get(other.id);
      const gap = relationshipPairGap(component, node.id, other.id);
      const overlapX = (firstSize.width + secondSize.width) / 2 + gap
        - Math.abs(second.x - first.x);
      const overlapY = (firstSize.height + secondSize.height) / 2 + gap
        - Math.abs(second.y - first.y);
      if (overlapX <= 0 || overlapY <= 0) return;
      moved = true;
      if (overlapX < overlapY) {
        const direction = second.x === first.x
          ? (node.id.localeCompare(other.id) < 0 ? 1 : -1)
          : Math.sign(second.x - first.x);
        first.x -= direction * overlapX / 2;
        second.x += direction * overlapX / 2;
      } else {
        const direction = second.y === first.y
          ? (node.id.localeCompare(other.id) < 0 ? 1 : -1)
          : Math.sign(second.y - first.y);
        first.y -= direction * overlapY / 2;
        second.y += direction * overlapY / 2;
      }
    }));
    if (!moved) break;
  }
}

/** Remove remaining axis slack without crossing another node's protected envelope. */
function compactRelationshipAxes(component, positions, dimensions) {
  for (let pass = 0; pass < 12; pass += 1) {
    let moved = false;
    const centroid = component.nodes.reduce((point, node) => ({
      x: point.x + positions.get(node.id).x / component.nodes.length,
      y: point.y + positions.get(node.id).y / component.nodes.length,
    }), { x: 0, y: 0 });
    component.nodes.slice().sort((left, right) => (
      right.neighbors.length - left.neighbors.length || left.id.localeCompare(right.id)
    )).forEach((node) => {
      ["x", "y"].forEach((axis) => {
        const point = positions.get(node.id);
        let movement = centroid[axis] - point[axis];
        while (Math.abs(movement) >= 0.5) {
          const candidate = { ...point, [axis]: point[axis] + movement };
          if (relationshipNodePositionClears(
            component, node, candidate, positions, dimensions,
          )) {
            point[axis] = candidate[axis];
            moved = true;
            break;
          }
          movement /= 2;
        }
      });
    });
    if (!moved) break;
  }
}

function relationshipRectangleSupport(size, direction) {
  return Math.abs(direction.x) * size.width / 2 + Math.abs(direction.y) * size.height / 2;
}

/** Pull connected nodes toward their minimum safe edge gap without introducing overlap. */
function compactRelationshipComponent(component, positions, dimensions, rootId) {
  for (let iteration = 0; iteration < 48; iteration += 1) {
    component.edges.forEach((edge) => {
      const source = positions.get(edge.sourceId);
      const target = positions.get(edge.targetId);
      const difference = { x: target.x - source.x, y: target.y - source.y };
      const length = Math.hypot(difference.x, difference.y) || 1;
      const direction = { x: difference.x / length, y: difference.y / length };
      const desired = relationshipRectangleSupport(dimensions.get(edge.sourceId), direction)
        + relationshipRectangleSupport(dimensions.get(edge.targetId), direction)
        + TOPOLOGY_CONNECTED_GAP;
      const adjustment = Math.max(0, length - desired) * 0.18;
      if (!adjustment) return;
      const sourceWeight = edge.sourceId === rootId ? 0 : edge.targetId === rootId ? 1 : 0.5;
      const targetWeight = 1 - sourceWeight;
      source.x += direction.x * adjustment * sourceWeight;
      source.y += direction.y * adjustment * sourceWeight;
      target.x -= direction.x * adjustment * targetWeight;
      target.y -= direction.y * adjustment * targetWeight;
    });
    const centroid = component.nodes.reduce((point, node) => ({
      x: point.x + positions.get(node.id).x / component.nodes.length,
      y: point.y + positions.get(node.id).y / component.nodes.length,
    }), { x: 0, y: 0 });
    component.nodes.forEach((node) => {
      if (node.id === rootId) return;
      const point = positions.get(node.id);
      point.x += (centroid.x - point.x) * 0.025;
      point.y += (centroid.y - point.y) * 0.025;
    });
    separateRelationshipNodes(component, positions, dimensions);
  }
  compactRelationshipAxes(component, positions, dimensions);
}

function relationshipBounds(nodes, positions, dimensions) {
  const left = Math.min(...nodes.map((node) => (
    positions.get(node.id).x - dimensions.get(node.id).width / 2
  )));
  const right = Math.max(...nodes.map((node) => (
    positions.get(node.id).x + dimensions.get(node.id).width / 2
  )));
  const top = Math.min(...nodes.map((node) => (
    positions.get(node.id).y - dimensions.get(node.id).height / 2
  )));
  const bottom = Math.max(...nodes.map((node) => (
    positions.get(node.id).y + dimensions.get(node.id).height / 2
  )));
  return { left, right, top, bottom, width: right - left, height: bottom - top };
}

function relationshipEdgeCrossings(components, positions) {
  const orientation = (first, second, third) => (
    (second.x - first.x) * (third.y - first.y)
    - (second.y - first.y) * (third.x - first.x)
  );
  return components.reduce((count, component) => count + component.edges.reduce(
    (edgeCount, edge, index) => edgeCount + component.edges.slice(index + 1).filter((other) => {
      if ([edge.sourceId, edge.targetId].some((id) => (
        id === other.sourceId || id === other.targetId
      ))) return false;
      const first = positions.get(edge.sourceId);
      const second = positions.get(edge.targetId);
      const third = positions.get(other.sourceId);
      const fourth = positions.get(other.targetId);
      return orientation(first, second, third) * orientation(first, second, fourth) < 0
        && orientation(third, fourth, first) * orientation(third, fourth, second) < 0;
    }).length,
    0,
  ), 0);
}

/** Build, orient, and compact one deterministic cardinal-topology candidate. */
function legacyRelationshipTopologyLayoutCandidate(components, specification, options = {}) {
  const componentLayouts = components.map((component, componentIndex) => {
    const root = specification.roots[componentIndex];
    let dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node),
    ]));
    let positions = radialRelationshipComponent(
      component, specification.rotation, dimensions, root, specification.orderMode,
    );
    let dockSides = new Map(component.nodes.filter((node) => node.kind === "pathway")
      .map((node) => [node.id, relationshipPathwayDockSides(component, node, positions)]));
    dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ]));
    positions = radialRelationshipComponent(
      component, specification.rotation, dimensions, root, specification.orderMode,
    );
    dockSides = new Map(component.nodes.filter((node) => node.kind === "pathway")
      .map((node) => [node.id, relationshipPathwayDockSides(component, node, positions)]));
    dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ]));
    separateRelationshipNodes(component, positions, dimensions);
    compactRelationshipComponent(component, positions, dimensions, root.id);
    return { component, positions, dockSides, dimensions,
      bounds: relationshipBounds(component.nodes, positions, dimensions) };
  });
  const padding = TOPOLOGY_CANVAS_PADDING;
  const gap = TOPOLOGY_COMPONENT_GAP;
  const totalArea = componentLayouts.reduce(
    (total, item) => total + (item.bounds.width + gap) * (item.bounds.height + gap), 0,
  );
  const viewportAspect = Math.max(0.5, Math.min(
    2.5,
    (options.width || 1) / Math.max(1, options.height || 1),
  ));
  const rowTarget = Math.max(260, Math.sqrt(totalArea * viewportAspect));
  const positions = new Map();
  const dockSides = new Map();
  const dimensions = new Map();
  let x = padding;
  let y = padding;
  let rowHeight = 0;
  let maximumRight = padding;
  componentLayouts.forEach((item) => {
    if (x > padding && x + item.bounds.width > rowTarget + padding) {
      x = padding;
      y += rowHeight + gap;
      rowHeight = 0;
    }
    item.component.nodes.forEach((node) => {
      const point = item.positions.get(node.id);
      positions.set(node.id, {
        x: x + point.x - item.bounds.left,
        y: y + point.y - item.bounds.top,
      });
      dimensions.set(node.id, item.dimensions.get(node.id));
    });
    item.dockSides.forEach((sides, id) => dockSides.set(id, sides));
    maximumRight = Math.max(maximumRight, x + item.bounds.width);
    rowHeight = Math.max(rowHeight, item.bounds.height);
    x += item.bounds.width + gap;
  });
  const width = Math.max(260, maximumRight + padding);
  const height = Math.max(260, y + rowHeight + padding);
  const edgeLength = components.flatMap((component) => component.edges).reduce(
    (total, edge) => {
      const source = positions.get(edge.sourceId);
      const target = positions.get(edge.targetId);
      return total + Math.hypot(target.x - source.x, target.y - source.y);
    }, 0,
  );
  return {
    positions, dockSides, dimensions, width, height,
    rotation: specification.rotation,
    layoutKey: specification.key,
    crossings: relationshipEdgeCrossings(components, positions),
    edgeLength,
  };
}

function relationshipLayerOrder(nodes, orderMode, optimizedOrder) {
  const ordered = nodes.slice().sort((left, right) => (
    orderMode === "dense"
      ? right.neighbors.length - left.neighbors.length
        || optimizedOrder.get(left.id) - optimizedOrder.get(right.id)
      : optimizedOrder.get(left.id) - optimizedOrder.get(right.id)
        || left.id.localeCompare(right.id)
  ));
  return orderMode === "reverse" ? ordered.reverse() : ordered;
}

/** Place topology layers without overlap using immutable visible-node dimensions. */
function layeredRelationshipGeometry(components, specification, dimensions) {
  const horizontal = specification.flow === "horizontal";
  const componentLayouts = components.map((component, componentIndex) => {
    const root = specification.roots[componentIndex];
    const depths = new Map([[root.id, 0]]);
    const queue = [root];
    while (queue.length) {
      const node = queue.shift();
      relationshipOrderedNeighbors(component, node, specification.orderMode)
        .forEach((neighborId) => {
          if (depths.has(neighborId)) return;
          depths.set(neighborId, depths.get(node.id) + 1);
          queue.push(component.nodes.find((candidate) => candidate.id === neighborId));
        });
    }
    const depthComponent = {
      ...component,
      nodes: component.nodes.map((node) => ({ ...node, depth: depths.get(node.id) || 0 })),
    };
    const optimizedOrder = new Map(optimizeRelationshipNodeOrder(depthComponent).map(
      (node, index) => [node.id, index],
    ));
    const byDepth = new Map();
    component.nodes.forEach((node) => {
      const depth = depths.get(node.id) || 0;
      if (!byDepth.has(depth)) byDepth.set(depth, []);
      byDepth.get(depth).push(node);
    });
    const sortedDepths = [...byDepth.keys()].sort((left, right) => left - right);
    if (specification.direction === "reverse") sortedDepths.reverse();
    const layers = sortedDepths.map((depth) => {
      const nodes = relationshipLayerOrder(
        byDepth.get(depth), specification.orderMode, optimizedOrder,
      );
      const sizes = nodes.map((node) => dimensions.get(node.id));
      return {
        nodes,
        width: horizontal
          ? Math.max(...sizes.map((size) => size.width))
          : sizes.reduce((total, size) => total + size.width, 0)
            + Math.max(0, sizes.length - 1) * TOPOLOGY_NODE_GAP,
        height: horizontal
          ? sizes.reduce((total, size) => total + size.height, 0)
            + Math.max(0, sizes.length - 1) * TOPOLOGY_NODE_GAP
          : Math.max(...sizes.map((size) => size.height)),
      };
    });
    const width = horizontal
      ? layers.reduce((total, layer) => total + layer.width, 0)
        + Math.max(0, layers.length - 1) * TOPOLOGY_CONNECTED_GAP
      : Math.max(...layers.map((layer) => layer.width));
    const height = horizontal
      ? Math.max(...layers.map((layer) => layer.height))
      : layers.reduce((total, layer) => total + layer.height, 0)
        + Math.max(0, layers.length - 1) * TOPOLOGY_CONNECTED_GAP;
    const positions = new Map();
    let flowOffset = 0;
    layers.forEach((layer) => {
      let crossOffset = horizontal ? (height - layer.height) / 2 : (width - layer.width) / 2;
      layer.nodes.forEach((node) => {
        const size = dimensions.get(node.id);
        positions.set(node.id, horizontal ? {
          x: flowOffset + layer.width / 2,
          y: crossOffset + size.height / 2,
        } : {
          x: crossOffset + size.width / 2,
          y: flowOffset + layer.height / 2,
        });
        crossOffset += (horizontal ? size.height : size.width) + TOPOLOGY_NODE_GAP;
      });
      flowOffset += (horizontal ? layer.width : layer.height) + TOPOLOGY_CONNECTED_GAP;
    });
    return { component, positions, width, height };
  });
  const positions = new Map();
  let componentOffset = TOPOLOGY_CANVAS_PADDING;
  let maximumCrossExtent = 0;
  componentLayouts.forEach((layout) => {
    layout.component.nodes.forEach((node) => {
      const point = layout.positions.get(node.id);
      positions.set(node.id, horizontal ? {
        x: point.x + TOPOLOGY_CANVAS_PADDING,
        y: point.y + componentOffset,
      } : {
        x: point.x + componentOffset,
        y: point.y + TOPOLOGY_CANVAS_PADDING,
      });
    });
    componentOffset += (horizontal ? layout.height : layout.width) + TOPOLOGY_COMPONENT_GAP;
    maximumCrossExtent = Math.max(
      maximumCrossExtent, horizontal ? layout.width : layout.height,
    );
  });
  return {
    positions,
    width: horizontal
      ? maximumCrossExtent + TOPOLOGY_CANVAS_PADDING * 2
      : componentOffset - TOPOLOGY_COMPONENT_GAP + TOPOLOGY_CANVAS_PADDING,
    height: horizontal
      ? componentOffset - TOPOLOGY_COMPONENT_GAP + TOPOLOGY_CANVAS_PADDING
      : maximumCrossExtent + TOPOLOGY_CANVAS_PADDING * 2,
  };
}

/** Build a layered candidate whose dimensions and endpoint orientation converge. */
function relationshipTopologyLayoutCandidate(components, specification) {
  let dockSides = new Map(components.flatMap((component) => component.nodes
    .filter((node) => node.kind === "pathway")
    .map((node) => [node.id, { start: "left", end: "right" }])));
  let dimensions;
  let geometry;
  for (let pass = 0; pass < 4; pass += 1) {
    dimensions = new Map(components.flatMap((component) => component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ])));
    geometry = layeredRelationshipGeometry(components, specification, dimensions);
    const nextDockSides = new Map(components.flatMap((component) => component.nodes
      .filter((node) => node.kind === "pathway")
      .map((node) => [
        node.id, relationshipPathwayDockSides(component, node, geometry.positions),
      ])));
    const unchanged = [...nextDockSides].every(([id, sides]) => (
      sides.start === dockSides.get(id)?.start && sides.end === dockSides.get(id)?.end
    ));
    dockSides = nextDockSides;
    if (unchanged) break;
  }
  dimensions = new Map(components.flatMap((component) => component.nodes.map((node) => [
    node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
  ])));
  geometry = layeredRelationshipGeometry(components, specification, dimensions);
  const edgeLength = components.flatMap((component) => component.edges).reduce(
    (total, edge) => {
      const source = geometry.positions.get(edge.sourceId);
      const target = geometry.positions.get(edge.targetId);
      return total + Math.abs(target.x - source.x) + Math.abs(target.y - source.y);
    }, 0,
  );
  return {
    positions: geometry.positions,
    dockSides,
    dimensions,
    width: Math.max(260, geometry.width),
    height: Math.max(260, geometry.height),
    rotation: specification.rotation,
    layoutKey: specification.key,
    crossings: relationshipEdgeCrossings(components, geometry.positions),
    edgeLength,
  };
}

function relationshipLayoutSpecifications(components) {
  const roots = components.map(relationshipRootCandidates);
  const maximumRootCount = Math.max(...roots.map((items) => items.length));
  const specifications = [];
  for (let rootIndex = 0; rootIndex < maximumRootCount; rootIndex += 1) {
    ["horizontal", "vertical"].forEach((flow, flowIndex) => {
      ["forward", "reverse"].forEach((direction, directionIndex) => {
        ["stable", "reverse", "dense"].forEach((orderMode) => {
          const selectedRoots = roots.map((items) => items[rootIndex % items.length]);
          const rotation = flowIndex + directionIndex * 2;
          specifications.push({
            flow, direction, orderMode, rotation, roots: selectedRoots,
            key: [flow, direction, orderMode, ...selectedRoots.map((root) => root.id)].join("|"),
          });
        });
      });
    });
  }
  return specifications.slice(0, TOPOLOGY_LAYOUT_CANDIDATE_LIMIT);
}

/** Materialize one candidate as plain geometry without changing rendered elements. */
function materializeRelationshipLayout(components, layout) {
  return components.map((component) => ({
    ...component,
    nodes: component.nodes.map((node) => {
      const center = layout.positions.get(node.id);
      const dimensions = layout.dimensions.get(node.id);
      const left = center.x - dimensions.width / 2;
      const top = center.y - dimensions.height / 2;
      if (node.kind !== "pathway") {
        return {
          ...node, ...dimensions, left, top, hubCenter: center,
          dockPoints: null,
        };
      }
      const dockSides = layout.dockSides.get(node.id);
      const dockPoints = {};
      ["start", "end"].forEach((endpoint) => {
        const point = dimensions.docks[endpoint];
        dockPoints[dockSides[endpoint]] = { x: left + point.x, y: top + point.y };
      });
      return {
        ...node,
        ...dimensions,
        left,
        top,
        dockSides,
        dockPoints,
        hubCenter: { x: left + dimensions.centerX, y: top + dimensions.centerY },
      };
    }),
  }));
}

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
    const edgeGroups = new Map(component.edges.map((edge) => [
      relationshipEdgeId(edge),
      relationshipEndpointGroups(harness, edge.junction, edge.relationship),
    ]));
    const candidates = [
      { reverseOrder: false, portMode: "fan" },
      { reverseOrder: true, portMode: "fan" },
      { reverseOrder: false, portMode: "spread" },
      { reverseOrder: true, portMode: "spread" },
      { reverseOrder: false, portMode: "aligned" },
      { reverseOrder: true, portMode: "aligned" },
    ].map(({ reverseOrder, portMode }) => {
      const ports = allocateRelationshipPorts(component, reverseOrder, portMode);
      const routes = routeRelationshipEdges(component, ports, edgeGroups);
      return { component, ports, edgeGroups, routes,
        quality: topologyRouteSetQuality(routes) };
    }).sort((left, right) => (
      compareTopologyRouteQuality(left.quality, right.quality)
    ));
    return candidates[0];
  });
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

/** Route the compact shortlist first, widening only when it has no viable layout. */
function routeRelationshipLayoutPool(layouts, routeLayout, shortlistSize) {
  const candidates = [];
  const attempt = (items) => items.forEach((layout) => {
    const candidate = routeLayout(layout);
    if (candidate) candidates.push(candidate);
  });
  const preliminary = layouts.slice(0, shortlistSize);
  attempt(preliminary);
  if (!candidates.length && preliminary.length < layouts.length) {
    attempt(layouts.slice(preliminary.length));
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
  const candidates = routeRelationshipLayoutPool(layouts, (layout) => {
    layout.geometryComponents = materializeRelationshipLayout(components, layout);
    try {
      layout.routeSets = relationshipLayoutRouteSets(layout.geometryComponents, harness);
    } catch (_error) {
      return null;
    }
    const routes = new Map(layout.routeSets.flatMap((routeSet) => [...routeSet.routes]));
    layout.routeQuality = topologyRouteSetQuality(routes);
    return layout;
  }, shortlistSize);
  if (!candidates.length) throw new Error("Unable to produce a routed relationship layout.");
  const safe = candidates.filter((candidate) => (
    candidate.routeQuality.overlaps === 0
    && candidate.routeQuality.parallelConflicts === 0
    && candidate.routeQuality.crossings === 0
  )).sort(compareRelationshipLayouts);
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
  return safe.filter((candidate) => {
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
  layout.routeSets.forEach(({ component, ports, edgeGroups, routes }) => {
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
      overlay.append(renderTopologyEdge(edge, route, groups));
      portsById.get(`${edgeId}:source`).groups = groups;
      portsById.get(`${edgeId}:target`).groups = groups;
    });
    ports.forEach((port) => overlay.append(renderTopologyPort(port)));
  });
  stack.querySelector(".relationship-topology-edges")?.remove();
  stack.insertBefore(overlay, stack.children[0] || null);
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
