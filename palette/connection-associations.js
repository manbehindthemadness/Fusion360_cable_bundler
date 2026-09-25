/** Return current association rows and unassigned candidate pools. */
function initialConnectionAssociationAssignments(harness, left, right) {
  const leftIds = new Set(left.map((item) => item.attachmentId));
  const rightIds = new Set(right.map((item) => item.attachmentId));
  const leftUsed = new Set();
  const rightUsed = new Set();
  const rows = [];
  const elsewhereIds = new Set();
  const existingIds = new Set();
  const associationMembers = new Map();
  const outsideByMember = new Map();
  const groupSources = new Map();
  (harness.attachmentAssociations || []).forEach((association) => {
    const members = association.attachmentIds || [];
    existingIds.add(association.associationId);
    associationMembers.set(association.associationId, members);
    groupSources.set(association.associationId, new Set([association.associationId]));
    const leftMembers = members.filter((id) => leftIds.has(id));
    const rightMembers = members.filter((id) => rightIds.has(id));
    if (leftMembers.length && rightMembers.length) {
      leftMembers.forEach((id) => leftUsed.add(id));
      rightMembers.forEach((id) => rightUsed.add(id));
      if (leftMembers.length + rightMembers.length !== members.length) {
        [...leftMembers, ...rightMembers].forEach((id) => {
          elsewhereIds.add(id);
          outsideByMember.set(id, association.associationId);
        });
      }
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
      if (leftIds.has(id) || rightIds.has(id)) {
        elsewhereIds.add(id);
        outsideByMember.set(id, association.associationId);
      }
    });
  });
  const orderedPool = (items, used) => {
    const available = items.map((item) => item.attachmentId).filter((id) => !used.has(id));
    const groups = new Map();
    available.forEach((id) => {
      const groupId = outsideByMember.get(id);
      if (!groupId) return;
      if (!groups.has(groupId)) groups.set(groupId, []);
      groups.get(groupId).push(id);
    });
    const emitted = new Set();
    return available.flatMap((id) => {
      if (emitted.has(id)) return [];
      const members = groups.get(outsideByMember.get(id)) || [id];
      members.forEach((memberId) => emitted.add(memberId));
      return members;
    });
  };
  return {
    pools: {
      left: orderedPool(left, leftUsed),
      right: orderedPool(right, rightUsed),
    },
    rows,
    elsewhereIds,
    existingIds,
    associationMembers,
    outsideByMember,
    groupSources,
    selectedIds: new Set([...leftIds, ...rightIds]),
  };
}

/** Bring every visible member of an outside association into the center together. */
function materializeOutsideConnectionAssociation(assignments, associationId, target) {
  const members = new Set(assignments.associationMembers.get(associationId));
  const visible = Object.fromEntries(["left", "right"].map((side) => [
    side, assignments.pools[side].filter((id) => members.has(id)),
  ]));
  if (!visible.left.length && !visible.right.length) return;
  const targetRow = ["extend", "pending"].includes(target.location)
    ? assignments.rows[target.rowIndex] : null;
  const targetRows = targetRow
    ? assignments.rows.filter((row) => row.groupId === targetRow.groupId) : [];
  const insertion = targetRows.length
    ? assignments.rows.lastIndexOf(targetRows[targetRows.length - 1]) + 1
    : Math.max(0, Math.min(target.rowIndex ?? assignments.rows.length, assignments.rows.length));
  ["left", "right"].forEach((side) => {
    assignments.pools[side] = assignments.pools[side].filter((id) => !members.has(id));
  });
  const rows = [];
  for (let index = 0; index < Math.max(visible.left.length, visible.right.length); index += 1) {
    rows.push({
      groupId: associationId,
      left: visible.left[index] ? { connectionId: visible.left[index] } : null,
      right: visible.right[index] ? { connectionId: visible.right[index] } : null,
    });
  }
  assignments.rows.splice(insertion, 0, ...rows);
  if (targetRow) {
    joinConnectionAssociationGroups(assignments, insertion, assignments.rows.indexOf(targetRow));
  }
}

