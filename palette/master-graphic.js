const RELATIONSHIP_DIAGRAM_CONTRACT_VERSION = "4";
const RELATIONSHIP_DIAGRAM_LAYOUT = "endpoint-junction-forest";
const TOPOLOGY_TRACE_CLEARANCE = 14;
const TOPOLOGY_TRACE_CORNER_RADIUS = 8;
const TOPOLOGY_LANE_LIMIT = 5;
const TOPOLOGY_LANE_SPACING = 4;

function relationshipWireIds(wires) {
  return wires.map((wire) => wire.wireId).join(" ");
}

function relationshipElementWireIds(element) {
  const value = element.dataset?.wireIds || element.dataset?.wireId || "";
  return new Set(value.split(" ").filter(Boolean));
}

function relationshipSetsIntersect(left, right) {
  return [...left].some((value) => right.has(value));
}

/** Apply transient focus to every master-diagram element sharing route membership. */
function createRelationshipFocusController(container) {
  const itemClasses = [
    "relationship-topology-node",
    "relationship-topology-edge",
    "relationship-topology-port",
    "relationship-end-entry",
    "wire-trace",
    "stripe-trace",
    "aggregate-trace",
  ];
  let pointerFocus = null;
  let keyboardFocus = null;
  const sources = new Set();

  const items = () => [...new Set(itemClasses.flatMap(
    (className) => Array.from(container.querySelectorAll(`.${className}`)),
  ))];
  const clearClasses = () => {
    container.classList.remove("relationship-focus-active");
    items().forEach((item) => item.classList.remove(
      "relationship-focus-match", "relationship-focus-dimmed", "relationship-focus-source",
    ));
    sources.forEach((source) => source.classList.remove(
      "relationship-focus-match", "relationship-focus-dimmed", "relationship-focus-source",
    ));
  };
  const apply = () => {
    clearClasses();
    const focus = keyboardFocus || pointerFocus;
    if (!focus) return;
    container.classList.add("relationship-focus-active");
    const wireIds = new Set(focus.wireIds);
    const nodeIds = new Set(focus.nodeIds);
    items().forEach((item) => {
      const itemWireIds = relationshipElementWireIds(item);
      const itemNodeIds = new Set([
        item.dataset?.nodeId,
        item.dataset?.sourceId,
        item.dataset?.targetId,
      ].filter(Boolean));
      const matches = wireIds.size
        ? relationshipSetsIntersect(wireIds, itemWireIds)
        : relationshipSetsIntersect(nodeIds, itemNodeIds);
      item.classList.add(matches ? "relationship-focus-match" : "relationship-focus-dimmed");
    });
    focus.source.classList.add("relationship-focus-source", "relationship-focus-match");
    focus.source.classList.remove("relationship-focus-dimmed");
  };
  const bind = (source, descriptor) => {
    sources.add(source);
    const focus = {
      source,
      wireIds: descriptor.wires.map((wire) => wire.wireId),
      nodeIds: descriptor.nodeIds || [],
    };
    source.addEventListener("mouseenter", () => {
      pointerFocus = focus;
      apply();
    });
    source.addEventListener("mouseleave", () => {
      if (pointerFocus === focus) pointerFocus = null;
      apply();
    });
    source.addEventListener("focus", () => {
      keyboardFocus = focus;
      apply();
    });
    source.addEventListener("blur", () => {
      if (keyboardFocus === focus) keyboardFocus = null;
      apply();
    });
  };
  return { bind };
}

