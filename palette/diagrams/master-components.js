/** Build the interactive controls and node components used by the master diagram. */
/* global openJunctionPopupId */

function openJunctionRelationships(harness, junction) {
  retainConfigurationPopupParent(harness);
  closePathwayPopup(true);
  closeCableGroupDetails();
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
  const memberGroups = relationshipJunctionGroups(harness, junction);
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
    const childGroups = relationshipEndpointGroups(harness, junction, relationship);
    const row = memberRow(
      `${pathway?.name || "Missing pathway"} · ${endpointLabel}`,
      () => highlightMember(harness, "pathway_gates", relationship.pathwayId),
      [actionButton("×", `Remove ${endpointLabel} relationship`, () => {
        if (childGroups.length && !window.confirm(
          `${childGroups.length} ${childGroups.length === 1 ? "cable group traverses" : "cable groups traverse"} this relationship. Remove it?`,
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
  if (!memberGroups.length) {
    occupancy.append(emptyMessage("No cable groups traverse this junction."));
  }
  memberGroups.forEach((group) => {
    const row = memberRow(
      cableGroupLabel(harness, group),
      () => highlightMember(harness, "cable_group", group.cableGroupId),
    );
    row.dataset.cableGroupId = group.cableGroupId;
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
    const isCurrent = document.body.querySelector(".junction-relationships-popup") === dialog;
    if (isCurrent) {
      openJunctionPopupId = "";
    }
    dialog.remove();
    if (isCurrent) restoreConfigurationPopupParent();
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
      "Cable Group Occupancy",
      `${memberGroups.length}`,
      occupancyContent,
      () => highlightMember(harness, "junction", junction.junctionId),
    ),
  );
  const entry = nestedSection(
    `junction:${junction.junctionId}`,
    junctionName,
    `${existingRelationships.length} pathway ${existingRelationships.length === 1 ? "endpoint" : "endpoints"} · ${memberGroups.length} cable groups`,
    content,
    () => highlightMember(harness, "junction", junction.junctionId),
  );
  entry.open = true;
  entry.classList.add("pathway-popup-entry");
  dialog.append(entry, actions);
  document.body.append(dialog);
  dialog.showModal();
}

function closeJunctionRelationships(preserveParent = false) {
  const dialog = document.body.querySelector(".junction-relationships-popup");
  openJunctionPopupId = "";
  if (!preserveParent) configurationPopupParentState = null;
  dialog?.remove();
  if (dialog?.open) dialog.close();
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
    groups: relationshipJunctionGroups(harness, junction),
    nodeIds,
  });
  hub.addEventListener("click", () => activateJunctionNode(harness, junction));
  hub.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, junctionNodeContextItems(harness, junction));
  });
  hub.append(name, kind);
  return hub;
}

function renderRelationshipConnector(
  endGroups, routeGroups, fromEndList, expanded, showPlaceholder = false,
) {
  const svg = svgElement("svg", {
    class: "relationship-connector",
    viewBox: "0 0 100 100",
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  let dockSide = fromEndList ? "left" : "right";
  let currentExpanded = expanded;
  const curvePath = (listPosition, hubPosition) => {
    if (dockSide === "left") {
      return `M 0 ${listPosition} C 44 ${listPosition}, 56 ${hubPosition}, 100 ${hubPosition}`;
    }
    if (dockSide === "right") {
      return `M 0 ${hubPosition} C 44 ${hubPosition}, 56 ${listPosition}, 100 ${listPosition}`;
    }
    if (dockSide === "top") {
      return `M ${listPosition} 0 C ${listPosition} 44, ${hubPosition} 56, ${hubPosition} 100`;
    }
    return `M ${hubPosition} 0 C ${hubPosition} 44, ${listPosition} 56, ${listPosition} 100`;
  };
  const redraw = (isExpanded) => {
    currentExpanded = isExpanded;
    svg.replaceChildren();
    if (!routeGroups.length && showPlaceholder) {
      svg.append(svgElement("path", { class: "placeholder-trace", d: curvePath(50, 50) }));
      return;
    }
    if (!routeGroups.length) return;
    const listedGroupIds = new Set(
      endGroups.flatMap((group) => group.groups.map((member) => member.cableGroupId)),
    );
    if (!isExpanded && routeGroups.every((group) => listedGroupIds.has(group.cableGroupId))) {
      svg.append(svgElement("path", {
        class: "aggregate-trace",
        d: curvePath(50, 50),
        "data-cable-group-ids": relationshipGroupIds(routeGroups),
      }));
      return;
    }
    const endPositions = new Map();
    endGroups.forEach((group, index) => group.groups.forEach((member) => {
      endPositions.set(
        member.cableGroupId,
        20 + 75 * ((index + 0.5) / endGroups.length),
      );
    }));
    const hubSpacing = Math.min(2.5, 14 / Math.max(1, routeGroups.length - 1));
    routeGroups.forEach((group, index) => {
      const hubY = 50 + (index - (routeGroups.length - 1) / 2) * hubSpacing;
      const listY = endPositions.get(group.cableGroupId) ?? hubY;
      const mainColor = group.materials?.mainColor?.hex || "#1777c8";
      appendContrastTrace(svg, {
        class: "cable-trace",
        d: curvePath(listY, hubY),
        stroke: mainColor,
        "data-cable-group-id": group.cableGroupId,
      }, { haloWidth: 10 });
      (group.materials?.stripes || []).slice(0, 3).forEach((stripe, stripeIndex, stripes) => {
        const stripeOffset = centeredStripeOffset(stripeIndex, stripes.length, 2);
        svg.append(svgElement("path", {
          class: "stripe-trace",
          d: curvePath(listY + stripeOffset, hubY + stripeOffset),
          stroke: stripe.color?.hex || "#fff",
          "stroke-dasharray": stripe.pattern === "solid" ? "none" : "8 5",
          "data-cable-group-id": group.cableGroupId,
        }));
      });
    });
  };
  svg.setDockSide = (side) => {
    dockSide = side;
    svg.dataset.side = side;
    redraw(currentExpanded);
  };
  svg.redraw = redraw;
  redraw(expanded);
  return svg;
}

/** Measure intrinsic list width without inheriting its allocated grid-track width. */
function relationshipIntrinsicEndListWidth(list) {
  const prior = {
    width: list.style.width,
    minWidth: list.style.minWidth,
    maxWidth: list.style.maxWidth,
    justifySelf: list.style.justifySelf,
  };
  Object.assign(list.style, {
    width: "max-content",
    minWidth: "0",
    maxWidth: "none",
    justifySelf: "start",
  });
  const layoutWidth = list.offsetWidth || list.getBoundingClientRect?.().width || 0;
  const width = Math.ceil(layoutWidth || list.scrollWidth || 0);
  Object.assign(list.style, prior);
  return width;
}

/** Return the intrinsic visible footprint of one endpoint list. */
function relationshipEndListSize(list) {
  const empty = list.className.split(" ").includes("empty");
  return {
    width: Math.max(empty ? 64 : 96, relationshipIntrinsicEndListWidth(list)),
    height: Math.max(34, list.scrollHeight || 0),
  };
}

/** Return grid tracks and fallback dock points from the same rendered-list metrics. */
function relationshipPathwayDockMetrics(
  pathwayGroup, startSide, endSide, intrinsicSizes = null,
) {
  const sides = { start: startSide, end: endSide };
  const sizes = intrinsicSizes || {
    start: relationshipEndListSize(pathwayGroup.relationshipEndpointLists.start),
    end: relationshipEndListSize(pathwayGroup.relationshipEndpointLists.end),
  };
  const endpointOn = (side) => Object.keys(sides).find(
    (endpoint) => sides[endpoint] === side,
  );
  const sideSize = (side) => {
    const endpoint = endpointOn(side);
    return endpoint ? sizes[endpoint] : null;
  };
  const leftWidth = sideSize("left")?.width || 0;
  const rightWidth = sideSize("right")?.width || 0;
  const centerWidth = Math.max(
    154,
    sideSize("top")?.width || 0,
    sideSize("bottom")?.width || 0,
  );
  const topHeight = sideSize("top")?.height || 0;
  const bottomHeight = sideSize("bottom")?.height || 0;
  const centerHeight = Math.max(
    92,
    sideSize("left")?.height || 0,
    sideSize("right")?.height || 0,
  );
  const columns = [
    leftWidth,
    leftWidth ? RELATIONSHIP_DIAGRAM_SPACING : 0,
    centerWidth,
    rightWidth ? RELATIONSHIP_DIAGRAM_SPACING : 0,
    rightWidth,
  ];
  const rows = [
    topHeight,
    topHeight ? RELATIONSHIP_DIAGRAM_SPACING : 0,
    centerHeight,
    bottomHeight ? RELATIONSHIP_DIAGRAM_SPACING : 0,
    bottomHeight,
  ];
  const width = columns.reduce((total, value) => total + value, 0);
  const height = rows.reduce((total, value) => total + value, 0);
  const centerX = leftWidth
    + (leftWidth ? RELATIONSHIP_DIAGRAM_SPACING : 0)
    + centerWidth / 2;
  const centerY = topHeight
    + (topHeight ? RELATIONSHIP_DIAGRAM_SPACING : 0)
    + centerHeight / 2;
  const docks = Object.fromEntries(Object.entries(sides).map(([endpoint, side]) => {
    const point = {
      left: { x: 0, y: centerY },
      right: { x: width, y: centerY },
      top: { x: centerX, y: 0 },
      bottom: { x: centerX, y: height },
    }[side];
    return [endpoint, point];
  }));
  return { sides, sizes, columns, rows, width, height, centerX, centerY, docks };
}

function alignRelationshipDockElement(element, side, empty) {
  element.style.justifySelf = ["left", "right"].includes(side)
    ? (side === "left" ? "end" : "start")
    : (empty ? "center" : "stretch");
  element.style.alignSelf = ["top", "bottom"].includes(side)
    ? (side === "top" ? "end" : "start")
    : "";
}

function overlapRelationshipConnector(connector, side, metrics) {
  const horizontal = ["left", "right"].includes(side);
  const centerPadding = horizontal
    ? (metrics.columns[2] - 154) / 2
    : (metrics.rows[2] - 92) / 2;
  connector.style.width = horizontal
    ? `calc(100% + ${centerPadding + 2}px)` : "100%";
  connector.style.height = horizontal
    ? "100%" : `calc(100% + ${centerPadding + 2}px)`;
  connector.style.marginLeft = horizontal
    ? (side === "right" ? `${-centerPadding - 1}px` : "-1px") : "0";
  connector.style.marginRight = "0";
  connector.style.marginTop = horizontal
    ? "0" : (side === "bottom" ? `${-centerPadding - 1}px` : "-1px");
  connector.style.marginBottom = "0";
}

/** Arrange one existing pathway card around two distinct cardinal endpoint docks. */
function configureRelationshipPathwayDocking(
  pathwayGroup, startSide, endSide, intrinsicSizes = null,
) {
  const metrics = relationshipPathwayDockMetrics(
    pathwayGroup, startSide, endSide, intrinsicSizes,
  );
  pathwayGroup.dataset.startSide = startSide;
  pathwayGroup.dataset.endSide = endSide;
  pathwayGroup.style.gridTemplateColumns = metrics.columns.map((value) => `${value}px`).join(" ");
  pathwayGroup.style.gridTemplateRows = metrics.rows.map((value) => `${value}px`).join(" ");
  pathwayGroup.style.gridTemplateAreas = [
    '". . top-end . ."',
    '". . top-connector . ."',
    '"left-end left-connector hub right-connector right-end"',
    '". . bottom-connector . ."',
    '". . bottom-end . ."',
  ].join(" ");
  const area = (side, suffix) => `${side}-${suffix}`;
  pathwayGroup.relationshipEndpointLists.start.style.gridArea = area(startSide, "end");
  pathwayGroup.relationshipEndpointLists.end.style.gridArea = area(endSide, "end");
  pathwayGroup.relationshipConnectors.start.style.gridArea = area(startSide, "connector");
  pathwayGroup.relationshipConnectors.end.style.gridArea = area(endSide, "connector");
  pathwayGroup.relationshipHub.style.gridArea = "hub";
  Object.entries(metrics.sides).forEach(([endpoint, side]) => {
    const list = pathwayGroup.relationshipEndpointLists[endpoint];
    list.style.width = ["left", "right"].includes(side)
      ? `${metrics.sizes[endpoint].width}px` : "";
    alignRelationshipDockElement(list, side, list.className.split(" ").includes("empty"));
    overlapRelationshipConnector(pathwayGroup.relationshipConnectors[endpoint], side, metrics);
  });
  pathwayGroup.relationshipConnectors.start.setDockSide(startSide);
  pathwayGroup.relationshipConnectors.end.setDockSide(endSide);
  pathwayGroup.relationshipDockMetrics = metrics;
}

function renderRelationshipBridge(groups) {
  const svg = svgElement("svg", {
    class: "relationship-chain-link",
    viewBox: "0 0 22 100",
    preserveAspectRatio: "none",
    "aria-hidden": "true",
  });
  if (!groups.length) {
    svg.append(svgElement("path", { class: "structural-trace", d: "M 0 50 L 22 50" }));
    return svg;
  }
  const spacing = Math.min(2.5, 14 / Math.max(1, groups.length - 1));
  groups.forEach((group, index) => {
    const y = 50 + (index - (groups.length - 1) / 2) * spacing;
    const mainColor = group.materials?.mainColor?.hex || "#1777c8";
    appendContrastTrace(svg, {
      class: "cable-trace",
      d: `M 0 ${y} L 22 ${y}`,
      stroke: mainColor,
      "data-cable-group-id": group.cableGroupId,
    }, { haloWidth: 10 });
    (group.materials?.stripes || []).slice(0, 3).forEach((stripe, stripeIndex, stripes) => {
      const stripeOffset = centeredStripeOffset(stripeIndex, stripes.length, 2);
      svg.append(svgElement("path", {
        class: "stripe-trace",
        d: `M 0 ${y + stripeOffset} L 22 ${y + stripeOffset}`,
        stroke: stripe.color?.hex || "#fff",
        "stroke-dasharray": stripe.pattern === "solid" ? "none" : "8 5",
        "data-cable-group-id": group.cableGroupId,
      }));
    });
  });
  return svg;
}

function renderRelationshipEndList(
  harness, pathway, endpoint, groups, visibleGroups, query, collapseLimit,
  showContextMenu, focusController, cableCreationController, updateTopologyTrace,
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
  hoverHighlight(summary, () => highlightMember(harness, "pathway", pathway.pathwayId));
  focusController.bind(summary, {
    groups: groups.flatMap((group) => group.groups),
    nodeIds: [`pathway:${pathway.pathwayId}`],
  });
  const cableCreationBoundary = cableCreationController.bind(
    pathway, endpoint, groups, summary,
  );
  summary.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, [{
      label: "Route Editor",
      action: () => cableCreationController.begin(cableCreationBoundary),
      disabled: !groups.length,
      title: groups.length ? "" : "Requires at least one end",
    }]);
  });
  if (!groups.length) {
    details.open = false;
    summary.append(label);
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      openPathwayPopup(harness, pathway.pathwayId);
    });
    details.append(summary);
    return details;
  }
  summary.append(label, count);
  items.className = "relationship-end-items";
  visibleGroups.forEach((group) => {
    const button = document.createElement("div");
    const name = document.createElement("strong");
    const meta = document.createElement("small");
    button.className = "relationship-end-entry";
    button.dataset.connectionId = group.connectionId;
    button.dataset.cableGroupIds = relationshipGroupIds(group.groups);
    name.textContent = group.label;
    const connectionContext = group.connectionName && group.connectionName !== group.label
      ? `${group.connectionName} · ` : "";
    meta.textContent = `${connectionContext}${group.cableGroupId ? "Connected" : "Disconnected"}`;
    button.append(name, meta);
    hoverHighlight(button, () => highlightMember(harness, "connection", group.connectionId));
    focusController.bind(button, {
      groups: group.groups,
      nodeIds: [`pathway:${pathway.pathwayId}`],
    });
    const setRenameEditing = (editing) => {
      focusController.setPointerEnabled(!editing);
    };
    const openDetails = () => openCableGroupDetails(
      harness, group.cableGroupId, group.connectionId,
    );
    if (group.cableGroupId) button.addEventListener("click", openDetails);
    if (!group.cableGroupId) button.dataset.disconnected = "true";
    button.tabIndex = 0;
    button.setAttribute(
      "aria-label", `${group.label}, ${group.cableGroupId ? "connected" : "disconnected"} end`,
    );
    if (group.cableGroupId) {
      button.setAttribute("role", "button");
      button.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openDetails();
      });
    }
    button.addEventListener("contextmenu", (event) => {
      event.stopPropagation();
      const contextItems = [
        ...endRoutingContextItems(harness, group.connectionId, false),
        ...(!group.cableGroupId ? [{
          label: "Switch",
          action: () => mutate("switch_standalone_end", {
            harnessId: harness.harnessId,
            connectionId: group.connectionId,
          }, `Switching ${group.label} to End ${side === "A" ? "B" : "A"}…`),
        }] : []),
        {
          label: "Rename",
          action: () => renameRelationshipEnd(
            harness, group, button, name, meta, setRenameEditing,
          ),
        },
        {
          label: "Delete",
          action: () => mutate("remove_standalone_end", {
            harnessId: harness.harnessId,
            connectionId: group.connectionId,
          }, `Deleting ${group.label}…`),
        },
        {
          label: "Properties",
          action: () => openCableEndProperties(harness, group.connectionId),
        },
      ];
      if (group.cableGroupId) {
        contextItems.unshift({ label: "Details", action: openDetails });
      }
      showContextMenu(event, contextItems);
    });
    items.append(button);
  });
  if (!visibleGroups.length) items.append(emptyMessage(`No matching End ${side} connections.`));
  details.addEventListener("toggle", () => {
    if (!query) relationshipEndListOverrides.set(overrideKey, details.open);
    if (details.redrawConnector) details.redrawConnector(details.open);
    if (updateTopologyTrace) updateTopologyTrace(pathway.pathwayId, endpoint);
  });
  details.append(summary, items);
  return details;
}

