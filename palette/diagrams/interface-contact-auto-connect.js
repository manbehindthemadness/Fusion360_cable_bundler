/** Connect one or two selected Interfaces and associate unique matching pins. */

let pendingAutoConnectTargetSelection = null;
let pendingAutoConnectEndingSelection = null;
let autoConnectEndingRequestSequence = 0;

/** Return selected contact identities, or every loaded contact when nothing is selected. */
function autoConnectContactIds(state) {
  return state.items
    .filter((item) => !state.selectedIds.size || state.selectedIds.has(item.id))
    .map((item) => item.id);
}

/** Create one pane's ending button and options. */
function autoConnectEndingPane(units) {
  const pane = document.createElement("div");
  const select = document.createElement("button");
  const selected = document.createElement("small");
  const pinsLabel = document.createElement("label");
  const pins = document.createElement("input");
  const valuesLabel = document.createElement("label");
  const values = document.createElement("input");
  const diameterLabel = document.createElement("label");
  const diameter = document.createElement("input");
  pane.className = "interface-contact-auto-connect-ending";
  select.type = "button";
  select.className = "button compact";
  select.textContent = "Select Ending";
  select.title = "Choose a grouped cable ending in Fusion";
  selected.className = "interface-contact-auto-connect-selected-ending";
  selected.textContent = "No ending selected";
  pins.type = "checkbox";
  pins.checked = true;
  pinsLabel.append(pins, "Include pins");
  values.type = "checkbox";
  values.checked = true;
  valuesLabel.append(values, "Include values");
  diameterLabel.textContent = `Connection diameter (${units.symbol})`;
  diameter.type = "number";
  diameter.min = "0";
  diameter.step = "any";
  diameter.placeholder = "Auto";
  diameterLabel.append(diameter);
  pane.append(select, selected, pinsLabel, valuesLabel, diameterLabel);
  return { pane, select, selected, pins, values, diameter };
}

/** Convert a pane's optional displayed diameter into millimeters. */
function autoConnectDiameter(input, units) {
  if (!input.value.trim()) return null;
  const amount = Number(input.value);
  const scale = Number(units.millimetersPerUnit);
  if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(scale) || scale <= 0) {
    throw new Error("Enter a positive connection diameter or leave it blank for Auto.");
  }
  return amount * scale;
}

