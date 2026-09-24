/** Render route and member details for one assigned cable-end group. */
/* global openCableEndRoutingPopupId, openCableGroupDetailsState */

const CABLE_GROUP_DETAILS_NODE_HEIGHT = 40;
const CABLE_GROUP_DETAILS_ROW_GAP = 90;
const CABLE_GROUP_DETAILS_COLUMN_GAP = 80;
const CABLE_GROUP_DETAILS_PADDING = 40;
let cableGroupDetailsTextContext;

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

/** Count edge inversions between matching pairs of adjacent diagram columns. */
function cableGroupDetailsEdgeCrossingCount(edges, positions, depths) {
  let crossings = 0;
  edges.forEach((edge, index) => {
    const leftDepth = depths.get(edge.leftId);
    const rightDepth = depths.get(edge.rightId);
    const sourceId = leftDepth <= rightDepth ? edge.leftId : edge.rightId;
    const targetId = sourceId === edge.leftId ? edge.rightId : edge.leftId;
    edges.slice(index + 1).forEach((other) => {
      const otherLeftDepth = depths.get(other.leftId);
      const otherRightDepth = depths.get(other.rightId);
      const otherSourceId = otherLeftDepth <= otherRightDepth
        ? other.leftId : other.rightId;
      const otherTargetId = otherSourceId === other.leftId ? other.rightId : other.leftId;
      if (depths.get(sourceId) !== depths.get(otherSourceId)
        || depths.get(targetId) !== depths.get(otherTargetId)
        || sourceId === otherSourceId || targetId === otherTargetId) return;
      const sourceOrder = positions.get(sourceId) - positions.get(otherSourceId);
      const targetOrder = positions.get(targetId) - positions.get(otherTargetId);
      if (sourceOrder * targetOrder < 0) crossings += 1;
    });
  });
  return crossings;
}

/** Prefer fewer crossings, then shorter vertical travel through the layered graph. */
function cableGroupDetailsOrderingScore(topology, positions, depths) {
  const crossings = cableGroupDetailsEdgeCrossingCount(topology.edges, positions, depths);
  const verticalTravel = topology.edges.reduce((total, edge) => (
    total + Math.abs(positions.get(edge.leftId) - positions.get(edge.rightId))
  ), 0);
  return { crossings, verticalTravel };
}

/** Return whether a candidate layered ordering is better than the retained one. */
function cableGroupDetailsOrderingIsBetter(candidate, retained) {
  return candidate.crossings < retained.crossings
    || (candidate.crossings === retained.crossings
      && candidate.verticalTravel < retained.verticalTravel);
}