function addRelationshipMapContextMenu(workspace, harness) {
  const show = addContextMenu(workspace.viewport, workspace.viewport);
  workspace.viewport.addEventListener("contextmenu", (event) => {
    const hasCableGroups = Boolean((harness.cableGroups || []).length);
    show(event, [
      {
        label: "Render",
        items: [
          {
            label: "Preview",
            checked: Boolean(harness.hasRoutePreview),
            action: activatePreview,
            onToggle: setPreviewEnabled,
            disabled: !hasCableGroups && !harness.hasRoutePreview,
            title: hasCableGroups ? "" : "Requires at least one cable group",
          },
          {
            label: "Solids",
            checked: Boolean(harness.hasGeneratedSolids),
            action: generateSolids,
            onToggle: setSolidsEnabled,
            disabled: !hasCableGroups && !harness.hasGeneratedSolids,
            title: hasCableGroups ? "" : "Requires at least one cable group",
          },
          {
            label: "Finalize",
            checked: Boolean(harness.hasFinalizedGeometry),
            action: finalizeSolids,
            onToggle: setFinalizeEnabled,
            disabled: !hasCableGroups && !harness.hasFinalizedGeometry,
            title: hasCableGroups ? "" : "Requires at least one cable group",
          },
        ],
      },
      {
        label: "Add",
        items: [
          { label: "Pathway", action: addPathway },
          { label: "Junction", action: addJunction },
          { label: "Ending", action: addEnd },
        ],
      },
      { label: "Materials", action: () => openMaterialOptions(harness) },
      { label: "Defaults", action: () => openInterpolationOptions(harness, "defaults") },
      { label: "Properties", action: () => openHarnessProperties(harness) },
    ]);
  });
  return show;
}

