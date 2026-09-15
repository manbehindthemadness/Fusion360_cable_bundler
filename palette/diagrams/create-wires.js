/** Coordinate pathway-boundary selection and the planned wire-creation workspace. */

let cancelActiveWireCreationSelection = null;

/** Return the stable graph identity for one pathway boundary. */
function wireCreationBoundaryKey(pathwayId, endpoint) {
  return `pathway:${pathwayId}:${endpoint}`;
}

/** Return every pathway boundary physically reachable from one boundary. */
function wireCreationReachableBoundaries(harness, sourceKey) {
  const graph = new Map();
  const addNode = (key) => {
    if (!graph.has(key)) graph.set(key, new Set());
  };
  const connect = (left, right) => {
    addNode(left);
    addNode(right);
    graph.get(left).add(right);
    graph.get(right).add(left);
  };
  harness.pathways.forEach((pathway) => connect(
    wireCreationBoundaryKey(pathway.pathwayId, "start"),
    wireCreationBoundaryKey(pathway.pathwayId, "end"),
  ));
  (harness.junctions || []).forEach((junction) => {
    const junctionKey = `junction:${junction.junctionId}`;
    addNode(junctionKey);
    (junction.pathwayRelationships || []).forEach((relationship) => connect(
      junctionKey,
      wireCreationBoundaryKey(relationship.pathwayId, relationship.endpoint),
    ));
  });

  const reachable = new Set();
  const pending = [sourceKey];
  while (pending.length) {
    const current = pending.shift();
    if (reachable.has(current)) continue;
    reachable.add(current);
    (graph.get(current) || []).forEach((neighbor) => pending.push(neighbor));
  }
  reachable.delete(sourceKey);
  return reachable;
}

/** Return the two master-graphic boundaries terminated by one complete wire. */
function wireCreationTerminalBoundaries(wire) {
  const pathwayIds = wire.orderedPathwayIds || [];
  if (!pathwayIds.length) return null;
  return {
    start: wireCreationBoundaryKey(pathwayIds[0], "start"),
    end: wireCreationBoundaryKey(pathwayIds[pathwayIds.length - 1], "end"),
  };
}

/** Remove ends already joined by a wire across the two selected boundaries. */
function wireCreationDisconnectedGroups(harness, left, right) {
  const connectedLeft = new Set();
  const connectedRight = new Set();
  harness.wires.forEach((wire) => {
    const boundaries = wireCreationTerminalBoundaries(wire);
    if (!boundaries) return;
    if (boundaries.start === left.key && boundaries.end === right.key) {
      connectedLeft.add(wire.startConnectionId);
      connectedRight.add(wire.endConnectionId);
    } else if (boundaries.start === right.key && boundaries.end === left.key) {
      connectedLeft.add(wire.endConnectionId);
      connectedRight.add(wire.startConnectionId);
    }
  });
  return {
    left: left.groups.filter((group) => !connectedLeft.has(group.connectionId)),
    right: right.groups.filter((group) => !connectedRight.has(group.connectionId)),
  };
}

/** Format one selected boundary for a popup column heading. */
function wireCreationBoundaryLabel(boundary) {
  const side = boundary.endpoint === "start" ? "A" : "B";
  return `${boundary.pathway.name || "Unnamed pathway"} · End ${side}`;
}

/** Return the durable identity needed to rebuild one popup boundary. */
function wireCreationBoundaryState(boundary) {
  return { pathwayId: boundary.pathway.pathwayId, endpoint: boundary.endpoint };
}

/** Rebuild one popup boundary from refreshed harness state. */
function resolveWireCreationBoundary(harness, state) {
  const pathway = harness.pathways.find(
    (candidate) => candidate.pathwayId === state.pathwayId,
  );
  if (!pathway || !["start", "end"].includes(state.endpoint)) return null;
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  return {
    key: wireCreationBoundaryKey(pathway.pathwayId, state.endpoint),
    pathway,
    endpoint: state.endpoint,
    groups: relationshipEndGroups(harness, pathway.pathwayId, state.endpoint, connections),
  };
}