/** Order layered nodes with deterministic barycentric sweeps. */
function optimizeCableGroupDetailsNodeOrder(topology, columns, depths) {
  const columnDepths = [...columns.keys()].sort((left, right) => left - right);
  const stableKeys = new Map(topology.nodes.map((node) => [
    node.id, `${node.kind}:${node.label}:${node.id}`,
  ]));
  columnDepths.forEach((depth) => columns.get(depth).sort((left, right) => (
    stableKeys.get(left.id).localeCompare(stableKeys.get(right.id))
  )));
  const positions = new Map();
  const recordPositions = () => columnDepths.forEach((depth) => (
    columns.get(depth).forEach((node, index) => positions.set(node.id, index))
  ));
  const snapshot = () => new Map(columnDepths.map((depth) => [
    depth, columns.get(depth).map((node) => node.id),
  ]));
  recordPositions();
  let bestOrder = snapshot();
  let bestScore = cableGroupDetailsOrderingScore(topology, positions, depths);
  const sweep = (forward) => {
    const orderedDepths = forward ? columnDepths.slice(1) : columnDepths.slice(0, -1).reverse();
    orderedDepths.forEach((depth) => {
      const adjacentDepth = depth + (forward ? -1 : 1);
      const scores = new Map(columns.get(depth).map((node) => {
        const adjacent = [...node.neighbors]
          .filter((neighborId) => depths.get(neighborId) === adjacentDepth)
          .map((neighborId) => positions.get(neighborId));
        const score = adjacent.length
          ? adjacent.reduce((total, position) => total + position, 0) / adjacent.length
          : positions.get(node.id);
        return [node.id, score];
      }));
      columns.get(depth).sort((left, right) => (
        scores.get(left.id) - scores.get(right.id)
        || stableKeys.get(left.id).localeCompare(stableKeys.get(right.id))
      ));
      columns.get(depth).forEach((node, index) => positions.set(node.id, index));
    });
  };
  for (let iteration = 0; iteration < 6; iteration += 1) {
    sweep(true);
    sweep(false);
    recordPositions();
    const score = cableGroupDetailsOrderingScore(topology, positions, depths);
    if (cableGroupDetailsOrderingIsBetter(score, bestScore)) {
      bestScore = score;
      bestOrder = snapshot();
    }
  }
  columnDepths.forEach((depth) => {
    const nodes = new Map(columns.get(depth).map((node) => [node.id, node]));
    columns.set(depth, bestOrder.get(depth).map((nodeId) => nodes.get(nodeId)));
  });
  return bestScore;
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
  const orderingScore = optimizeCableGroupDetailsNodeOrder(topology, columns, depths);
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

/** Render one cable end's controls in their terminal-to-pathway traversal order. */
function renderCableEndRoutingControls(harness, connection, end) {
  const content = document.createElement("div");
  const sequence = document.createElement("div");
  const addGuides = document.createElement("button");
  const addRefine = document.createElement("button");
  const controls = new Map(
    harness.controls.map((control) => [control.controlId, control]),
  );
  const routingItems = (connection.members || []).map((member) => ({
    id: member.memberId,
    label: `Guide ${member.index + 1}`,
    kind: "guide",
    hasLinkedGeometry: member.hasLinkedGeometry,
    edit: () => openInterpolationOptions(
      harness,
      "end",
      connection.connectionId,
      `Guide ${member.index + 1}`,
      member.interpolation,
      member.usesDefaults,
      member.memberId,
    ),
    highlight: () => highlightMember(
      harness, "connection", connection.connectionId, { memberIndex: member.index },
    ),
    remove: () => removeEndGuide(
      harness, connection.connectionId, member.memberId, `Guide ${member.index + 1}`,
    ),
    removeDisabled: connection.members.length === 1,
    removeTitle: connection.members.length === 1
      ? "A cable end must retain at least one guide"
      : `Remove Guide ${member.index + 1}`,
  }));
  end.orderedControlIds.forEach((controlId) => {
    const control = controls.get(controlId);
    const isRefine = control?.kind === "refine";
    routingItems.push({
      id: controlId,
      label: control?.name || "Missing control",
      kind: isRefine ? "refine" : "guide",
      hasLinkedGeometry: control?.hasLinkedGeometry,
      edit: isRefine
        ? () => editPathwayRefine(harness, control)
        : () => openInterpolationOptions(
          harness, "gate", controlId, control?.name || "Guide", control?.interpolation,
          control?.usesDefaults ?? true,
        ),
      highlight: () => highlightMember(harness, "control", controlId),
      remove: () => removeEndControl(
        harness, connection.connectionId, controlId, control?.name || "this control",
      ),
      removeDisabled: false,
      removeTitle: `Remove ${control?.name || "control"}`,
    });
  });
  content.className = "section-content";
  sequence.className = "sequence";
  routingItems.forEach((item, index) => {
    const row = memberRow(
      `${item.label} #${item.id.slice(0, 8)}`,
      item.highlight,
      [
        optionsButton(
          item.kind === "refine"
            ? "Move, rotate, or resize refine point"
            : "Guide interpolation options",
          item.edit,
          !item.id,
        ),
        actionButton("×", item.removeTitle, item.remove, item.removeDisabled, true),
      ],
      !item.hasLinkedGeometry,
    );
    const position = document.createElement("span");
    row.classList.add("has-sequence-position");
    position.className = "sequence-position";
    position.textContent = `${index + 1}`;
    position.setAttribute("aria-label", `Position ${index + 1}`);
    row.insertBefore(position, row.children[0]);
    row.children[1].title = `Click for ${item.kind} options`;
    sequence.append(row);
  });
  if (!routingItems.length) {
    sequence.append(emptyMessage("No end-owned routing controls."));
  }
  addGuides.type = "button";
  addGuides.className = "button compact";
  addGuides.textContent = "+ Add Guides";
  addGuides.addEventListener("click", () => appendEndGuides(harness, connection.connectionId));
  addRefine.type = "button";
  addRefine.className = "button compact";
  addRefine.textContent = "+ Add Refine Point";
  const pathway = harness.pathways.find((candidate) => candidate.pathwayId === end.pathwayId);
  addRefine.disabled = !pathway || !(pathway.orderedControlIds || []).length;
  addRefine.title = addRefine.disabled
    ? "Requires a pathway with a routing gate"
    : "";
  addRefine.addEventListener("click", () => addEndRefine(harness, connection.connectionId));
  content.append(sequence, addGuides, addRefine);
  const section = nestedSection(
    `end:${connection.connectionId}:routing`,
    "Routing Controls · Traversal Order",
    `${routingItems.length}`,
    content,
    () => highlightMember(harness, "connection", connection.connectionId),
  );
  section.open = true;
  section.classList.add("pathway-popup-entry");
  return section;
}

/** Close the active cable-end routing panel. */
function closeCableEndRoutingPopup(preserveParent = false) {
  const dialog = document.body.querySelector(".cable-end-routing-popup");
  openCableEndRoutingPopupId = "";
  if (!preserveParent) configurationPopupParentState = null;
  dialog?.remove();
  if (dialog?.open) dialog.close();
}

/** Open a refresh-stable routing-control panel for one physical cable end. */
function openCableEndRoutingPopup(harness, connectionId) {
  retainConfigurationPopupParent(harness);
  closePathwayPopup(true);
  closeJunctionRelationships(true);
  closeCableGroupDetails();
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const end = (harness.standaloneEnds || []).find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const prior = document.body.querySelector(".cable-end-routing-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  if (!connection || !end) {
    openCableEndRoutingPopupId = "";
    restoreConfigurationPopupParent();
    return;
  }
  openCableEndRoutingPopupId = connectionId;
  const dialog = document.createElement("dialog");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const connectionName = connection.name || "Unnamed cable end";
  dialog.className = "cable-end-routing-popup";
  dialog.setAttribute("aria-label", `Cable end routing controls: ${connectionName}`);
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    const isCurrent = document.body.querySelector(".cable-end-routing-popup") === dialog;
    if (isCurrent) openCableEndRoutingPopupId = "";
    dialog.remove();
    if (isCurrent) restoreConfigurationPopupParent();
  });
  actions.append(close);
  dialog.append(renderCableEndRoutingControls(harness, connection, end), actions);
  document.body.append(dialog);
  dialog.showModal();
}