function renderRelationshipPathwayNode(
  harness, candidate, connections, query, collapseLimit, showContextMenu,
  focusController, cableCreationController, nodeIds, updateTopologyTrace,
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
  const matchingGroupIds = new Set(
    [...visibleStart, ...visibleEnd].flatMap(
      (group) => group.groups.map((member) => member.cableGroupId),
    ),
  );
  const allPathwayGroups = relationshipPathwayGroups(harness, candidate.pathwayId);
  const pathwayGroups = allPathwayGroups
    .filter((group) => pathwayMatches || matchingGroupIds.has(group.cableGroupId));
  const pathwayGroup = document.createElement("div");
  const startList = renderRelationshipEndList(
    harness, candidate, "start", groups.start, visibleStart, query, collapseLimit,
    showContextMenu, focusController, cableCreationController, updateTopologyTrace,
  );
  const endList = renderRelationshipEndList(
    harness, candidate, "end", groups.end, visibleEnd, query, collapseLimit,
    showContextMenu, focusController, cableCreationController, updateTopologyTrace,
  );
  const startConnector = renderRelationshipConnector(
    visibleStart, pathwayGroups, true, startList.open, pathwayGroups.length === 0,
  );
  const endConnector = renderRelationshipConnector(
    visibleEnd, pathwayGroups, false, endList.open, pathwayGroups.length === 0,
  );
  const hub = document.createElement("button");
  const hubName = document.createElement("strong");
  const hubDirection = document.createElement("small");
  pathwayGroup.className = "relationship-pathway-group";
  pathwayGroup.dataset.pathwayId = candidate.pathwayId;
  hub.type = "button";
  hub.className = "relationship-pathway-hub";
  hub.title = "Open pathway configuration";
  hubName.textContent = candidate.name || "Unnamed pathway";
  hubDirection.textContent = pathwayDirection(candidate);
  hoverHighlight(hub, () => highlightMember(harness, "pathway_gates", candidate.pathwayId));
  focusController.bind(hub, { groups: allPathwayGroups, nodeIds });
  hub.addEventListener("click", () => activatePathwayNode(harness, candidate));
  hub.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, pathwayNodeContextItems(harness, candidate));
  });
  hub.append(hubName, hubDirection);
  startList.redrawConnector = startConnector.redraw;
  endList.redrawConnector = endConnector.redraw;
  pathwayGroup.append(startList, startConnector, hub, endConnector, endList);
  pathwayGroup.relationshipEndpointLists = { start: startList, end: endList };
  pathwayGroup.relationshipConnectors = { start: startConnector, end: endConnector };
  pathwayGroup.relationshipHub = hub;
  configureRelationshipPathwayDocking(pathwayGroup, "left", "right");
  return pathwayGroup;
}
