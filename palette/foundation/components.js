/** Shared library, form, row, dialog, and context-menu components. */

function emptyMessage(text) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty";
  paragraph.textContent = text;
  return paragraph;
}

function statusBadge(harness) {
  const badge = document.createElement("span");
  badge.className = "status";
  badge.dataset.status = harness.status;
  badge.textContent = harness.status;
  return badge;
}

function renderLibrary() {
  const query = ui.harnessFilter.value.trim().toLocaleLowerCase();
  const harnesses = currentState.harnesses.filter((harness) => {
    const searchable = `${harness.componentName} ${harness.routingMode || ""} ${harness.status}`;
    return searchable.toLocaleLowerCase().includes(query);
  });
  ui.list.replaceChildren();
  if (!harnesses.length) {
    const message = currentState.harnesses.length
      ? "No harnesses match this filter."
      : "No procedural harnesses in this design.";
    ui.list.append(emptyMessage(message));
    return;
  }
  harnesses.forEach((harness) => {
    const button = document.createElement("button");
    const name = document.createElement("strong");
    const summary = document.createElement("span");
    button.type = "button";
    button.className = "harness-card";
    button.dataset.status = harness.status;
    name.textContent = harness.componentName;
    summary.className = "summary";
    summary.textContent = harness.status === "damaged"
      ? "Metadata could not be loaded"
      : `${harness.routingMode} · ${(harness.cableGroups || []).length} cable groups`;
    button.append(name, statusBadge(harness), summary);
    button.addEventListener("click", () => openHarness(harnessKey(harness)));
    ui.list.append(button);
  });
}

function editorSection(id, title, count, content, openByDefault = false) {
  const section = document.createElement("details");
  const summary = document.createElement("summary");
  const label = document.createElement("span");
  const counter = document.createElement("span");
  section.dataset.section = id;
  section.open = expandedSections.has(id) || (openByDefault && !hasStoredExpansionState);
  label.textContent = title;
  counter.className = "count";
  counter.textContent = count;
  summary.append(label, counter);
  section.append(summary, content);
  section.addEventListener("toggle", () => {
    hasStoredExpansionState = true;
    if (section.open) expandedSections.add(id);
    else expandedSections.delete(id);
    writeSession(
      "cableBundler.expandedSections",
      JSON.stringify([...expandedSections]),
    );
  });
  return section;
}

function nestedSection(id, title, count, content, onHover) {
  const section = editorSection(id, title, count, content);
  section.className = "nested-details";
  if (onHover) hoverHighlight(section.children[0], onHover);
  return section;
}

function actionButton(label, title, handler, disabled = false, danger = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `icon-button${danger ? " danger" : ""}`;
  button.textContent = label;
  button.title = title;
  button.setAttribute("aria-label", title);
  button.disabled = disabled;
  button.addEventListener("click", handler);
  return button;
}

function optionsButton(title, handler, disabled = false) {
  const button = actionButton("Options", title, handler, disabled);
  button.className = "icon-button options-button";
  return button;
}

function hoverHighlight(node, onHover) {
  let active = false;
  const enabled = () => {
    let ancestor = node;
    while (ancestor) {
      if (ancestor.dataset?.hoverDisabled === "true") return false;
      ancestor = ancestor.parentElement;
    }
    return true;
  };
  const clear = () => {
    if (!active) return;
    active = false;
    send("clear_highlight").catch(() => {});
  };
  node.addEventListener("mouseenter", () => {
    if (!enabled()) return;
    active = true;
    onHover();
  });
  node.addEventListener("mouseleave", clear);
}

function memberRow(label, onReveal, actions = [], missing = false, clickToActivate = false) {
  const row = document.createElement("div");
  const reference = document.createElement("button");
  const actionContainer = document.createElement("div");
  row.className = `member-row${missing ? " missing" : ""}`;
  reference.type = "button";
  reference.className = "member-reference";
  reference.textContent = missing ? `${label} (geometry missing)` : label;
  reference.title = "Show linked sketch profile in Fusion";
  if (clickToActivate) reference.addEventListener("click", onReveal);
  else hoverHighlight(row, onReveal);
  actionContainer.className = "member-actions";
  actionContainer.append(...actions);
  row.append(reference, actionContainer);
  return row;
}

function nameField(
  label, value, action, payload, placeholder = "Optional name", { showLabel = true } = {},
) {
  const field = document.createElement("label");
  const input = document.createElement("input");
  if (showLabel) field.textContent = label;
  input.type = "text";
  input.className = "filter";
  input.value = value || "";
  input.placeholder = placeholder;
  input.setAttribute("aria-label", label);
  input.addEventListener("change", () => mutate(
    action, { ...payload, name: input.value }, "Saving name…",
  ));
  field.append(input);
  return field;
}