/** Open Auto Connect options and allow a second Interface to be picked on the master diagram. */
function openInterfaceAutoConnect(naming, diagram, harness, interfaceId) {
  const existing = naming.querySelector(".interface-contact-auto-connect");
  if (existing) { existing.remove(); return; }
  const dialog = naming.parentElement.parentElement;
  const source = (harness.interfaces || []).find((item) => item.interfaceId === interfaceId);
  const units = harness.lengthUnits || { symbol: "mm", millimetersPerUnit: 1 };
  const panel = document.createElement("div");
  const title = document.createElement("strong");
  const panes = document.createElement("div");
  const first = autoConnectEndingPane(units);
  const second = autoConnectEndingPane(units);
  const firstCaption = document.createElement("small");
  const secondCaption = document.createElement("small");
  const selectTarget = document.createElement("button");
  const actions = document.createElement("div");
  const apply = document.createElement("button");
  const close = document.createElement("button");
  let sourceIds = null;
  let target = null;
  let sourceEnding = null;
  let targetEnding = null;
  let pendingEnding = null;
  let sourceEditor = null;
  panel.className = "interface-contact-auto-connect";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Auto Connect options");
  title.textContent = "Auto Connect";
  panes.className = "interface-contact-auto-connect-panes";
  firstCaption.textContent = source?.name || "Source Interface";
  first.pane.prepend(firstCaption);
  secondCaption.textContent = "Select a target Interface";
  second.pane.prepend(secondCaption);
  selectTarget.type = "button";
  selectTarget.className = "button compact";
  selectTarget.textContent = "Select Target Contacts";
  second.pane.insertBefore(selectTarget, second.select);
  second.select.disabled = true;
  apply.type = "button";
  apply.className = "button compact";
  apply.textContent = "Apply";
  apply.disabled = true;
  actions.className = "interface-contact-auto-connect-actions";
  close.type = "button";
  close.className = "button compact";
  close.textContent = "Close";
  /** Dismiss the options while restoring the source editor after a target preview. */
  const closeAutoConnect = () => {
    pendingAutoConnectEndingSelection = null;
    panel.remove();
    if (!sourceEditor || !dialog.open || !diagram.contactState?.autoConnectTargetPreview) return;
    const state = diagram.contactState;
    dialog.dataset.interfaceId = interfaceId;
    dialog.setAttribute("aria-label", `Contacts Editor: ${source?.name || "Interface"}`);
    dialog.children[0].textContent = `Contacts Editor · ${source?.name || "Interface"}`;
    state.interfaceId = interfaceId;
    state.autoConnectTargetPreview = false;
    state.selectedIds.clear();
    sourceEditor.selectedIds.forEach((id) => state.selectedIds.add(id));
    Object.assign(state, sourceEditor.handlers);
    sourceEditor.buttons.forEach(([button, disabled]) => { button.disabled = disabled; });
    dialog.loadedGeometryKey = null;
    dialog.contactDisplayKey = null;
    dialog.contactSignatures = sourceEditor.contactSignatures;
    const currentHarness = currentState.harnesses.find((item) => item.harnessId === harness.harnessId);
    const currentSource = (currentHarness?.interfaces || []).find((item) => item.interfaceId === interfaceId);
    updateInterfaceContactData(dialog, currentSource?.contacts || sourceEditor.contacts);
  };
  close.addEventListener("click", () => {
    closeAutoConnect();
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    closeAutoConnect();
  });
  const updateApply = () => {
    apply.disabled = !sourceEnding || !!pendingEnding
      || (!!target && (!targetEnding || targetEnding.connectionId === sourceEnding.connectionId));
  };
  const pickEnding = (side) => {
    if (pendingEnding || (side === "target" && !target)) return;
    const requestId = `${++autoConnectEndingRequestSequence}`;
    pendingEnding = { side, requestId };
    first.select.disabled = true;
    second.select.disabled = true;
    selectTarget.disabled = true;
    updateApply();
    pendingAutoConnectEndingSelection = (result) => {
      if (result.harnessId !== harness.harnessId || result.side !== side
        || result.requestId !== requestId) return;
      pendingEnding = null;
      pendingAutoConnectEndingSelection = null;
      first.select.disabled = false;
      second.select.disabled = !target;
      selectTarget.disabled = false;
      if (!result.cancelled && result.connectionId) {
        const ending = {
          connectionId: result.connectionId,
          parentAttachmentId: result.parentAttachmentId || null,
        };
        const selected = side === "source" ? first : second;
        selected.selected.textContent = `Selected: ${result.name || "Cable ending"}`;
        if (side === "source") sourceEnding = ending;
        else targetEnding = ending;
      }
      if (result.error) appendNotice(result.error, true);
      updateApply();
    };
    void send("auto_connect_interface_contacts", {
      harnessId: harness.harnessId, side, requestId,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not open ending picker.");
    }).catch((error) => {
      if (pendingEnding?.requestId !== requestId) return;
      pendingEnding = null;
      pendingAutoConnectEndingSelection = null;
      first.select.disabled = false;
      second.select.disabled = !target;
      selectTarget.disabled = false;
      updateApply();
      appendNotice(String(error), true);
    });
  };
  selectTarget.addEventListener("click", () => {
    const state = diagram.contactState;
    if (!state?.items.length || state.workspace.root.hidden) {
      appendNotice("Auto Connect needs loaded source contacts.", true);
      return;
    }
    const master = document.body.querySelector(".relationship-map");
    const masterToolbar = master?.querySelector(".relationship-map-toolbar");
    if (!masterToolbar) {
      appendNotice("Open the master diagram before selecting a target Interface.", true);
      return;
    }
    if (!target) {
      sourceIds = autoConnectContactIds(state);
      sourceEditor = {
        contacts: dialog.contactMetadata,
        contactSignatures: dialog.contactSignatures,
        selectedIds: new Set(state.selectedIds),
        handlers: {
          onEditContact: state.onEditContact,
          onEditOrientation: state.onEditOrientation,
          onDeleteContacts: state.onDeleteContacts,
          onClearPins: state.onClearPins,
          onClearValues: state.onClearValues,
        },
        buttons: [
          ...dialog.children[1].children[0].querySelectorAll("button"),
          ...[...naming.children].filter((item) => item !== panel),
        ].map((button) => [button, button.disabled]),
      };
    }
    const prompt = document.createElement("div");
    const promptText = document.createElement("span");
    const cancelButton = document.createElement("button");
    prompt.className = "interface-auto-connect-target-prompt";
    prompt.setAttribute("role", "status");
    promptText.textContent = "Select a target Interface card in this master diagram.";
    cancelButton.type = "button";
    cancelButton.className = "button compact";
    cancelButton.textContent = "Cancel";
    prompt.append(promptText, cancelButton);
    masterToolbar.prepend(prompt);
    master.dataset.autoConnectSelectingTarget = "true";
    const filter = masterToolbar.querySelector(".filter");
    if (filter?.value) {
      filter.value = "";
      filter.dispatchEvent(new window.Event("input"));
    }
    const finishSelection = () => {
      document.removeEventListener("keydown", cancelSelection);
      prompt.remove();
      delete master.dataset.autoConnectSelectingTarget;
      pendingAutoConnectTargetSelection = null;
    };
    const cancelSelection = (event) => {
      if (event.key !== "Escape") return;
      event.preventDefault?.();
      finishSelection();
      dialog.showModal();
      logContactEditorLifecycle(dialog, "open-shown", "auto-connect-target-cancelled");
    };
    cancelButton.addEventListener("click", () => cancelSelection({ key: "Escape" }));
    document.addEventListener("keydown", cancelSelection);
    pendingAutoConnectTargetSelection = (chosenHarness, chosenInterface) => {
      if (chosenHarness.harnessId !== harness.harnessId
        || chosenInterface.interfaceId === interfaceId) {
        appendNotice("Select a different Interface in this harness.", true);
        return true;
      }
      finishSelection();
      target = chosenInterface;
      targetEnding = null;
      second.selected.textContent = "No ending selected";
      secondCaption.textContent = chosenInterface.name;
      second.select.disabled = false;
      updateApply();
      dialog.dataset.interfaceId = chosenInterface.interfaceId;
      diagram.contactState.interfaceId = chosenInterface.interfaceId;
      dialog.children[0].textContent = `Contacts Editor · ${chosenInterface.name}`;
      dialog.loadedGeometryKey = null;
      dialog.contactDisplayKey = null;
      dialog.contactSignatures = currentContactGeometry(dialog)?.signatures || null;
      diagram.contactState.selectedIds.clear();
      diagram.contactState.autoConnectTargetPreview = true;
      diagram.contactState.onEditContact = null;
      diagram.contactState.onEditOrientation = null;
      diagram.contactState.onDeleteContacts = null;
      diagram.contactState.onClearPins = null;
      diagram.contactState.onClearValues = null;
      dialog.children[1].children[0].querySelectorAll("button").forEach((item) => {
        item.disabled = true;
      });
      [...naming.children].filter((item) => item !== panel).forEach((item) => {
        item.disabled = true;
      });
      dialog.showModal();
      logContactEditorLifecycle(dialog, "open-shown", "auto-connect-target-preview");
      updateInterfaceContactData(dialog, chosenInterface.contacts || []);
      return true;
    };
    pendingAutoConnectTargetSelection.dialog = dialog;
    dialog.autoConnectSuspendedCloses = (dialog.autoConnectSuspendedCloses || 0) + 1;
    dialog.contactCloseReason = "auto-connect-target-pick";
    dialog.close();
    prompt.scrollIntoView({ block: "nearest" });
  });
  apply.addEventListener("click", () => {
    if (apply.disabled) return;
    const state = diagram.contactState;
    const contactIds = sourceIds || autoConnectContactIds(state);
    const targetContactIds = target ? autoConnectContactIds(state) : [];
    if (!contactIds.length || state.workspace.root.hidden || (target && !targetContactIds.length)) {
      appendNotice("Auto Connect needs loaded contacts on both selected Interfaces.", true);
      return;
    }
    let diameterMm;
    let targetDiameterMm;
    try {
      diameterMm = autoConnectDiameter(first.diameter, units);
      targetDiameterMm = autoConnectDiameter(second.diameter, units);
    } catch (error) {
      appendNotice(String(error), true);
      return;
    }
    apply.disabled = true;
    void send("apply_auto_connect_interface_contacts", {
      autoHide: false,
      harnessId: harness.harnessId, interfaceId, contactIds,
      connectionId: sourceEnding.connectionId,
      parentAttachmentId: sourceEnding.parentAttachmentId,
      includePins: first.pins.checked, includeValues: first.values.checked,
      diameterMm,
      targetInterfaceId: target?.interfaceId || null, targetContactIds,
      targetConnectionId: targetEnding?.connectionId || null,
      targetParentAttachmentId: targetEnding?.parentAttachmentId || null,
      targetIncludePins: second.pins.checked, targetIncludeValues: second.values.checked,
      targetDiameterMm,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not apply Auto Connect.");
      closeAutoConnect();
    }).catch((error) => appendNotice(String(error), true))
      .finally(updateApply);
  });
  first.select.addEventListener("click", () => pickEnding("source"));
  second.select.addEventListener("click", () => pickEnding("target"));
  panes.append(first.pane, second.pane);
  actions.append(close, apply);
  panel.append(title, panes, actions);
  naming.append(panel);
}
