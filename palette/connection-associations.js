/** Select attachment hierarchies and edit their persistent terminal associations. */

let cancelActiveConnectionAssociationSelection = null;
let nextConnectionAssociationGroupId = 0;

/** Resolve terminal attachment nodes beneath one cable-end diagram node. */
function connectionAssociationCandidates(harness, anchor) {
  if (anchor.nodeKind === "pathway" || anchor.nodeKind === "junction") {
    const dialog = document.body.querySelector(".cable-group-details-popup");
    const graphic = dialog?.querySelector(".cable-group-details-graphic");
    const nodes = new Map([...graphic?.querySelectorAll(".cable-group-details-node") || []]
      .map((node) => [node.dataset.nodeId, node]));
    const startId = `${anchor.nodeKind}:${anchor.nodeId}`;
    if (!nodes.has(startId)) return [];
    const neighbors = new Map([...nodes.keys()].map((id) => [id, new Set()]));
    graphic.querySelectorAll(".cable-group-route-link").forEach((edge) => {
      const left = edge.dataset.startNodeId;
      const right = edge.dataset.endNodeId;
      neighbors.get(left)?.add(right);
      neighbors.get(right)?.add(left);
    });
    const reachable = new Set([startId]);
    const pending = [startId];
    while (pending.length) {
      const currentId = pending.pop();
      const currentDepth = Number(nodes.get(currentId).dataset.depth);
      (neighbors.get(currentId) || []).forEach((neighbor) => {
        if (reachable.has(neighbor)) return;
        if (Number(nodes.get(neighbor).dataset.depth) <= currentDepth) return;
        reachable.add(neighbor);
        pending.push(neighbor);
      });
    }
    const candidates = [];
    reachable.forEach((id) => {
      const node = nodes.get(id);
      if (node?.classList.contains("connection")) {
        candidates.push(...connectionAssociationCandidates(harness, {
          connectionId: node.dataset.connectionId,
          attachmentId: null,
        }));
      }
    });
    return candidates;
  }
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === anchor.connectionId,
  );
  if (!connection) return [];
  const attachments = connection.attachments || (connection.attachment ? [connection.attachment] : []);
  const byId = new Map(attachments.map((attachment) => [attachment.attachmentId, attachment]));
  const children = new Map();
  attachments.forEach((attachment) => {
    const key = attachment.parentAttachmentId || "";
    if (!children.has(key)) children.set(key, []);
    children.get(key).push(attachment);
  });
  const roots = anchor.attachmentId
    ? (byId.has(anchor.attachmentId) ? [byId.get(anchor.attachmentId)] : [])
    : (children.get("") || []);
  const result = [];
  const pending = [...roots].reverse();
  while (pending.length) {
    const attachment = pending.pop();
    const descendants = children.get(attachment.attachmentId) || [];
    if (descendants.length) {
      pending.push(...[...descendants].reverse());
    } else {
      result.push({
        attachmentId: attachment.attachmentId,
        connectionId: connection.connectionId,
        connectionName: connection.name || "Cable end",
        label: attachment.name || "Connection",
      });
    }
  }
  return result;
}

/** Clear node-selection styling and document-level listeners. */
function clearConnectionAssociationSelection(container) {
  container.classList.remove("connection-association-selecting");
  container.querySelectorAll(
    ".connection-association-source, .connection-association-target, .connection-association-unavailable",
  ).forEach((node) => node.classList.remove(
    "connection-association-source",
    "connection-association-target",
    "connection-association-unavailable",
  ));
  document.removeEventListener("click", handleConnectionAssociationClick, true);
  document.removeEventListener("keydown", handleConnectionAssociationKeyDown, true);
}

let connectionAssociationSelection = null;

/** Select a highlighted second hierarchy or cancel on another click. */
function handleConnectionAssociationClick(event) {
  const selection = connectionAssociationSelection;
  if (!selection) return;
  const node = event.target.closest?.(".cable-group-details-node");
  const anchor = node ? connectionAssociationAnchorFromElement(node) : null;
  if (node && selection.eligible.has(node)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const candidates = connectionAssociationCandidates(selection.harness, anchor);
    const targetAnchor = anchor.nodeKind
      ? { ...anchor, candidateAttachmentIds: candidates.map((item) => item.attachmentId) }
      : anchor;
    clearConnectionAssociationSelection(selection.container);
    connectionAssociationSelection = null;
    cancelActiveConnectionAssociationSelection = null;
    openConnectionAssociationPanel(
      selection.harness,
      selection.sourceAnchor,
      targetAnchor,
      selection.sourceCandidates,
      candidates,
      selection.sourceLabel,
      node.getAttribute("aria-label") || "Selected connection",
    );
    return;
  }
  if (selection.container.contains(event.target)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }
  selection.cancel();
}

