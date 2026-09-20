/** Retain pathway interactions that are independent of legacy persistent cables. */

function enableSequenceDrag(
  sequence, memberRows, row, memberIndex, onMove, onActivate = null,
  locked = false, lockedIndexes = new Set(),
) {
  const position = document.createElement("span");
  position.className = "sequence-position";
  position.textContent = `${memberIndex + 1}`;
  position.setAttribute("aria-label", `Position ${memberIndex + 1}`);
  row.insertBefore(position, row.children[0]);
  row.dataset.reorder = locked ? "locked" : "true";
  memberRows.push(row);
  if (locked) return;
  let drag = null;
  const clearDrag = () => {
    drag = null;
    delete row.dataset.dragging;
    memberRows.forEach((item) => { delete item.dataset.drop; });
  };
  row.addEventListener("dragstart", (event) => event.preventDefault());
  row.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest(".icon-button")) return;
    drag = { x: event.clientX, y: event.clientY, active: false, target: memberIndex };
    row.setPointerCapture(event.pointerId);
  });
  row.addEventListener("pointermove", (event) => {
    if (!drag) return;
    if (!drag.active && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5) return;
    event.preventDefault();
    drag.active = true;
    row.dataset.dragging = "true";
    memberRows.forEach((item) => { delete item.dataset.drop; });
    const bounds = sequence.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top - 12 || event.clientY > bounds.bottom + 12) {
      drag.target = null;
      return;
    }
    const others = memberRows.filter((item) => item !== row);
    const next = others.findIndex((item) => {
      const rect = item.getBoundingClientRect();
      return event.clientY < rect.top + rect.height / 2;
    });
    drag.target = next < 0 ? others.length : next;
    if (lockedIndexes.has(0)) drag.target = Math.max(1, drag.target);
    if (lockedIndexes.has(memberRows.length - 1)) {
      drag.target = Math.min(memberRows.length - 2, drag.target);
    }
    if (others.length) {
      const marker = memberRows[drag.target] || memberRows[memberRows.length - 1];
      marker.dataset.drop = drag.target >= memberRows.length - 1 ? "after" : "before";
    }
  });
  row.addEventListener("pointerup", (event) => {
    if (!drag) return;
    const target = drag.target;
    const clicked = !drag.active;
    const moved = drag.active && target !== null && target !== memberIndex;
    clearDrag();
    if (row.hasPointerCapture(event.pointerId)) row.releasePointerCapture(event.pointerId);
    if (moved) onMove(target);
    else if (clicked && onActivate) onActivate();
  });
  row.addEventListener("pointercancel", clearDrag);
  row.addEventListener("lostpointercapture", clearDrag);
}

