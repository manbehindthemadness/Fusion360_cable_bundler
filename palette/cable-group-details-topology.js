/** Render route and member details for one assigned cable-end group. */
/* global openCableEndRoutingPopupId, openCableGroupDetailsState */

const CABLE_GROUP_DETAILS_NODE_HEIGHT = 40;
const CABLE_GROUP_DETAILS_ROW_GAP = 90;
const CABLE_GROUP_DETAILS_COLUMN_GAP = 80;
const CABLE_GROUP_DETAILS_PADDING = 40;
let cableGroupDetailsTextContext;

/** Assign stable visible numbers and colors to persisted attachment groups. */
function cableGroupDetailsAssociationBadges(harness) {
  const badges = new Map();
  const associations = (harness.attachmentAssociations || []).slice().sort((left, right) => (
    String(left.associationId).localeCompare(String(right.associationId))
  ));
  associations.forEach((association, index) => {
    const hue = Math.round((210 + index * 137.508) % 360);
    const badge = {
      number: index + 1,
      color: `hsl(${hue}, 60%, 35%)`,
      associationId: association.associationId,
    };
    (association.attachmentIds || []).forEach((attachmentId) => {
      badges.set(attachmentId, badge);
    });
  });
  return badges;
}

/** Return the authoritative pathway boundary occupied by every standalone end. */
function cableGroupEndLocations(harness) {
  const locations = new Map();
  (harness.standaloneEnds || []).forEach((end) => {
    locations.set(end.connectionId, {
      pathwayId: end.pathwayId,
      endpoint: end.endpoint,
    });
  });
  return locations;
}

/** Build the route-tree nodes and edges selected by the application route planner. */
function cableGroupDetailsTopology(harness, group) {
  const locations = cableGroupEndLocations(harness);
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  const pathways = new Map(
    harness.pathways.map((pathway) => [pathway.pathwayId, pathway]),
  );
  const junctions = new Map(
    (harness.junctions || []).map((junction) => [junction.junctionId, junction]),
  );
  const junctionByControl = new Map(
    [...junctions.values()].map((junction) => [junction.controlId, junction]),
  );
  const activePathwayIds = new Set();
  const activeJunctionIds = new Set();
  (group.routeLegs || []).forEach((leg) => {
    (leg.pathwayIds || []).forEach((pathwayId) => activePathwayIds.add(pathwayId));
    (leg.controlSteps || []).forEach((step) => {
      const junction = junctionByControl.get(step.controlId);
      if (junction) activeJunctionIds.add(junction.junctionId);
    });
  });
  group.connectionIds.forEach((connectionId) => {
    const location = locations.get(connectionId);
    if (location) activePathwayIds.add(location.pathwayId);
  });

  const nodes = new Map();
  const edges = [];
  const edgeIds = new Set();
  const addNode = (id, kind, item, label) => {
    if (!nodes.has(id)) nodes.set(id, { id, kind, item, label, neighbors: new Set() });
  };
  const connect = (leftId, rightId) => {
    if (!nodes.has(leftId) || !nodes.has(rightId)) return;
    const edgeId = [leftId, rightId].sort().join("|");
    if (edgeIds.has(edgeId)) return;
    edgeIds.add(edgeId);
    nodes.get(leftId).neighbors.add(rightId);
    nodes.get(rightId).neighbors.add(leftId);
    edges.push({ id: edgeId, leftId, rightId });
  };
  activePathwayIds.forEach((pathwayId) => {
    const pathway = pathways.get(pathwayId);
    addNode(
      `pathway:${pathwayId}`,
      "pathway",
      pathway,
      pathway?.name || "Missing pathway",
    );
  });
  activeJunctionIds.forEach((junctionId) => {
    const junction = junctions.get(junctionId);
    addNode(
      `junction:${junctionId}`,
      "junction",
      junction,
      junction?.name || "Missing junction",
    );
  });
  group.connectionIds.forEach((connectionId) => {
    const connection = connections.get(connectionId);
    const location = locations.get(connectionId);
    addNode(
      `connection:${connectionId}`,
      "connection",
      connection,
      connection?.name || "Missing end",
    );
    if (location) connect(`connection:${connectionId}`, `pathway:${location.pathwayId}`);
    const attachments = connection?.attachments || (
      connection?.attachment ? [connection.attachment] : []
    );
    attachments.forEach((attachment, attachmentIndex) => {
      const attachmentId = attachment.attachmentId || `legacy-${attachmentIndex}`;
      const nodeId = `attachment:${connectionId}:${attachmentId}`;
      addNode(
        nodeId,
        "attachment",
        { ...attachment, connectionId },
        attachment.name || "Unnamed connection",
      );
    });
    attachments.forEach((attachment, attachmentIndex) => {
      const attachmentId = attachment.attachmentId || `legacy-${attachmentIndex}`;
      const parentNodeId = attachment.parentAttachmentId
        ? `attachment:${connectionId}:${attachment.parentAttachmentId}`
        : `connection:${connectionId}`;
      connect(parentNodeId, `attachment:${connectionId}:${attachmentId}`);
    });
  });
  activeJunctionIds.forEach((junctionId) => {
    const junction = junctions.get(junctionId);
    (junction?.pathwayRelationships || []).forEach((relationship) => {
      if (activePathwayIds.has(relationship.pathwayId)) {
        connect(`junction:${junctionId}`, `pathway:${relationship.pathwayId}`);
      }
    });
  });
  return { nodes: [...nodes.values()], edges };
}