/** Allow Escape to cancel and Enter/Space to choose a highlighted hierarchy. */
function handleConnectionAssociationKeyDown(event) {
  if (!connectionAssociationSelection) return;
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    connectionAssociationSelection.cancel();
    return;
  }
  if (!(["Enter", " "].includes(event.key))) return;
  const node = event.target.closest?.(".cable-group-details-node");
  if (!node || !connectionAssociationSelection.eligible.has(node)) return;
  event.preventDefault();
  node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

/** Recover a selection anchor from a rendered diagram node. */
function connectionAssociationAnchorFromElement(node) {
  if (node.classList.contains("pathway") || node.classList.contains("junction")) {
    const [nodeKind, nodeId] = node.dataset.nodeId.split(":");
    return { nodeKind, nodeId };
  }
  const connectionId = node.dataset.connectionId;
  return node.classList.contains("attachment")
    ? { connectionId, attachmentId: node.dataset.attachmentId }
    : { connectionId, attachmentId: null };
}

/** Begin choosing a second cable-end node for a terminal association panel. */
function beginCableGroupAttachmentAssociation(harness, source) {
  if (cancelActiveConnectionAssociationSelection) {
    cancelActiveConnectionAssociationSelection();
  }
  const dialog = document.body.querySelector(".cable-group-details-popup");
  const container = dialog?.querySelector(".cable-group-details-graphic");
  if (!container) return;
  const sourceCandidates = connectionAssociationCandidates(harness, source);
  const sourceAnchor = source.nodeKind
    ? { ...source, candidateAttachmentIds: sourceCandidates.map((item) => item.attachmentId) }
    : source;
  const sourceIds = new Set(sourceCandidates.map((item) => item.attachmentId));
  const eligible = new Set();
  const nodeElements = container.querySelectorAll(".cable-group-details-node");
  nodeElements.forEach((node) => {
    const anchor = connectionAssociationAnchorFromElement(node);
    const candidates = connectionAssociationCandidates(harness, anchor);
    const overlaps = candidates.some((candidate) => sourceIds.has(candidate.attachmentId));
    node.classList.remove(
      "connection-association-source",
      "connection-association-target",
      "connection-association-unavailable",
    );
    const isSource = node.dataset.nodeId === (source.nodeKind
      ? `${source.nodeKind}:${source.nodeId}`
      : (source.attachmentId
      ? `attachment:${source.connectionId}:${source.attachmentId}`
      : `connection:${source.connectionId}`));
    if (isSource) {
      node.classList.add("connection-association-source");
    } else if (candidates.length && !overlaps) {
      eligible.add(node);
      node.classList.add("connection-association-target");
    } else {
      node.classList.add("connection-association-unavailable");
    }
  });
  container.classList.add("connection-association-selecting");
  let active = true;
  const cancel = () => {
    if (!active) return;
    active = false;
    clearConnectionAssociationSelection(container);
    if (connectionAssociationSelection?.cancel === cancel) {
      connectionAssociationSelection = null;
    }
    if (cancelActiveConnectionAssociationSelection === cancel) {
      cancelActiveConnectionAssociationSelection = null;
    }
  };
  connectionAssociationSelection = {
    harness,
    source,
    sourceAnchor,
    sourceCandidates,
    sourceLabel: [...nodeElements]
      .find((node) => node.classList.contains("connection-association-source"))
      ?.getAttribute("aria-label") || "Selected connection",
    container,
    eligible,
    cancel,
  };
  cancelActiveConnectionAssociationSelection = cancel;
  appendNotice("Associate: choose a highlighted connection node, or press Escape to cancel.");
  document.addEventListener("click", handleConnectionAssociationClick, true);
  document.addEventListener("keydown", handleConnectionAssociationKeyDown, true);
}

