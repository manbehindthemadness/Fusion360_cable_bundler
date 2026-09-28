/** Batch-connect selected Interface contacts to a picked grouped cable ending. */

/** Open the two-pane Auto Connect dialog; only ending selection is available now. */
function openInterfaceAutoConnect(naming, diagram, harness, interfaceId) {
  const existing = naming.querySelector(".interface-contact-auto-connect");
  if (existing) { existing.remove(); return; }
  const panel = document.createElement("div");
  const title = document.createElement("strong");
  const panes = document.createElement("div");
  const ending = document.createElement("div");
  const future = document.createElement("div");
  const select = document.createElement("button");
  const pinsLabel = document.createElement("label");
  const pins = document.createElement("input");
  const valuesLabel = document.createElement("label");
  const values = document.createElement("input");
  const diameterLabel = document.createElement("label");
  const diameter = document.createElement("input");
  const close = document.createElement("button");
  const units = harness.lengthUnits || { symbol: "mm", millimetersPerUnit: 1 };
  panel.className = "interface-contact-auto-connect";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Auto Connect options");
  title.textContent = "Auto Connect";
  panes.className = "interface-contact-auto-connect-panes";
  ending.className = "interface-contact-auto-connect-ending";
  future.className = "interface-contact-auto-connect-future";
  future.textContent = "Second action · Coming later";
  select.type = "button";
  select.className = "button compact";
  select.textContent = "Select Ending";
  select.title = "Pick a grouped cable end or its connected profile node in Fusion";
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
  close.type = "button";
  close.className = "button compact";
  close.textContent = "Close";
  close.addEventListener("click", () => panel.remove());
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    panel.remove();
  });
  select.addEventListener("click", () => {
    const state = diagram.contactState;
    const contactIds = state.items
      .filter((item) => !state.selectedIds.size || state.selectedIds.has(item.id))
      .map((item) => item.id);
    const amount = diameter.value.trim() ? Number(diameter.value) : null;
    const millimetersPerUnit = Number(units.millimetersPerUnit);
    if (!contactIds.length || state.workspace.root.hidden) {
      appendNotice("Auto Connect needs loaded contacts.", true);
      return;
    }
    if (amount !== null && (!Number.isFinite(amount) || amount <= 0
      || !Number.isFinite(millimetersPerUnit) || millimetersPerUnit <= 0)) {
      appendNotice("Enter a positive connection diameter or leave it blank for Auto.", true);
      return;
    }
    select.disabled = true;
    void send("auto_connect_interface_contacts", {
      harnessId: harness.harnessId, interfaceId, contactIds,
      includePins: pins.checked, includeValues: values.checked,
      diameterMm: amount === null ? null : amount * millimetersPerUnit,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not open Auto Connect.");
      panel.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { select.disabled = false; });
  });
  ending.append(select, pinsLabel, valuesLabel, diameterLabel);
  panes.append(ending, future);
  panel.append(title, panes, close);
  naming.append(panel);
}
