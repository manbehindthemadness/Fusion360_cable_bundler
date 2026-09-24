/** Manage cable-details member actions and the refresh-stable modal dialog. */
/* global beginCableGroupAttachmentAssociation, cancelActiveConnectionAssociationSelection, connectionAssociationCandidates, openCableGroupDetailsState */

/** Open a small modal editor for one diagram-only connection node name. */
function renameCableGroupAttachment(harness, attachment) {
  const dialog = document.createElement("dialog");
  const form = document.createElement("form");
  const field = document.createElement("label");
  const input = document.createElement("input");
  const actions = document.createElement("div");
  const cancel = document.createElement("button");
  const save = document.createElement("button");
  dialog.className = "connection-name-popup";
  form.method = "dialog";
  field.textContent = "Connection Name";
  input.type = "text";
  input.className = "filter";
  input.value = attachment.nameOverride || "";
  input.placeholder = attachment.name || "Inherited target name";
  input.setAttribute("aria-label", "Connection name");
  actions.className = "pathway-popup-actions";
  cancel.type = "button";
  cancel.className = "button secondary";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => dialog.close());
  save.type = "submit";
  save.className = "button";
  save.textContent = "Save";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    dialog.close();
    void mutate("rename_cable_end_attachment", {
      harnessId: harness.harnessId,
      connectionId: attachment.connectionId,
      attachmentId: attachment.attachmentId,
      name: input.value,
    }, "Saving connection name…");
  });
  dialog.addEventListener("close", () => dialog.remove());
  field.append(input);
  actions.append(cancel, save);
  form.append(field, actions);
  dialog.append(form);
  document.body.append(dialog);
  dialog.showModal();
  input.focus();
  input.select();
}

/** Return Cable Details actions for attaching one physical cable end. */
function cableGroupDetailsEndContextItems(harness, connection) {
  const anchor = { connectionId: connection.connectionId, attachmentId: null };
  return [
    {
      label: "Associate",
      action: () => beginCableGroupAttachmentAssociation(harness, anchor),
      disabled: connectionAssociationCandidates(harness, anchor).length === 0,
      title: "Select another connection hierarchy to associate its terminal nodes",
    },
    ...endRoutingContextItems(harness, connection.connectionId),
  ];
}

/** Return actions for one diagram-only connection node. */
function cableGroupAttachmentContextItems(harness, group, attachment) {
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === attachment.connectionId,
  );
  const canAddConnection = attachment.connected && attachment.targetKind === "profile";
  const hasChildren = (connection?.attachments || []).some(
    (candidate) => candidate.parentAttachmentId === attachment.attachmentId,
  );
  const materials = connection
    ? cableEndAttachmentMaterials(group, connection, attachment) : group.materials;
  const hasShielding = typeof materials?.shielding === "string"
    && materials.shielding.trim() !== "";
  const hasShieldingConnection = !hasChildren && hasShielding;
  const hasMainRelationship = attachment.targetKind !== null
    && attachment.targetKind !== undefined;
  const hasShieldingRelationship = attachment.shieldingTarget !== null
    && attachment.shieldingTarget !== undefined;
  const mainConnect = {
    label: "Main",
    action: () => connectCableEnd(
      harness, attachment.connectionId, attachment.attachmentId, "main",
    ),
    disabled: attachment.connected,
    title: attachment.connected ? "This connection already has a main target" : "",
  };
  return [
    {
      label: "Associate",
      action: () => beginCableGroupAttachmentAssociation(harness, {
        connectionId: attachment.connectionId,
        attachmentId: attachment.attachmentId,
      }),
      disabled: connectionAssociationCandidates(harness, {
        connectionId: attachment.connectionId,
        attachmentId: attachment.attachmentId,
      }).length === 0,
      title: "Select another connection hierarchy to associate its terminal nodes",
    },
    hasShieldingConnection ? {
      label: "Connect",
      items: [
        mainConnect,
        {
          label: "Shielding",
          action: () => connectCableEnd(
            harness, attachment.connectionId, attachment.attachmentId, "shielding",
          ),
          disabled: attachment.shieldingTarget?.connected === true,
          title: attachment.shieldingTarget?.connected
            ? "This connection already has a shielding target" : "",
        },
      ],
    } : {
      label: "Connect",
      action: () => connectCableEnd(
        harness, attachment.connectionId, attachment.attachmentId, "main",
      ),
      disabled: attachment.connected,
      title: attachment.connected ? "This connection already has a target" : "",
    },
    {
      label: "Disconnect",
      items: [
        {
          label: "Main",
          action: () => mutate("disconnect_cable_end_relationship", {
            harnessId: harness.harnessId,
            connectionId: attachment.connectionId,
            attachmentId: attachment.attachmentId,
            relationship: "main",
          }, "Disconnecting main relationship…"),
          disabled: !hasMainRelationship || hasChildren,
          title: hasChildren
            ? "Disconnect child connection nodes before their parent profile"
            : (!hasMainRelationship ? "This connection has no main relationship" : ""),
        },
        ...((hasShielding || hasShieldingRelationship) ? [{
          label: "Shielding",
          action: () => mutate("disconnect_cable_end_relationship", {
            harnessId: harness.harnessId,
            connectionId: attachment.connectionId,
            attachmentId: attachment.attachmentId,
            relationship: "shielding",
          }, "Disconnecting shielding relationship…"),
          disabled: !hasShieldingRelationship,
          title: hasShieldingRelationship
            ? "" : "This connection has no shielding relationship",
        }] : []),
      ],
    },
    {
      label: "Add",
      items: [
        {
          label: "Connection",
          action: () => addCableEndConnection(
            harness, attachment.connectionId, attachment.attachmentId,
          ),
          disabled: !canAddConnection,
          title: canAddConnection
            ? ""
            : "Requires this connection to be attached to a sketch profile",
        },
        ...(attachment.connected ? [{
          label: "Refine",
          action: () => addConnectionRefine(
            harness, attachment.connectionId, attachment.attachmentId,
          ),
        }] : []),
      ],
    },
    {
      label: "Rename",
      action: () => renameCableGroupAttachment(harness, attachment),
    },
    {
      label: "Materials",
      action: () => openMaterialOptions(harness, group, attachment),
    },
    {
      label: "Delete",
      action: () => mutate("remove_cable_end_attachment", {
        harnessId: harness.harnessId,
        connectionId: attachment.connectionId,
        attachmentId: attachment.attachmentId,
      }, `Deleting connection ${attachment.name}…`),
    },
    {
      label: "Properties",
      action: () => openCableEndAttachmentProperties(harness, group, attachment),
    },
  ];
}