function relationshipEndGroups(harness, pathwayId, endpoint, connections) {
  const connectionField = endpoint === "start" ? "startConnectionId" : "endConnectionId";
  const endpointNameField = endpoint === "start" ? "startEndName" : "endEndName";
  const groups = new Map();
  harness.wires
    .filter((wire) => {
      const pathwayIndex = endpoint === "start" ? 0 : wire.orderedPathwayIds.length - 1;
      return wire.orderedPathwayIds[pathwayIndex] === pathwayId;
    })
    .forEach((wire) => {
      const connectionId = wire[connectionField] || "";
      const groupKey = connectionId || `missing:${wire.wireId}`;
      if (!groups.has(groupKey)) {
        groups.set(groupKey, {
          connectionId,
          connectionName: connections.get(connectionId)?.name || "",
          endpointNames: new Set(),
          wires: [],
        });
      }
      const group = groups.get(groupKey);
      if (wire[endpointNameField]) group.endpointNames.add(wire[endpointNameField]);
      group.wires.push(wire);
    });
  return [...groups.values()].map((group) => {
    const endpointNames = [...group.endpointNames];
    const label = endpointNames.length === 1
      ? endpointNames[0]
      : group.connectionName || `Missing End ${endpoint === "start" ? "A" : "B"}`;
    const wireSearch = group.wires.map((wire) => (
      `${wireLabel(wire)} ${wire.wireNumber} ${wire.materials?.insulationMaterial || ""} ${wire.materials?.mainColor?.name || ""}`
    )).join(" ");
    return {
      ...group,
      label,
      searchable: `${label} ${group.connectionName} ${endpointNames.join(" ")} ${wireSearch}`
        .toLocaleLowerCase(),
    };
  });
}

function relationshipPathwayWires(harness, pathwayId) {
  return harness.wires.filter((wire) => wire.orderedPathwayIds.includes(pathwayId));
}

function relationshipJunctionWires(harness, junction) {
  const relationships = junction.pathwayRelationships || [];
  const preceding = new Set(
    relationships.filter((item) => item.endpoint === "end").map((item) => item.pathwayId),
  );
  const following = new Set(
    relationships.filter((item) => item.endpoint === "start").map((item) => item.pathwayId),
  );
  return harness.wires.filter((wire) => wire.orderedPathwayIds.some((pathwayId, index) => (
    preceding.has(pathwayId) && following.has(wire.orderedPathwayIds[index + 1])
  )));
}

function relationshipTopology(harness) {
  const nodes = new Map();
  const edges = [];
  const addNode = (kind, item, index) => {
    const id = `${kind}:${kind === "pathway" ? item.pathwayId : item.junctionId}`;
    nodes.set(id, { id, kind, item, index, incoming: [], outgoing: [], neighbors: [] });
  };
  harness.pathways.forEach((pathway, index) => addNode("pathway", pathway, index));
  (harness.junctions || []).forEach((junction, index) => (
    addNode("junction", junction, harness.pathways.length + index)
  ));
  (harness.junctions || []).forEach((junction) => {
    const junctionId = `junction:${junction.junctionId}`;
    (junction.pathwayRelationships || []).forEach((relationship) => {
      const pathwayId = `pathway:${relationship.pathwayId}`;
      if (!nodes.has(junctionId) || !nodes.has(pathwayId)) return;
      const sourceId = relationship.endpoint === "end" ? pathwayId : junctionId;
      const targetId = relationship.endpoint === "end" ? junctionId : pathwayId;
      const edge = { junction, relationship, sourceId, targetId };
      edges.push(edge);
      nodes.get(sourceId).outgoing.push(targetId);
      nodes.get(targetId).incoming.push(sourceId);
      nodes.get(junctionId).neighbors.push(pathwayId);
      nodes.get(pathwayId).neighbors.push(junctionId);
    });
  });
  const indegrees = new Map([...nodes].map(([id, node]) => [id, node.incoming.length]));
  const ready = [...nodes.values()].filter((node) => !indegrees.get(node.id))
    .sort((left, right) => left.index - right.index);
  const depths = new Map([...nodes.keys()].map((id) => [id, 0]));
  while (ready.length) {
    const node = ready.shift();
    node.outgoing.forEach((targetId) => {
      depths.set(targetId, Math.max(depths.get(targetId), depths.get(node.id) + 1));
      indegrees.set(targetId, indegrees.get(targetId) - 1);
      if (!indegrees.get(targetId)) {
        ready.push(nodes.get(targetId));
        ready.sort((left, right) => left.index - right.index);
      }
    });
  }
  const visited = new Set();
  const components = [];
  [...nodes.values()].sort((left, right) => left.index - right.index).forEach((root) => {
    if (visited.has(root.id)) return;
    const queue = [root];
    const componentNodes = [];
    visited.add(root.id);
    while (queue.length) {
      const node = queue.shift();
      componentNodes.push({ ...node, depth: depths.get(node.id) || 0 });
      node.neighbors.forEach((neighborId) => {
        if (!visited.has(neighborId)) {
          visited.add(neighborId);
          queue.push(nodes.get(neighborId));
        }
      });
    }
    componentNodes.sort((left, right) => left.depth - right.depth || left.index - right.index);
    const nodeIds = new Set(componentNodes.map((node) => node.id));
    components.push({
      nodes: componentNodes,
      edges: edges.filter((edge) => nodeIds.has(edge.sourceId) && nodeIds.has(edge.targetId)),
    });
  });
  return components;
}

