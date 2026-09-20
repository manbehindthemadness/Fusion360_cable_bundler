/** SVG rendering for routed master topology edges and ports. */

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