/** Highlight the geometry represented by one popup end group. */
function highlightWireCreationEnd(harness, group) {
  if (group.connectionId) {
    return highlightMember(harness, "connection", group.connectionId);
  }
  const wire = group.wires[0];
  if (wire) return highlightMember(harness, "preview_wire", wire.wireId);
  return undefined;
}

/** Render one endpoint pool with the master diagram's end interactions. */
function renderWireCreationEndPool(harness, boundary, groups, showContextMenu) {
  const column = document.createElement("section");
  const heading = document.createElement("h3");
  const list = document.createElement("div");
  column.className = "create-wires-column create-wires-end-pool";
  column.dataset.pathwayId = boundary.pathway.pathwayId;
  column.dataset.endpoint = boundary.endpoint;
  heading.textContent = wireCreationBoundaryLabel(boundary);
  list.className = "create-wires-end-list";
  list.setAttribute("role", "list");
  groups.forEach((group) => {
    const card = document.createElement("div");
    const name = document.createElement("strong");
    const status = document.createElement("small");
    card.className = "relationship-end-entry create-wires-end-card";
    card.dataset.connectionId = group.connectionId;
    card.dataset.pathwayId = boundary.pathway.pathwayId;
    card.dataset.endpoint = boundary.endpoint;
    card.dataset.wireIds = relationshipWireIds(group.wires);
    card.setAttribute("role", "listitem");
    name.textContent = group.label;
    status.textContent = "Disconnected";
    card.append(name, status);
    hoverHighlight(card, () => highlightWireCreationEnd(harness, group));
    if (group.standalone) {
      card.dataset.disconnected = "true";
      card.tabIndex = 0;
      card.setAttribute("aria-label", `${group.label}, disconnected end`);
      card.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, [
          {
            label: "Rename",
            action: () => renameRelationshipEnd(harness, group, card, name, status),
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
    list.append(card);
  });
  if (!groups.length) list.append(emptyMessage("No disconnected ends."));
  column.append(heading, list);
  return column;
}

/** Remove the popup while optionally retaining enough state to restore it. */
function removeCreateWiresPopup(preserveState) {
  if (cancelActiveWireCreationSelection) cancelActiveWireCreationSelection();
  const dialog = document.body.querySelector(".create-wires-popup");
  if (preserveState && dialog && openCreateWiresPopupState) {
    openCreateWiresPopupState.scrollPositions = Array.from(
      dialog.querySelectorAll(".create-wires-column"),
    ).map((column) => column.scrollTop || 0);
    dialog.remove();
    return;
  }
  if (!preserveState) openCreateWiresPopupState = null;
  if (dialog?.open) dialog.close();
  else dialog?.remove();
}

/** Close the wire-creation workspace and clear its restoration state. */
function closeCreateWiresPopup() {
  removeCreateWiresPopup(false);
}

/** Temporarily remove the popup while the selected harness is rerendered. */
function suspendCreateWiresPopup() {
  removeCreateWiresPopup(true);
}

/** Open the three-column workspace for two selected boundaries. */
function openCreateWiresPopup(harness, left, right, scrollPositions = [0, 0, 0]) {
  closePathwayPopup();
  closeJunctionRelationships();
  closeCreateWiresPopup();
  const dialog = document.createElement("dialog");
  const heading = document.createElement("h2");
  const layout = document.createElement("div");
  const center = document.createElement("section");
  const centerHeading = document.createElement("h3");
  const centerContent = document.createElement("div");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const groups = wireCreationDisconnectedGroups(harness, left, right);
  dialog.className = "create-wires-popup";
  dialog.setAttribute("aria-labelledby", "create-wires-title");
  const showContextMenu = addContextMenu(dialog);
  openCreateWiresPopupState = {
    harnessKey: harnessKey(harness),
    left: wireCreationBoundaryState(left),
    right: wireCreationBoundaryState(right),
    scrollPositions: [...scrollPositions],
  };
  heading.id = "create-wires-title";
  heading.textContent = "Create Wires";
  layout.className = "create-wires-layout";
  center.className = "create-wires-column create-wires-assignment-pool";
  centerHeading.textContent = "Wire Assignments";
  centerContent.className = "create-wires-assignment-content";
  centerContent.setAttribute("aria-label", "Wire assignments reserved for future editing");
  center.append(centerHeading, centerContent);
  layout.append(
    renderWireCreationEndPool(harness, left, groups.left, showContextMenu),
    center,
    renderWireCreationEndPool(harness, right, groups.right, showContextMenu),
  );
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", closeCreateWiresPopup);
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".create-wires-popup") === dialog) {
      openCreateWiresPopupState = null;
    }
    dialog.remove();
  });
  actions.append(close);
  dialog.append(heading, layout, actions);
  document.body.append(dialog);
  dialog.showModal();
  window.requestAnimationFrame(() => {
    Array.from(dialog.querySelectorAll(".create-wires-column")).forEach((column, index) => {
      column.scrollTop = scrollPositions[index] || 0;
    });
  });
  close.focus();
}