/** Temporarily replace a label and report editing until any requested save settles. */
function beginInlineNameEdit(container, label, before, options) {
  if (container.querySelector("input")) return;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "filter";
  input.value = options.value || "";
  input.placeholder = options.placeholder;
  input.setAttribute("aria-label", options.ariaLabel);
  label.hidden = true;
  container.insertBefore(input, before);
  options.onEditingChange?.(true);
  let finished = false;
  const finish = (save) => {
    if (finished) return;
    finished = true;
    input.remove();
    label.hidden = false;
    if (!save) {
      options.onEditingChange?.(false);
      return;
    }
    let saveResult;
    try {
      saveResult = options.onSave(input.value);
    } catch (error) {
      options.onEditingChange?.(false);
      throw error;
    }
    void Promise.resolve(saveResult).finally(() => options.onEditingChange?.(false));
  };
  input.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Enter" || event.key === "Escape") {
      event.preventDefault();
      finish(event.key === "Enter");
    }
  });
  ["mousedown", "click", "contextmenu"].forEach((eventName) => {
    input.addEventListener(eventName, (event) => event.stopPropagation());
  });
  input.addEventListener("blur", () => finish(true));
  input.focus();
  input.select();
}

/** Replace one standalone-end label with the shared inline rename editor. */
function renameRelationshipEnd(harness, group, entry, name, metadata, onEditingChange) {
  beginInlineNameEdit(entry, name, metadata, {
    value: group.connectionName || group.label,
    placeholder: group.label || "End name",
    ariaLabel: "End name",
    onEditingChange,
    onSave: (value) => mutate("rename_standalone_end", {
      harnessId: harness.harnessId,
      connectionId: group.connectionId,
      name: value,
    }, "Saving end name…"),
  });
}

/** Add one positioned, keyboard-dismissible context menu to a UI surface. */
function addContextMenu(root, returnFocus = null) {
  const menu = document.createElement("div");
  const close = () => {
    menu.hidden = true;
    document.removeEventListener("mousedown", dismissOnOutsideMouseDown, true);
  };
  const dismissOnOutsideMouseDown = (event) => {
    if (!menu.contains(event.target)) close();
  };
  menu.className = "relationship-map-context-menu";
  menu.hidden = true;
  menu.setAttribute("role", "menu");
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close();
      if (returnFocus) returnFocus.focus();
    }
  });
  const appendItem = (parent, item, closeMenu) => {
    if (item.items) {
      const branch = document.createElement("div");
      const trigger = document.createElement("button");
      const submenu = document.createElement("div");
      branch.className = "context-menu-branch";
      trigger.type = "button";
      trigger.className = "context-menu-branch-trigger";
      trigger.setAttribute("role", "menuitem");
      trigger.setAttribute("aria-haspopup", "menu");
      trigger.textContent = item.label;
      trigger.disabled = item.disabled || false;
      trigger.title = item.title || "";
      submenu.className = "context-menu-submenu";
      submenu.setAttribute("role", "menu");
      item.items.forEach((child) => appendItem(submenu, child, closeMenu));
      branch.append(trigger, submenu);
      parent.append(branch);
      return;
    }
    if (typeof item.checked === "boolean") {
      const row = document.createElement("div");
      const button = document.createElement("button");
      const checkbox = document.createElement("input");
      row.className = "context-menu-toggle";
      button.type = "button";
      button.setAttribute("role", "menuitem");
      button.textContent = item.label;
      button.disabled = item.disabled || false;
      button.title = item.title || "";
      checkbox.type = "checkbox";
      checkbox.checked = item.checked;
      checkbox.disabled = item.disabled || false;
      checkbox.setAttribute("aria-label", `${item.label} enabled`);
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
        closeMenu();
        void item.onToggle(checkbox.checked);
      });
      button.addEventListener("click", () => {
        closeMenu();
        void item.action();
      });
      row.append(button, checkbox);
      parent.append(row);
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = item.label;
    button.disabled = item.disabled || false;
    button.title = item.title || "";
    button.addEventListener("click", () => {
      closeMenu();
      void item.action();
    });
    parent.append(button);
  };
  const show = (event, items) => {
    event.preventDefault();
    const bounds = root.getBoundingClientRect();
    menu.replaceChildren();
    items.forEach((item) => appendItem(menu, item, close));
    menu.style.left = "4px";
    menu.style.top = "4px";
    menu.hidden = false;
    const menuBounds = menu.getBoundingClientRect();
    const left = Math.min(
      Math.max(4, event.clientX - bounds.left),
      Math.max(4, root.clientWidth - menuBounds.width - 4),
    );
    const top = Math.min(
      Math.max(4, event.clientY - bounds.top),
      Math.max(4, root.clientHeight - menuBounds.height - 4),
    );
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.dataset.submenuDirection = (
      left + menuBounds.width + 140 > root.clientWidth ? "left" : "right"
    );
    document.addEventListener("mousedown", dismissOnOutsideMouseDown, true);
    const firstEnabled = Array.from(menu.querySelectorAll("button")).find(
      (button) => !button.disabled,
    );
    if (firstEnabled) firstEnabled.focus();
  };
  root.append(menu);
  return show;
}