/** Move a pool attachment into a new row or the specified existing association. */
function assignConnectionAssociationItem(assignments, side, attachmentId, target) {
  const poolIndex = assignments.pools[side].indexOf(attachmentId);
  if (poolIndex < 0) return;
  const targetRow = ["extend", "pending"].includes(target.location)
    ? assignments.rows[target.rowIndex] : null;
  if (["extend", "pending"].includes(target.location) && !targetRow) return;
  const outsideId = assignments.outsideByMember.get(attachmentId);
  if (outsideId) {
    materializeOutsideConnectionAssociation(assignments, outsideId, target);
    return;
  }
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
  const outsideId = assignments.outsideByMember.get(item.connectionId);
  if (outsideId) {
    const groupId = row.groupId;
    assignments.rows.forEach((groupRow) => {
      if (groupRow.groupId !== groupId) return;
      ["left", "right"].forEach((memberSide) => {
        const member = groupRow[memberSide];
        if (member && assignments.outsideByMember.get(member.connectionId) === outsideId) {
          assignments.pools[memberSide].push(member.connectionId);
          groupRow[memberSide] = null;
        }
      });
    });
    assignments.rows = assignments.rows.filter((groupRow) => groupRow.left || groupRow.right);
    const sources = assignments.groupSources.get(groupId);
    sources?.delete(outsideId);
    if (groupId === outsideId && assignments.rows.some((groupRow) => groupRow.groupId === groupId)) {
      const replacement = [...sources].find((id) => assignments.existingIds.has(id))
        || `new:${++nextConnectionAssociationGroupId}`;
      assignments.rows.forEach((groupRow) => {
        if (groupRow.groupId === groupId) groupRow.groupId = replacement;
      });
      assignments.groupSources.set(replacement, sources);
    }
    if (groupId === outsideId) assignments.groupSources.delete(groupId);
    return;
  }
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
  const sources = new Set([
    ...(assignments.groupSources.get(source.groupId) || []),
    ...(assignments.groupSources.get(target.groupId) || []),
  ]);
  assignments.groupSources.delete(source.groupId);
  assignments.groupSources.delete(target.groupId);
  assignments.groupSources.set(groupId, sources);
  targetRows.forEach((row) => { row.groupId = groupId; });
  moving.forEach((row) => { row.groupId = groupId; });
  assignments.rows.splice(insertIndex, 0, ...moving);
}

