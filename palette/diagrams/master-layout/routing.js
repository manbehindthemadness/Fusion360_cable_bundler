/** Orthogonal route construction and scoring for master topology edges. */

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
    return (groupCount - 1) * TOPOLOGY_LANE_SPACING / 2 + 3;
  }
  return 5;
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
