/** Connect one or two selected Interfaces and associate unique matching pins. */

let pendingAutoConnectTargetSelection = null;

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
  select.title = "Pick grouped cable endings in Fusion";
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
  pane.append(select, pinsLabel, valuesLabel, diameterLabel);
  return { pane, select, pins, values, diameter };
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
  const close = document.createElement("button");
  let sourceIds = null;
  let target = null;
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
  close.type = "button";
  close.className = "button compact";
  close.textContent = "Close";
  close.addEventListener("click", () => {
    if (target) dialog.close();
    else panel.remove();
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    if (target) dialog.close();
    else panel.remove();
  });
  selectTarget.addEventListener("click", () => {
    const state = diagram.contactState;
    if (!state?.items.length || state.workspace.root.hidden) {
      appendNotice("Auto Connect needs loaded source contacts.", true);
      return;
    }
    if (!target) sourceIds = autoConnectContactIds(state);
    dialog.autoConnectSelectingTarget = true;
    dialog.close();
    const cancelSelection = (event) => {
      if (event.key !== "Escape") return;
      document.removeEventListener("keydown", cancelSelection);
      pendingAutoConnectTargetSelection = null;
      dialog.autoConnectSelectingTarget = false;
      dialog.showModal();
    };
    document.addEventListener("keydown", cancelSelection);
    pendingAutoConnectTargetSelection = (chosenHarness, chosenInterface) => {
      if (chosenHarness.harnessId !== harness.harnessId
        || chosenInterface.interfaceId === interfaceId) {
        appendNotice("Select a different Interface in this harness.", true);
        return true;
      }
      document.removeEventListener("keydown", cancelSelection);
      pendingAutoConnectTargetSelection = null;
      target = chosenInterface;
      secondCaption.textContent = chosenInterface.name;
      second.select.disabled = false;
      dialog.dataset.interfaceId = chosenInterface.interfaceId;
      diagram.contactState.interfaceId = chosenInterface.interfaceId;
      dialog.children[0].textContent = `Contacts Editor · ${chosenInterface.name}`;
      dialog.loadedGeometryKey = null;
      dialog.contactDisplayKey = null;
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
      dialog.autoConnectSelectingTarget = false;
      dialog.showModal();
      updateInterfaceContactData(dialog, chosenInterface.contacts || []);
      return true;
    };
    pendingAutoConnectTargetSelection.dialog = dialog;
    appendNotice("Select the target Interface on the master diagram. Press Escape to cancel.");
  });
  const launch = (button) => {
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
    button.disabled = true;
    void send("auto_connect_interface_contacts", {
      harnessId: harness.harnessId, interfaceId, contactIds,
      includePins: first.pins.checked, includeValues: first.values.checked,
      diameterMm,
      targetInterfaceId: target?.interfaceId || null, targetContactIds,
      targetIncludePins: second.pins.checked, targetIncludeValues: second.values.checked,
      targetDiameterMm,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not open Auto Connect.");
      if (target) dialog.close();
      else panel.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { button.disabled = false; });
  };
  first.select.addEventListener("click", () => launch(first.select));
  second.select.addEventListener("click", () => launch(second.select));
  panes.append(first.pane, second.pane);
  panel.append(title, panes, close);
  naming.append(panel);
}
