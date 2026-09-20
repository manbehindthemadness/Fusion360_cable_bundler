/** Constants and port allocation for the master topology diagram. */

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
  * TOPOLOGY_LANE_SPACING / 2 + 3;
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
  return (harness.cableGroups || []).filter((group) => (group.routeLegs || []).some((leg) => (
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