/** Render the physical member list for one cable group. */
function renderCableGroupDetailsMembers(
  harness, group, focusedConnectionId, onSelect, showContextMenu,
) {
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  const pathways = new Map(
    harness.pathways.map((pathway) => [pathway.pathwayId, pathway]),
  );
  const locations = cableGroupEndLocations(harness);
  const members = document.createElement("div");
  members.className = "occupancy";
  group.connectionIds.forEach((connectionId) => {
    const connection = connections.get(connectionId);
    const location = locations.get(connectionId);
    const pathway = pathways.get(location?.pathwayId);
    const side = location?.endpoint === "start" ? "End A" : "End B";
    const boundary = location
      ? `${pathway?.name || "Missing pathway"} · ${side}`
      : "Unlocated end";
    const row = memberRow(
      `${connection?.name || "Missing end"} · ${boundary} · ${
        connection?.attachment ? "Attached" : "Detached"
      }`,
      () => highlightMember(harness, "connection", connectionId),
      [],
      !connection || !location,
    );
    row.classList.add("cable-group-details-member");
    row.dataset.connectionId = `${connectionId}`;
    const reference = row.querySelector(".member-reference");
    const isFocused = connectionId === focusedConnectionId;
    reference.title = `Start diagram from ${connection?.name || "this assigned end"}`;
    reference.setAttribute("aria-label", reference.title);
    reference.setAttribute("aria-pressed", isFocused ? "true" : "false");
    reference.addEventListener("click", () => onSelect(connectionId));
    row.addEventListener("contextmenu", (event) => {
      event.stopPropagation();
      showContextMenu(event, cableGroupDetailsEndContextItems(harness, connection));
    });
    if (isFocused) row.classList.add("focused");
    members.append(row);
  });
  return members;
}

/** Move the selected styling within an existing Assigned Ends list. */
function focusCableGroupDetailsMember(members, connectionId) {
  members.querySelectorAll(".cable-group-details-member").forEach((row) => {
    const isFocused = row.dataset.connectionId === connectionId;
    row.classList[isFocused ? "add" : "remove"]("focused");
    row.querySelector(".member-reference").setAttribute(
      "aria-pressed", isFocused ? "true" : "false",
    );
  });
}

/** Close the active cable-group details dialog and clear its refresh state. */
function closeCableGroupDetails() {
  if (cancelActiveConnectionAssociationSelection) {
    cancelActiveConnectionAssociationSelection();
  }
  const dialog = document.body.querySelector(".cable-group-details-popup");
  openCableGroupDetailsState = null;
  if (dialog?.open) dialog.close();
  else dialog?.remove();
}

/** Return whether a Cable Details context-menu event belongs to an interactive child. */
function cableGroupDetailsContextTargetIsInteractive(target, dialog) {
  const interactiveTags = new Set([
    "button", "input", "select", "textarea", "a", "summary", "label",
    "h1", "h2", "h3", "p", "strong", "small", "text", "path", "rect",
  ]);
  let current = target;
  while (current && current !== dialog) {
    const classes = typeof current.className === "string" ? current.className.split(" ") : [];
    const tag = `${current.tagName || current.tag || ""}`.toLocaleLowerCase();
    if (interactiveTags.has(tag)
      || classes.some((name) => [
        "cable-group-details-node",
        "cable-group-details-member",
        "relationship-map-context-menu",
      ].includes(name))) return true;
    current = current.parentElement;
  }
  return false;
}