function cableGroupLabel(harness, group) {
  if (group.name) return group.name;
  const index = (harness.cableGroups || []).findIndex(
    (candidate) => candidate.cableGroupId === group.cableGroupId,
  );
  return `Cable Group ${index >= 0 ? index + 1 : "?"}`;
}

/** Return end-owned routing actions shared by every end representation. */
function endRoutingContextItems(harness, connectionId, includeProperties = true) {
  const connection = (harness.connections || []).find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const end = (harness.standaloneEnds || []).find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const pathway = end && harness.pathways.find(
    (candidate) => candidate.pathwayId === end.pathwayId,
  );
  const unavailable = !end || !pathway;
  const refineUnavailable = unavailable || !(pathway.orderedControlIds || []).length;
  return [
    {
      label: "Add",
      items: [
        {
          label: "Connection",
          action: () => addCableEndConnection(harness, connectionId),
          disabled: !connection || Boolean(connection.attachment),
          title: connection?.attachment ? "This cable end already has a connection" : "",
        },
        {
          label: "Guides",
          action: () => appendEndGuides(harness, connectionId),
          disabled: unavailable,
          title: unavailable ? "Requires an end attached to an existing pathway" : "",
        },
        {
          label: "Refine",
          action: () => addEndRefine(harness, connectionId),
          disabled: refineUnavailable,
          title: refineUnavailable
            ? "Requires an end attached to a pathway with a routing gate"
            : "",
        },
      ],
    },
    ...(includeProperties ? [{
      label: "Properties",
      action: () => openCableEndProperties(harness, connectionId),
    }] : []),
  ];
}

/** Open the configuration owned by one pathway diagram node. */
function activatePathwayNode(harness, pathway) {
  if (pathway) openPathwayPopup(harness, pathway.pathwayId);
}

/** Return the pathway actions shared by master and Cable Details diagram nodes. */
function pathwayNodeContextItems(harness, pathway) {
  const controls = new Map(harness.controls.map((control) => [control.controlId, control]));
  const canSegment = pathway.orderedControlIds.slice(1, -1).some((controlId) => {
    const control = controls.get(controlId);
    return control && ["routing_gate", "refine"].includes(control.kind);
  });
  return [
    {
      label: "Add",
      items: [{ label: "Refine", action: () => addPathwayRefine(harness, pathway) }],
    },
    {
      label: "Segment",
      action: () => segmentPathway(harness, pathway),
      disabled: !canSegment,
      title: canSegment ? "" : "Requires an interior routing gate or refine point",
    },
    { label: "Delete", action: () => removePathway(harness, pathway) },
    { label: "Properties", action: () => openPathwayProperties(harness, pathway) },
  ];
}

/** Open the configuration owned by one junction diagram node. */
function activateJunctionNode(harness, junction) {
  if (junction) openJunctionRelationships(harness, junction);
}

/** Return the junction actions shared by master and Cable Details diagram nodes. */
function junctionNodeContextItems(harness, junction) {
  return [
    {
      label: "Open junction configuration",
      action: () => activateJunctionNode(harness, junction),
    },
    { label: "Delete", action: () => removeJunction(harness, junction) },
    { label: "Properties", action: () => openJunctionProperties(harness, junction) },
  ];
}

function pathwayDirection(pathway) {
  const start = pathway?.startName || "A";
  const end = pathway?.endName || "B";
  return `${start} → ${end}`;
}

function centeredStripeOffset(index, count, spacing) {
  return (index - (count - 1) / 2) * spacing;
}

function createOptionsDialog(className) {
  const dialog = document.createElement("dialog");
  const form = document.createElement("form");
  const heading = document.createElement("h2");
  const note = document.createElement("p");
  const error = document.createElement("p");
  const actions = document.createElement("div");
  const cancel = document.createElement("button");
  const save = document.createElement("button");
  dialog.className = className;
  error.setAttribute("role", "alert");
  error.style.color = "var(--danger)";
  actions.className = "actions";
  cancel.type = "button";
  cancel.className = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => {
    if (typeof dialog.cancelOptions === "function") return dialog.cancelOptions();
    dialog.close();
    return undefined;
  });
  dialog.addEventListener("cancel", (event) => {
    if (typeof dialog.cancelOptions !== "function") return;
    event.preventDefault();
    void dialog.cancelOptions();
  });
  save.type = "submit";
  save.className = "button primary";
  save.textContent = "Save";
  return { dialog, form, heading, note, error, actions, cancel, save };
}