/** Open interpolation settings for harness defaults or one pathway gate. */
function openInterpolationOptions(
  harness, target, targetId = null, name = "", settings = {}, useDefaults = false,
) {
  if (!["defaults", "gate"].includes(target)) {
    throw new TypeError(`Unsupported pathway interpolation target: ${target}`);
  }
  const { dialog, form, heading, note, error, actions, cancel, save } = createOptionsDialog(
    "cable-options",
  );
  const isDefaults = target === "defaults";
  heading.textContent = isDefaults ? "Generation defaults" : `Interpolation · ${name}`;
  dialog.setAttribute("aria-label", heading.textContent);
  note.textContent = "Leave a distance blank for Auto. The harness relaxation preset sets Auto's preferred curve extent; safe bend minimums may expand it, crowded values are reduced to the feasible range, and crowded spans use a direct profile-to-profile curve when it preserves that radius. "
    + (isDefaults
      ? "Distance presets are used for new controls. Existing controls follow defaults unless individually customized. The relaxation preset applies to every Auto distance in this harness."
      : "Approach and departure follow the gate traversal order. Changes affect all cable groups through this gate.");
  form.append(heading, note);
  const applyExisting = document.createElement("input");
  applyExisting.type = "checkbox";
  applyExisting.checked = true;
  if (isDefaults) {
    const applyLabel = document.createElement("label");
    const applyText = document.createElement("span");
    applyLabel.className = "apply-existing";
    applyText.textContent = "Update existing controls using defaults";
    applyExisting.setAttribute("aria-label", applyText.textContent);
    applyLabel.append(applyExisting, applyText);
    form.append(applyLabel);
  }
  const status = document.createElement("p");
  const updateStatus = () => {
    status.textContent = useDefaults ? "Using harness defaults" : "Custom settings";
  };
  if (!isDefaults) {
    updateStatus();
    form.append(status);
  }
  const fields = [];
  const addFields = (prefix, initial, endSection) => {
    const inputs = {};
    for (const [key, text] of [
      ["approach_mm", endSection ? "Terminal-side transition" : "Approach transition"],
      ["departure_mm", endSection ? "Pathway-side transition" : "Departure transition"],
    ]) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      label.textContent = `${prefix}${text} (mm)`;
      input.type = "number";
      input.className = "filter";
      input.step = "any";
      input.min = "0";
      input.placeholder = "Auto";
      input.value = initial?.[key] == null ? "" : `${initial[key]}`;
      input.addEventListener("input", () => {
        useDefaults = false;
        updateStatus();
      });
      input.setAttribute("aria-label", label.textContent);
      label.append(input);
      form.append(label);
      fields.push(input);
      inputs[key] = input;
    }
    return inputs;
  };
  const primary = addFields(
    isDefaults ? "Gates · " : "",
    isDefaults ? harness.gateDefaults : settings,
    false,
  );
  const ends = isDefaults ? addFields("Ends · ", harness.endDefaults, true) : null;
  let minimumClearance = null;
  let autoTransitionPreset = null;
  const autoTransitionPresets = ["tight", "compact", "balanced", "relaxed", "loose"];
  if (isDefaults) {
    const presetField = document.createElement("div");
    const presetLabel = document.createElement("label");
    const presetHeading = document.createElement("span");
    const presetTitle = document.createElement("span");
    const presetValue = document.createElement("output");
    autoTransitionPreset = document.createElement("input");
    presetField.className = "auto-transition-preset";
    presetHeading.className = "auto-transition-heading";
    presetTitle.textContent = "Automatic transition relaxation";
    autoTransitionPreset.type = "range";
    autoTransitionPreset.min = "0";
    autoTransitionPreset.max = `${autoTransitionPresets.length - 1}`;
    autoTransitionPreset.step = "1";
    autoTransitionPreset.value = `${Math.max(
      0, autoTransitionPresets.indexOf(harness.autoTransitionPreset || "tight"),
    )}`;
    autoTransitionPreset.setAttribute("aria-label", presetTitle.textContent);
    const updatePresetValue = () => {
      const preset = autoTransitionPresets[Number(autoTransitionPreset.value)];
      const display = `${preset.charAt(0).toUpperCase()}${preset.slice(1)}`;
      presetValue.textContent = display;
      autoTransitionPreset.setAttribute("aria-valuetext", display);
    };
    autoTransitionPreset.addEventListener("input", updatePresetValue);
    presetHeading.append(presetTitle, presetValue);
    presetLabel.append(presetHeading, autoTransitionPreset);
    presetField.append(presetLabel);
    form.append(presetField);
    updatePresetValue();

    const clearanceLabel = document.createElement("label");
    minimumClearance = document.createElement("input");
    clearanceLabel.textContent = "Minimum member gap (mm)";
    minimumClearance.type = "number";
    minimumClearance.className = "filter";
    minimumClearance.step = "any";
    minimumClearance.min = "0";
    minimumClearance.required = true;
    minimumClearance.value = `${harness.minimumClearanceMm ?? 0}`;
    minimumClearance.setAttribute("aria-label", clearanceLabel.textContent);
    clearanceLabel.append(minimumClearance);
    form.append(clearanceLabel);
    fields.push(minimumClearance);
  }
  if (!isDefaults) {
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "button";
    reset.textContent = "Use harness defaults";
    reset.addEventListener("click", () => {
      useDefaults = true;
      updateStatus();
      for (const [key, input] of Object.entries(primary)) {
        input.value = harness.gateDefaults?.[key] == null
          ? "" : `${harness.gateDefaults[key]}`;
      }
    });
    form.append(reset);
  }
  const values = (inputs) => Object.fromEntries(Object.entries(inputs).map(([key, input]) => (
    [key, input.value.trim() === "" ? null : Number(input.value)]
  )));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (fields.some((input) => input.validity?.badInput || (input.value.trim() !== ""
      && (!Number.isFinite(Number(input.value)) || Number(input.value) < 0)))) {
      error.textContent = "Enter nonnegative distances in millimeters, or leave blank for Auto.";
      return;
    }
    save.disabled = true;
    try {
      const response = await send("set_interpolation", {
        harnessId: harness.harnessId,
        target,
        targetId,
        useDefaults,
        settings: values(primary),
        ...(ends ? { endDefaults: values(ends), applyExisting: applyExisting.checked } : {}),
        ...(minimumClearance ? { minimumClearanceMm: Number(minimumClearance.value) } : {}),
        ...(autoTransitionPreset ? {
          autoTransitionPreset: autoTransitionPresets[Number(autoTransitionPreset.value)],
        } : {}),
      });
      if (response.ok) dialog.close();
      else error.textContent = response.error || "Could not save interpolation options.";
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      save.disabled = false;
    }
  });
  dialog.addEventListener("close", () => dialog.remove());
  actions.append(cancel, save);
  form.append(error, actions);
  dialog.append(form);
  document.body.append(dialog);
  dialog.showModal();
}