/** Return current association rows and unassigned candidate pools. */
function initialConnectionAssociationAssignments(harness, left, right) {
  const leftIds = new Set(left.map((item) => item.attachmentId));
  const rightIds = new Set(right.map((item) => item.attachmentId));
  const leftUsed = new Set();
  const rightUsed = new Set();
  const rows = [];
  const lockedIds = new Set();
  const existingIds = new Set();
  (harness.attachmentAssociations || []).forEach((association) => {
    const members = association.attachmentIds || [];
    const leftMembers = members.filter((id) => leftIds.has(id));
    const rightMembers = members.filter((id) => rightIds.has(id));
    if (leftMembers.length && rightMembers.length &&
        leftMembers.length + rightMembers.length === members.length) {
      existingIds.add(association.associationId);
      leftMembers.forEach((id) => leftUsed.add(id));
      rightMembers.forEach((id) => rightUsed.add(id));
      for (let index = 0; index < Math.max(leftMembers.length, rightMembers.length); index += 1) {
        rows.push({
          groupId: association.associationId,
          left: leftMembers[index]
            ? { connectionId: leftMembers[index], returnIndex: 0 } : null,
          right: rightMembers[index]
            ? { connectionId: rightMembers[index], returnIndex: 0 } : null,
        });
      }
    } else members.forEach((id) => {
      if (leftIds.has(id) || rightIds.has(id)) lockedIds.add(id);
    });
  });
  return {
    pools: {
      left: left.map((item) => item.attachmentId).filter((id) => !leftUsed.has(id)),
      right: right.map((item) => item.attachmentId).filter((id) => !rightUsed.has(id)),
    },
    rows,
    lockedIds,
    existingIds,
  };
}

/** Move a pool attachment into a new row or the specified existing association. */
function assignConnectionAssociationItem(assignments, side, attachmentId, target) {
  const poolIndex = assignments.pools[side].indexOf(attachmentId);
  if (poolIndex < 0) return;
  const targetRow = ["extend", "pending"].includes(target.location)
    ? assignments.rows[target.rowIndex] : null;
  if (["extend", "pending"].includes(target.location) && !targetRow) return;
  assignments.pools[side].splice(poolIndex, 1);
  const item = { connectionId: attachmentId, returnIndex: poolIndex };
  if (target.location === "extend") {
    const groupRows = assignments.rows.filter((row) => row.groupId === targetRow.groupId);
    const lastRow = groupRows[groupRows.length - 1];
    if (!lastRow[side]) lastRow[side] = item;
    else {
      const row = { groupId: targetRow.groupId, left: null, right: null };
      row[side] = item;
      assignments.rows.splice(assignments.rows.lastIndexOf(lastRow) + 1, 0, row);
    }
    return;
  }
  if (target.location === "pending") {
    if (!targetRow[side]) {
      targetRow[side] = item;
      return;
    }
  }
  const row = { groupId: `new:${++nextConnectionAssociationGroupId}`, left: null, right: null };
  row[side] = item;
  const index = Math.max(0, Math.min(target.rowIndex ?? assignments.rows.length, assignments.rows.length));
  assignments.rows.splice(index, 0, row);
}

/** Return a center attachment to its source pool without changing other groups. */
function unassignConnectionAssociationItem(assignments, side, rowIndex, poolIndex) {
  const row = assignments.rows[rowIndex];
  const item = row?.[side];
  if (!item) return;
  const pool = assignments.pools[side];
  pool.splice(Math.max(0, Math.min(poolIndex, pool.length)), 0, item.connectionId);
  row[side] = null;
  if (!row.left && !row.right) assignments.rows.splice(rowIndex, 1);
}

/** Combine two staged association groups while keeping one existing identity. */
function joinConnectionAssociationGroups(assignments, sourceRowIndex, targetRowIndex) {
  const source = assignments.rows[sourceRowIndex];
  const target = assignments.rows[targetRowIndex];
  if (!source || !target || source.groupId === target.groupId) return;
  const groupId = assignments.existingIds.has(target.groupId) ? target.groupId
    : assignments.existingIds.has(source.groupId) ? source.groupId : target.groupId;
  const moving = assignments.rows.filter((row) => row.groupId === source.groupId);
  assignments.rows = assignments.rows.filter((row) => row.groupId !== source.groupId);
  const targetRows = assignments.rows.filter((row) => row.groupId === target.groupId);
  const insertIndex = assignments.rows.lastIndexOf(targetRows[targetRows.length - 1]) + 1;
  targetRows.forEach((row) => { row.groupId = groupId; });
  moving.forEach((row) => { row.groupId = groupId; });
  assignments.rows.splice(insertIndex, 0, ...moving);
}