/** Build one draggable terminal-connection card for an association pool or row. */
function renderConnectionAssociationCard(item, elsewhere, showContextMenu, contextItems) {
  const card = document.createElement("div");
  const name = document.createElement("strong");
  const owner = document.createElement("small");
  card.className = "relationship-end-entry create-cables-end-card create-association-card";
  card.dataset.attachmentId = item.attachmentId;
  card.setAttribute("role", "listitem");
  name.textContent = item.label;
  owner.textContent = elsewhere ? `${item.connectionName} · Associated elsewhere` : item.connectionName;
  card.append(name, owner);
  if (elsewhere) {
    card.title = "Drag to bring this connection and its existing association into the center.";
  } else card.title = `${item.label} · Drag to create or change an association`;
  card.addEventListener("contextmenu", (event) => {
    event.stopPropagation();
    showContextMenu(event, contextItems(item));
  });
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
  const associations = [...grouped].filter(([groupId, group]) => {
    const sources = assignments.groupSources.get(groupId) || new Set();
    sources.forEach((sourceId) => {
      (assignments.associationMembers.get(sourceId) || []).forEach((memberId) => {
        if (!assignments.selectedIds.has(memberId)) group.attachmentIds.push(memberId);
      });
    });
    group.attachmentIds = [...new Set(group.attachmentIds)];
    return group.attachmentIds.length >= 2 &&
      ((group.left && group.right) || sources.size > 0);
  })
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
  const showContextMenu = addContextMenu(dialog);
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
  const pools = { left: leftPool, right: rightPool };
  const cardContextItems = (item) => [{
    label: "Details", disabled: true, title: "Connection details are coming soon",
  }, {
    label: "Rename",
    action: () => {
      const connection = harness.connections.find(
        (candidate) => candidate.connectionId === item.connectionId,
      );
      const attachment = (connection?.attachments || []).find(
        (candidate) => candidate.attachmentId === item.attachmentId,
      );
      if (!attachment) {
        appendNotice("This connection is no longer available.", true);
        return;
      }
      renameCableGroupAttachment(harness, { ...attachment, connectionId: item.connectionId },
        (name) => {
          item.label = name.trim() || attachment.name;
          attachment.nameOverride = name;
          if (name.trim()) attachment.name = item.label;
          renderConnectionAssociationAssignments(
            harness, assignments, groups, pools, centerContent, showContextMenu,
            cardContextItems,
          );
        });
    },
  }, {
    label: "Delete",
    action: async () => {
      appendNotice(`Deleting connection ${item.label}…`);
      try {
        const response = await send("remove_cable_end_attachment", {
          harnessId: harness.harnessId,
          connectionId: item.connectionId,
          attachmentId: item.attachmentId,
        });
        if (response.ok) dialog.close();
        else appendNotice(response.error || "Connection could not be deleted.", true);
      } catch (error) {
        appendNotice(error.message, true);
      }
    },
  }];
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
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (!openCableGroupDetailsState) return;
    const currentHarness = currentState.harnesses.find(
      (candidate) => candidate.harnessId === harness.harnessId,
    );
    if (currentHarness) {
      openCableGroupDetails(
        currentHarness,
        openCableGroupDetailsState.cableGroupId,
        openCableGroupDetailsState.connectionId,
      );
    }
  });
  document.body.append(dialog);
  dialog.showModal();
  renderConnectionAssociationAssignments(
    harness, assignments, groups, pools, centerContent,
    showContextMenu, cardContextItems,
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
function renderConnectionAssociationAssignments(
  harness, assignments, groups, pools, center, showContextMenu, cardContextItems,
) {
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
    const poolIds = assignments.pools[side];
    const poolGroupCounts = new Map();
    poolIds.forEach((id) => {
      const groupId = assignments.outsideByMember.get(id);
      if (groupId) poolGroupCounts.set(groupId, (poolGroupCounts.get(groupId) || 0) + 1);
    });
    poolIds.forEach((attachmentId, index) => {
      const item = groups[side].get(attachmentId);
      if (!item) return;
      const elsewhere = assignments.elsewhereIds.has(attachmentId);
      const card = renderConnectionAssociationCard(
        item, elsewhere, showContextMenu, cardContextItems,
      );
      const groupId = assignments.outsideByMember.get(attachmentId);
      if (poolGroupCounts.get(groupId) > 1) {
        card.dataset.grouped = "true";
        if (assignments.outsideByMember.get(poolIds[index - 1]) === groupId) {
          card.dataset.groupContinuation = "true";
        }
        if (assignments.outsideByMember.get(poolIds[index + 1]) === groupId) {
          card.dataset.groupContinues = "true";
        }
      }
      card.dataset.assignmentSide = side;
      card.dataset.assignmentLocation = "pool";
      surfaces.pools[side].cards.push(card);
      pools[side].list.append(card);
      enableCableCreationDrag(card, { location: "pool", side }, surfaces,
        (target) => handleConnectionAssociationDrop(
          assignments, side, null, target, attachmentId, pools, center, harness, groups,
          showContextMenu, cardContextItems,
        ), null, "association");
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
          const card = renderConnectionAssociationCard(
            item, false, showContextMenu, cardContextItems,
          );
          card.dataset.assignmentSide = side;
          card.dataset.assignmentLocation = "row";
          card.title = "Drag onto another association to combine groups; Option-drag to swap ends.";
          slot.append(card);
          enableCableCreationDrag(card, {
            location: "row", side, rowIndex: index, groupId: assignment.groupId,
          }, surfaces,
            (target) => handleConnectionAssociationDrop(
              assignments, side, index, target, attachmentId, pools, center, harness, groups,
              showContextMenu, cardContextItems,
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
  showContextMenu, cardContextItems,
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
  renderConnectionAssociationAssignments(
    harness, assignments, groups, pools, center, showContextMenu, cardContextItems,
  );
}
