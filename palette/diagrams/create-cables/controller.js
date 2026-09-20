/** Dialog lifecycle and persistence controller for cable creation. */

function removeCreateCablesPopup(preserveState) {
  if (cancelActiveCableCreationSelection) cancelActiveCableCreationSelection();
  const dialog = document.body.querySelector(".create-cables-popup");
  if (preserveState && dialog && openCreateCablesPopupState) {
    openCreateCablesPopupState.scrollPositions = Array.from(
      dialog.querySelectorAll(".create-cables-column"),
    ).map((column) => column.scrollTop || 0);
    dialog.remove();
    return;
  }
  if (!preserveState) openCreateCablesPopupState = null;
  if (dialog?.open) dialog.close();
  else dialog?.remove();
}

/** Close the cable-creation workspace and clear its restoration state. */
function closeCreateCablesPopup() {
  removeCreateCablesPopup(false);
}

/** Temporarily remove the popup while the selected harness is rerendered. */
function suspendCreateCablesPopup() {
  removeCreateCablesPopup(true);
}

/** Commit every staged Route Editor change through one host transaction. */
async function saveCableCreationAssignments(harness, boundaries, assignments, saveButton) {
  const pairings = cableCreationCompletePairings(assignments);
  const deletedConnectionIds = Object.keys(assignments.deletedConnectionIds);
  const deleted = new Set(deletedConnectionIds);
  const detachedConnectionIds = cableCreationDetachedConnectionIds(
    assignments, pairings, deleted,
  );
  const renames = Object.entries(assignments.renames)
    .filter(([connectionId]) => !deleted.has(connectionId))
    .map(([connectionId, name]) => ({ connectionId, name }));
  saveButton.disabled = true;
  appendNotice("Saving Route Editor changes…");
  try {
    const response = await send("save_cable_editor", {
      harnessId: harness.harnessId,
      leftBoundary: cableCreationBoundaryState(boundaries.left),
      rightBoundary: cableCreationBoundaryState(boundaries.right),
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
    closeCreateCablesPopup();
  } catch (error) {
    appendNotice(error.message, true);
    saveButton.disabled = false;
  }
}

/** Open the three-column workspace for two selected boundaries. */
function openCreateCablesPopup(
  harness, left, right, scrollPositions = [0, 0, 0], restoredAssignments = null,
) {
  closePathwayPopup();
  closeJunctionRelationships();
  closeCreateCablesPopup();
  const dialog = document.createElement("dialog");
  const heading = document.createElement("h2");
  const layout = document.createElement("div");
  const center = document.createElement("section");
  const centerHeading = document.createElement("h3");
  const centerContent = document.createElement("div");
  const actions = document.createElement("div");
  const cancel = document.createElement("button");
  const save = document.createElement("button");
  const groups = cableCreationDisconnectedGroups(harness, left, right);
  const assignments = reconcileCableCreationAssignments(restoredAssignments, groups);
  const leftPool = createCableCreationEndPool(left);
  const rightPool = createCableCreationEndPool(right);
  dialog.className = "create-cables-popup";
  dialog.setAttribute("aria-labelledby", "create-cables-title");
  const showContextMenu = addContextMenu(dialog);
  openCreateCablesPopupState = {
    harnessKey: harnessKey(harness),
    left: cableCreationBoundaryState(left),
    right: cableCreationBoundaryState(right),
    scrollPositions: [...scrollPositions],
    assignments,
  };
  heading.id = "create-cables-title";
  heading.textContent = "Route Editor";
  layout.className = "create-cables-layout";
  center.className = "create-cables-column create-cables-assignment-pool";
  centerHeading.textContent = "Cable Assignments";
  centerContent.className = "create-cables-assignment-content";
  centerContent.setAttribute("aria-label", "Visual cable assignments");
  center.append(centerHeading, centerContent);
  layout.append(
    leftPool.column,
    center,
    rightPool.column,
  );
  renderCableCreationAssignments(
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
  cancel.addEventListener("click", closeCreateCablesPopup);
  save.type = "button";
  save.className = "button";
  save.textContent = "Save";
  save.addEventListener("click", () => saveCableCreationAssignments(
    harness, { left, right }, assignments, save,
  ));
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeCreateCablesPopup();
  });
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".create-cables-popup") === dialog) {
      openCreateCablesPopupState = null;
    }
    dialog.remove();
  });
  actions.append(cancel, save);
  dialog.append(heading, layout, actions);
  document.body.append(dialog);
  dialog.showModal();
  window.requestAnimationFrame(() => {
    Array.from(dialog.querySelectorAll(".create-cables-column")).forEach((column, index) => {
      column.scrollTop = scrollPositions[index] || 0;
    });
  });
  save.focus();
}

/** Restore an open popup after refreshed harness state has rebuilt the editor. */
function restoreCreateCablesPopup(harness) {
  const state = openCreateCablesPopupState;
  if (!state) return;
  if (state.harnessKey !== harnessKey(harness)) {
    closeCreateCablesPopup();
    return;
  }
  const left = resolveCableCreationBoundary(harness, state.left);
  const right = resolveCableCreationBoundary(harness, state.right);
  if (!left || !right) {
    closeCreateCablesPopup();
    return;
  }
  openCreateCablesPopup(
    harness, left, right, state.scrollPositions, state.assignments,
  );
}

/** Own the transient first/second-boundary selection mode for one diagram render. */
function createCableCreationController(harness, container) {
  const boundaries = new Map();
  let source = null;
  let eligibleKeys = new Set();

  const applyClasses = () => {
    container.classList.add("cable-creation-selecting");
    boundaries.forEach((boundary, key) => {
      boundary.summary.classList.remove(
        "cable-creation-source", "cable-creation-target", "cable-creation-unavailable",
      );
      boundary.summary.classList.add(
        key === source.key
          ? "cable-creation-source"
          : eligibleKeys.has(key) ? "cable-creation-target" : "cable-creation-unavailable",
      );
    });
  };
  const boundaryForTarget = (target) => [...boundaries.values()].find(
    (boundary) => boundary.summary.contains(target),
  );
  const cancel = () => {
    source = null;
    eligibleKeys = new Set();
    container.classList.remove("cable-creation-selecting");
    boundaries.forEach((boundary) => boundary.summary.classList.remove(
      "cable-creation-source", "cable-creation-target", "cable-creation-unavailable",
    ));
    document.removeEventListener("click", handleDocumentClick, true);
    document.removeEventListener("keydown", handleDocumentKeyDown, true);
    if (cancelActiveCableCreationSelection === cancel) {
      cancelActiveCableCreationSelection = null;
    }
  };
  const choose = (boundary, event) => {
    event.preventDefault();
    event.stopPropagation();
    const left = source;
    cancel();
    openCreateCablesPopup(harness, left, boundary);
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
    if (cancelActiveCableCreationSelection) cancelActiveCableCreationSelection();
    cancel();
    source = boundary;
    const reachable = cableCreationReachableBoundaries(harness, source.key);
    eligibleKeys = new Set([...reachable].filter((key) => boundaries.get(key)?.groups.length));
    applyClasses();
    document.addEventListener("click", handleDocumentClick, true);
    document.addEventListener("keydown", handleDocumentKeyDown, true);
    cancelActiveCableCreationSelection = cancel;
  };
  const bind = (pathway, endpoint, groups, summary) => {
    const key = cableCreationBoundaryKey(pathway.pathwayId, endpoint);
    const boundary = { key, pathway, endpoint, groups, summary };
    boundaries.set(key, boundary);
    return boundary;
  };
  return { begin, bind, cancel };
}

