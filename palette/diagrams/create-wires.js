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

/** Create the transient ordered state for a newly opened wire workspace. */
function initialWireCreationAssignments(groups) {
  const rightByGroup = new Map(
    groups.right.filter((group) => group.wireGroupId).map((group) => [
      group.wireGroupId, group,
    ]),
  );
  const pairedIds = new Set();
  const initialPartners = {};
  const rows = [];
  groups.left.forEach((left) => {
    const right = left.wireGroupId && rightByGroup.get(left.wireGroupId);
    if (!right) return;
    pairedIds.add(left.connectionId);
    pairedIds.add(right.connectionId);
    initialPartners[left.connectionId] = right.connectionId;
    initialPartners[right.connectionId] = left.connectionId;
    rows.push({
      left: { connectionId: left.connectionId, returnIndex: 0 },
      right: { connectionId: right.connectionId, returnIndex: 0 },
    });
  });
  return {
    pools: {
      left: groups.left.map((group) => group.connectionId).filter((id) => !pairedIds.has(id)),
      right: groups.right.map((group) => group.connectionId).filter((id) => !pairedIds.has(id)),
    },
    rows,
    initialPartners,
    movedConnectionIds: {},
    renames: {},
    deletedConnectionIds: {},
  };
}

/** Reconcile popup-only assignments with refreshed harness data. */
function reconcileWireCreationAssignments(assignments, groups) {
  if (!assignments) return initialWireCreationAssignments(groups);
  if (!assignments.pools) assignments.pools = { left: [], right: [] };
  assignments.initialPartners ||= {};
  assignments.movedConnectionIds ||= {};
  assignments.renames ||= {};
  assignments.deletedConnectionIds ||= {};
  const available = {
    left: new Set(groups.left.map((group) => group.connectionId).filter(
      (connectionId) => !assignments.deletedConnectionIds[connectionId],
    )),
    right: new Set(groups.right.map((group) => group.connectionId).filter(
      (connectionId) => !assignments.deletedConnectionIds[connectionId],
    )),
  };
  const seen = { left: new Set(), right: new Set() };
  let newlyPendingRow = null;
  assignments.rows = (assignments.rows || []).map((row) => {
    const wasComplete = Boolean(row.left) && Boolean(row.right);
    const refreshed = { left: null, right: null };
    ["left", "right"].forEach((side) => {
      const item = row[side];
      if (item && available[side].has(item.connectionId) &&
          !seen[side].has(item.connectionId)) {
        refreshed[side] = item;
        seen[side].add(item.connectionId);
      }
    });
    if (wasComplete && Boolean(refreshed.left) !== Boolean(refreshed.right)) {
      newlyPendingRow = refreshed;
    }
    return refreshed;
  }).filter((row) => row.left || row.right);
  ["left", "right"].forEach((side) => {
    const pool = (assignments.pools?.[side] || []).filter((connectionId) => {
      if (!available[side].has(connectionId) || seen[side].has(connectionId)) return false;
      seen[side].add(connectionId);
      return true;
    });
    groups[side].forEach((group) => {
      if (!seen[side].has(group.connectionId)) {
        pool.push(group.connectionId);
        seen[side].add(group.connectionId);
      }
    });
    assignments.pools[side] = pool;
  });
  const pendingRows = assignments.rows.filter(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  if (pendingRows.length > 1) {
    returnOtherPendingWireCreationRows(assignments, newlyPendingRow || pendingRows[0]);
  }
  return assignments;
}

/** Insert an item into its outer pool without exceeding the current list bounds. */
function insertWireCreationPoolItem(assignments, side, item, index) {
  const pool = assignments.pools[side];
  const target = Math.max(0, Math.min(index, pool.length));
  pool.splice(target, 0, item.connectionId);
}

/** Return every incomplete row except the requested row to its outer pool. */
function returnOtherPendingWireCreationRows(assignments, keepRow) {
  assignments.rows = assignments.rows.filter((row) => {
    if (row === keepRow || Boolean(row.left) === Boolean(row.right)) return true;
    const side = row.left ? "left" : "right";
    const item = row[side];
    insertWireCreationPoolItem(assignments, side, item, item.returnIndex);
    return false;
  });
}

/** Move one outer-pool card into a center row. */
function assignWireCreationPoolItem(assignments, side, poolIndex, rowIndex) {
  const connectionId = assignments.pools[side][poolIndex];
  if (!connectionId) return;
  const pendingIndex = assignments.rows.findIndex(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  const opposite = side === "left" ? "right" : "left";
  const pending = assignments.rows[pendingIndex];
  assignments.pools[side].splice(poolIndex, 1);
  const item = { connectionId, returnIndex: poolIndex };
  if (pending && pending[opposite] && !pending[side]) {
    pending[side] = item;
    return;
  }
  if (pending && pending[side]) {
    insertWireCreationPoolItem(assignments, side, pending[side], pending[side].returnIndex);
    assignments.rows.splice(pendingIndex, 1);
    if (pendingIndex < rowIndex) rowIndex -= 1;
  }
  const row = { left: null, right: null };
  row[side] = item;
  assignments.rows.splice(Math.max(0, Math.min(rowIndex, assignments.rows.length)), 0, row);
}

/** Return one center card to its source pool and preserve the one-pending-row invariant. */
function unassignWireCreationRowItem(assignments, side, rowIndex, poolIndex) {
  const row = assignments.rows[rowIndex];
  const item = row?.[side];
  if (!item) return;
  if (assignments.initialPartners?.[item.connectionId]) {
    assignments.movedConnectionIds ||= {};
    assignments.movedConnectionIds[item.connectionId] = true;
  }
  insertWireCreationPoolItem(assignments, side, item, poolIndex);
  row[side] = null;
  if (!row.left && !row.right) assignments.rows.splice(rowIndex, 1);
  else returnOtherPendingWireCreationRows(assignments, row);
}

/** Exchange two occupied center-row members without moving their partners. */
function swapWireCreationRowItems(assignments, side, sourceRowIndex, targetRowIndex) {
  if (sourceRowIndex === targetRowIndex) return;
  const source = assignments.rows[sourceRowIndex];
  const target = assignments.rows[targetRowIndex];
  if (!source?.[side] || !target?.[side]) return;
  [source[side], target[side]].forEach((item) => {
    if (assignments.initialPartners?.[item.connectionId]) {
      assignments.movedConnectionIds ||= {};
      assignments.movedConnectionIds[item.connectionId] = true;
    }
  });
  [source[side], target[side]] = [target[side], source[side]];
}

/** Remove one standalone end from the staged workspace without persisting it. */
function deleteWireCreationEnd(assignments, connectionId) {
  assignments.deletedConnectionIds[connectionId] = true;
  delete assignments.renames[connectionId];
  ["left", "right"].forEach((side) => {
    assignments.pools[side] = assignments.pools[side].filter((id) => id !== connectionId);
  });
  assignments.rows.forEach((row) => {
    ["left", "right"].forEach((side) => {
      if (row[side]?.connectionId === connectionId) row[side] = null;
    });
  });
  assignments.rows = assignments.rows.filter((row) => row.left || row.right);
  const pendingRows = assignments.rows.filter(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  if (pendingRows.length > 1) returnOtherPendingWireCreationRows(assignments, pendingRows[0]);
}

/** Return the complete left/right relationships currently staged in the center. */
function wireCreationCompletePairings(assignments) {
  return assignments.rows.filter((row) => row.left && row.right).map((row) => ({
    leftConnectionId: row.left.connectionId,
    rightConnectionId: row.right.connectionId,
  }));
}

/** Return persisted-pair members that the current arrangement explicitly reassigns. */
function wireCreationDetachedConnectionIds(assignments, pairings, deleted) {
  const finalPartners = {};
  pairings.forEach((pairing) => {
    finalPartners[pairing.leftConnectionId] = pairing.rightConnectionId;
    finalPartners[pairing.rightConnectionId] = pairing.leftConnectionId;
  });
  return Object.keys(assignments.movedConnectionIds).filter(
    (connectionId) => !deleted.has(connectionId)
      && finalPartners[connectionId] !== assignments.initialPartners[connectionId],
  );
}

/** Resolve staged connected status using the same detach-then-merge semantics as Save. */
function wireCreationStagedConnectedIds(harness, assignments) {
  const deleted = new Set(Object.keys(assignments.deletedConnectionIds));
  const pairings = wireCreationCompletePairings(assignments);
  const detached = new Set(
    wireCreationDetachedConnectionIds(assignments, pairings, deleted),
  );
  const groups = (harness.wireGroups || []).map((group) => (
    (group.connectionIds || []).filter(
      (connectionId) => !deleted.has(connectionId) && !detached.has(connectionId),
    )
  ));
  const groupIndex = (connectionId) => groups.findIndex(
    (members) => members.includes(connectionId),
  );
  pairings.forEach((pairing) => {
    const leftIndex = groupIndex(pairing.leftConnectionId);
    const rightIndex = groupIndex(pairing.rightConnectionId);
    if (leftIndex >= 0 && leftIndex === rightIndex) return;
    if (leftIndex < 0 && rightIndex < 0) {
      groups.push([pairing.leftConnectionId, pairing.rightConnectionId]);
    } else if (leftIndex < 0) {
      groups[rightIndex].push(pairing.leftConnectionId);
    } else if (rightIndex < 0) {
      groups[leftIndex].push(pairing.rightConnectionId);
    } else {
      const keepIndex = Math.min(leftIndex, rightIndex);
      const removeIndex = Math.max(leftIndex, rightIndex);
      groups[keepIndex].push(...groups[removeIndex]);
      groups.splice(removeIndex, 1);
    }
  });
  return new Set(groups.filter((members) => members.length >= 2).flat());
}

/** Render one draggable end card with the master diagram's end interactions. */
function renderWireCreationEndCard(
  harness, boundary, group, assignments, connected, showContextMenu, rerender,
) {
  const card = document.createElement("div");
  const name = document.createElement("strong");
  const status = document.createElement("small");
  card.className = "relationship-end-entry create-wires-end-card";
  card.dataset.connectionId = group.connectionId;
  card.dataset.pathwayId = boundary.pathway.pathwayId;
  card.dataset.endpoint = boundary.endpoint;
  card.dataset.wireIds = relationshipWireIds(group.wires);
  card.setAttribute("role", "listitem");
  name.textContent = assignments.renames[group.connectionId] ?? group.label;
  status.textContent = connected ? "Connected" : "Disconnected";
  card.append(name, status);
  hoverHighlight(card, () => highlightWireCreationEnd(harness, group));
  if (group.standalone) {
    if (!connected) card.dataset.disconnected = "true";
    card.tabIndex = 0;
    card.setAttribute("aria-label", `${group.label}, ${connected ? "connected" : "disconnected"} end`);
    card.addEventListener("contextmenu", (event) => {
      event.stopPropagation();
      showContextMenu(event, [
        {
          label: "Rename",
          action: () => beginInlineNameEdit(card, name, status, {
            value: assignments.renames[group.connectionId]
              ?? group.connectionName ?? group.label,
            placeholder: group.label || "End name",
            ariaLabel: "End name",
            onSave: (value) => {
              assignments.renames[group.connectionId] = value;
              rerender();
            },
          }),
        },
        {
          label: "Delete",
          action: () => {
            deleteWireCreationEnd(assignments, group.connectionId);
            rerender();
          },
        },
      ]);
    });
  }
  return card;
}

/** Return an insertion index based on the pointer's vertical position. */
function wireCreationInsertionIndex(elements, clientY) {
  const index = elements.findIndex((element) => {
    const bounds = element.getBoundingClientRect();
    return clientY < bounds.top + bounds.height / 2;
  });
  return index < 0 ? elements.length : index;
}

/** Return whether a pointer is inside one drop surface. */
function wireCreationContainsPoint(element, clientX, clientY) {
  const bounds = element.getBoundingClientRect();
  return clientX >= bounds.left && clientX <= bounds.right &&
    clientY >= bounds.top && clientY <= bounds.bottom;
}

/** Add pathway-guide-style pointer dragging to one Connection Editor card. */
function enableWireCreationDrag(card, source, surfaces, onDrop) {
  let drag = null;
  const clearMarkers = () => {
    surfaces.markers.forEach((element) => {
      delete element.dataset.drop;
      delete element.dataset.dropSide;
    });
    surfaces.markers.clear();
  };
  const mark = (element, value, side = "") => {
    clearMarkers();
    element.dataset.drop = value;
    if (side) element.dataset.dropSide = side;
    surfaces.markers.add(element);
  };
  const clearDrag = () => {
    drag = null;
    delete card.dataset.dragging;
    clearMarkers();
  };
  card.addEventListener("dragstart", (event) => event.preventDefault());
  card.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("input")) return;
    drag = { x: event.clientX, y: event.clientY, active: false, target: null };
    card.setPointerCapture(event.pointerId);
  });
  card.addEventListener("pointermove", (event) => {
    if (!drag) return;
    if (!drag.active && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5) return;
    event.preventDefault();
    drag.active = true;
    card.dataset.dragging = "true";
    drag.target = null;
    clearMarkers();
    if (source.location === "pool") {
      const pending = surfaces.rows.find((record) => record.pending);
      if (pending && pending.emptySide === source.side) {
        if (wireCreationContainsPoint(surfaces.center, event.clientX, event.clientY)) {
          drag.target = { location: "pending", rowIndex: pending.index };
          mark(pending.slots[source.side], "slot", source.side);
        }
        return;
      }
      if (!wireCreationContainsPoint(surfaces.center, event.clientX, event.clientY)) return;
      const rowIndex = wireCreationInsertionIndex(
        surfaces.rows.map((record) => record.row), event.clientY,
      );
      drag.target = { location: "center", rowIndex };
      if (!surfaces.rows.length) mark(surfaces.center, "empty", source.side);
      else {
        const markerIndex = Math.min(rowIndex, surfaces.rows.length - 1);
        mark(surfaces.rows[markerIndex].row,
          rowIndex >= surfaces.rows.length ? "after" : "before", source.side);
      }
      return;
    }
    const swapTarget = surfaces.rows.find((record) => {
      if (record.index === source.rowIndex) return false;
      const targetCard = record.slots[source.side].children[0];
      return targetCard && wireCreationContainsPoint(
        targetCard, event.clientX, event.clientY,
      );
    });
    if (swapTarget) {
      drag.target = { location: "swap", rowIndex: swapTarget.index };
      mark(swapTarget.slots[source.side].children[0], "swap", source.side);
      return;
    }
    const pool = surfaces.pools[source.side];
    if (!wireCreationContainsPoint(pool.list, event.clientX, event.clientY)) return;
    const poolIndex = wireCreationInsertionIndex(pool.cards, event.clientY);
    drag.target = { location: "pool", poolIndex };
    if (!pool.cards.length) mark(pool.list, "empty", source.side);
    else {
      const markerIndex = Math.min(poolIndex, pool.cards.length - 1);
      mark(pool.cards[markerIndex], poolIndex >= pool.cards.length ? "after" : "before");
    }
  });
  card.addEventListener("pointerup", (event) => {
    if (!drag) return;
    const target = drag.active ? drag.target : null;
    clearDrag();
    if (card.hasPointerCapture(event.pointerId)) card.releasePointerCapture(event.pointerId);
    if (target) onDrop(target);
  });
  card.addEventListener("pointercancel", clearDrag);
  card.addEventListener("lostpointercapture", clearDrag);
}

