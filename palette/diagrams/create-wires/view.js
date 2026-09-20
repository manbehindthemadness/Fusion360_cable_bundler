/** Drag-and-drop rendering for staged wire assignments. */

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
  card.dataset.wireGroupIds = relationshipGroupIds(group.groups);
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

/** Add pathway-guide-style pointer dragging to one Route Editor card. */
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