/** Restore an open popup after refreshed harness state has rebuilt the editor. */
function restoreCreateWiresPopup(harness) {
  const state = openCreateWiresPopupState;
  if (!state) return;
  if (state.harnessKey !== harnessKey(harness)) {
    closeCreateWiresPopup();
    return;
  }
  const left = resolveWireCreationBoundary(harness, state.left);
  const right = resolveWireCreationBoundary(harness, state.right);
  if (!left || !right) {
    closeCreateWiresPopup();
    return;
  }
  openCreateWiresPopup(harness, left, right, state.scrollPositions);
}

/** Own the transient first/second-boundary selection mode for one diagram render. */
function createWireCreationController(harness, container) {
  const boundaries = new Map();
  let source = null;
  let eligibleKeys = new Set();

  const applyClasses = () => {
    container.classList.add("wire-creation-selecting");
    boundaries.forEach((boundary, key) => {
      boundary.summary.classList.remove(
        "wire-creation-source", "wire-creation-target", "wire-creation-unavailable",
      );
      boundary.summary.classList.add(
        key === source.key
          ? "wire-creation-source"
          : eligibleKeys.has(key) ? "wire-creation-target" : "wire-creation-unavailable",
      );
    });
  };
  const boundaryForTarget = (target) => [...boundaries.values()].find(
    (boundary) => boundary.summary.contains(target),
  );
  const cancel = () => {
    source = null;
    eligibleKeys = new Set();
    container.classList.remove("wire-creation-selecting");
    boundaries.forEach((boundary) => boundary.summary.classList.remove(
      "wire-creation-source", "wire-creation-target", "wire-creation-unavailable",
    ));
    document.removeEventListener("click", handleDocumentClick, true);
    document.removeEventListener("keydown", handleDocumentKeyDown, true);
    if (cancelActiveWireCreationSelection === cancel) {
      cancelActiveWireCreationSelection = null;
    }
  };
  const choose = (boundary, event) => {
    event.preventDefault();
    event.stopPropagation();
    const left = source;
    cancel();
    openCreateWiresPopup(harness, left, boundary);
  };
  const handleDocumentClick = (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    const boundary = boundaryForTarget(event.target);
    if (boundary && eligibleKeys.has(boundary.key)) {
      choose(boundary, event);
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    cancel();
  };
  const handleDocumentKeyDown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancel();
      return;
    }
    if (!["Enter", " "].includes(event.key)) return;
    const boundary = boundaryForTarget(event.target);
    if (boundary && eligibleKeys.has(boundary.key)) choose(boundary, event);
  };
  const begin = (boundary) => {
    if (cancelActiveWireCreationSelection) cancelActiveWireCreationSelection();
    cancel();
    source = boundary;
    const reachable = wireCreationReachableBoundaries(harness, source.key);
    eligibleKeys = new Set([...reachable].filter((key) => boundaries.get(key)?.groups.length));
    applyClasses();
    document.addEventListener("click", handleDocumentClick, true);
    document.addEventListener("keydown", handleDocumentKeyDown, true);
    cancelActiveWireCreationSelection = cancel;
  };
  const bind = (pathway, endpoint, groups, summary) => {
    const key = wireCreationBoundaryKey(pathway.pathwayId, endpoint);
    const boundary = { key, pathway, endpoint, groups, summary };
    boundaries.set(key, boundary);
    return boundary;
  };
  return { begin, bind, cancel };
}
