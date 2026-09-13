/** Route, render, and position the master diagram's topology edges and nodes. */

const TOPOLOGY_TRACE_CLEARANCE = 14;
const TOPOLOGY_TRACE_CORNER_RADIUS = 8;
const TOPOLOGY_LANE_LIMIT = 5;
const TOPOLOGY_LANE_SPACING = 4;

function relationshipEndpointWires(harness, junction, relationship) {
  const relationships = junction.pathwayRelationships || [];
  const preceding = new Set(
    relationships.filter((item) => item.endpoint === "end").map((item) => item.pathwayId),
  );
  const following = new Set(
    relationships.filter((item) => item.endpoint === "start").map((item) => item.pathwayId),
  );
  return harness.wires.filter((wire) => wire.orderedPathwayIds.some((pathwayId, index) => {
    const nextPathwayId = wire.orderedPathwayIds[index + 1];
    if (!preceding.has(pathwayId) || !following.has(nextPathwayId)) return false;
    return relationship.endpoint === "end"
      ? relationship.pathwayId === pathwayId
      : relationship.pathwayId === nextPathwayId;
  }));
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

function cubicPoint(start, firstControl, secondControl, end, progress) {
  const remainder = 1 - progress;
  return {
    x: remainder ** 3 * start.x
      + 3 * remainder ** 2 * progress * firstControl.x
      + 3 * remainder * progress ** 2 * secondControl.x
      + progress ** 3 * end.x,
    y: remainder ** 3 * start.y
      + 3 * remainder ** 2 * progress * firstControl.y
      + 3 * remainder * progress ** 2 * secondControl.y
      + progress ** 3 * end.y,
  };
}

function directTopologyCurve(start, end, rectangles) {
  const middleX = (start.x + end.x) / 2;
  const firstControl = { x: middleX, y: start.y };
  const secondControl = { x: middleX, y: end.y };
  const samples = Math.max(24, Math.ceil(Math.abs(end.x - start.x) / 6));
  for (let index = 0; index <= samples; index += 1) {
    const point = cubicPoint(start, firstControl, secondControl, end, index / samples);
    if (rectangles.some((rectangle) => pointInsideRectangle(point, rectangle))) return null;
  }
  return `M ${start.x} ${start.y} C ${middleX} ${start.y}, ${middleX} ${end.y}, ${end.x} ${end.y}`;
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

/** Find a deterministic, bend-aware left-to-right route through measured node bounds. */
function topologyVisibilityRoute(start, end, rectangles) {
  const xs = [...new Set([
    start.x,
    end.x,
    ...rectangles.flatMap((rectangle) => [rectangle.left, rectangle.right]),
  ])].filter((x) => x >= start.x && x <= end.x).sort((left, right) => left - right);
  const ys = [...new Set([
    start.y,
    end.y,
    ...rectangles.flatMap((rectangle) => [rectangle.top, rectangle.bottom]),
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
      neighbors.get(index).push({ index: nextIndex, direction: horizontal ? "h" : "v", distance });
      if (!horizontal) {
        neighbors.get(nextIndex).push({ index, direction: "v", distance });
      }
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
      const cost = current.cost + neighbor.distance + bendCost;
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

/** Route one edge around every unrelated topology node where measured geometry permits. */
function routeRelationshipEdge(source, target, nodes) {
  const start = { x: source.left + source.width, y: source.top + source.height / 2 };
  const end = { x: target.left, y: target.top + target.height / 2 };
  const rectangles = nodes.filter((node) => node.id !== source.id && node.id !== target.id)
    .map((node) => ({
      left: node.left - TOPOLOGY_TRACE_CLEARANCE,
      right: node.left + node.width + TOPOLOGY_TRACE_CLEARANCE,
      top: node.top - TOPOLOGY_TRACE_CLEARANCE,
      bottom: node.top + node.height + TOPOLOGY_TRACE_CLEARANCE,
    }));
  const direct = directTopologyCurve(start, end, rectangles);
  if (direct) return { d: direct, kind: "direct", points: [start, end] };
  const points = topologyVisibilityRoute(start, end, rectangles);
  if (points) return { d: roundedTopologyRoute(points), kind: "detour", points };
  const middleX = (start.x + end.x) / 2;
  return {
    d: `M ${start.x} ${start.y} C ${middleX} ${start.y}, ${middleX} ${end.y}, ${end.x} ${end.y}`,
    kind: "fallback",
    points: [start, end],
  };
}

function topologyRouteMidpoint(route) {
  if (route.points.length === 2) {
    const [start, end] = route.points;
    const middleX = (start.x + end.x) / 2;
    return cubicPoint(
      start,
      { x: middleX, y: start.y },
      { x: middleX, y: end.y },
      end,
      0.5,
    );
  }
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

function topologyWireMode(wires) {
  if (!wires.length) return "structure";
  return wires.length <= TOPOLOGY_LANE_LIMIT ? "lanes" : "bundle";
}

/** Render one routed topology edge using bounded, deterministic wire detail. */
function renderTopologyEdge(edge, route, wires) {
  const group = svgElement("g", {
    class: "relationship-topology-edge",
    "data-source-id": edge.sourceId,
    "data-target-id": edge.targetId,
    "data-wire-ids": relationshipWireIds(wires),
    "data-wire-count": wires.length,
    "data-render-mode": topologyWireMode(wires),
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
  if (wires.length <= TOPOLOGY_LANE_LIMIT) {
    wires.forEach((wire, index) => {
      const offset = (index - (wires.length - 1) / 2) * TOPOLOGY_LANE_SPACING;
      group.append(svgElement("path", {
        class: "wire-trace relationship-wire-lane",
        d: route.d,
        stroke: wire.materials?.mainColor?.hex || "#1777c8",
        transform: `translate(0 ${offset})`,
        "data-lane-offset": `${offset}`,
        "data-wire-id": wire.wireId,
      }));
    });
  } else {
    const colors = new Set(
      wires.map((wire) => wire.materials?.mainColor?.hex || "#1777c8"),
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
    badge.children[1].textContent = `×${wires.length}`;
    group.append(
      svgElement("path", {
        class: "wire-trace relationship-wire-bundle",
        d: route.d,
        stroke: colors.size === 1 ? [...colors][0] : "#526f85",
        "data-wire-ids": relationshipWireIds(wires),
      }),
      badge,
    );
  }
  return group;
}

function recordTopologyPort(ports, nodeId, side, point, wires) {
  const key = `${nodeId}:${side}`;
  const prior = ports.get(key) || {
    nodeId,
    side,
    point,
    wireIds: new Set(),
    maximumLaneCount: 0,
  };
  wires.forEach((wire) => prior.wireIds.add(wire.wireId));
  const laneCount = wires.length <= TOPOLOGY_LANE_LIMIT ? wires.length : 1;
  prior.maximumLaneCount = Math.max(prior.maximumLaneCount, laneCount);
  ports.set(key, prior);
}

function renderTopologyPort(port) {
  const laneCount = port.maximumLaneCount;
  const height = laneCount > 1
    ? (laneCount - 1) * TOPOLOGY_LANE_SPACING + 8
    : 8;
  return svgElement("rect", {
    class: "relationship-topology-port",
    x: port.point.x - 4,
    y: port.point.y - height / 2,
    width: 8,
    height,
    rx: 4,
    "data-node-id": port.nodeId,
    "data-side": port.side,
    "data-wire-ids": [...port.wireIds].join(" "),
  });
}

/**
 * Position acyclic topology components in stable layers and draw their edges.
 */
function layoutRelationshipGraph(stack, components, harness) {
  const padding = 30;
  const layerGap = 54;
  const rowGap = 40;
  let componentTop = padding;
  let maximumRight = 760 - padding;
  components.forEach((component) => {
    component.nodes = optimizeRelationshipNodeOrder(component);
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
    const rowHeight = Math.max(
      112,
      ...component.nodes.map((node) => node.height),
    );
    const componentRows = Math.max(1, ...rowsByDepth.values());
    const layerWidths = new Map(
      [...nodesByDepth].map(([depth, nodes]) => [
        depth,
        Math.max(...nodes.map((node) => node.width)),
      ]),
    );
    const layerLefts = new Map();
    let nextLeft = padding;
    [...layerWidths.keys()].sort((left, right) => left - right).forEach((depth) => {
      layerLefts.set(depth, nextLeft);
      nextLeft += layerWidths.get(depth) + layerGap;
    });
    component.nodes.forEach((node) => {
      const nodesAtDepth = rowsByDepth.get(node.depth);
      const centeredRow = node.row + (componentRows - nodesAtDepth) / 2;
      node.left = layerLefts.get(node.depth)
        + (layerWidths.get(node.depth) - node.width) / 2;
      node.top = componentTop + centeredRow * (rowHeight + rowGap);
      node.element.style.left = `${node.left}px`;
      node.element.style.top = `${node.top}px`;
    });
    maximumRight = Math.max(maximumRight, nextLeft - layerGap);
    componentTop += componentRows * (rowHeight + rowGap) + layerGap;
  });
  const canvasWidth = Math.max(760, maximumRight + padding);
  const canvasHeight = Math.max(componentTop - layerGap + padding, 260);
  const overlay = svgElement("svg", {
    class: "relationship-topology-edges",
    viewBox: `0 0 ${canvasWidth} ${canvasHeight}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  const ports = new Map();
  components.forEach((component) => {
    const nodes = new Map(component.nodes.map((node) => [node.id, node]));
    component.edges.forEach((edge) => {
      const source = nodes.get(edge.sourceId);
      const target = nodes.get(edge.targetId);
      if (!source || !target) return;
      const sourceX = source.left + source.width;
      const targetX = target.left;
      const sourceY = source.top + source.height / 2;
      const targetY = target.top + target.height / 2;
      const route = routeRelationshipEdge(source, target, component.nodes);
      const wires = relationshipEndpointWires(
        harness,
        edge.junction,
        edge.relationship,
      );
      overlay.append(renderTopologyEdge(edge, route, wires));
      recordTopologyPort(
        ports, source.id, "right", { x: sourceX, y: sourceY }, wires,
      );
      recordTopologyPort(
        ports, target.id, "left", { x: targetX, y: targetY }, wires,
      );
    });
  });
  ports.forEach((port) => overlay.append(renderTopologyPort(port)));
  stack.insertBefore(overlay, stack.children[0] || null);
  stack.style.width = `${canvasWidth}px`;
  stack.style.height = `${canvasHeight}px`;
}