/** Create one static outer column and its replaceable list. */
function createWireCreationEndPool(boundary) {
  const column = document.createElement("section");
  const heading = document.createElement("h3");
  const list = document.createElement("div");
  column.className = "create-wires-column create-wires-end-pool";
  column.dataset.pathwayId = boundary.pathway.pathwayId;
  column.dataset.endpoint = boundary.endpoint;
  heading.textContent = wireCreationBoundaryLabel(boundary);
  list.className = "create-wires-end-list";
  list.setAttribute("role", "list");
  column.append(heading, list);
  return { column, list };
}

/** Render the current popup-only pool and assignment state. */
function renderWireCreationAssignments(
  harness, boundaries, groups, assignments, pools, center, showContextMenu,
) {
  const rerender = () => renderWireCreationAssignments(
    harness, boundaries, groups, assignments, pools, center, showContextMenu,
  );
  const groupMaps = {
    left: new Map(groups.left.map((group) => [group.connectionId, group])),
    right: new Map(groups.right.map((group) => [group.connectionId, group])),
  };
  const connectedIds = wireCreationStagedConnectedIds(harness, assignments);
  const surfaces = {
    center,
    markers: new Set(),
    pools: {
      left: { list: pools.left.list, cards: [] },
      right: { list: pools.right.list, cards: [] },
    },
    rows: [],
  };
  ["left", "right"].forEach((side) => {
    pools[side].list.replaceChildren();
    assignments.pools[side].forEach((connectionId) => {
      const group = groupMaps[side].get(connectionId);
      if (!group) return;
      const card = renderWireCreationEndCard(
        harness,
        boundaries[side],
        group,
        assignments,
        connectedIds.has(connectionId),
        showContextMenu,
        rerender,
      );
      card.dataset.assignmentSide = side;
      card.dataset.assignmentLocation = "pool";
      surfaces.pools[side].cards.push(card);
      pools[side].list.append(card);
    });
    if (!surfaces.pools[side].cards.length) {
      pools[side].list.append(emptyMessage("No disconnected ends."));
    }
  });

  center.replaceChildren();
  assignments.rows.forEach((assignment, index) => {
    const row = document.createElement("div");
    const leftSlot = document.createElement("div");
    const connector = document.createElement("span");
    const rightSlot = document.createElement("div");
    const slots = { left: leftSlot, right: rightSlot };
    row.className = "create-wires-assignment-row";
    row.dataset.assignmentRow = `${index}`;
    leftSlot.className = "create-wires-assignment-slot left";
    rightSlot.className = "create-wires-assignment-slot right";
    connector.className = "create-wires-assignment-connector";
    connector.setAttribute("aria-hidden", "true");
    if (assignment.left && assignment.right) row.dataset.complete = "true";
    ["left", "right"].forEach((side) => {
      const item = assignment[side];
      const group = item && groupMaps[side].get(item.connectionId);
      if (!group) return;
      const card = renderWireCreationEndCard(
        harness,
        boundaries[side],
        group,
        assignments,
        connectedIds.has(item.connectionId),
        showContextMenu,
        rerender,
      );
      card.dataset.assignmentSide = side;
      card.dataset.assignmentLocation = "center";
      slots[side].append(card);
    });
    row.append(leftSlot, connector, rightSlot);
    center.append(row);
    surfaces.rows.push({
      row,
      slots,
      index,
      pending: Boolean(assignment.left) !== Boolean(assignment.right),
      emptySide: assignment.left ? "right" : "left",
    });
  });

  ["left", "right"].forEach((side) => {
    surfaces.pools[side].cards.forEach((card, poolIndex) => {
      enableWireCreationDrag(
        card,
        { location: "pool", side, poolIndex },
        surfaces,
        (target) => {
          void send("clear_highlight").catch(() => {});
          assignWireCreationPoolItem(assignments, side, poolIndex, target.rowIndex ?? 0);
          rerender();
        },
      );
    });
  });
  surfaces.rows.forEach((record, rowIndex) => {
    ["left", "right"].forEach((side) => {
      const card = record.slots[side].children[0];
      if (!card) return;
      enableWireCreationDrag(
        card,
        { location: "center", side, rowIndex },
        surfaces,
        (target) => {
          void send("clear_highlight").catch(() => {});
          if (target.location === "swap") {
            swapWireCreationRowItems(assignments, side, rowIndex, target.rowIndex);
          } else {
            unassignWireCreationRowItem(assignments, side, rowIndex, target.poolIndex);
          }
          rerender();
        },
      );
    });
  });
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

/** Commit every staged Connection Editor change through one host transaction. */
async function saveWireCreationAssignments(harness, boundaries, assignments, saveButton) {
  const pairings = wireCreationCompletePairings(assignments);
  const deletedConnectionIds = Object.keys(assignments.deletedConnectionIds);
  const deleted = new Set(deletedConnectionIds);
  const detachedConnectionIds = wireCreationDetachedConnectionIds(
    assignments, pairings, deleted,
  );
  const renames = Object.entries(assignments.renames)
    .filter(([connectionId]) => !deleted.has(connectionId))
    .map(([connectionId, name]) => ({ connectionId, name }));
  saveButton.disabled = true;
  appendNotice("Saving Connection Editor changes…");
  try {
    const response = await send("save_wire_editor", {
      harnessId: harness.harnessId,
      leftBoundary: wireCreationBoundaryState(boundaries.left),
      rightBoundary: wireCreationBoundaryState(boundaries.right),
      pairings,
      detachedConnectionIds,
      renames,
      deletedConnectionIds,
    });
    if (!response.ok) {
      appendNotice(response.error || "Connection Editor changes could not be saved.", true);
      saveButton.disabled = false;
      return;
    }
    closeCreateWiresPopup();
  } catch (error) {
    appendNotice(error.message, true);
    saveButton.disabled = false;
  }
}

/** Open the three-column workspace for two selected boundaries. */
function openCreateWiresPopup(
  harness, left, right, scrollPositions = [0, 0, 0], restoredAssignments = null,
) {
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
  const cancel = document.createElement("button");
  const save = document.createElement("button");
  const groups = wireCreationDisconnectedGroups(harness, left, right);
  const assignments = reconcileWireCreationAssignments(restoredAssignments, groups);
  const leftPool = createWireCreationEndPool(left);
  const rightPool = createWireCreationEndPool(right);
  dialog.className = "create-wires-popup";
  dialog.setAttribute("aria-labelledby", "create-wires-title");
  const showContextMenu = addContextMenu(dialog);
  openCreateWiresPopupState = {
    harnessKey: harnessKey(harness),
    left: wireCreationBoundaryState(left),
    right: wireCreationBoundaryState(right),
    scrollPositions: [...scrollPositions],
    assignments,
  };
  heading.id = "create-wires-title";
  heading.textContent = "Connection Editor";
  layout.className = "create-wires-layout";
  center.className = "create-wires-column create-wires-assignment-pool";
  centerHeading.textContent = "Wire Assignments";
  centerContent.className = "create-wires-assignment-content";
  centerContent.setAttribute("aria-label", "Visual wire assignments");
  center.append(centerHeading, centerContent);
  layout.append(
    leftPool.column,
    center,
    rightPool.column,
  );
  renderWireCreationAssignments(
    harness,
    { left, right },
    groups,
    assignments,
    { left: leftPool, right: rightPool },
    centerContent,
    showContextMenu,
  );
  actions.className = "pathway-popup-actions";
  cancel.type = "button";
  cancel.className = "button secondary";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", closeCreateWiresPopup);
  save.type = "button";
  save.className = "button";
  save.textContent = "Save";
  save.addEventListener("click", () => saveWireCreationAssignments(
    harness, { left, right }, assignments, save,
  ));
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeCreateWiresPopup();
  });
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".create-wires-popup") === dialog) {
      openCreateWiresPopupState = null;
    }
    dialog.remove();
  });
  actions.append(cancel, save);
  dialog.append(heading, layout, actions);
  document.body.append(dialog);
  dialog.showModal();
  window.requestAnimationFrame(() => {
    Array.from(dialog.querySelectorAll(".create-wires-column")).forEach((column, index) => {
      column.scrollTop = scrollPositions[index] || 0;
    });
  });
  save.focus();
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
  openCreateWiresPopup(
    harness, left, right, state.scrollPositions, state.assignments,
  );
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