function openJunctionRelationships(harness, junction) {
  closePathwayPopup();
  const prior = document.body.querySelector(".junction-relationships-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  openJunctionPopupId = junction.junctionId;
  const dialog = document.createElement("dialog");
  const content = document.createElement("div");
  const relationshipContent = document.createElement("div");
  const relationshipSequence = document.createElement("div");
  const occupancyContent = document.createElement("div");
  const occupancy = document.createElement("div");
  const add = document.createElement("button");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const pathways = new Map(
    harness.pathways.map((pathway) => [pathway.pathwayId, pathway]),
  );
  const existingRelationships = junction.pathwayRelationships || [];
  const memberWires = relationshipJunctionWires(harness, junction);
  const junctionName = junction.name || "Unnamed junction";
  dialog.className = "junction-relationships-popup";
  dialog.setAttribute("aria-label", `Junction configuration: ${junctionName}`);
  content.className = "section-content";
  relationshipContent.className = "section-content";
  relationshipSequence.className = "sequence";
  occupancyContent.className = "section-content";
  occupancy.className = "occupancy";
  existingRelationships.forEach((relationship) => {
    const pathway = pathways.get(relationship.pathwayId);
    const endpointLabel = relationship.endpoint === "start" ? "End A" : "End B";
    const childWires = relationshipEndpointWires(harness, junction, relationship);
    const row = memberRow(
      `${pathway?.name || "Missing pathway"} · ${endpointLabel}`,
      () => highlightMember(harness, "pathway_gates", relationship.pathwayId),
      [actionButton("×", `Remove ${endpointLabel} relationship`, () => {
        if (childWires.length && !window.confirm(
          `${childWires.length} ${childWires.length === 1 ? "wire pathway traverses" : "wire pathways traverse"} this relationship. Remove it?`,
        )) return;
        void mutate("remove_junction_relationship", {
          harnessId: harness.harnessId,
          junctionId: junction.junctionId,
          pathwayId: relationship.pathwayId,
          endpoint: relationship.endpoint,
        }, "Removing junction relationship…");
      }, false, true)],
      !pathway,
    );
    row.dataset.pathwayId = relationship.pathwayId;
    row.dataset.endpoint = relationship.endpoint;
    relationshipSequence.append(row);
  });
  if (!existingRelationships.length) {
    relationshipSequence.append(emptyMessage("No pathway relationships."));
  }
  add.type = "button";
  add.className = "button compact";
  add.textContent = "+ Add Relationship";
  add.addEventListener("click", () => addJunctionRelationship(junction.junctionId));
  relationshipContent.append(relationshipSequence, add);
  if (!memberWires.length) {
    occupancy.append(emptyMessage("No wires traverse this junction."));
  }
  memberWires.forEach((wire) => {
    const row = memberRow(
      wireLabel(wire),
      () => highlightMember(harness, "preview_wire", wire.wireId),
    );
    row.dataset.wireId = wire.wireId;
    occupancy.append(row);
  });
  occupancyContent.append(occupancy);
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  actions.className = "pathway-popup-actions";
  actions.append(close);
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".junction-relationships-popup") === dialog) {
      openJunctionPopupId = "";
    }
    dialog.remove();
  });
  content.append(
    nameField(
      "Junction Name",
      junction.name,
      "rename_junction",
      { harnessId: harness.harnessId, junctionId: junction.junctionId },
      "Junction name",
      { showLabel: false },
    ),
    nestedSection(
      `junction:${junction.junctionId}:relationships`,
      "Pathway Relationships",
      `${existingRelationships.length}`,
      relationshipContent,
      () => highlightMember(harness, "junction", junction.junctionId),
    ),
    nestedSection(
      `junction:${junction.junctionId}:occupancy`,
      "Wire Occupancy",
      `${memberWires.length}`,
      occupancyContent,
      () => highlightMember(harness, "junction", junction.junctionId),
    ),
  );
  const entry = nestedSection(
    `junction:${junction.junctionId}`,
    junctionName,
    `${existingRelationships.length} pathway ${existingRelationships.length === 1 ? "endpoint" : "endpoints"} · ${memberWires.length} ${memberWires.length === 1 ? "wire" : "wires"}`,
    content,
    () => highlightMember(harness, "junction", junction.junctionId),
  );
  entry.open = true;
  entry.classList.add("pathway-popup-entry");
  dialog.append(entry, actions);
  document.body.append(dialog);
  dialog.showModal();
}