/** Build one draggable terminal-connection card for an association pool or row. */
function renderConnectionAssociationCard(item, locked = false) {
  const card = document.createElement("div");
  const name = document.createElement("strong");
  const owner = document.createElement("small");
  card.className = "relationship-end-entry create-cables-end-card create-association-card";
  card.dataset.attachmentId = item.attachmentId;
  card.setAttribute("role", "listitem");
  name.textContent = item.label;
  owner.textContent = locked ? `${item.connectionName} · Associated elsewhere` : item.connectionName;
  card.append(name, owner);
  if (locked) {
    card.dataset.associationLocked = "true";
    card.title = "This connection is associated outside the selected hierarchies.";
  } else card.title = `${item.label} · Drag to create or change an association`;
  return card;
}

/** Persist staged association rows and keep the details view available on failure. */
async function saveConnectionAssociations(
  harness, anchors, assignments, button, dialog,
) {
  const grouped = new Map();
  assignments.rows.forEach((row) => {
    const group = grouped.get(row.groupId) || { attachmentIds: [], left: 0, right: 0 };
    if (row.left) {
      group.attachmentIds.push(row.left.connectionId);
      group.left += 1;
    }
    if (row.right) {
      group.attachmentIds.push(row.right.connectionId);
      group.right += 1;
    }
    grouped.set(row.groupId, group);
  });
  const associations = [...grouped].filter(([, group]) => group.left && group.right)
    .map(([groupId, group]) => ({
      attachmentIds: group.attachmentIds,
      associationId: assignments.existingIds.has(groupId) ? groupId : null,
    }));
  button.disabled = true;
  appendNotice("Saving connection associations…");
  try {
    const response = await send("save_attachment_associations", {
      harnessId: harness.harnessId,
      leftAnchor: anchors.left,
      rightAnchor: anchors.right,
      associations,
    });
    if (response.ok) dialog.close();
    else appendNotice(response.error || "Connection associations could not be saved.", true);
  } catch (error) {
    appendNotice(error.message, true);
  } finally {
    button.disabled = false;
  }
}

/** Open the three-column association panel for two selected connection hierarchies. */
function openConnectionAssociationPanel(
  harness, leftAnchor, rightAnchor, leftItems, rightItems, leftLabel, rightLabel,
) {
  const prior = document.body.querySelector(".connection-associations-popup");
  if (prior?.open) prior.close();
  else prior?.remove();
  const dialog = document.createElement("dialog");
  const heading = document.createElement("h2");
  const layout = document.createElement("div");
  const leftPool = createConnectionAssociationPool(leftAnchor, leftItems, "left", leftLabel);
  const rightPool = createConnectionAssociationPool(rightAnchor, rightItems, "right", rightLabel);
  const center = document.createElement("section");
  const centerHeading = document.createElement("h3");
  const centerContent = document.createElement("div");
  const actions = document.createElement("div");
  const cancel = document.createElement("button");
  const save = document.createElement("button");
  const assignments = initialConnectionAssociationAssignments(harness, leftItems, rightItems);
  const groups = {
    left: new Map(leftItems.map((item) => [item.attachmentId, item])),
    right: new Map(rightItems.map((item) => [item.attachmentId, item])),
  };
  dialog.className = "connection-associations-popup";
  heading.textContent = "Connection Associations";
  layout.className = "create-cables-layout";
  center.className = "create-cables-column create-cables-assignment-pool";
  centerHeading.textContent = "Associations";
  centerContent.className = "create-cables-assignment-content";
  centerContent.setAttribute("aria-label", "Connection associations");
  center.append(centerHeading, centerContent);
  layout.append(leftPool.column, center, rightPool.column);
  actions.className = "pathway-popup-actions";
  cancel.type = "button";
  cancel.className = "button secondary";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => dialog.close());
  save.type = "button";
  save.className = "button";
  save.textContent = "Save";
  save.addEventListener("click", () => saveConnectionAssociations(
    harness,
    { left: leftAnchor, right: rightAnchor },
    assignments,
    save,
    dialog,
  ));
  actions.append(cancel, save);
  dialog.append(heading, layout, actions);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
  renderConnectionAssociationAssignments(
    harness, assignments, groups, { left: leftPool, right: rightPool }, centerContent,
  );
}

/** Create one association candidate column. */
function createConnectionAssociationPool(anchor, items, side, label) {
  const column = document.createElement("section");
  const heading = document.createElement("h3");
  const list = document.createElement("div");
  column.className = "create-cables-column create-cables-end-pool";
  column.dataset.connectionId = anchor.connectionId;
  if (anchor.attachmentId) column.dataset.attachmentId = anchor.attachmentId;
  heading.textContent = label;
  list.className = "create-cables-end-list";
  list.setAttribute("role", "list");
  column.append(heading, list);
  const pool = { column, list };
  pool.column.classList.add("create-association-pool");
  pool.list.classList.add("create-association-list");
  pool.list.setAttribute("aria-label", `${items[0]?.connectionName || "Connection"} terminal connections`);
  return pool;
}

