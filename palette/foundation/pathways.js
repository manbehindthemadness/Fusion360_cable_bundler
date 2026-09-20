/** Pathway list rendering and pathway-configuration dialog lifecycle. */

function renderPathways(harness, selectedPathwayId = null) {
  const container = document.createElement("div");
  const controls = new Map(
    harness.controls.map((control) => [control.controlId, control]),
  );
  container.className = "section-content";
  if (!harness.pathways.length) {
    container.append(emptyMessage("No pathways defined yet."));
    return container;
  }
  const renderedPathways = harness.pathways.filter(
    (pathway) => !selectedPathwayId || pathway.pathwayId === selectedPathwayId,
  );
  renderedPathways.forEach((pathway) => {
    const pathwayContent = document.createElement("div");
    const gateContent = document.createElement("div");
    const sequence = document.createElement("div");
    const occupancyContent = document.createElement("div");
    const occupancy = document.createElement("div");
    const addGates = document.createElement("button");
    const addRefine = document.createElement("button");
    const members = relationshipPathwayGroups(harness, pathway.pathwayId);
    pathwayContent.className = "section-content";
    gateContent.className = "section-content";
    sequence.className = "sequence";
    const relatedEndpoints = new Set(
      [
        ...(harness.junctions || []).flatMap(
          (junction) => junction.pathwayRelationships || [],
        ),
        ...(harness.standaloneEnds || []),
      ]
        .filter((relationship) => relationship.pathwayId === pathway.pathwayId)
        .map((relationship) => relationship.endpoint),
    );
    const lockedIndexes = new Set();
    if (pathway.orderedControlIds.length && relatedEndpoints.has("start")) lockedIndexes.add(0);
    if (pathway.orderedControlIds.length && relatedEndpoints.has("end")) {
      lockedIndexes.add(pathway.orderedControlIds.length - 1);
    }
    const gateRows = [];
    pathway.orderedControlIds.forEach((controlId, index) => {
      const control = controls.get(controlId);
      const isRefine = control?.kind === "refine";
      const isLocked = lockedIndexes.has(index);
      const openOptions = () => openInterpolationOptions(
        harness, "gate", controlId, control?.name || "Gate", control?.interpolation,
        control?.usesDefaults ?? true,
      );
      const editControl = isRefine
        ? () => editPathwayRefine(harness, control)
        : openOptions;
      const movePayload = { harnessId: harness.harnessId, pathwayId: pathway.pathwayId, controlId };
      const row = memberRow(
        `${control?.name || "Missing gate"} #${controlId.slice(0, 8)}`,
        () => highlightMember(harness, "control", controlId),
        [
          optionsButton(
            isRefine ? "Move, rotate, or resize refine point" : "Gate interpolation options",
            editControl,
            !control,
          ),
          actionButton("×", "Remove gate", () => removeGate(
            harness, pathway, controlId, control?.name || "this gate",
          ), pathway.orderedControlIds.length === 1 || isLocked, true),
        ],
        !control || !control.hasLinkedGeometry,
      );
      row.children[0].title = isLocked
        ? `Click for ${control?.kind === "refine" ? "refine" : "gate"} options; pathway endpoint is locked`
        : `Click for ${control?.kind === "refine" ? "refine" : "gate"} options; drag to reorder`;
      row.children[0].addEventListener("click", (event) => {
        if (event.detail === 0 && control) void editControl();
      });
      row.title = isLocked
        ? `${control?.name || "Gate"} is preserved by a junction or standalone end attachment`
        : `Drag to reorder ${control?.name || "gate"} (${controlId})`;
      enableSequenceDrag(sequence, gateRows, row, index, (target) => mutate(
        "move_pathway_gate", { ...movePayload, offset: target - index }, "Reordering gate…",
      ), control ? editControl : null, isLocked, lockedIndexes);
      sequence.append(row);
    });
    occupancyContent.className = "section-content";
    occupancy.className = "occupancy";
    if (!members.length) {
      occupancy.append(emptyMessage("No cable groups traverse this pathway."));
    }
    members.forEach((group) => {
      occupancy.append(memberRow(
        cableGroupLabel(harness, group),
        () => highlightMember(harness, "cable_group", group.cableGroupId),
      ));
    });
    addGates.type = "button";
    addGates.className = "button compact";
    addGates.textContent = "+ Add Gates";
    const hasInteriorInsertion = !(
      pathway.orderedControlIds.length === 1
      && relatedEndpoints.has("start")
      && relatedEndpoints.has("end")
    );
    addGates.disabled = !hasInteriorInsertion;
    addGates.title = hasInteriorInsertion
      ? ""
      : "Detach one junction endpoint before adding controls";
    addGates.addEventListener("click", () => appendPathwayGates(harness, pathway));
    addRefine.type = "button";
    addRefine.className = "button compact";
    addRefine.textContent = "+ Add Refine Point";
    addRefine.disabled = !hasInteriorInsertion;
    addRefine.title = addGates.title;
    addRefine.addEventListener("click", () => addPathwayRefine(harness, pathway));
    const namePayload = { harnessId: harness.harnessId, pathwayId: pathway.pathwayId };
    gateContent.append(
      nameField("Start Name", pathway.startName, "rename_pathway", {
        ...namePayload, field: "start_name",
      }),
      sequence,
      nameField("End Name", pathway.endName, "rename_pathway", {
        ...namePayload, field: "end_name",
      }),
      addGates,
      addRefine,
    );
    occupancyContent.append(occupancy);
    pathwayContent.append(
      nameField("", pathway.name, "rename_pathway", {
        ...namePayload, field: "name",
      }),
      nestedSection(
        `pathway:${pathway.pathwayId}:gates`,
        "Routing Controls · Traversal Order",
        `${pathway.orderedControlIds.length}`,
        gateContent,
        () => highlightMember(harness, "pathway_gates", pathway.pathwayId),
      ),
      nestedSection(
        `pathway:${pathway.pathwayId}:occupancy`,
        "Cable Group Occupancy",
        `${members.length}`,
        occupancyContent,
        () => highlightMember(harness, "pathway", pathway.pathwayId),
      ),
    );
    container.append(nestedSection(
      `pathway:${pathway.pathwayId}`,
      pathway.name,
      `${pathwayDirection(pathway)} · ${members.length} cable groups`,
      pathwayContent,
      () => highlightMember(harness, "pathway", pathway.pathwayId),
    ));
  });
  return container;
}