/** Return a browser-measured label width with a deterministic headless fallback. */
function cableGroupDetailsLabelWidth(label) {
  if (cableGroupDetailsTextContext === undefined) {
    const canvas = document.createElement("canvas");
    cableGroupDetailsTextContext = canvas.getContext?.("2d") || null;
    if (cableGroupDetailsTextContext) {
      cableGroupDetailsTextContext.font = [
        "10px -apple-system", "BlinkMacSystemFont", '"Segoe UI"', "sans-serif",
      ].join(", ");
    }
  }
  const measured = cableGroupDetailsTextContext?.measureText(label).width;
  if (Number.isFinite(measured)) return measured;
  return [...label].reduce((width, character) => {
    if (/[MW@#%&]/.test(character)) return width + 8;
    if (/[ilI.,'|!]/.test(character)) return width + 3;
    if (character === " ") return width + 3.5;
    return width + 5.8;
  }, 0);
}

/** Return the complete single-line node width required by its visible label. */
function cableGroupDetailsNodeWidth(node) {
  const minimum = node.kind === "pathway" ? 150 : 120;
  return Math.ceil(Math.max(minimum, cableGroupDetailsLabelWidth(node.label) + 32));
}

/** Assign deterministic, crossing-reduced columns from the clicked cable end. */
function layoutCableGroupDetailsTopology(topology, focusedConnectionId) {
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const depths = new Map();
  const pending = [];
  const enqueueComponent = (startId, offset) => {
    depths.set(startId, offset);
    pending.push(startId);
    while (pending.length) {
      const currentId = pending.shift();
      const current = nodes.get(currentId);
      current.neighbors.forEach((neighborId) => {
        if (depths.has(neighborId)) return;
        depths.set(neighborId, depths.get(currentId) + 1);
        pending.push(neighborId);
      });
    }
  };
  const preferredId = `connection:${focusedConnectionId}`;
  if (nodes.has(preferredId)) enqueueComponent(preferredId, 0);
  topology.nodes.forEach((node) => {
    if (!depths.has(node.id)) {
      const offset = depths.size ? Math.max(...depths.values()) + 1 : 0;
      enqueueComponent(node.id, offset);
    }
  });
  const columns = new Map();
  topology.nodes.forEach((node) => {
    const depth = depths.get(node.id) || 0;
    node.depth = depth;
    node.width = cableGroupDetailsNodeWidth(node);
    node.height = CABLE_GROUP_DETAILS_NODE_HEIGHT;
    if (!columns.has(depth)) columns.set(depth, []);
    columns.get(depth).push(node);
  });
  const columnDepths = [...columns.keys()].sort((left, right) => left - right);
  const orderingScore = optimizeCableGroupDetailsNodeOrder(
    topology, columns, depths, preferredId,
  );
  const maxRows = Math.max(1, ...[...columns.values()].map((column) => column.length));
  const height = Math.max(
    180,
    CABLE_GROUP_DETAILS_PADDING * 2 + CABLE_GROUP_DETAILS_NODE_HEIGHT
      + Math.max(0, maxRows - 1) * CABLE_GROUP_DETAILS_ROW_GAP,
  );
  const columnWidths = columnDepths.map((depth) => Math.max(
    ...columns.get(depth).map((node) => node.width),
  ));
  let nextX = CABLE_GROUP_DETAILS_PADDING;
  columnDepths.forEach((depth, columnIndex) => {
    const column = columns.get(depth);
    const columnHeight = CABLE_GROUP_DETAILS_NODE_HEIGHT
      + Math.max(0, column.length - 1) * CABLE_GROUP_DETAILS_ROW_GAP;
    const firstY = (height - columnHeight) / 2 + CABLE_GROUP_DETAILS_NODE_HEIGHT / 2;
    const columnWidth = columnWidths[columnIndex];
    column.forEach((node, rowIndex) => {
      node.x = nextX + columnWidth / 2;
      node.y = firstY + rowIndex * CABLE_GROUP_DETAILS_ROW_GAP;
      node.row = rowIndex;
    });
    nextX += columnWidth + CABLE_GROUP_DETAILS_COLUMN_GAP;
  });
  const naturalWidth = nextX - CABLE_GROUP_DETAILS_COLUMN_GAP + CABLE_GROUP_DETAILS_PADDING;
  return { ...topology, width: Math.max(560, naturalWidth), height, orderingScore };
}

/** Assign ordered, separated ports to every visible route edge. */
function routeCableGroupDetailsEdges(topology) {
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const routed = topology.edges.map((edge) => {
    const first = nodes.get(edge.leftId);
    const second = nodes.get(edge.rightId);
    const start = first.x < second.x || (first.x === second.x && first.id < second.id)
      ? first : second;
    const end = start === first ? second : first;
    return { ...edge, start, end, startY: start.y, endY: end.y };
  });
  routed.sort((left, right) => (
    left.start.depth - right.start.depth
    || left.start.row - right.start.row
    || left.end.row - right.end.row
    || left.id.localeCompare(right.id)
  ));
  const ports = new Map();
  const addPort = (node, side, neighbor, route, field) => {
    const key = `${node.id}:${side}`;
    if (!ports.has(key)) ports.set(key, []);
    ports.get(key).push({ neighbor, route, field });
  };
  routed.forEach((route) => {
    addPort(route.start, "right", route.end, route, "startY");
    addPort(route.end, "left", route.start, route, "endY");
  });
  ports.forEach((entries) => {
    entries.sort((left, right) => (
      left.neighbor.y - right.neighbor.y || left.neighbor.id.localeCompare(right.neighbor.id)
    ));
    const span = Math.min(24, Math.max(0, entries.length - 1) * 8);
    entries.forEach((entry, index) => {
      entry.route[entry.field] = entry.route[entry.field]
        - span / 2 + (entries.length === 1 ? 0 : index * span / (entries.length - 1));
    });
  });
  return routed.map((route) => {
    const startX = route.start.x + route.start.width / 2;
    const endX = route.end.x - route.end.width / 2;
    const middleX = (startX + endX) / 2;
    return {
      ...route,
      d: `M ${startX} ${route.startY} C ${middleX} ${route.startY}, `
        + `${middleX} ${route.endY}, ${endX} ${route.endY}`,
    };
  });
}

