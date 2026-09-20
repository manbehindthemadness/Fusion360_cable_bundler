function renderEditor(harness) {
  suspendCreateCablesPopup();
  resetMasterDiagramSizing();
  ui.editor.replaceChildren();
  clearValidationDisplay();

  if (harness.status === "damaged") {
    closeCreateCablesPopup();
    closePathwayPopup();
    closeJunctionRelationships();
    closeCableGroupDetails();
    const error = document.createElement("div");
    const actions = document.createElement("div");
    const remove = document.createElement("button");
    error.className = "error-panel";
    error.textContent = harness.error || "The stored definition could not be loaded.";
    actions.className = "damaged-harness-actions";
    remove.type = "button";
    remove.className = "button danger";
    remove.textContent = "Delete damaged harness";
    remove.disabled = !harness.deletionToken;
    remove.title = harness.deletionToken
      ? "Delete this damaged harness component"
      : "Refresh to locate this damaged harness component";
    remove.addEventListener("click", () => {
      if (!window.confirm(
        `Delete damaged harness “${harness.componentName}”? This removes its Fusion component and everything inside it.`,
      )) return;
      void mutate(
        "delete_damaged_harness",
        { deletionToken: harness.deletionToken },
        `Deleting damaged harness ${harness.componentName}…`,
      );
    });
    actions.append(remove);
    ui.editor.append(error, actions);
    return;
  }

  const validation = document.createElement("div");
  validation.className = "section-content";
  if (harness.validationMessages.length) {
    const list = document.createElement("ul");
    list.className = "validation-list errors";
    harness.validationMessages.forEach((message) => {
      const item = document.createElement("li");
      item.textContent = String(message);
      list.append(item);
    });
    validation.append(list);
  } else {
    validation.append(emptyMessage("No logical validation findings."));
  }
  const findingCount = harness.validationMessages.length;
  ui.validationOutput.replaceChildren(...validation.children);
  ui.validationOutput.hidden = false;
  ui.validationEventsStatus.textContent = findingCount
    ? `${findingCount} ${findingCount === 1 ? "finding" : "findings"}`
    : "Clear";

  const relationshipMap = renderRelationshipMap(harness);
  const masterSection = editorSection(
    "master-relationship-graphic",
    "Master Relationship Graphic",
    `${harness.pathways.length} pathways`,
    relationshipMap,
    true,
  );
  ui.editor.append(masterSection);
  observeMasterDiagramSize(masterSection, relationshipMap);
  if (openPathwayPopupId) openPathwayPopup(harness, openPathwayPopupId);
  if (openJunctionPopupId) {
    const junction = (harness.junctions || []).find(
      (candidate) => candidate.junctionId === openJunctionPopupId,
    );
    if (junction) openJunctionRelationships(harness, junction);
    else closeJunctionRelationships();
  }
  const materialOptions = document.body.querySelector(".material-options");
  // Keep the foreground material editor above its originating details dialog during refresh.
  if (openCableGroupDetailsState && !materialOptions?.open) {
    openCableGroupDetails(
      harness,
      openCableGroupDetailsState.cableGroupId,
      openCableGroupDetailsState.connectionId,
    );
  }
  restoreCreateCablesPopup(harness);
}

function clearValidationDisplay() {
  ui.validationOutput.replaceChildren();
  ui.validationOutput.hidden = true;
  ui.validationEventsStatus.textContent = "";
}

function resetMasterDiagramSizing() {
  masterDiagramResizeObserver?.disconnect();
  masterDiagramResizeObserver = null;
}

function observeMasterDiagramSize(section, relationshipMap) {
  let initialFitPending = relationshipMap.dataset.hasSavedDiagramView !== "true";
  const resize = () => {
    if (!section.open) return;
    const summaryHeight = section.children[0]?.getBoundingClientRect().height || 0;
    const availableHeight = Math.floor(section.clientHeight - summaryHeight);
    if (availableHeight <= 0) return;
    relationshipMap.style.height = `${availableHeight}px`;
    if (!initialFitPending) return;
    initialFitPending = false;
    window.requestAnimationFrame(() => relationshipMap.fitDiagram());
  };
  section.addEventListener("toggle", () => window.requestAnimationFrame(resize));
  if (typeof window.ResizeObserver === "function") {
    masterDiagramResizeObserver = new window.ResizeObserver(resize);
    masterDiagramResizeObserver.observe(section);
  }
  window.requestAnimationFrame(resize);
}