function closePathwayPopup(preserveParent = false) {
  const dialog = document.body.querySelector(".pathway-popup");
  openPathwayPopupId = "";
  if (!preserveParent) configurationPopupParentState = null;
  dialog?.remove();
  if (dialog?.open) dialog.close();
}

/** Retain Cable Details as the parent of a pathway or junction configuration popup. */
function retainConfigurationPopupParent(harness) {
  const replacingConfiguration = document.body.querySelector(".pathway-popup")
    || document.body.querySelector(".junction-relationships-popup");
  if (openCableGroupDetailsState) {
    configurationPopupParentState = { harness, ...openCableGroupDetailsState };
  } else if (replacingConfiguration && configurationPopupParentState) {
    configurationPopupParentState.harness = harness;
  } else if (!replacingConfiguration) {
    configurationPopupParentState = null;
  }
}

/** Reopen the immediate Cable Details parent after its child configuration closes. */
function restoreConfigurationPopupParent() {
  const parent = configurationPopupParentState;
  configurationPopupParentState = null;
  if (!parent) return;
  openCableGroupDetails(parent.harness, parent.cableGroupId, parent.connectionId);
}

function openPathwayPopup(harness, pathwayId) {
  retainConfigurationPopupParent(harness);
  closeJunctionRelationships(true);
  closeCableGroupDetails();
  const pathway = harness.pathways.find((candidate) => candidate.pathwayId === pathwayId);
  const existing = document.body.querySelector(".pathway-popup");
  if (existing) {
    existing.remove();
    if (existing.open) existing.close();
  }
  if (!pathway) {
    openPathwayPopupId = "";
    restoreConfigurationPopupParent();
    return;
  }
  openPathwayPopupId = pathwayId;
  const dialog = document.createElement("dialog");
  const rendered = renderPathways(harness, pathwayId);
  const entry = rendered.children[0];
  const actions = document.createElement("div");
  const close = document.createElement("button");
  dialog.className = "pathway-popup";
  dialog.setAttribute("aria-label", `Pathway configuration: ${pathway.name}`);
  entry.open = true;
  entry.classList.add("pathway-popup-entry");
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    const isCurrent = document.body.querySelector(".pathway-popup") === dialog;
    if (isCurrent) {
      openPathwayPopupId = "";
    }
    dialog.remove();
    if (isCurrent) restoreConfigurationPopupParent();
  });
  actions.append(close);
  dialog.append(entry, actions);
  document.body.append(dialog);
  dialog.showModal();
}

