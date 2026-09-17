/** Render route and member details for one connected wire-end group. */
/* global openWireGroupDetailsState */

const WIRE_GROUP_DETAILS_NODE_HEIGHT = 40;
const WIRE_GROUP_DETAILS_ROW_GAP = 90;
const WIRE_GROUP_DETAILS_COLUMN_GAP = 80;
const WIRE_GROUP_DETAILS_PADDING = 40;
let wireGroupDetailsTextContext;

/** Return the authoritative pathway boundary occupied by every standalone end. */
function wireGroupEndLocations(harness) {
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
function wireGroupDetailsTopology(harness, group) {
  const locations = wireGroupEndLocations(harness);
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
function wireGroupDetailsLabelWidth(label) {
  if (wireGroupDetailsTextContext === undefined) {
    const canvas = document.createElement("canvas");
    wireGroupDetailsTextContext = canvas.getContext?.("2d") || null;
    if (wireGroupDetailsTextContext) {
      wireGroupDetailsTextContext.font = [
        "10px -apple-system", "BlinkMacSystemFont", '"Segoe UI"', "sans-serif",
      ].join(", ");
    }
  }
  const measured = wireGroupDetailsTextContext?.measureText(label).width;
  if (Number.isFinite(measured)) return measured;
  return [...label].reduce((width, character) => {
    if (/[MW@#%&]/.test(character)) return width + 8;
    if (/[ilI.,'|!]/.test(character)) return width + 3;
    if (character === " ") return width + 3.5;
    return width + 5.8;
  }, 0);
}

/** Return the complete single-line node width required by its visible label. */
function wireGroupDetailsNodeWidth(node) {
  const minimum = node.kind === "pathway" ? 150 : 120;
  return Math.ceil(Math.max(minimum, wireGroupDetailsLabelWidth(node.label) + 32));
}

/** Count edge inversions between matching pairs of adjacent diagram columns. */
function wireGroupDetailsEdgeCrossingCount(edges, positions, depths) {
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
function wireGroupDetailsOrderingScore(topology, positions, depths) {
  const crossings = wireGroupDetailsEdgeCrossingCount(topology.edges, positions, depths);
  const verticalTravel = topology.edges.reduce((total, edge) => (
    total + Math.abs(positions.get(edge.leftId) - positions.get(edge.rightId))
  ), 0);
  return { crossings, verticalTravel };
}

/** Return whether a candidate layered ordering is better than the retained one. */
function wireGroupDetailsOrderingIsBetter(candidate, retained) {
  return candidate.crossings < retained.crossings
    || (candidate.crossings === retained.crossings
      && candidate.verticalTravel < retained.verticalTravel);
}

/** Order layered nodes with deterministic barycentric sweeps. */
function optimizeWireGroupDetailsNodeOrder(topology, columns, depths) {
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
  let bestScore = wireGroupDetailsOrderingScore(topology, positions, depths);
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
    const score = wireGroupDetailsOrderingScore(topology, positions, depths);
    if (wireGroupDetailsOrderingIsBetter(score, bestScore)) {
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

/** Assign deterministic, crossing-reduced columns from the clicked wire end. */
function layoutWireGroupDetailsTopology(topology, focusedConnectionId) {
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
    node.width = wireGroupDetailsNodeWidth(node);
    node.height = WIRE_GROUP_DETAILS_NODE_HEIGHT;
    if (!columns.has(depth)) columns.set(depth, []);
    columns.get(depth).push(node);
  });
  const columnDepths = [...columns.keys()].sort((left, right) => left - right);
  const orderingScore = optimizeWireGroupDetailsNodeOrder(topology, columns, depths);
  const maxRows = Math.max(1, ...[...columns.values()].map((column) => column.length));
  const height = Math.max(
    180,
    WIRE_GROUP_DETAILS_PADDING * 2 + WIRE_GROUP_DETAILS_NODE_HEIGHT
      + Math.max(0, maxRows - 1) * WIRE_GROUP_DETAILS_ROW_GAP,
  );
  const columnWidths = columnDepths.map((depth) => Math.max(
    ...columns.get(depth).map((node) => node.width),
  ));
  let nextX = WIRE_GROUP_DETAILS_PADDING;
  columnDepths.forEach((depth, columnIndex) => {
    const column = columns.get(depth);
    const columnHeight = WIRE_GROUP_DETAILS_NODE_HEIGHT
      + Math.max(0, column.length - 1) * WIRE_GROUP_DETAILS_ROW_GAP;
    const firstY = (height - columnHeight) / 2 + WIRE_GROUP_DETAILS_NODE_HEIGHT / 2;
    const columnWidth = columnWidths[columnIndex];
    column.forEach((node, rowIndex) => {
      node.x = nextX + columnWidth / 2;
      node.y = firstY + rowIndex * WIRE_GROUP_DETAILS_ROW_GAP;
      node.row = rowIndex;
    });
    nextX += columnWidth + WIRE_GROUP_DETAILS_COLUMN_GAP;
  });
  const naturalWidth = nextX - WIRE_GROUP_DETAILS_COLUMN_GAP + WIRE_GROUP_DETAILS_PADDING;
  return { ...topology, width: Math.max(560, naturalWidth), height, orderingScore };
}

/** Assign ordered, separated ports to every visible route edge. */
function routeWireGroupDetailsEdges(topology) {
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const routed = topology.edges.map((edge) => {
    const first = nodes.get(edge.leftId);
    const second = nodes.get(edge.rightId);
    const start = first.x < second.x || (first.x === second.x && first.id < second.id)
      ? first : second;
    const end = start === first ? second : first;
    return { ...edge, start, end, startY: start.y, endY: end.y };
  }).sort((left, right) => (
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

/** Render the routed pathways, junctions, and physical ends for one group. */
function renderWireGroupDetailsGraphic(harness, group, focusedConnectionId) {
  const topology = layoutWireGroupDetailsTopology(
    wireGroupDetailsTopology(harness, group), focusedConnectionId,
  );
  const svg = svgElement("svg", {
    class: "wire-group-details-svg",
    width: topology.width,
    height: topology.height,
    viewBox: `0 0 ${topology.width} ${topology.height}`,
    role: "group",
    "aria-label": "Connected wire route",
  });
  routeWireGroupDetailsEdges(topology).forEach((edge) => {
    svg.append(svgElement("path", {
      class: "wire-group-route-link",
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
      class: `wire-group-details-node ${node.kind}${isFocused ? " focused" : ""}`,
      tabindex: "0",
      role: node.kind === "connection" ? "group" : "button",
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
    kind.textContent = node.kind === "connection" ? "Wire End" : node.kind;
    title.textContent = node.label;
    shape.append(title);
    groupNode.append(shape, label, kind);
    if (node.kind === "connection") {
      const connectionId = node.id.slice("connection:".length);
      groupNode.dataset.connectionId = connectionId;
      hoverHighlight(groupNode, () => highlightMember(harness, "connection", connectionId));
    } else if (node.kind === "pathway") {
      const pathwayId = node.id.slice("pathway:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "pathway_gates", pathwayId));
      const activate = () => openPathwayPopup(harness, pathwayId);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
    } else {
      const junctionId = node.id.slice("junction:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "junction", junctionId));
      const activate = () => {
        const junction = (harness.junctions || []).find(
          (candidate) => candidate.junctionId === junctionId,
        );
        if (junction) openJunctionRelationships(harness, junction);
      };
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
    }
    svg.append(groupNode);
  });
  const workspace = createBlockDiagramWorkspace("Zoomable connected wire route", {
    contentSize: { width: topology.width, height: topology.height },
    minScale: 0.01,
  });
  workspace.root.classList.add("wire-group-details-graphic");
  workspace.stage.append(svg);
  return workspace;
}

/** Render the physical member list for one wire group. */
function renderWireGroupDetailsMembers(harness, group, focusedConnectionId, onSelect) {
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  const pathways = new Map(
    harness.pathways.map((pathway) => [pathway.pathwayId, pathway]),
  );
  const locations = wireGroupEndLocations(harness);
  const members = document.createElement("div");
  members.className = "occupancy";
  group.connectionIds.forEach((connectionId) => {
    const connection = connections.get(connectionId);
    const location = locations.get(connectionId);
    const pathway = pathways.get(location?.pathwayId);
    const side = location?.endpoint === "start" ? "End A" : "End B";
    const boundary = location
      ? `${pathway?.name || "Missing pathway"} · ${side}`
      : "Unlocated end";
    const row = memberRow(
      `${connection?.name || "Missing end"} · ${boundary}`,
      () => highlightMember(harness, "connection", connectionId),
      [],
      !connection || !location,
    );
    row.classList.add("wire-group-details-member");
    row.dataset.connectionId = `${connectionId}`;
    const reference = row.querySelector(".member-reference");
    const isFocused = connectionId === focusedConnectionId;
    reference.title = `Start diagram from ${connection?.name || "this connected end"}`;
    reference.setAttribute("aria-label", reference.title);
    reference.setAttribute("aria-pressed", isFocused ? "true" : "false");
    reference.addEventListener("click", () => onSelect(connectionId));
    if (isFocused) row.classList.add("focused");
    members.append(row);
  });
  return members;
}

/** Move the selected styling within an existing Connected Ends list. */
function focusWireGroupDetailsMember(members, connectionId) {
  members.querySelectorAll(".wire-group-details-member").forEach((row) => {
    const isFocused = row.dataset.connectionId === connectionId;
    row.classList[isFocused ? "add" : "remove"]("focused");
    row.querySelector(".member-reference").setAttribute(
      "aria-pressed", isFocused ? "true" : "false",
    );
  });
}

/** Close the active wire-group details dialog and clear its refresh state. */
function closeWireGroupDetails() {
  const dialog = document.body.querySelector(".wire-group-details-popup");
  openWireGroupDetailsState = null;
  if (dialog?.open) dialog.close();
  else dialog?.remove();
}

/** Return whether a Wire Details context-menu event belongs to an interactive child. */
function wireGroupDetailsContextTargetIsInteractive(target, dialog) {
  const interactiveTags = new Set([
    "button", "input", "select", "textarea", "a", "summary", "label",
    "h1", "h2", "h3", "p", "strong", "small", "text", "path", "rect",
  ]);
  let current = target;
  while (current && current !== dialog) {
    const classes = typeof current.className === "string" ? current.className.split(" ") : [];
    const tag = `${current.tagName || current.tag || ""}`.toLocaleLowerCase();
    if (interactiveTags.has(tag)
      || classes.some((name) => [
        "wire-group-details-node",
        "wire-group-details-member",
        "relationship-map-context-menu",
      ].includes(name))) return true;
    current = current.parentElement;
  }
  return false;
}

/** Open one refresh-stable route-and-member dialog for a connected wire group. */
function openWireGroupDetails(harness, wireGroupId, connectionId) {
  closePathwayPopup();
  closeJunctionRelationships();
  closeCreateWiresPopup();
  const prior = document.body.querySelector(".wire-group-details-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  const group = (harness.wireGroups || []).find(
    (candidate) => candidate.wireGroupId === wireGroupId,
  );
  if (!group || !group.connectionIds.includes(connectionId)) {
    openWireGroupDetailsState = null;
    return;
  }
  openWireGroupDetailsState = { wireGroupId, connectionId };
  const dialog = document.createElement("dialog");
  const content = document.createElement("div");
  const heading = document.createElement("div");
  const title = document.createElement("h2");
  const summary = document.createElement("p");
  const memberHeading = document.createElement("h3");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  let focusedConnectionId = connectionId;
  let graphicWorkspace = null;
  let members = null;
  dialog.className = "wire-group-details-popup";
  dialog.setAttribute("aria-label", "Wire details");
  content.className = "wire-group-details-content";
  const showContextMenu = addContextMenu(dialog, dialog);
  dialog.addEventListener("contextmenu", (event) => {
    if (wireGroupDetailsContextTargetIsInteractive(event.target, dialog)) return;
    showContextMenu(event, [
      { label: "Materials", action: () => openMaterialOptions(harness, group) },
      { label: "Properties", action: () => openWireGroupProperties(harness, group) },
    ]);
  });
  heading.className = "wire-group-details-heading";
  title.textContent = "Wire Details";
  summary.textContent = `${group.connectionIds.length} connected ${
    group.connectionIds.length === 1 ? "end" : "ends"
  }`;
  heading.append(title, summary);
  content.append(heading);
  if (harness.wireGroupRouteError) {
    const error = document.createElement("div");
    error.className = "wire-group-route-error";
    error.textContent = `Route graphic unavailable: ${harness.wireGroupRouteError}`;
    content.append(error);
  } else {
    graphicWorkspace = renderWireGroupDetailsGraphic(harness, group, focusedConnectionId);
    content.append(graphicWorkspace.root);
  }
  memberHeading.textContent = "Connected Ends";
  const selectConnection = (selectedConnectionId) => {
    if (selectedConnectionId === focusedConnectionId
      || !group.connectionIds.includes(selectedConnectionId)) return;
    focusedConnectionId = selectedConnectionId;
    openWireGroupDetailsState = { wireGroupId, connectionId: selectedConnectionId };
    focusWireGroupDetailsMember(members, selectedConnectionId);
    if (harness.wireGroupRouteError || !graphicWorkspace) return;
    const replacement = renderWireGroupDetailsGraphic(
      harness, group, selectedConnectionId,
    );
    graphicWorkspace.root.parentElement.insertBefore(replacement.root, graphicWorkspace.root);
    graphicWorkspace.root.remove();
    graphicWorkspace = replacement;
    window.requestAnimationFrame(() => graphicWorkspace.fit());
  };
  members = renderWireGroupDetailsMembers(
    harness, group, focusedConnectionId, selectConnection,
  );
  content.append(
    memberHeading,
    members,
  );
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", closeWireGroupDetails);
  actions.append(close);
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".wire-group-details-popup") === dialog) {
      openWireGroupDetailsState = null;
    }
    dialog.remove();
  });
  dialog.append(content, actions);
  document.body.append(dialog);
  dialog.showModal();
  if (graphicWorkspace) window.requestAnimationFrame(() => graphicWorkspace.fit());
}