/** Render the routed pathways, junctions, and physical ends for one group. */
function renderCableGroupDetailsGraphic(harness, group, focusedConnectionId, showContextMenu) {
  const topology = layoutCableGroupDetailsTopology(
    cableGroupDetailsTopology(harness, group), focusedConnectionId,
  );
  const svg = svgElement("svg", {
    class: "cable-group-details-svg",
    width: topology.width,
    height: topology.height,
    viewBox: `0 0 ${topology.width} ${topology.height}`,
    role: "group",
    "aria-label": "Connected cable route",
  });
  routeCableGroupDetailsEdges(topology).forEach((edge) => {
    svg.append(svgElement("path", {
      class: "cable-group-route-link",
      d: edge.d,
      "data-start-node-id": edge.start.id,
      "data-end-node-id": edge.end.id,
      "data-start-y": edge.startY,
      "data-end-y": edge.endY,
    }));
  });
  topology.nodes.forEach((node) => {
    const isFocused = node.id === `connection:${focusedConnectionId}`;
    const groupNode = svgElement("g", {
      class: `cable-group-details-node ${node.kind}${isFocused ? " focused" : ""}`,
      tabindex: "0",
      role: node.kind === "attachment" ? "group" : "button",
      "aria-label": `${node.kind}: ${node.label}`,
      "data-node-id": node.id,
    });
    const shape = svgElement("rect", {
      class: `relationship-node ${node.kind}`,
      x: node.x - node.width / 2,
      y: node.y - node.height / 2,
      width: node.width,
      height: node.height,
      rx: node.kind === "pathway" ? 20 : 7,
    });
    const label = svgElement("text", {
      class: "relationship-node-label",
      x: node.x,
      y: node.y + 3,
    });
    const kind = svgElement("text", {
      class: "relationship-node-kind",
      x: node.x,
      y: node.y - 25,
    });
    const title = svgElement("title");
    label.textContent = node.label;
    if (node.kind === "connection") {
      kind.textContent = `Cable End · ${node.item?.attachment ? "Attached" : "Detached"}`;
    } else if (node.kind === "attachment") {
      kind.textContent = node.item.connected ? "Connected" : "Disconnected";
      groupNode.dataset.connected = node.item.connected ? "true" : "false";
      const connection = harness.connections.find(
        (candidate) => candidate.connectionId === node.item.connectionId,
      );
      const shielding = connection
        ? cableEndAttachmentMaterials(group, connection, node.item).shielding : "";
      const hasShielding = typeof shielding === "string" && shielding.trim() !== "";
      const shieldingConnected = node.item.shieldingTarget?.connected === true;
      groupNode.dataset.shielding = hasShielding
        ? (shieldingConnected ? "connected" : "disconnected") : "none";
      if (hasShielding) {
        const shieldingStatus = shieldingConnected ? "connected" : "disconnected";
        const indicator = svgElement("g", {
          class: `connection-shielding-indicator ${shieldingStatus}`,
          role: "img",
          "aria-label": `Shielding ${shieldingStatus}`,
        });
        const indicatorCircle = svgElement("circle", {
          cx: node.x + node.width / 2 - 10,
          cy: node.y - node.height / 2 + 10,
          r: 8,
        });
        const indicatorLabel = svgElement("text", {
          x: node.x + node.width / 2 - 10,
          y: node.y - node.height / 2 + 13,
        });
        const indicatorTitle = svgElement("title");
        indicatorLabel.textContent = shieldingConnected ? "S+" : "S−";
        indicatorTitle.textContent = `Shielding ${shieldingStatus}`;
        indicator.append(indicatorCircle, indicatorLabel, indicatorTitle);
        groupNode.append(indicator);
      }
    } else {
      kind.textContent = node.kind;
    }
    title.textContent = node.label;
    shape.append(title);
    groupNode.prepend(shape, label, kind);
    if (node.kind === "connection") {
      const connectionId = node.id.slice("connection:".length);
      groupNode.dataset.connectionId = connectionId;
      hoverHighlight(groupNode, () => highlightMember(harness, "connection", connectionId));
      const activate = () => openCableEndRoutingPopup(harness, connectionId);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      groupNode.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, cableGroupDetailsEndContextItems(harness, node.item));
      });
    } else if (node.kind === "attachment") {
      hoverHighlight(groupNode, () => highlightMember(
        harness, "attachment", node.item.attachmentId,
        { connectionId: node.item.connectionId },
      ));
      groupNode.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, cableGroupAttachmentContextItems(harness, group, node.item));
      });
    } else if (node.kind === "pathway") {
      const pathwayId = node.id.slice("pathway:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "pathway_gates", pathwayId));
      const activate = () => activatePathwayNode(harness, node.item);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      if (node.item) {
        groupNode.addEventListener("contextmenu", (event) => {
          event.stopPropagation();
          showContextMenu(event, pathwayNodeContextItems(harness, node.item));
        });
      }
    } else {
      const junctionId = node.id.slice("junction:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "junction", junctionId));
      const activate = () => activateJunctionNode(harness, node.item);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      if (node.item) {
        groupNode.addEventListener("contextmenu", (event) => {
          event.stopPropagation();
          showContextMenu(event, junctionNodeContextItems(harness, node.item));
        });
      }
    }
    svg.append(groupNode);
  });
  const workspace = createBlockDiagramWorkspace("Zoomable connected cable route", {
    contentSize: { width: topology.width, height: topology.height },
    minScale: 0.01,
  });
  workspace.root.classList.add("cable-group-details-graphic");
  workspace.stage.append(svg);
  return workspace;
}
