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
  const catalog = currentState.catalog || {
    insulationMaterials: [], conductorMaterials: [], colors: [], stripePatterns: [],
  };
  heading.textContent = isCableGroup ? "Connected Cable Properties" : "Harness Properties";
  note.textContent = isCableGroup
    ? "Checked property fields override this harness for the connected cable group."
    : "These values are inherited by connected cable groups unless they override a field.";
  form.append(heading, note);

  let diameter = null;
  if (isCableGroup) {
    const diameterLabel = document.createElement("label");
    diameter = document.createElement("input");
    diameterLabel.textContent = "Diameter (mm)";
    diameter.type = "number";
    diameter.className = "filter";
    diameter.step = "any";
    diameter.required = true;
    diameter.value = `${cableGroup.diameterMm}`;
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
    controls[key] = { input, toggle };
  };
  addMaterialField(
    "insulationMaterial", "Insulation Material", catalog.insulationMaterials,
  );
  addMaterialField(
    "conductorMaterial", "Conductor Material", catalog.conductorMaterials,
  );
  addMaterialField("manufacturer", "Manufacturer");
  addMaterialField("partNumber", "Part Number");
  const metadataEditor = createMetadataEditor(
    harness.metadata || [], isCableGroup ? cableGroup.metadataOverrides || [] : null,
  );
  form.append(metadataEditor.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const diameterMm = isCableGroup ? Number(diameter.value) : null;
    if (isCableGroup && (!Number.isFinite(diameterMm) || diameterMm <= 0)) {
      error.textContent = "Enter a positive diameter in millimeters.";
      return;
    }
    const fieldValue = (key) => isCableGroup && !controls[key].toggle.checked
      ? null : controls[key].input.value;
    const insulationMaterial = fieldValue("insulationMaterial");
    const conductorMaterial = fieldValue("conductorMaterial");
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
            insulationMaterial,
            conductorMaterial,
            manufacturer,
            partNumber,
            metadataOverrides: metadataEditor.read(),
          }
          : {
            harnessId: harness.harnessId,
            insulationMaterial,
            conductorMaterial,
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

function openMaterialOptions(harness, cableGroup = null) {
  const isCableGroup = cableGroup !== null;
  const hasOverrides = isCableGroup;
  const settings = isCableGroup ? cableGroup.materials : harness.materialDefaults;
  const overrides = isCableGroup ? cableGroup.materialOverrides : null;
  const originalMaterials = JSON.parse(JSON.stringify(hasOverrides ? overrides : settings));
  let hasAppliedChanges = false;
  let cancelInProgress = false;
  const catalog = currentState.catalog || {
    insulationMaterials: [], conductorMaterials: [], colors: [], stripePatterns: [],
  };
  const { dialog, form, heading, note, error, actions, cancel, save } = createOptionsDialog(
    "cable-options material-options",
  );
  const apply = document.createElement("button");
  heading.textContent = isCableGroup ? "Connected Cable Group Materials" : "Harness Materials";
  note.textContent = isCableGroup
    ? "Checked visual fields override this harness for the connected cable group."
    : "These visual values are inherited by connected cable groups without overrides.";
  form.append(heading, note);

  const addOverrideToggle = (header, key, update) => {
    if (!hasOverrides) return null;
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    const text = document.createElement("span");
    checkbox.type = "checkbox";
    checkbox.checked = overrides[key] !== null;
    text.textContent = "Override";
    checkbox.addEventListener("change", update);
    label.append(checkbox, text);
    header.append(label);
    return checkbox;
  };

  const colorWrapper = document.createElement("div");
  const colorHeader = document.createElement("div");
  const colorLabel = document.createElement("strong");
  const colorRow = document.createElement("div");
  const colorPicker = document.createElement("input");
  const colorNameWrapper = document.createElement("div");
  const colorName = document.createElement("input");
  const appearanceSource = document.createElement("select");
  const libraryControls = document.createElement("div");
  const libraryLabel = document.createElement("label");
  const librarySelect = document.createElement("select");
  const appearanceLabel = document.createElement("label");
  const appearanceSelect = document.createElement("select");
  colorWrapper.className = "material-field";
  colorHeader.className = "material-field-heading";
  colorLabel.textContent = "Main insulation appearance";
  colorRow.className = "material-color-row";
  appearanceSource.className = "appearance-source";
  libraryControls.className = "appearance-library-controls";
  colorPicker.type = "color";
  colorPicker.value = settings.mainColor.hex;
  colorName.type = "text";
  colorName.className = "filter";
  colorName.value = settings.mainColor.name;
  [
    ["color", "Catalog or custom color"],
    ["library", "Fusion library appearance"],
  ].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    appearanceSource.append(option);
  });
  appearanceSource.value = settings.appearance ? "library" : "color";
  librarySelect.title = "Fusion appearance library";
  appearanceSelect.title = "Fusion appearance";
  let loadedLibraries = [];
  let loadedAppearances = [];
  const setOptions = (select, values, selectedId, placeholder) => {
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = placeholder;
    select.append(empty);
    values.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      option.selected = item.id === selectedId;
      select.append(option);
    });
    select.value = values.some((item) => item.id === selectedId) ? selectedId : "";
  };
  const loadAppearances = async (libraryId, selectedId = "") => {
    setOptions(appearanceSelect, [], "", "Loading appearances…");
    appearanceSelect.disabled = true;
    const response = await send("get_library_appearances", { libraryId });
    if (!response.ok) throw new Error(response.error || "Could not read Fusion appearances.");
    loadedAppearances = response.appearances;
    setOptions(appearanceSelect, loadedAppearances, selectedId, "Select appearance");
    updateColor();
  };
  const loadAppearanceLibraries = async () => {
    try {
      const response = await send("get_appearance_libraries");
      if (!response.ok) {
        error.textContent = response.error || "Could not read appearance libraries.";
        setOptions(librarySelect, [], "", "Libraries unavailable");
        setOptions(appearanceSelect, [], "", "Appearances unavailable");
        return;
      }
      loadedLibraries = response.libraries;
      const selectedLibrary = settings.appearance?.libraryId || loadedLibraries[0]?.id || "";
      setOptions(librarySelect, loadedLibraries, selectedLibrary, "Select library");
      if (selectedLibrary && appearanceSource.value === "library") {
        await loadAppearances(selectedLibrary, settings.appearance?.appearanceId || "");
      }
      updateColor();
    } catch (failure) {
      error.textContent = failure.message;
      setOptions(librarySelect, [], "", "Libraries unavailable");
      setOptions(appearanceSelect, [], "", "Appearances unavailable");
    }
  };
  const updateColor = () => {
    const disabled = Boolean(colorToggle && !colorToggle.checked);
    const usesLibrary = appearanceSource.value === "library";
    appearanceSource.disabled = disabled;
    colorPicker.disabled = disabled || usesLibrary;
    colorName.disabled = disabled || usesLibrary;
    libraryControls.hidden = !usesLibrary;
    librarySelect.disabled = disabled || !usesLibrary || loadedLibraries.length === 0;
    appearanceSelect.disabled = disabled || !usesLibrary || loadedAppearances.length === 0;
  };
  const colorToggle = addOverrideToggle(colorHeader, "mainColor", updateColor);
  colorName.addEventListener("change", () => {
    const match = catalog.colors.find(
      (item) => item.name.toLocaleLowerCase() === colorName.value.trim().toLocaleLowerCase(),
    );
    if (match) colorPicker.value = match.hex;
  });
  colorPicker.addEventListener("input", () => {
    const match = catalog.colors.find(
      (item) => item.hex.toLocaleLowerCase() === colorPicker.value.toLocaleLowerCase(),
    );
    colorName.value = match?.name || "Custom";
  });
  addMaterialColorContextMenu(
    colorRow,
    colorPicker,
    () => colorName.value,
    (color) => {
      colorPicker.value = color.hex;
      colorName.value = color.name;
    },
  );
  appearanceSource.addEventListener("change", async () => {
    updateColor();
    if (appearanceSource.value === "library" && librarySelect.value
        && loadedAppearances.length === 0) {
      try {
        await loadAppearances(librarySelect.value, settings.appearance?.appearanceId || "");
      } catch (failure) {
        error.textContent = failure.message;
      }
    }
  });
  librarySelect.addEventListener("change", async () => {
    try {
      if (!librarySelect.value) {
        loadedAppearances = [];
        setOptions(appearanceSelect, [], "", "Select appearance");
        updateColor();
        return;
      }
      await loadAppearances(librarySelect.value);
    } catch (failure) {
      error.textContent = failure.message;
    }
  });
  colorHeader.prepend(colorLabel);
  updateColor();
  colorNameWrapper.append(colorName);
  colorRow.append(colorPicker, colorNameWrapper);
  libraryLabel.textContent = "Library";
  libraryLabel.append(librarySelect);
  appearanceLabel.textContent = "Appearance";
  appearanceLabel.append(appearanceSelect);
  libraryControls.append(libraryLabel, appearanceLabel);
  colorWrapper.append(colorHeader, appearanceSource, colorRow, libraryControls);
  addMaterialAutocomplete(colorNameWrapper, colorName, catalog.colors, (name) => {
    const match = catalog.colors.find((item) => item.name === name);
    if (match) colorPicker.value = match.hex;
  });
  form.append(colorWrapper);

  const stripeWrapper = document.createElement("div");
  const stripeHeader = document.createElement("div");
  const stripeLabel = document.createElement("strong");
  const stripeList = document.createElement("div");
  const addStripe = document.createElement("button");
  stripeWrapper.className = "material-field";
  stripeHeader.className = "material-field-heading";
  stripeLabel.textContent = "Procedural stripes";
  stripeList.className = "stripe-list";
  addStripe.type = "button";
  addStripe.className = "button compact";
  addStripe.textContent = "+ Add stripe";

  const appendStripe = (stripe = null) => {
    const value = stripe || {
      color: catalog.colors.find((item) => item.name === "White")
        || { name: "White", hex: "#F5F5F5" },
      widthMm: 0.4, pattern: "longitudinal", angleDeg: 0, repeatMm: null,
    };
    const row = document.createElement("div");
    const picker = document.createElement("input");
    const values = document.createElement("div");
    const pattern = document.createElement("select");
    const width = document.createElement("input");
    const angle = document.createElement("input");
    const repeat = document.createElement("input");
    const remove = document.createElement("button");
    row.className = "stripe-row";
    picker.type = "color";
    picker.value = value.color.hex;
    repeat.className = "stripe-repeat";
    addMaterialColorContextMenu(
      row,
      picker,
      () => catalog.colors.find(
        (item) => item.hex.toLocaleLowerCase() === picker.value.toLocaleLowerCase(),
      )?.name || "Custom",
      (color) => { picker.value = color.hex; },
    );
    values.className = "stripe-values";
    (catalog.stripePatterns.length
      ? catalog.stripePatterns : ["longitudinal", "dashed", "helical"]
    ).forEach((item) => {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      option.selected = item === value.pattern;
      pattern.append(option);
    });
    const numericField = (labelText, input, initial) => {
      const label = document.createElement("label");
      label.textContent = labelText;
      input.type = "number";
      input.step = "any";
      input.value = initial == null ? "" : `${initial}`;
      label.append(input);
      return label;
    };
    const updateRepeat = () => {
      repeat.disabled = pattern.disabled || pattern.value === "longitudinal";
      if (pattern.value === "longitudinal") repeat.value = "";
    };
    pattern.addEventListener("change", updateRepeat);
    remove.type = "button";
    remove.className = "icon-button danger";
    remove.textContent = "×";
    remove.title = "Remove stripe";
    remove.addEventListener("click", () => row.remove());
    values.append(
      numericField("Width (mm)", width, value.widthMm),
      numericField("Angle (deg)", angle, value.angleDeg),
      (() => {
        const label = document.createElement("label");
        label.textContent = "Pattern";
        label.append(pattern);
        return label;
      })(),
      numericField("Repeat (mm)", repeat, value.repeatMm),
    );
    row.append(picker, values, remove);
    stripeList.append(row);
    updateRepeat();
    updateStripes();
  };
  const updateStripes = () => {
    const disabled = Boolean(stripeToggle && !stripeToggle.checked);
    addStripe.disabled = disabled;
    stripeList.querySelectorAll("input, select, button").forEach((input) => {
      input.disabled = disabled;
    });
    if (!disabled) {
      Array.from(stripeList.children).forEach((row) => {
        const pattern = row.querySelector("select");
        const repeat = row.querySelector(".stripe-repeat");
        repeat.disabled = pattern.value === "longitudinal";
      });
    }
  };
  const stripeToggle = addOverrideToggle(stripeHeader, "stripes", updateStripes);
  stripeHeader.prepend(stripeLabel);
  (settings.stripes || []).forEach(appendStripe);
  addStripe.addEventListener("click", () => appendStripe());
  updateStripes();
  stripeWrapper.append(stripeHeader, stripeList, addStripe);
  form.append(stripeWrapper);

  const readStripes = () => [...stripeList.children].map((row, index) => {
    const inputs = row.querySelectorAll("input");
    const pattern = row.querySelector("select").value;
    const width = Number(inputs[1].value);
    const angle = Number(inputs[2].value);
    const repeat = inputs[3].value.trim() === "" ? null : Number(inputs[3].value);
    if (!Number.isFinite(width) || width <= 0 || !Number.isFinite(angle)
        || (pattern !== "longitudinal" && (!Number.isFinite(repeat) || repeat <= 0))) {
      throw new Error(`Stripe ${index + 1} needs a positive width, finite angle, and pattern repeat.`);
    }
    const catalogColor = catalog.colors.find(
      (item) => item.hex.toLocaleLowerCase() === inputs[0].value.toLocaleLowerCase(),
    );
    return {
      color: colorFromHex(catalogColor?.name || "Custom", inputs[0].value),
      widthMm: width, pattern, angleDeg: angle, repeatMm: repeat,
    };
  });

  apply.type = "button";
  apply.className = "button";
  apply.textContent = "Apply";
  const applyMaterials = async (closeAfter) => {
    try {
      let appearance = null;
      if ((!hasOverrides || colorToggle.checked) && appearanceSource.value === "library") {
        const library = loadedLibraries.find((item) => item.id === librarySelect.value);
        const selected = loadedAppearances.find(
          (item) => item.id === appearanceSelect.value,
        );
        if (!library || !selected) {
          error.textContent = "Select a Fusion appearance library and appearance.";
          return;
        }
        appearance = {
          libraryId: library.id,
          libraryName: library.name,
          appearanceId: selected.id,
          appearanceName: selected.name,
        };
      }
      const materials = {
        insulationMaterial: isCableGroup
          ? overrides.insulationMaterial : settings.insulationMaterial,
        conductorMaterial: isCableGroup
          ? overrides.conductorMaterial : settings.conductorMaterial,
        mainColor: hasOverrides && !colorToggle.checked ? null
          : colorFromHex(colorName.value, colorPicker.value),
        appearance: hasOverrides && !colorToggle.checked ? null : appearance,
        stripes: hasOverrides && !stripeToggle.checked ? null : readStripes(),
        manufacturer: isCableGroup
          ? overrides.manufacturer : settings.manufacturer,
        partNumber: isCableGroup ? overrides.partNumber : settings.partNumber,
        notes: isCableGroup ? overrides.notes : settings.notes,
      };
      apply.disabled = true;
      cancel.disabled = true;
      save.disabled = true;
      const response = await send(
        isCableGroup ? "set_cable_group_material_overrides" : "set_harness_material_defaults",
        isCableGroup
          ? {
            harnessId: harness.harnessId,
            cableGroupId: cableGroup.cableGroupId,
            overrides: materials,
          }
          : { harnessId: harness.harnessId, materials },
      );
      if (response.ok) {
        hasAppliedChanges = !closeAfter;
        error.textContent = closeAfter ? "" : "Applied.";
        if (closeAfter) dialog.close();
      }
      else error.textContent = response.error || "Could not save cable materials.";
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      apply.disabled = false;
      cancel.disabled = false;
      save.disabled = false;
    }
  };
  dialog.cancelOptions = async () => {
    if (cancelInProgress) return;
    if (!hasAppliedChanges) {
      dialog.close();
      return;
    }
    cancelInProgress = true;
    apply.disabled = true;
    cancel.disabled = true;
    save.disabled = true;
    error.textContent = "Restoring saved options…";
    try {
      const response = await send(
        isCableGroup ? "set_cable_group_material_overrides" : "set_harness_material_defaults",
        isCableGroup
          ? {
            harnessId: harness.harnessId,
            cableGroupId: cableGroup.cableGroupId,
            overrides: originalMaterials,
          }
          : { harnessId: harness.harnessId, materials: originalMaterials },
      );
      if (!response.ok) {
        error.textContent = response.error || "Could not restore cable materials.";
        return;
      }
      hasAppliedChanges = false;
      dialog.close();
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      cancelInProgress = false;
      apply.disabled = false;
      cancel.disabled = false;
      save.disabled = false;
    }
  };
  apply.addEventListener("click", () => applyMaterials(false));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void applyMaterials(true);
  });
  dialog.addEventListener("close", () => dialog.remove());
  actions.append(cancel, apply, save);
  form.append(error, actions);
  dialog.append(form);
  document.body.append(dialog);
  dialog.showModal();
  void loadAppearanceLibraries();
}