/** Render staged pair rows using the Route Editor's drag markers and drop rules. */
function renderConnectionAssociationAssignments(harness, assignments, groups, pools, center) {
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
    assignments.pools[side].forEach((attachmentId) => {
      const item = groups[side].get(attachmentId);
      if (!item) return;
      const locked = assignments.lockedIds.has(attachmentId);
      const card = renderConnectionAssociationCard(item, locked);
      card.dataset.assignmentSide = side;
      card.dataset.assignmentLocation = "pool";
      surfaces.pools[side].cards.push(card);
      pools[side].list.append(card);
      if (!locked) {
        enableCableCreationDrag(card, { location: "pool", side }, surfaces,
          (target) => handleConnectionAssociationDrop(
            assignments, side, null, target, attachmentId, pools, center, harness, groups,
          ), null, "association");
      }
    });
    if (!pools[side].list.children.length) pools[side].list.append(emptyMessage("No available connections."));
  });
  center.replaceChildren();
  const rowCounts = new Map();
  assignments.rows.forEach((row) => {
    rowCounts.set(row.groupId, (rowCounts.get(row.groupId) || 0) + 1);
  });
  assignments.rows.forEach((assignment, index) => {
    const row = document.createElement("div");
    const leftSlot = document.createElement("div");
    const connector = document.createElement("span");
    const rightSlot = document.createElement("div");
    row.className = "create-cables-assignment-row";
    row.dataset.assignmentRow = `${index}`;
    if (rowCounts.get(assignment.groupId) > 1) {
      row.dataset.grouped = "true";
      if (assignments.rows[index - 1]?.groupId === assignment.groupId) {
        row.dataset.groupContinuation = "true";
      }
      if (assignments.rows[index + 1]?.groupId === assignment.groupId) {
        row.dataset.groupContinues = "true";
      }
      if (Boolean(assignment.left) !== Boolean(assignment.right)) {
        row.dataset.groupSingleSide = assignment.left ? "left" : "right";
      }
    }
    leftSlot.className = "create-cables-assignment-slot left";
    rightSlot.className = "create-cables-assignment-slot right";
    connector.className = "create-cables-assignment-connector";
    connector.setAttribute("aria-hidden", "true");
    if (assignment.left && assignment.right) row.dataset.complete = "true";
    [["left", leftSlot], ["right", rightSlot]].forEach(([side, slot]) => {
      const attachmentId = assignment[side]?.connectionId;
      if (attachmentId) {
        const item = groups[side].get(attachmentId);
        if (item) {
          const card = renderConnectionAssociationCard(item);
          card.dataset.assignmentSide = side;
          card.dataset.assignmentLocation = "row";
          card.title = "Drag onto another association to combine groups; Option-drag to swap ends.";
          slot.append(card);
          enableCableCreationDrag(card, {
            location: "row", side, rowIndex: index, groupId: assignment.groupId,
          }, surfaces,
            (target) => handleConnectionAssociationDrop(
              assignments, side, index, target, attachmentId, pools, center, harness, groups,
            ), null, "association");
        }
      }
    });
    row.append(leftSlot, connector, rightSlot);
    center.append(row);
    surfaces.rows.push({
      index, row, pending: Boolean(assignment.left) !== Boolean(assignment.right),
      groupId: assignment.groupId,
      emptySide: assignment.left ? "right" : "left",
      slots: { left: leftSlot, right: rightSlot },
    });
  });
  if (!assignments.rows.length) center.append(emptyMessage("Drag connections here to create associations."));
}

/** Apply one pool, group, swap, or unassignment drop to staged associations. */
function handleConnectionAssociationDrop(
  assignments, side, rowIndex, target, attachmentId, pools, center, harness, groups,
) {
  if (["center", "pending", "extend"].includes(target.location)) {
    assignConnectionAssociationItem(assignments, side, attachmentId, target);
  } else if (target.location === "join") {
    joinConnectionAssociationGroups(assignments, rowIndex, target.rowIndex);
  } else if (target.location === "swap") {
    swapCableCreationRowItems(assignments, side, rowIndex, target.rowIndex);
  } else if (target.location === "pool") {
    unassignConnectionAssociationItem(assignments, side, rowIndex, target.poolIndex);
  }
  renderConnectionAssociationAssignments(harness, assignments, groups, pools, center);
}
