/** Dialog lifecycle and persistence controller for wire creation. */

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

/** Commit every staged Route Editor change through one host transaction. */
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
  appendNotice("Saving Route Editor changes…");
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
      appendNotice(response.error || "Route Editor changes could not be saved.", true);
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
  heading.textContent = "Route Editor";
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