function closeJunctionRelationships() {
  const dialog = document.body.querySelector(".junction-relationships-popup");
  openJunctionPopupId = "";
  if (dialog?.open) dialog.close();
  else dialog?.remove();
}

function renderRelationshipJunctionHub(harness, junction, focusController, nodeIds) {
  const hub = document.createElement("button");
  const name = document.createElement("strong");
  const kind = document.createElement("small");
  hub.type = "button";
  hub.className = "relationship-junction-hub";
  hub.title = "Junction routing control";
  name.textContent = junction.name || "Unnamed junction";
  const relationshipCount = (junction.pathwayRelationships || []).length;
  kind.textContent = relationshipCount
    ? `${relationshipCount} pathway ${relationshipCount === 1 ? "endpoint" : "endpoints"}`
    : "Unconnected junction";
  hoverHighlight(hub, () => highlightMember(harness, "junction", junction.junctionId));
  focusController.bind(hub, {
    wires: relationshipJunctionWires(harness, junction),
    nodeIds,
  });
  hub.addEventListener("click", () => openJunctionRelationships(harness, junction));
  hub.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openJunctionRelationships(harness, junction);
  });
  hub.append(name, kind);
  return hub;
}

function renderRelationshipConnector(
  groups, wires, fromEndList, expanded, showPlaceholder = false,
) {
  const svg = svgElement("svg", {
    class: "relationship-connector",
    viewBox: "0 0 54 100",
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  const curvePath = (listY, hubY) => fromEndList
    ? `M 0 ${listY} C 24 ${listY}, 30 ${hubY}, 54 ${hubY}`
    : `M 0 ${hubY} C 24 ${hubY}, 30 ${listY}, 54 ${listY}`;
  const redraw = (isExpanded) => {
    svg.replaceChildren();
    if (!wires.length && showPlaceholder) {
      svg.append(svgElement("path", {
        class: "placeholder-trace",
        d: curvePath(50, 50),
      }));
      return;
    }
    if (!wires.length) return;
    const groupedWireIds = new Set(
      groups.flatMap((group) => group.wires.map((wire) => wire.wireId)),
    );
    if (!isExpanded && wires.every((wire) => groupedWireIds.has(wire.wireId))) {
      svg.append(svgElement("path", {
        class: "aggregate-trace",
        d: curvePath(50, 50),
        "data-wire-ids": relationshipWireIds(wires),
      }));
      return;
    }
    const groupPositions = new Map();
    groups.forEach((group, groupIndex) => {
      const groupY = 20 + 75 * ((groupIndex + 0.5) / groups.length);
      const spacing = Math.min(6, 14 / Math.max(1, group.wires.length - 1));
      group.wires.forEach((wire, wireIndex) => {
        groupPositions.set(
          wire.wireId,
          groupY + (wireIndex - (group.wires.length - 1) / 2) * spacing,
        );
      });
    });
    const hubSpacing = Math.min(2.5, 14 / Math.max(1, wires.length - 1));
    wires.forEach((wire, wireIndex) => {
      const hubY = 50 + (wireIndex - (wires.length - 1) / 2) * hubSpacing;
      const listY = groupPositions.get(wire.wireId) ?? hubY;
      const pathData = curvePath(listY, hubY);
      svg.append(svgElement("path", {
        class: "wire-trace",
        d: pathData,
        stroke: wire.materials?.mainColor?.hex || "#1777c8",
        "data-wire-id": wire.wireId,
      }));
      const stripes = (wire.materials?.stripes || []).slice(0, 3);
      stripes.forEach((stripe, stripeIndex) => {
        const stripeOffset = centeredStripeOffset(stripeIndex, stripes.length, 2);
        svg.append(svgElement("path", {
          class: "stripe-trace",
          d: curvePath(listY + stripeOffset, hubY + stripeOffset),
          stroke: stripe.color?.hex || "#fff",
          "stroke-dasharray": stripe.pattern === "solid" ? "none" : "8 5",
          "data-wire-id": wire.wireId,
        }));
      });
    });
  };
  svg.redraw = redraw;
  redraw(expanded);
  return svg;
}

function renderRelationshipBridge(wires) {
  const svg = svgElement("svg", {
    class: "relationship-chain-link",
    viewBox: "0 0 22 100",
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  if (!wires.length) {
    svg.append(svgElement("path", {
      class: "structural-trace",
      d: "M 0 50 L 22 50",
    }));
    return svg;
  }
  const spacing = Math.min(2.5, 14 / Math.max(1, wires.length - 1));
  wires.forEach((wire, wireIndex) => {
    const y = 50 + (wireIndex - (wires.length - 1) / 2) * spacing;
    svg.append(svgElement("path", {
      class: "wire-trace",
      d: `M 0 ${y} L 22 ${y}`,
      stroke: wire.materials?.mainColor?.hex || "#1777c8",
      "data-wire-id": wire.wireId,
    }));
    (wire.materials?.stripes || []).slice(0, 3).forEach((stripe, stripeIndex, stripes) => {
      const stripeOffset = centeredStripeOffset(stripeIndex, stripes.length, 2);
      svg.append(svgElement("path", {
        class: "stripe-trace",
        d: `M 0 ${y + stripeOffset} L 22 ${y + stripeOffset}`,
        stroke: stripe.color?.hex || "#fff",
        "stroke-dasharray": stripe.pattern === "solid" ? "none" : "8 5",
        "data-wire-id": wire.wireId,
      }));
    });
  });
  return svg;
}

function renderRelationshipEndList(
  harness, pathway, endpoint, groups, visibleGroups, query, collapseLimit,
  focusController,
) {
  const side = endpoint === "start" ? "A" : "B";
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  const label = document.createElement("span");
  const count = document.createElement("span");
  const items = document.createElement("div");
  const overrideKey = `${harnessKey(harness)}:${pathway.pathwayId}:${endpoint}`;
  const override = relationshipEndListOverrides.get(overrideKey);
  details.className = `relationship-end-list${groups.length ? "" : " empty"}`;
  details.dataset.pathwayId = pathway.pathwayId;
  details.dataset.endpoint = endpoint;
  details.open = query
    ? visibleGroups.length > 0
    : override ?? groups.length <= collapseLimit;
  label.textContent = `End ${side}`;
  count.textContent = query && visibleGroups.length !== groups.length
    ? `${visibleGroups.length} of ${groups.length}`
    : `${groups.length}`;
  hoverHighlight(summary, () => highlightMember(harness, "pathway_wires", pathway.pathwayId));
  focusController.bind(summary, {
    wires: groups.flatMap((group) => group.wires),
    nodeIds: [`pathway:${pathway.pathwayId}`],
  });
  if (!groups.length) {
    details.open = false;
    summary.append(label);
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      navigateToPathway(pathway.pathwayId);
    });
    details.append(summary);
    return details;
  }
  summary.append(label, count);
  items.className = "relationship-end-items";
  visibleGroups.forEach((group) => {
    const button = document.createElement("button");
    const name = document.createElement("strong");
    const meta = document.createElement("small");
    button.type = "button";
    button.className = "relationship-end-entry";
    button.dataset.connectionId = group.connectionId;
    button.dataset.wireIds = relationshipWireIds(group.wires);
    name.textContent = group.label;
    const connectionContext = group.connectionName && group.connectionName !== group.label
      ? `${group.connectionName} · ` : "";
    meta.textContent = `${connectionContext}${group.wires.length} ${group.wires.length === 1 ? "wire" : "wires"}`;
    button.append(name, meta);
    hoverHighlight(button, () => group.connectionId
      ? highlightMember(harness, "connection", group.connectionId)
      : highlightMember(harness, "preview_wire", group.wires[0].wireId));
    focusController.bind(button, {
      wires: group.wires,
      nodeIds: [`pathway:${pathway.pathwayId}`],
    });
    button.addEventListener("click", () => navigateToWire(group.wires[0].wireId));
    items.append(button);
  });
  if (!visibleGroups.length) items.append(emptyMessage(`No matching End ${side} connections.`));
  details.addEventListener("toggle", () => {
    if (!query) relationshipEndListOverrides.set(overrideKey, details.open);
    if (details.redrawConnector) details.redrawConnector(details.open);
  });
  details.append(summary, items);
  return details;
}

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

function addRelationshipMapContextMenu(workspace) {
  const menu = document.createElement("div");
  const close = () => {
    menu.hidden = true;
    document.removeEventListener("mousedown", dismissOnOutsideMouseDown, true);
  };
  const dismissOnOutsideMouseDown = (event) => {
    if (!menu.contains(event.target)) close();
  };
  menu.className = "relationship-map-context-menu";
  menu.hidden = true;
  menu.setAttribute("role", "menu");
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
      workspace.viewport.focus();
    }
  });
  const show = (event, items) => {
    event.preventDefault();
    const bounds = workspace.root.getBoundingClientRect();
    const left = Math.min(
      Math.max(4, event.clientX - bounds.left),
      Math.max(4, workspace.root.clientWidth - 160),
    );
    const top = Math.min(
      Math.max(4, event.clientY - bounds.top),
      Math.max(4, workspace.root.clientHeight - 44 * items.length),
    );
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.replaceChildren();
    items.forEach(({ label, action, disabled = false, title = "" }) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "menuitem");
      button.textContent = label;
      button.disabled = disabled;
      button.title = title;
      button.addEventListener("click", () => {
        close();
        void action();
      });
      menu.append(button);
    });
    menu.hidden = false;
    document.addEventListener("mousedown", dismissOnOutsideMouseDown, true);
    const firstEnabled = Array.from(menu.children).find((button) => !button.disabled);
    if (firstEnabled) firstEnabled.focus();
  };
  workspace.viewport.addEventListener("contextmenu", (event) => {
    show(event, [
      { label: "Add pathway", action: addPathway },
      { label: "Add junction", action: addJunction },
    ]);
  });
  workspace.root.append(menu);
  return show;
}

