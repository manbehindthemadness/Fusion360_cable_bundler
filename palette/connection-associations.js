/** Select attachment hierarchies and edit their persistent terminal associations. */

let cancelActiveConnectionAssociationSelection = null;

/** Resolve terminal attachment nodes beneath one cable-end diagram node. */
function connectionAssociationCandidates(harness, anchor) {
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
  const node = event.target.closest?.(".cable-group-details-node.connection, .cable-group-details-node.attachment");
  const anchor = node ? connectionAssociationAnchorFromElement(node) : null;
  if (node && selection.eligible.has(node)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const candidates = connectionAssociationCandidates(selection.harness, anchor);
    clearConnectionAssociationSelection(selection.container);
    connectionAssociationSelection = null;
    cancelActiveConnectionAssociationSelection = null;
    openConnectionAssociationPanel(
      selection.harness,
      selection.source,
      anchor,
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
  const node = event.target.closest?.(".cable-group-details-node.connection, .cable-group-details-node.attachment");
  if (!node || !connectionAssociationSelection.eligible.has(node)) return;
  event.preventDefault();
  node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

/** Recover a selection anchor from a rendered diagram node. */
function connectionAssociationAnchorFromElement(node) {
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
  const sourceIds = new Set(sourceCandidates.map((item) => item.attachmentId));
  const eligible = new Set();
  const nodeElements = container.querySelectorAll(
    ".cable-group-details-node.connection, .cable-group-details-node.attachment",
  );
  nodeElements.forEach((node) => {
    const anchor = connectionAssociationAnchorFromElement(node);
    const candidates = connectionAssociationCandidates(harness, anchor);
    const overlaps = candidates.some((candidate) => sourceIds.has(candidate.attachmentId));
    node.classList.remove(
      "connection-association-source",
      "connection-association-target",
      "connection-association-unavailable",
    );
    if (node.dataset.nodeId === (source.attachmentId
      ? `attachment:${source.connectionId}:${source.attachmentId}`
      : `connection:${source.connectionId}`)) {
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
  (harness.attachmentAssociations || []).forEach((association) => {
    const [first, second] = association.attachmentIds || [];
    const firstOnLeft = leftIds.has(first);
    const secondOnLeft = leftIds.has(second);
    const firstOnRight = rightIds.has(first);
    const secondOnRight = rightIds.has(second);
    if (firstOnLeft && secondOnRight || secondOnLeft && firstOnRight) {
      const leftId = firstOnLeft ? first : second;
      const rightId = firstOnRight ? first : second;
      leftUsed.add(leftId);
      rightUsed.add(rightId);
      rows.push({
        left: { connectionId: leftId, returnIndex: 0 },
        right: { connectionId: rightId, returnIndex: 0 },
      });
    } else {
      if (firstOnLeft || firstOnRight) lockedIds.add(first);
      if (secondOnLeft || secondOnRight) lockedIds.add(second);
    }
  });
  return {
    pools: {
      left: left.map((item) => item.attachmentId).filter((id) => !leftUsed.has(id)),
      right: right.map((item) => item.attachmentId).filter((id) => !rightUsed.has(id)),
    },
    rows,
    lockedIds,
  };
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
  const pairs = assignments.rows.filter((row) => row.left && row.right).map((row) => ({
    leftAttachmentId: row.left.connectionId,
    rightAttachmentId: row.right.connectionId,
  }));
  button.disabled = true;
  appendNotice("Saving connection associations…");
  try {
    const response = await send("save_attachment_associations", {
      harnessId: harness.harnessId,
      leftAnchor: anchors.left,
      rightAnchor: anchors.right,
      associations: pairs,
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
          ));
      }
    });
    if (!pools[side].list.children.length) pools[side].list.append(emptyMessage("No available connections."));
  });
  center.replaceChildren();
  assignments.rows.forEach((assignment, index) => {
    const row = document.createElement("div");
    const leftSlot = document.createElement("div");
    const connector = document.createElement("span");
    const rightSlot = document.createElement("div");
    row.className = "create-cables-assignment-row";
    row.dataset.assignmentRow = `${index}`;
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
          slot.append(card);
          enableCableCreationDrag(card, { location: "row", side, rowIndex: index }, surfaces,
            (target) => handleConnectionAssociationDrop(
              assignments, side, index, target, attachmentId, pools, center, harness, groups,
            ));
        }
      }
    });
    row.append(leftSlot, connector, rightSlot);
    center.append(row);
    surfaces.rows.push({
      index, row, pending: Boolean(assignment.left) !== Boolean(assignment.right),
      emptySide: assignment.left ? "right" : "left",
      slots: { left: leftSlot, right: rightSlot },
    });
  });
  if (!assignments.rows.length) center.append(emptyMessage("Drag connections here to create associations."));
}

/** Apply one pool, row, or swap drop to the staged association state. */
function handleConnectionAssociationDrop(
  assignments, side, rowIndex, target, attachmentId, pools, center, harness, groups,
) {
  if (target.location === "center" || target.location === "pending") {
    const actualPoolIndex = assignments.pools[side].indexOf(attachmentId);
    if (actualPoolIndex >= 0) {
      assignCableCreationPoolItem(assignments, side, actualPoolIndex, target.rowIndex);
    }
  } else if (target.location === "swap") {
    swapCableCreationRowItems(assignments, side, rowIndex, target.rowIndex);
  } else if (target.location === "pool") {
    unassignCableCreationRowItem(assignments, side, rowIndex, target.poolIndex);
  }
  renderConnectionAssociationAssignments(harness, assignments, groups, pools, center);
}
