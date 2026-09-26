/** Edit junction pathway relationships in their own popup. */
/* global openJunctionPopupId */
function openJunctionRelationships(harness, junction) {
  retainConfigurationPopupParent(harness);
  closePathwayPopup(true);
  closeCableEndRoutingPopup(true);
  closeCableGroupDetails();
  const prior = document.body.querySelector(".junction-relationships-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  openJunctionPopupId = junction.junctionId;
  const dialog = document.createElement("dialog");
  const content = document.createElement("div");
  const relationshipContent = document.createElement("div");
  const relationshipSequence = document.createElement("div");
  const occupancyContent = document.createElement("div");
  const occupancy = document.createElement("div");
  const add = document.createElement("button");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const pathways = new Map(
    harness.pathways.map((pathway) => [pathway.pathwayId, pathway]),
  );
  const existingRelationships = junction.pathwayRelationships || [];
  const memberGroups = relationshipJunctionGroups(harness, junction);
  const junctionName = junction.name || "Unnamed junction";
  dialog.className = "junction-relationships-popup";
  dialog.setAttribute("aria-label", `Junction configuration: ${junctionName}`);
  content.className = "section-content";
  relationshipContent.className = "section-content";
  relationshipSequence.className = "sequence";
  occupancyContent.className = "section-content";
  occupancy.className = "occupancy";
  existingRelationships.forEach((relationship) => {
    const pathway = pathways.get(relationship.pathwayId);
    const endpointLabel = relationship.endpoint === "start" ? "End A" : "End B";
    const childGroups = relationshipEndpointGroups(harness, junction, relationship);
    const row = memberRow(
      `${pathway?.name || "Missing pathway"} · ${endpointLabel}`,
      () => highlightMember(harness, "pathway_gates", relationship.pathwayId),
      [actionButton("×", `Remove ${endpointLabel} relationship`, () => {
        if (childGroups.length && !window.confirm(
          `${childGroups.length} ${childGroups.length === 1 ? "cable group traverses" : "cable groups traverse"} this relationship. Remove it?`,
        )) return;
        void mutate("remove_junction_relationship", {
          harnessId: harness.harnessId,
          junctionId: junction.junctionId,
          pathwayId: relationship.pathwayId,
          endpoint: relationship.endpoint,
        }, "Removing junction relationship…");
      }, false, true)],
      !pathway,
    );
    row.dataset.pathwayId = relationship.pathwayId;
    row.dataset.endpoint = relationship.endpoint;
    relationshipSequence.append(row);
  });
  if (!existingRelationships.length) {
    relationshipSequence.append(emptyMessage("No pathway relationships."));
  }
  add.type = "button";
  add.className = "button compact";
  add.textContent = "+ Add Relationship";
  add.addEventListener("click", () => addJunctionRelationship(junction.junctionId));
  relationshipContent.append(relationshipSequence, add);
  if (!memberGroups.length) {
    occupancy.append(emptyMessage("No cable groups traverse this junction."));
  }
  memberGroups.forEach((group) => {
    const row = memberRow(
      cableGroupLabel(harness, group),
      () => highlightMember(harness, "cable_group", group.cableGroupId),
    );
    row.dataset.cableGroupId = group.cableGroupId;
    occupancy.append(row);
  });
  occupancyContent.append(occupancy);
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  actions.className = "pathway-popup-actions";
  actions.append(close);
  dialog.addEventListener("close", () => {
    const isCurrent = document.body.querySelector(".junction-relationships-popup") === dialog;
    if (isCurrent) {
      openJunctionPopupId = "";
    }
    dialog.remove();
    if (isCurrent) restoreConfigurationPopupParent();
  });
  content.append(
    nameField(
      "Junction Name",
      junction.name,
      "rename_junction",
      { harnessId: harness.harnessId, junctionId: junction.junctionId },
      "Junction name",
      { showLabel: false },
    ),
    nestedSection(
      `junction:${junction.junctionId}:relationships`,
      "Pathway Relationships",
      `${existingRelationships.length}`,
      relationshipContent,
      () => highlightMember(harness, "junction", junction.junctionId),
    ),
    nestedSection(
      `junction:${junction.junctionId}:occupancy`,
      "Cable Group Occupancy",
      `${memberGroups.length}`,
      occupancyContent,
      () => highlightMember(harness, "junction", junction.junctionId),
    ),
  );
  const entry = nestedSection(
    `junction:${junction.junctionId}`,
    junctionName,
    `${existingRelationships.length} pathway ${existingRelationships.length === 1 ? "endpoint" : "endpoints"} · ${memberGroups.length} cable groups`,
    content,
    () => highlightMember(harness, "junction", junction.junctionId),
  );
  entry.open = true;
  entry.classList.add("pathway-popup-entry");
  dialog.append(entry, actions);
  document.body.append(dialog);
  dialog.showModal();
}

function closeJunctionRelationships(preserveParent = false) {
  const dialog = document.body.querySelector(".junction-relationships-popup");
  openJunctionPopupId = "";
  if (!preserveParent) configurationPopupParentState = null;
  dialog?.remove();
  if (dialog?.open) dialog.close();
}
