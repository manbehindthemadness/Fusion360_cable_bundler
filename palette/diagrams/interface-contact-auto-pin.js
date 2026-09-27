/** Peel outer rows and columns in the corner and turn direction of an order. */
function spiralInterfaceContactIds(candidates, direction) {
  const rowsFirst = direction.startsWith("LR") || direction.startsWith("RL");
  const firstSide = rowsFirst
    ? (direction.endsWith("TB") ? "top" : "bottom")
    : (direction.endsWith("LR") ? "left" : "right");
  const firstAscending = rowsFirst ? direction.startsWith("LR") : direction.startsWith("TB");
  const secondSide = rowsFirst
    ? (firstAscending ? "right" : "left")
    : (firstAscending ? "bottom" : "top");
  const opposite = { top: "bottom", bottom: "top", left: "right", right: "left" };
  const passes = [
    { side: firstSide, axis: rowsFirst ? "x" : "y", ascending: firstAscending },
    { side: secondSide, axis: rowsFirst ? "y" : "x",
      ascending: rowsFirst ? firstSide === "top" : firstSide === "left" },
    { side: opposite[firstSide], axis: rowsFirst ? "x" : "y", ascending: !firstAscending },
    { side: opposite[secondSide], axis: rowsFirst ? "y" : "x",
      ascending: rowsFirst ? firstSide !== "top" : firstSide !== "left" },
  ];
  const tolerance = (axis) => {
    const spans = candidates.map((item) => axis === "x" ? item.width : item.height)
      .filter((span) => span > 0).sort((first, second) => first - second);
    return spans.length ? spans[Math.floor(spans.length / 2)] / 2 : 1;
  };
  const toleranceX = tolerance("x");
  const toleranceY = tolerance("y");
  let remaining = candidates.slice();
  const ordered = [];
  while (remaining.length) {
    passes.forEach(({ side, axis, ascending }) => {
      if (!remaining.length) return;
      const boundaryAxis = side === "top" || side === "bottom" ? "y" : "x";
      const extreme = side === "top" || side === "left"
        ? Math.min(...remaining.map((item) => item[boundaryAxis]))
        : Math.max(...remaining.map((item) => item[boundaryAxis]));
      const boundary = remaining.filter((item) => (
        Math.abs(item[boundaryAxis] - extreme) <= (boundaryAxis === "x" ? toleranceX : toleranceY)
      ));
      boundary.sort((first, second) => (ascending
        ? first[axis] - second[axis] : second[axis] - first[axis])
        || first.id.localeCompare(second.id));
      ordered.push(...boundary.map((item) => item.id));
      const used = new Set(boundary.map((item) => item.id));
      remaining = remaining.filter((item) => !used.has(item.id));
    });
  }
  return ordered;
}

/** Return contact IDs by visual groups using the selected numbering pattern. */
function orderedInterfaceContactIds(items, selectedIds, direction, pattern = "linear") {
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
  if (pattern === "spiral") return spiralInterfaceContactIds(candidates, direction);
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
  if (pattern === "zigzag") groups.forEach((group, index) => {
    if (index % 2) group.items.reverse();
  });
  return groups.flatMap((group) => group.items.map((item) => item.id));
}

/** Accept only Start values that the Auto Pin action can submit. */
function autoPinStartNumber(value) {
  if (!value || !value.trim()) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 && number <= 1_000_000_000
    ? number : null;
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
  const hopscotchLabel = document.createElement("label");
  const hopscotch = document.createElement("input");
  const zigzagLabel = document.createElement("label");
  const zigzag = document.createElement("input");
  const spiralLabel = document.createElement("label");
  const spiral = document.createElement("input");
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
  const rememberedStart = autoPinStartNumber(readSession("cableBundler.autoPinStart"));
  start.value = String(rememberedStart ?? 0);
  start.addEventListener("change", () => {
    const value = autoPinStartNumber(start.value);
    if (value !== null) writeSession("cableBundler.autoPinStart", String(value));
  });
  startLabel.append(start);
  hopscotch.type = "checkbox";
  hopscotch.checked = true;
  hopscotchLabel.textContent = "Hopscotch";
  hopscotchLabel.append(hopscotch);
  zigzag.type = "checkbox";
  zigzagLabel.textContent = "Zigzag";
  zigzagLabel.append(zigzag);
  spiral.type = "checkbox";
  spiralLabel.textContent = "Spiral";
  spiralLabel.append(spiral);
  zigzag.addEventListener("change", () => {
    if (zigzag.checked) spiral.checked = false;
  });
  spiral.addEventListener("change", () => {
    if (spiral.checked) zigzag.checked = false;
  });
  overwrite.type = "checkbox";
  overwriteLabel.textContent = "Overwrite";
  overwriteLabel.append(overwrite);
  hopscotch.addEventListener("change", () => {
    if (!hopscotch.checked) overwrite.checked = false;
    overwrite.disabled = !hopscotch.checked;
  });
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
    const pattern = spiral.checked ? "spiral" : zigzag.checked ? "zigzag" : "linear";
    const contactIds = orderedInterfaceContactIds(
      state.items, state.selectedIds, direction.value, pattern,
    );
    const first = autoPinStartNumber(start.value);
    if (!contactIds.length || first === null) {
      appendNotice("Auto Pin needs loaded contacts and a whole-number Start from 0 to 1000000000.", true);
      return;
    }
    writeSession("cableBundler.autoPinStart", String(first));
    apply.disabled = true;
    void send("auto_pin_interface_contacts", {
      harnessId, interfaceId, contactIds, start: first,
      hopscotch: hopscotch.checked, overwrite: overwrite.checked,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not pin contacts.");
      form.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { apply.disabled = false; });
  });
  form.append(directionLabel, startLabel, hopscotchLabel, zigzagLabel, spiralLabel,
    overwriteLabel, apply, cancel);
  naming.append(form);
  start.focus();
  start.select();
}
