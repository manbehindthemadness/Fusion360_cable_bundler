/** Return contact IDs by visual rows or columns with a stable identity tie-breaker. */
function orderedInterfaceContactIds(items, selectedIds, direction) {
  const candidates = items.filter((item) => !selectedIds.size || selectedIds.has(item.id))
    .map((item) => {
      const points = item.loops.flat();
      if (!points.length) return null;
      const xs = points.map((point) => point[0]);
      const ys = points.map((point) => point[1]);
      const left = Math.min(...xs);
      const right = Math.max(...xs);
      const top = Math.min(...ys);
      const bottom = Math.max(...ys);
      return { id: item.id, x: (left + right) / 2, y: (top + bottom) / 2,
        width: right - left, height: bottom - top };
    }).filter(Boolean);
  const rowsFirst = direction.startsWith("LR") || direction.startsWith("RL");
  const primaryAxis = rowsFirst ? "y" : "x";
  const secondaryAxis = rowsFirst ? "x" : "y";
  const spans = candidates.map((item) => rowsFirst ? item.height : item.width)
    .filter((span) => span > 0)
    .sort((first, second) => first - second);
  const groupTolerance = spans.length ? spans[Math.floor(spans.length / 2)] / 2 : 1;
  candidates.sort((first, second) => first[primaryAxis] - second[primaryAxis]
    || first[secondaryAxis] - second[secondaryAxis] || first.id.localeCompare(second.id));
  const groups = [];
  candidates.forEach((item) => {
    const group = groups.find((candidate) => (
      Math.abs(candidate.position - item[primaryAxis]) <= groupTolerance
    ));
    if (group) group.items.push(item);
    else groups.push({ position: item[primaryAxis], items: [item] });
  });
  const primaryReverse = rowsFirst ? direction.endsWith("BT") : direction.endsWith("RL");
  const secondaryReverse = rowsFirst ? direction.startsWith("RL") : direction.startsWith("BT");
  groups.forEach((group) => group.items.sort((first, second) => (
    (secondaryReverse ? second[secondaryAxis] - first[secondaryAxis]
      : first[secondaryAxis] - second[secondaryAxis])
      || first.id.localeCompare(second.id)
  )));
  if (primaryReverse) groups.reverse();
  return groups.flatMap((group) => group.items.map((item) => item.id));
}

/** Open a compact numbering form while retaining the current contact selection. */
function openInterfaceAutoPin(naming, diagram, harnessId, interfaceId) {
  const existing = naming.querySelector(".interface-contact-auto-pin");
  if (existing) { existing.remove(); return; }
  const form = document.createElement("form");
  const directionLabel = document.createElement("label");
  const direction = document.createElement("select");
  const startLabel = document.createElement("label");
  const start = document.createElement("input");
  const overwriteLabel = document.createElement("label");
  const overwrite = document.createElement("input");
  const apply = document.createElement("button");
  const cancel = document.createElement("button");
  form.className = "interface-contact-auto-pin";
  directionLabel.textContent = "Order";
  const orders = ["LRTB", "RLTB", "LRBT", "RLBT", "TBLR", "BTLR", "TBRL", "BTRL"];
  orders.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    direction.append(option);
  });
  const rememberedOrder = readSession("cableBundler.autoPinOrder");
  direction.value = orders.includes(rememberedOrder) ? rememberedOrder : "LRTB";
  direction.addEventListener("change", () => writeSession("cableBundler.autoPinOrder", direction.value));
  directionLabel.append(direction);
  startLabel.textContent = "Start";
  start.type = "number";
  start.min = "0";
  start.max = "1000000000";
  start.step = "1";
  start.required = true;
  start.value = "0";
  startLabel.append(start);
  overwrite.type = "checkbox";
  overwriteLabel.textContent = "Overwrite";
  overwriteLabel.append(overwrite);
  apply.type = "submit";
  apply.className = "button compact";
  apply.textContent = "Apply";
  cancel.type = "button";
  cancel.className = "button compact";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => form.remove());
  form.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    form.remove();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const state = diagram.contactState;
    const contactIds = orderedInterfaceContactIds(state.items, state.selectedIds, direction.value);
    const first = Number(start.value);
    if (!contactIds.length || !start.value.trim() || !Number.isSafeInteger(first)
      || first < 0 || first > 1_000_000_000) {
      appendNotice("Auto Pin needs loaded contacts and a whole-number Start from 0 to 1000000000.", true);
      return;
    }
    apply.disabled = true;
    void send("auto_pin_interface_contacts", {
      harnessId, interfaceId, contactIds, start: first, overwrite: overwrite.checked,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not pin contacts.");
      form.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { apply.disabled = false; });
  });
  form.append(directionLabel, startLabel, overwriteLabel, apply, cancel);
  naming.append(form);
  start.focus();
  start.select();
}