function renderRelationshipPathwayNode(
  harness, candidate, connections, query, collapseLimit, showContextMenu,
  focusController, nodeIds,
) {
  const groups = {
    start: relationshipEndGroups(harness, candidate.pathwayId, "start", connections),
    end: relationshipEndGroups(harness, candidate.pathwayId, "end", connections),
  };
  const pathwayMatches = !query || (
    `${candidate.name} ${candidate.startName || ""} ${candidate.endName || ""}`
      .toLocaleLowerCase().includes(query)
  );
  const visibleStart = pathwayMatches
    ? groups.start : groups.start.filter((group) => group.searchable.includes(query));
  const visibleEnd = pathwayMatches
    ? groups.end : groups.end.filter((group) => group.searchable.includes(query));
  const matchingWireIds = new Set(
    [...visibleStart, ...visibleEnd].flatMap((group) => group.wires.map((wire) => wire.wireId)),
  );
  const allPathwayWires = relationshipPathwayWires(harness, candidate.pathwayId);
  const pathwayWires = allPathwayWires
    .filter((wire) => pathwayMatches || matchingWireIds.has(wire.wireId));
  const pathwayGroup = document.createElement("div");
  const startList = renderRelationshipEndList(
    harness, candidate, "start", groups.start, visibleStart, query, collapseLimit,
    focusController,
  );
  const endList = renderRelationshipEndList(
    harness, candidate, "end", groups.end, visibleEnd, query, collapseLimit,
    focusController,
  );
  const startConnector = renderRelationshipConnector(
    visibleStart, pathwayWires, true, startList.open, pathwayWires.length === 0,
  );
  const endConnector = renderRelationshipConnector(
    visibleEnd, pathwayWires, false, endList.open, pathwayWires.length === 0,
  );
  const hub = document.createElement("button");
  const hubName = document.createElement("strong");
  const hubDirection = document.createElement("small");
  const controls = new Map(harness.controls.map((control) => [control.controlId, control]));
  const canSegment = candidate.orderedControlIds.slice(1, -1).some((controlId) => {
    const control = controls.get(controlId);
    return control && ["routing_gate", "refine"].includes(control.kind);
  });
  pathwayGroup.className = "relationship-pathway-group";
  pathwayGroup.dataset.pathwayId = candidate.pathwayId;
  pathwayGroup.style.gridTemplateColumns = [
    groups.start.length ? "210px" : "max-content",
    "32px",
    "154px",
    "32px",
    groups.end.length ? "210px" : "max-content",
  ].join(" ");
  hub.type = "button";
  hub.className = "relationship-pathway-hub";
  hub.title = "Open pathway configuration";
  hubName.textContent = candidate.name || "Unnamed pathway";
  hubDirection.textContent = pathwayDirection(candidate);
  hoverHighlight(hub, () => highlightMember(harness, "pathway_gates", candidate.pathwayId));
  focusController.bind(hub, { wires: allPathwayWires, nodeIds });
  hub.addEventListener("click", () => openPathwayPopup(harness, candidate.pathwayId));
  hub.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, [
      { label: "Add refine point", action: () => addPathwayRefine(harness, candidate) },
      {
        label: "Segment",
        action: () => segmentPathway(harness, candidate),
        disabled: !canSegment,
        title: canSegment ? "" : "Requires an interior routing gate or refine point",
      },
    ]);
  });
  hub.append(hubName, hubDirection);
  startList.redrawConnector = startConnector.redraw;
  endList.redrawConnector = endConnector.redraw;
  pathwayGroup.append(startList, startConnector, hub, endConnector, endList);
  return pathwayGroup;
}

