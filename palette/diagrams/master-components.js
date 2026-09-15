/** Build the interactive controls and node components used by the master diagram. */
/* global openJunctionPopupId */

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

function renderRelationshipJunctionHub(
  harness, junction, showContextMenu, focusController, nodeIds,
) {
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
    event.stopPropagation();
    showContextMenu(event, [
      { label: "Open junction configuration", action: () => openJunctionRelationships(harness, junction) },
      { label: "Delete", action: () => removeJunction(harness, junction) },
    ]);
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
  showContextMenu, focusController, wireCreationController,
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
  const wireCreationBoundary = wireCreationController.bind(
    pathway, endpoint, groups, summary,
  );
  summary.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, [{
      label: "Wire Editor",
      action: () => wireCreationController.begin(wireCreationBoundary),
      disabled: !groups.length,
      title: groups.length ? "" : "Requires at least one end",
    }]);
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
    const button = document.createElement(group.standalone ? "div" : "button");
    const name = document.createElement("strong");
    const meta = document.createElement("small");
    if (!group.standalone) button.type = "button";
    button.className = "relationship-end-entry";
    button.dataset.connectionId = group.connectionId;
    button.dataset.wireIds = relationshipWireIds(group.wires);
    name.textContent = group.label;
    const connectionContext = group.connectionName && group.connectionName !== group.label
      ? `${group.connectionName} · ` : "";
    meta.textContent = group.standalone
      ? `${connectionContext}${group.wireGroupId ? "Connected" : "Disconnected"}`
      : `${connectionContext}${group.wires.length} ${group.wires.length === 1 ? "wire" : "wires"}`;
    button.append(name, meta);
    hoverHighlight(button, () => group.connectionId
      ? highlightMember(harness, "connection", group.connectionId)
      : highlightMember(harness, "preview_wire", group.wires[0].wireId));
    focusController.bind(button, {
      wires: group.wires,
      nodeIds: [`pathway:${pathway.pathwayId}`],
    });
    if (!group.standalone) {
      button.addEventListener("click", () => navigateToWire(group.wires[0].wireId));
    } else {
      if (!group.wireGroupId) button.dataset.disconnected = "true";
      button.tabIndex = 0;
      button.setAttribute(
        "aria-label", `${group.label}, ${group.wireGroupId ? "connected" : "disconnected"} end`,
      );
      button.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, [
          {
            label: "Rename",
            action: () => renameRelationshipEnd(harness, group, button, name, meta),
          },
          {
            label: "Delete",
            action: () => mutate("remove_standalone_end", {
              harnessId: harness.harnessId,
              connectionId: group.connectionId,
            }, `Deleting ${group.label}…`),
          },
        ]);
      });
    }
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

function addRelationshipMapContextMenu(workspace) {
  const show = addContextMenu(workspace.root, workspace.viewport);
  workspace.viewport.addEventListener("contextmenu", (event) => {
    show(event, [
      { label: "Add pathway", action: addPathway },
      { label: "Add end", action: addEnd },
      { label: "Add junction", action: addJunction },
    ]);
  });
  return show;
}

function renderRelationshipPathwayNode(
  harness, candidate, connections, query, collapseLimit, showContextMenu,
  focusController, wireCreationController, nodeIds,
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
    showContextMenu, focusController, wireCreationController,
  );
  const endList = renderRelationshipEndList(
    harness, candidate, "end", groups.end, visibleEnd, query, collapseLimit,
    showContextMenu, focusController, wireCreationController,
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
      { label: "Delete", action: () => removePathway(harness, candidate) },
    ]);
  });
  hub.append(hubName, hubDirection);
  startList.redrawConnector = startConnector.redraw;
  endList.redrawConnector = endConnector.redraw;
  pathwayGroup.append(startList, startConnector, hub, endConnector, endList);
  return pathwayGroup;
}
