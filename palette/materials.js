function colorFromHex(name, hex) {
  const normalized = /^#[0-9a-f]{6}$/i.test(hex) ? hex.slice(1) : "202020";
  return {
    name: name.trim() || "Custom",
    red: Number.parseInt(normalized.slice(0, 2), 16),
    green: Number.parseInt(normalized.slice(2, 4), 16),
    blue: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

let copiedMaterialColor = null;

/** Add Copy and Paste actions to one editable material-color swatch. */
function addMaterialColorContextMenu(root, picker, readName, pasteColor) {
  root.classList.add("material-color-context");
  const showMenu = addContextMenu(root, picker);
  picker.addEventListener("contextmenu", (event) => {
    showMenu(event, [
      {
        label: "Copy",
        disabled: picker.disabled,
        action: () => {
          copiedMaterialColor = {
            name: readName().trim() || "Custom",
            hex: picker.value,
          };
        },
      },
      {
        label: "Paste",
        disabled: picker.disabled || copiedMaterialColor === null,
        action: () => pasteColor(copiedMaterialColor),
      },
    ]);
  });
}

/** Attach the controlled material-catalog suggestions used by text inputs. */
function addMaterialAutocomplete(wrapper, input, values, onChoose = () => {}) {
  const menu = document.createElement("div");
  const available = values.map((value) => typeof value === "string" ? value : value.name);
  wrapper.classList.add("autocomplete");
  menu.className = "autocomplete-suggestions";
  menu.hidden = true;
  const renderSuggestions = () => {
    const query = input.value.trim().toLocaleLowerCase();
    const matches = available.filter(
      (value) => !query || value.toLocaleLowerCase().includes(query),
    ).slice(0, 16);
    menu.replaceChildren();
    matches.forEach((value) => {
      const choice = document.createElement("button");
      choice.type = "button";
      choice.textContent = value;
      choice.addEventListener("mousedown", (event) => event.preventDefault());
      choice.addEventListener("click", () => {
        input.value = value;
        menu.hidden = true;
        onChoose(value);
      });
      menu.append(choice);
    });
    menu.hidden = matches.length === 0;
  };
  input.addEventListener("click", renderSuggestions);
  input.addEventListener("input", renderSuggestions);
  input.addEventListener("blur", () => { menu.hidden = true; });
  wrapper.append(menu);
}

/** Build one labeled text property with optional controlled catalog suggestions. */
function createMaterialTextField(settings, key, labelText, suggestions = [], multiline = false) {
  const wrapper = document.createElement("div");
  const header = document.createElement("div");
  const label = document.createElement("strong");
  const input = document.createElement(multiline ? "textarea" : "input");
  wrapper.className = "material-field";
  header.className = "material-field-heading";
  label.textContent = labelText;
  if (!multiline) input.type = "text";
  input.className = "filter";
  input.value = settings[key] || "";
  header.append(label);
  wrapper.append(header, input);
  if (!multiline && suggestions.length) {
    addMaterialAutocomplete(wrapper, input, suggestions);
  }
  return { wrapper, header, input };
}

/** Normalize a harness length-unit descriptor, retaining millimeters as fallback. */
function cableLengthUnits(harness) {
  const symbol = harness?.lengthUnits?.symbol;
  const millimetersPerUnit = Number(harness?.lengthUnits?.millimetersPerUnit);
  if (typeof symbol !== "string" || !symbol
      || !Number.isFinite(millimetersPerUnit) || millimetersPerUnit <= 0) {
    return { symbol: "mm", millimetersPerUnit: 1 };
  }
  return { symbol, millimetersPerUnit };
}

/** Format a persisted millimeter value in the active design length unit. */
function displayLengthValue(valueMm, units) {
  return `${Number((valueMm / units.millimetersPerUnit).toPrecision(8))}`;
}

/** Build an Auto-or-explicit conductor diameter tied to an outer diameter input. */
function createConductorDiameterField(outerDiameter, configuredDiameterMm, units) {
  const wrapper = document.createElement("div");
  const header = document.createElement("div");
  const label = document.createElement("strong");
  const hint = document.createElement("span");
  const input = document.createElement("input");
  wrapper.className = "material-field conductor-diameter-field";
  header.className = "material-field-heading";
  label.textContent = `Conductor Diameter (${units.symbol})`;
  hint.className = "conductor-diameter-hint";
  input.type = "text";
  input.className = "filter";
  input.value = configuredDiameterMm == null
    ? "auto" : displayLengthValue(configuredDiameterMm, units);
  const updateHint = () => {
    const diameter = Number(outerDiameter.value);
    hint.textContent = Number.isFinite(diameter) && diameter > 0
      ? `Auto = ${Number((diameter * 0.75).toPrecision(8))} ${units.symbol} (75%)`
      : "Auto = 75% of diameter";
  };
  const read = () => {
    const value = input.value.trim();
    if (value.toLocaleLowerCase() === "auto") return null;
    const conductorDiameter = Number(value);
    const outerDiameterValue = Number(outerDiameter.value);
    if (!Number.isFinite(conductorDiameter) || conductorDiameter <= 0) {
      throw new Error(
        `Conductor diameter must be Auto or a positive number in ${units.symbol}.`,
      );
    }
    if (Number.isFinite(outerDiameterValue) && conductorDiameter > outerDiameterValue) {
      throw new Error("Conductor diameter cannot exceed the cable or connection diameter.");
    }
    return conductorDiameter * units.millimetersPerUnit;
  };
  outerDiameter.addEventListener("input", updateHint);
  header.append(label, hint);
  wrapper.append(header, input);
  updateHint();
  return { wrapper, input, hint, read };
}

/** Build an ordered key/value editor with optional parent inheritance controls. */
function createMetadataEditor(parentEntries, overrideEntries = null) {
  const wrapper = document.createElement("section");
  const heading = document.createElement("div");
  const title = document.createElement("strong");
  const add = document.createElement("button");
  const list = document.createElement("div");
  const isCableGroup = overrideEntries !== null;
  const parentByKey = new Map(
    (parentEntries || []).map((entry) => [entry.key.trim().toLocaleLowerCase(), entry]),
  );
  const overridesByKey = new Map(
    (overrideEntries || []).map((entry) => [entry.key.trim().toLocaleLowerCase(), entry]),
  );
  wrapper.className = "metadata-editor";
  heading.className = "metadata-heading";
  title.textContent = "Custom Metadata";
  add.type = "button";
  add.className = "button compact";
  add.textContent = "Add Field";
  list.className = "metadata-list";
  heading.append(title, add);
  wrapper.append(heading, list);

  const appendRow = (entry = { key: "", value: "" }, inherited = false) => {
    const row = document.createElement("div");
    const key = document.createElement("input");
    const value = document.createElement("input");
    const remove = document.createElement("button");
    key.type = "text";
    key.className = "filter metadata-key";
    key.placeholder = "Key";
    key.setAttribute("aria-label", "Metadata key");
    key.value = entry.key || "";
    value.type = "text";
    value.className = "filter metadata-value";
    value.placeholder = "Value";
    value.setAttribute("aria-label", `${entry.key || "Metadata"} value`);
    value.value = entry.value || "";
    remove.type = "button";
    remove.className = "button compact metadata-row-action";
    row.className = "metadata-row";
    row.append(key, value);

    let override = null;
    if (isCableGroup && inherited) {
      const inheritedEntry = parentByKey.get(entry.key.trim().toLocaleLowerCase());
      const overrideLabel = document.createElement("label");
      const overrideText = document.createElement("span");
      override = document.createElement("input");
      override.type = "checkbox";
      override.checked = overridesByKey.has(entry.key.trim().toLocaleLowerCase());
      overrideText.textContent = "Override";
      key.disabled = true;
      const update = () => {
        value.disabled = !override.checked;
        if (!override.checked) value.value = inheritedEntry.value;
      };
      override.addEventListener("change", update);
      overrideLabel.className = "metadata-override";
      overrideLabel.append(override, overrideText);
      row.append(overrideLabel);
      update();
    } else {
      remove.textContent = "Remove";
      remove.addEventListener("click", () => row.remove());
      row.append(remove);
    }
    row.metadataControls = { key, value, inherited, override };
    list.append(row);
  };

  (parentEntries || []).forEach((parentEntry) => {
    const normalizedKey = parentEntry.key.trim().toLocaleLowerCase();
    appendRow(overridesByKey.get(normalizedKey) || parentEntry, isCableGroup);
  });
  if (isCableGroup) {
    (overrideEntries || []).filter(
      (entry) => !parentByKey.has(entry.key.trim().toLocaleLowerCase()),
    ).forEach((entry) => appendRow(entry));
  }
  add.addEventListener("click", () => appendRow());

  const read = () => {
    const rows = [...list.children].map((row) => row.metadataControls);
    const keys = new Set();
    rows.forEach((controls) => {
      const key = controls.key.value.trim();
      if (!key) throw new Error("Every metadata row needs a key.");
      const normalizedKey = key.toLocaleLowerCase();
      if (keys.has(normalizedKey)) {
        throw new Error("Metadata keys must be unique ignoring case.");
      }
      keys.add(normalizedKey);
    });
    return rows.filter(
      (controls) => !controls.inherited || controls.override.checked,
    ).map((controls) => ({
      key: controls.key.value.trim(), value: controls.value.value,
    }));
  };
  return { wrapper, read };
}

/** Open inheritable harness properties or one connected cable group's overrides. */
function openPropertiesDialog(harness, cableGroup = null) {
  const isCableGroup = cableGroup !== null;
  const { dialog, form, heading, note, error, actions, cancel, save } = createOptionsDialog(
    `cable-options ${isCableGroup ? "cable-group-properties" : "harness-properties"}`,
  );
  const settings = isCableGroup ? cableGroup.materials : harness.materialDefaults;
  const overrides = isCableGroup ? cableGroup.materialOverrides : null;
  const controls = {};
  const units = cableLengthUnits(harness);
  const catalog = currentState.catalog || {
    insulationMaterials: [], conductorMaterials: [], colors: [], stripePatterns: [],
  };
  heading.textContent = isCableGroup ? "Connected Cable Properties" : "Harness Properties";
  note.textContent = isCableGroup
    ? "Checked property fields override this harness for the connected cable group."
    : "These values are inherited by connected cable groups unless they override a field.";
  form.append(heading, note);

  let diameter = null;
  let conductorDiameter = null;
  if (isCableGroup) {
    const diameterLabel = document.createElement("label");
    diameter = document.createElement("input");
    diameterLabel.textContent = `Diameter (${units.symbol})`;
    diameter.type = "number";
    diameter.className = "filter";
    diameter.step = "any";
    diameter.required = true;
    diameter.value = displayLengthValue(cableGroup.diameterMm, units);
    diameterLabel.append(diameter);
    form.append(diameterLabel);
  }

  const addMaterialField = (key, labelText, suggestions = [], multiline = false) => {
    const { wrapper, header, input } = createMaterialTextField(
      settings, key, labelText, suggestions, multiline,
    );
    let toggle = null;
    if (isCableGroup) {
      const toggleLabel = document.createElement("label");
      const toggleText = document.createElement("span");
      toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = overrides[key] !== null;
      toggleText.textContent = "Override";
      const update = () => { input.disabled = !toggle.checked; };
      toggle.addEventListener("change", update);
      toggleLabel.append(toggle, toggleText);
      header.append(toggleLabel);
      update();
    }
    form.append(wrapper);
    controls[key] = { input, toggle, wrapper };
  };
  addMaterialField(
    "insulationMaterial", "Insulation Material", catalog.insulationMaterials,
  );
  addMaterialField(
    "conductorMaterial", "Conductor Material", catalog.conductorMaterials,
  );
  if (isCableGroup) {
    conductorDiameter = createConductorDiameterField(
      diameter, cableGroup.conductorDiameterMm, units,
    );
    form.append(conductorDiameter.wrapper);
  }
  addMaterialField("shielding", "Shielding");
  addMaterialField("dielectricMaterial", "Dielectric Material");
  const updateDielectricVisibility = () => {
    controls.dielectricMaterial.wrapper.hidden
      = controls.shielding.input.value.trim() === "";
  };
  controls.shielding.input.addEventListener("input", updateDielectricVisibility);
  controls.shielding.toggle?.addEventListener("change", updateDielectricVisibility);
  updateDielectricVisibility();
  addMaterialField("manufacturer", "Manufacturer");
  addMaterialField("partNumber", "Part Number");
  const metadataEditor = createMetadataEditor(
    harness.metadata || [], isCableGroup ? cableGroup.metadataOverrides || [] : null,
  );
  form.append(metadataEditor.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const diameterValue = isCableGroup ? Number(diameter.value) : null;
    const diameterMm = isCableGroup ? diameterValue * units.millimetersPerUnit : null;
    if (isCableGroup && (!Number.isFinite(diameterMm) || diameterMm <= 0)) {
      error.textContent = `Enter a positive diameter in ${units.symbol}.`;
      return;
    }
    let conductorDiameterMm = null;
    if (isCableGroup) {
      try {
        conductorDiameterMm = conductorDiameter.read();
      } catch (failure) {
        error.textContent = failure.message;
        return;
      }
    }
    const fieldValue = (key) => isCableGroup && !controls[key].toggle.checked
      ? null : controls[key].input.value;
    const insulationMaterial = fieldValue("insulationMaterial");
    const conductorMaterial = fieldValue("conductorMaterial");
    const shielding = fieldValue("shielding");
    const dielectricMaterial = controls.dielectricMaterial.wrapper.hidden
      ? (isCableGroup ? null : "") : fieldValue("dielectricMaterial");
    const manufacturer = fieldValue("manufacturer");
    const partNumber = fieldValue("partNumber");
    if (insulationMaterial !== null && !insulationMaterial.trim()) {
      error.textContent = "Insulation material must not be empty.";
      return;
    }
    if (conductorMaterial !== null && !conductorMaterial.trim()) {
      error.textContent = "Conductor material must not be empty.";
      return;
    }
    cancel.disabled = true;
    save.disabled = true;
    try {
      const response = await send(
        isCableGroup ? "set_cable_group_properties" : "set_harness_properties",
        isCableGroup
          ? {
            harnessId: harness.harnessId,
            cableGroupId: cableGroup.cableGroupId,
            diameterMm,
            conductorDiameterMm,
            insulationMaterial,
            conductorMaterial,
            shielding,
            dielectricMaterial,
            manufacturer,
            partNumber,
            metadataOverrides: metadataEditor.read(),
          }
          : {
            harnessId: harness.harnessId,
            insulationMaterial,
            conductorMaterial,
            shielding,
            dielectricMaterial,
            manufacturer,
            partNumber,
            metadata: metadataEditor.read(),
          },
      );
      if (response.ok) dialog.close();
      else error.textContent = response.error || `Could not save ${
        isCableGroup ? "connected-cable" : "harness"
      } properties.`;
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      cancel.disabled = false;
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

/** Open parent properties inherited by connected cable groups. */
function openHarnessProperties(harness) {
  openPropertiesDialog(harness);
}

/** Open one connected cable group's inherited construction properties. */
function openCableGroupProperties(harness, cableGroup) {
  openPropertiesDialog(harness, cableGroup);
}

/** Open a metadata-only properties dialog for one identity-owned harness entity. */
function openEntityMetadataProperties(
  harness, entity, title, className, action, identityPayload,
) {
  const { dialog, form, heading, error, actions, cancel, save } = createOptionsDialog(
    `cable-options ${className}`,
  );
  const metadataEditor = createMetadataEditor(entity.metadata || []);
  heading.textContent = title;
  form.append(heading, metadataEditor.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    cancel.disabled = true;
    save.disabled = true;
    try {
      const response = await send(action, {
        harnessId: harness.harnessId,
        ...identityPayload,
        metadata: metadataEditor.read(),
      });
      if (response.ok) dialog.close();
      else error.textContent = response.error || `Could not save ${title.toLowerCase()}.`;
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      cancel.disabled = false;
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

/** Open searchable custom metadata owned by one pathway. */
function openPathwayProperties(harness, pathway) {
  openEntityMetadataProperties(
    harness, pathway, "Pathway Properties", "pathway-properties", "set_pathway_properties",
    { pathwayId: pathway.pathwayId },
  );
}

/** Open searchable custom metadata owned by one pathway boundary. */
function openPathwayEndProperties(harness, pathway, endpoint) {
  const side = endpoint === "start" ? "A" : "B";
  const metadata = endpoint === "start" ? pathway.startMetadata : pathway.endMetadata;
  openEntityMetadataProperties(
    harness, { metadata }, `Pathway End ${side} Properties`, "pathway-end-properties",
    "set_pathway_end_properties", { pathwayId: pathway.pathwayId, endpoint },
  );
}

/** Open searchable custom metadata owned by one junction. */
function openJunctionProperties(harness, junction) {
  openEntityMetadataProperties(
    harness, junction, "Junction Properties", "junction-properties", "set_junction_properties",
    { junctionId: junction.junctionId },
  );
}

/** Open searchable custom metadata owned by one cable end. */
function openCableEndProperties(harness, connectionId) {
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === connectionId,
  );
  if (!connection) return;
  openEntityMetadataProperties(
    harness, connection, "Cable End Properties", "cable-end-properties",
    "set_cable_end_properties", { connectionId },
  );
}

/** Return direct siblings of one connection node in stable display order. */
function cableEndAttachmentSiblings(connection, attachment) {
  return (connection.attachments || []).filter(
    (candidate) => (candidate.parentAttachmentId || null)
      === (attachment.parentAttachmentId || null),
  );
}

/** Resolve the diameter inherited by one connection node from its immediate parent. */
function cableEndAttachmentParentDiameter(cableGroup, connection, attachment) {
  if (!attachment.parentAttachmentId) return cableGroup.diameterMm;
  const parent = (connection.attachments || []).find(
    (candidate) => candidate.attachmentId === attachment.parentAttachmentId,
  );
  if (!parent) return cableGroup.diameterMm;
  const siblings = cableEndAttachmentSiblings(connection, parent);
  const inherited = cableEndAttachmentParentDiameter(cableGroup, connection, parent)
    / Math.max(1, siblings.length);
  if (siblings.length <= 1) return inherited;
  return parent.visualOverrides?.diameterMm ?? inherited;
}

/** Resolve materials inherited by one connection node from its immediate parent. */
function cableEndAttachmentParentMaterials(cableGroup, connection, attachment) {
  if (!attachment.parentAttachmentId) return cableGroup.materials;
  const parent = (connection.attachments || []).find(
    (candidate) => candidate.attachmentId === attachment.parentAttachmentId,
  );
  if (!parent) return cableGroup.materials;
  const inherited = cableEndAttachmentParentMaterials(cableGroup, connection, parent);
  const siblings = cableEndAttachmentSiblings(connection, parent);
  const overrides = parent.visualOverrides || {};
  if (siblings.length <= 1) {
    const shielding = overrides.shielding ?? inherited.shielding;
    const dielectricMaterial = overrides.dielectricMaterial ?? inherited.dielectricMaterial;
    return {
      ...inherited,
      shielding,
      dielectricMaterial: shielding?.trim() ? dielectricMaterial : "",
    };
  }
  const resolved = {
    ...inherited,
    ...Object.fromEntries(
      [
        "insulationMaterial", "conductorMaterial", "shielding", "dielectricMaterial",
        "manufacturer", "partNumber",
        "mainColor", "appearance", "stripes", "pullback",
      ]
        .filter((key) => overrides[key] !== null && overrides[key] !== undefined)
        .map((key) => [key, overrides[key]]),
    ),
  };
  return {
    ...resolved,
    dielectricMaterial: resolved.shielding?.trim() ? resolved.dielectricMaterial : "",
  };
}

/** Resolve construction values owned by one branch under the domain inheritance rules. */
function cableEndAttachmentMaterials(cableGroup, connection, attachment) {
  const inherited = cableEndAttachmentParentMaterials(cableGroup, connection, attachment);
  const siblings = cableEndAttachmentSiblings(connection, attachment);
  const overrides = attachment.visualOverrides || {};
  if (siblings.length <= 1) {
    const shielding = overrides.shielding ?? inherited.shielding;
    const dielectricMaterial = overrides.dielectricMaterial ?? inherited.dielectricMaterial;
    return {
      ...inherited,
      shielding,
      dielectricMaterial: shielding?.trim() ? dielectricMaterial : "",
    };
  }
  const resolved = {
    ...inherited,
    ...Object.fromEntries(
      [
        "insulationMaterial", "conductorMaterial", "shielding", "dielectricMaterial",
        "manufacturer", "partNumber",
        "pullback",
      ]
        .filter((key) => overrides[key] !== null && overrides[key] !== undefined)
        .map((key) => [key, overrides[key]]),
    ),
  };
  return {
    ...resolved,
    dielectricMaterial: resolved.shielding?.trim() ? resolved.dielectricMaterial : "",
  };
}

/** Append shielding and its conditionally available dielectric override. */
function appendShieldingOverrideControls(form, inherited, overrides) {
  const addControl = (key, labelText) => {
    const { wrapper, header, input } = createMaterialTextField(
      { [key]: overrides[key] ?? inherited[key] }, key, labelText, [],
    );
    const toggleLabel = document.createElement("label");
    const toggle = document.createElement("input");
    const toggleText = document.createElement("span");
    toggle.type = "checkbox";
    toggle.checked = overrides[key] !== null && overrides[key] !== undefined;
    toggleText.textContent = "Override";
    const update = () => {
      input.disabled = !toggle.checked;
      if (!toggle.checked) input.value = inherited[key];
    };
    toggle.addEventListener("change", update);
    toggleLabel.append(toggle, toggleText);
    header.append(toggleLabel);
    update();
    form.append(wrapper);
    return { input, toggle, wrapper };
  };
  const shielding = addControl("shielding", "Shielding");
  const dielectricMaterial = addControl("dielectricMaterial", "Dielectric Material");
  const updateDielectricVisibility = () => {
    dielectricMaterial.wrapper.hidden = shielding.input.value.trim() === "";
  };
  shielding.input.addEventListener("input", updateDielectricVisibility);
  shielding.toggle.addEventListener("change", updateDielectricVisibility);
  updateDielectricVisibility();
  return { shielding, dielectricMaterial };
}

/** Open construction overrides and metadata owned by one divided connection branch. */
function openCableEndAttachmentProperties(harness, cableGroup, attachment) {
  if (!attachment) return;
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === attachment.connectionId,
  );
  const siblings = connection ? cableEndAttachmentSiblings(connection, attachment) : [];
  if (!cableGroup || !connection) {
    openEntityMetadataProperties(
      harness, attachment, "Connection Properties", "connection-properties",
      "set_cable_end_attachment_properties", {
        connectionId: attachment.connectionId,
        attachmentId: attachment.attachmentId,
      },
    );
    return;
  }
  const overrides = attachment.visualOverrides || {};
  const inheritedMaterials = cableEndAttachmentParentMaterials(
    cableGroup, connection, attachment,
  );
  if (siblings.length <= 1) {
    const { dialog, form, heading, error, actions, cancel, save } = createOptionsDialog(
      "cable-options connection-properties",
    );
    heading.textContent = "Connection Properties";
    form.append(heading);
    const shieldingControls = appendShieldingOverrideControls(
      form, inheritedMaterials, overrides,
    );
    const metadataEditor = createMetadataEditor(attachment.metadata || []);
    form.append(metadataEditor.wrapper);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      cancel.disabled = true;
      save.disabled = true;
      try {
        const response = await send("set_cable_end_attachment_shielding", {
          harnessId: harness.harnessId,
          connectionId: attachment.connectionId,
          attachmentId: attachment.attachmentId,
          shielding: shieldingControls.shielding.toggle.checked
            ? shieldingControls.shielding.input.value.trim() : null,
          dielectricMaterial: shieldingControls.dielectricMaterial.wrapper.hidden
            ? null
            : (shieldingControls.dielectricMaterial.toggle.checked
              ? shieldingControls.dielectricMaterial.input.value.trim() : null),
          metadata: metadataEditor.read(),
        });
        if (response.ok) dialog.close();
        else error.textContent = response.error || "Could not save connection properties.";
      } catch (failure) {
        error.textContent = failure.message;
      } finally {
        cancel.disabled = false;
        save.disabled = false;
      }
    });
    dialog.addEventListener("close", () => dialog.remove());
    actions.append(cancel, save);
    form.append(error, actions);
    dialog.append(form);
    document.body.append(dialog);
    dialog.showModal();
    return;
  }
  const parentDiameter = cableEndAttachmentParentDiameter(cableGroup, connection, attachment);
  const inheritedDiameter = parentDiameter / siblings.length;
  const units = cableLengthUnits(harness);
  const { dialog, form, heading, error, actions, cancel, save } = createOptionsDialog(
    "cable-options connection-properties",
  );
  const diameterLabel = document.createElement("label");
  const diameter = document.createElement("input");
  diameterLabel.textContent = `Diameter (${units.symbol})`;
  diameter.type = "number";
  diameter.className = "filter";
  diameter.step = "any";
  diameter.required = true;
  diameter.value = displayLengthValue(overrides.diameterMm ?? inheritedDiameter, units);
  diameterLabel.append(diameter);
  heading.textContent = "Connection Properties";
  form.append(heading, diameterLabel);

  const materialControls = {};
  const addMaterialOverride = (key, labelText, suggestions) => {
    const values = { [key]: overrides[key] ?? inheritedMaterials[key] };
    const { wrapper, header, input } = createMaterialTextField(
      values, key, labelText, suggestions,
    );
    const toggleLabel = document.createElement("label");
    const toggle = document.createElement("input");
    const toggleText = document.createElement("span");
    toggle.type = "checkbox";
    toggle.checked = overrides[key] !== null && overrides[key] !== undefined;
    toggleText.textContent = "Override";
    const update = () => {
      input.disabled = !toggle.checked;
      if (!toggle.checked) input.value = inheritedMaterials[key];
    };
    toggle.addEventListener("change", update);
    toggleLabel.append(toggle, toggleText);
    header.append(toggleLabel);
    update();
    form.append(wrapper);
    materialControls[key] = { input, toggle, wrapper };
  };
  const catalog = currentState.catalog || { insulationMaterials: [], conductorMaterials: [] };
  addMaterialOverride(
    "insulationMaterial", "Insulation Material", catalog.insulationMaterials || [],
  );
  addMaterialOverride(
    "conductorMaterial", "Conductor Material", catalog.conductorMaterials || [],
  );
  const conductorDiameter = createConductorDiameterField(
    diameter, overrides.conductorDiameterMm, units,
  );
  form.append(conductorDiameter.wrapper);
  addMaterialOverride("shielding", "Shielding", []);
  addMaterialOverride("dielectricMaterial", "Dielectric Material", []);
  const updateDielectricVisibility = () => {
    materialControls.dielectricMaterial.wrapper.hidden
      = materialControls.shielding.input.value.trim() === "";
  };
  materialControls.shielding.input.addEventListener("input", updateDielectricVisibility);
  materialControls.shielding.toggle.addEventListener("change", updateDielectricVisibility);
  updateDielectricVisibility();
  addMaterialOverride("manufacturer", "Manufacturer", []);
  addMaterialOverride("partNumber", "Part Number", []);
  const metadataEditor = createMetadataEditor(attachment.metadata || []);
  form.append(metadataEditor.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const diameterMm = Number(diameter.value) * units.millimetersPerUnit;
      if (!Number.isFinite(diameterMm) || diameterMm <= 0) {
        throw new Error("Diameter must be a positive number.");
      }
      const conductorDiameterMm = conductorDiameter.read();
      const combinedDiameter = siblings.reduce((total, candidate) => {
        if (candidate.attachmentId === attachment.attachmentId) return total + diameterMm;
        return total + (candidate.visualOverrides?.diameterMm ?? inheritedDiameter);
      }, 0);
      if (combinedDiameter > parentDiameter + 1e-9) {
        throw new Error(
          "Connection diameters cannot collectively exceed the parent cable diameter.",
        );
      }
      const insulationMaterial = materialControls.insulationMaterial.toggle.checked
        ? materialControls.insulationMaterial.input.value.trim() : null;
      const conductorMaterial = materialControls.conductorMaterial.toggle.checked
        ? materialControls.conductorMaterial.input.value.trim() : null;
      const shielding = materialControls.shielding.toggle.checked
        ? materialControls.shielding.input.value.trim() : null;
      const dielectricMaterial = materialControls.dielectricMaterial.wrapper.hidden
        ? null
        : (materialControls.dielectricMaterial.toggle.checked
          ? materialControls.dielectricMaterial.input.value.trim() : null);
      const manufacturer = materialControls.manufacturer.toggle.checked
        ? materialControls.manufacturer.input.value.trim() : null;
      const partNumber = materialControls.partNumber.toggle.checked
        ? materialControls.partNumber.input.value.trim() : null;
      if (insulationMaterial === "" || conductorMaterial === "") {
        throw new Error("Enabled material overrides must not be empty.");
      }
      cancel.disabled = true;
      save.disabled = true;
      const response = await send("set_cable_end_attachment_properties", {
        harnessId: harness.harnessId,
        connectionId: attachment.connectionId,
        attachmentId: attachment.attachmentId,
        diameterMm,
        conductorDiameterMm,
        insulationMaterial,
        conductorMaterial,
        shielding,
        dielectricMaterial,
        manufacturer,
        partNumber,
        metadata: metadataEditor.read(),
      });
      if (response.ok) dialog.close();
      else error.textContent = response.error || "Could not save connection properties.";
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      cancel.disabled = false;
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