function renderRelationshipMap(harness, auditIssues) {
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  const container = document.createElement("div");
  const toolbar = document.createElement("div");
  const filter = document.createElement("input");
  const summary = document.createElement("span");
  const settings = document.createElement("label");
  const collapseInput = document.createElement("input");
  const workspace = createBlockDiagramWorkspace("Zoomable master relationship diagram");
  const focusController = createRelationshipFocusController(container);
  const showContextMenu = addRelationshipMapContextMenu(workspace);
  container.className = "section-content relationship-map";
  container.dataset.diagramContractVersion = RELATIONSHIP_DIAGRAM_CONTRACT_VERSION;
  container.dataset.diagramLayout = RELATIONSHIP_DIAGRAM_LAYOUT;
  toolbar.className = "relationship-map-toolbar";
  filter.className = "filter";
  filter.type = "search";
  filter.placeholder = "Find a wire, connection, or pathway…";
  filter.setAttribute("aria-label", "Filter master relationship graphic");
  filter.autocomplete = "off";
  filter.value = relationshipFilters.get(harnessKey(harness)) || "";
  summary.className = "relationship-map-summary";
  summary.textContent = auditIssues.length ? `${auditIssues.length} cross-check findings` : "Cross-check clear";
  toolbar.append(filter, summary);
  settings.className = "relationship-map-settings";
  settings.textContent = "Collapse end lists above";
  collapseInput.type = "number";
  collapseInput.min = `${MIN_RELATIONSHIP_COLLAPSE_LIMIT}`;
  collapseInput.max = `${MAX_RELATIONSHIP_COLLAPSE_LIMIT}`;
  collapseInput.step = "1";
  collapseInput.value = `${relationshipCollapseLimit(harness)}`;
  collapseInput.setAttribute("aria-label", "Connections before end lists collapse");
  settings.append(collapseInput, "connections");

  const draw = () => {
    const query = filter.value.trim().toLocaleLowerCase();
    const collapseLimit = clampRelationshipCollapseLimit(collapseInput.value);
    relationshipFilters.set(harnessKey(harness), query);
    workspace.stage.replaceChildren();
    const stack = document.createElement("div");
    const renderedComponents = [];
    stack.className = "relationship-pathway-stack";
    stack.dataset.diagramContractVersion = RELATIONSHIP_DIAGRAM_CONTRACT_VERSION;
    stack.dataset.diagramLayout = RELATIONSHIP_DIAGRAM_LAYOUT;
    relationshipTopology(harness).forEach((component) => {
      const searchable = component.nodes.map((node) => {
        if (node.kind === "junction") return node.item.name || "";
        const wires = relationshipPathwayWires(harness, node.item.pathwayId);
        const endpointSearch = ["start", "end"].flatMap((endpoint) => (
          relationshipEndGroups(harness, node.item.pathwayId, endpoint, connections)
            .map((group) => group.searchable)
        )).join(" ");
        const wireSearch = wires.reduce((search, wire) => `${search} ${wireLabel(wire)}`, "");
        return `${node.item.name} ${node.item.startName || ""} ${node.item.endName || ""} ${wireSearch} ${endpointSearch}`;
      }).join(" ").toLocaleLowerCase();
      if (query && !searchable.includes(query)) return;
      component.nodes.forEach((node) => {
        const wrapper = document.createElement("div");
        const memberWires = node.kind === "junction"
          ? relationshipJunctionWires(harness, node.item)
          : relationshipPathwayWires(harness, node.item.pathwayId);
        const focusNodeIds = [node.id, ...node.neighbors];
        wrapper.className = `relationship-topology-node relationship-topology-${node.kind}`;
        wrapper.dataset.nodeId = node.id;
        wrapper.dataset.wireIds = relationshipWireIds(memberWires);
        if (node.kind === "junction") {
          wrapper.dataset.junctionId = node.item.junctionId;
          wrapper.append(renderRelationshipJunctionHub(
            harness, node.item, focusController, focusNodeIds,
          ));
        } else {
          wrapper.dataset.pathwayId = node.item.pathwayId;
          wrapper.append(renderRelationshipPathwayNode(
            harness,
            node.item,
            connections,
            query,
            collapseLimit,
            showContextMenu,
            focusController,
            focusNodeIds,
          ));
        }
        node.element = wrapper;
        stack.append(wrapper);
      });
      renderedComponents.push(component);
    });
    if (!renderedComponents.length) {
      const message = emptyMessage(
        harness.pathways.length || (harness.junctions || []).length
          ? "No relationships match this filter."
          : "No pathways or junctions to display yet.",
      );
      message.className = "empty relationship-map-empty";
      workspace.stage.append(message);
      window.requestAnimationFrame(() => workspace.fit());
      return;
    }
    workspace.stage.append(stack);
    window.requestAnimationFrame(() => {
      layoutRelationshipGraph(stack, renderedComponents, harness);
      workspace.fit();
    });
  };
  filter.addEventListener("input", draw);
  collapseInput.addEventListener("change", () => {
    const limit = clampRelationshipCollapseLimit(collapseInput.value);
    collapseInput.value = `${limit}`;
    writeSession(relationshipCollapseStorageKey(harness), `${limit}`);
    [...relationshipEndListOverrides.keys()]
      .filter((key) => key.startsWith(`${harnessKey(harness)}:`))
      .forEach((key) => relationshipEndListOverrides.delete(key));
    draw();
  });
  container.append(toolbar, settings, workspace.root);
  draw();
  return container;
}