/** Open one refresh-stable route-and-member dialog for a connected cable group. */
function openCableGroupDetails(
  harness, cableGroupId, connectionId, options = {},
) {
  if (cancelActiveConnectionAssociationSelection) {
    cancelActiveConnectionAssociationSelection();
  }
  closePathwayPopup();
  closeJunctionRelationships();
  closeCableEndRoutingPopup();
  if (!options.preserveCreateCablesPopup) closeCreateCablesPopup();
  const prior = document.body.querySelector(".cable-group-details-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  const group = (harness.cableGroups || []).find(
    (candidate) => candidate.cableGroupId === cableGroupId,
  );
  if (!group || !group.connectionIds.includes(connectionId)) {
    openCableGroupDetailsState = null;
    return;
  }
  openCableGroupDetailsState = { cableGroupId, connectionId };
  const dialog = document.createElement("dialog");
  const content = document.createElement("div");
  const heading = document.createElement("div");
  const titleRow = document.createElement("div");
  const title = document.createElement("h2");
  const rename = document.createElement("button");
  const summary = document.createElement("p");
  const memberHeading = document.createElement("h3");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  let focusedConnectionId = connectionId;
  let graphicWorkspace = null;
  let members = null;
  dialog.className = "cable-group-details-popup";
  dialog.setAttribute("aria-label", "Cable details");
  content.className = "cable-group-details-content";
  const showContextMenu = addContextMenu(dialog, dialog);
  dialog.addEventListener("contextmenu", (event) => {
    if (cableGroupDetailsContextTargetIsInteractive(event.target, dialog)) return;
    showContextMenu(event, [
      { label: "Materials", action: () => openMaterialOptions(harness, group) },
      { label: "Properties", action: () => openCableGroupProperties(harness, group) },
    ]);
  });
  heading.className = "cable-group-details-heading";
  titleRow.className = "cable-group-details-title";
  title.textContent = cableGroupLabel(harness, group);
  rename.type = "button";
  rename.className = "button secondary cable-group-details-rename";
  rename.textContent = "Rename";
  rename.addEventListener("click", () => beginInlineNameEdit(titleRow, title, rename, {
    value: group.name || title.textContent,
    placeholder: cableGroupLabel(harness, { ...group, name: "" }),
    ariaLabel: "Cable group name",
    onSave: (value) => mutate("rename_cable_group", {
      harnessId: harness.harnessId,
      cableGroupId: group.cableGroupId,
      name: value,
    }, "Saving cable-group name…"),
  }));
  titleRow.append(title, rename);
  summary.textContent = `${group.connectionIds.length} assigned ${
    group.connectionIds.length === 1 ? "end" : "ends"
  }`;
  heading.append(titleRow, summary);
  content.append(heading);
  if (harness.cableGroupRouteError) {
    const error = document.createElement("div");
    error.className = "cable-group-route-error";
    error.textContent = `Route graphic unavailable: ${harness.cableGroupRouteError}`;
    content.append(error);
  } else {
    graphicWorkspace = renderCableGroupDetailsGraphic(
      harness, group, focusedConnectionId, showContextMenu,
    );
    content.append(graphicWorkspace.root);
  }
  memberHeading.textContent = "Assigned Ends";
  const selectConnection = (selectedConnectionId) => {
    if (selectedConnectionId === focusedConnectionId
      || !group.connectionIds.includes(selectedConnectionId)) return;
    focusedConnectionId = selectedConnectionId;
    openCableGroupDetailsState = { cableGroupId, connectionId: selectedConnectionId };
    focusCableGroupDetailsMember(members, selectedConnectionId);
    if (harness.cableGroupRouteError || !graphicWorkspace) return;
    const replacement = renderCableGroupDetailsGraphic(
      harness, group, selectedConnectionId, showContextMenu,
    );
    graphicWorkspace.root.parentElement.insertBefore(replacement.root, graphicWorkspace.root);
    graphicWorkspace.root.remove();
    graphicWorkspace = replacement;
    window.requestAnimationFrame(() => graphicWorkspace.fit());
  };
  members = renderCableGroupDetailsMembers(
    harness, group, focusedConnectionId, selectConnection, showContextMenu,
  );
  content.append(memberHeading, members);
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", closeCableGroupDetails);
  actions.append(close);
  dialog.addEventListener("close", () => {
    if (document.body.querySelector(".cable-group-details-popup") === dialog) {
      openCableGroupDetailsState = null;
    }
    dialog.remove();
  });
  dialog.append(content, actions);
  document.body.append(dialog);
  dialog.showModal();
  if (graphicWorkspace) window.requestAnimationFrame(() => graphicWorkspace.fit());
}
