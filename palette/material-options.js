/** Open visual material and stripe options for a harness or cable group. */
/* global currentState */

/** Build a reusable color-or-Fusion-library appearance editor. */
function createAppearanceEditor(settings, title, catalog, error, addOverrideToggle, overrideKey) {
  const wrapper = document.createElement("div");
  const header = document.createElement("div");
  const titleElement = document.createElement("strong");
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
  wrapper.className = "material-field";
  header.className = "material-field-heading";
  titleElement.textContent = title;
  colorRow.className = "material-color-row";
  appearanceSource.className = "appearance-source";
  libraryControls.className = "appearance-library-controls";
  colorPicker.type = "color";
  colorPicker.value = settings.color.hex;
  colorName.type = "text";
  colorName.className = "filter";
  colorName.value = settings.color.name;
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
  const update = () => {
    const disabled = Boolean(toggle && !toggle.checked);
    const usesLibrary = appearanceSource.value === "library";
    appearanceSource.disabled = disabled;
    colorPicker.disabled = disabled || usesLibrary;
    colorName.disabled = disabled || usesLibrary;
    libraryControls.hidden = !usesLibrary;
    librarySelect.disabled = disabled || !usesLibrary || loadedLibraries.length === 0;
    appearanceSelect.disabled = disabled || !usesLibrary || loadedAppearances.length === 0;
  };
  const toggle = addOverrideToggle(header, overrideKey, update);
  const loadAppearances = async (libraryId, selectedId = "") => {
    setOptions(appearanceSelect, [], "", "Loading appearances…");
    appearanceSelect.disabled = true;
    const response = await send("get_library_appearances", { libraryId });
    if (!response.ok) throw new Error(response.error || "Could not read Fusion appearances.");
    loadedAppearances = response["appearances"];
    setOptions(appearanceSelect, loadedAppearances, selectedId, "Select appearance");
    update();
  };
  const load = async () => {
    try {
      const response = await send("get_appearance_libraries");
      if (!response.ok) {
        error.textContent = response.error || "Could not read appearance libraries.";
        setOptions(librarySelect, [], "", "Libraries unavailable");
        setOptions(appearanceSelect, [], "", "Appearances unavailable");
        return;
      }
      loadedLibraries = response["libraries"];
      const selectedLibrary = settings.appearance?.libraryId || loadedLibraries[0]?.id || "";
      setOptions(librarySelect, loadedLibraries, selectedLibrary, "Select library");
      if (selectedLibrary && appearanceSource.value === "library") {
        await loadAppearances(selectedLibrary, settings.appearance?.appearanceId || "");
      }
      update();
    } catch (failure) {
      error.textContent = failure.message;
      setOptions(librarySelect, [], "", "Libraries unavailable");
      setOptions(appearanceSelect, [], "", "Appearances unavailable");
    }
  };
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
  addMaterialColorContextMenu(colorRow, colorPicker, () => colorName.value, (color) => {
    colorPicker.value = color.hex;
    colorName.value = color.name;
  });
  appearanceSource.addEventListener("change", async () => {
    update();
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
        update();
        return;
      }
      await loadAppearances(librarySelect.value);
    } catch (failure) {
      error.textContent = failure.message;
    }
  });
  titleElement.textContent = title;
  header.prepend(titleElement);
  colorNameWrapper.append(colorName);
  colorRow.append(colorPicker, colorNameWrapper);
  libraryLabel.textContent = "Library";
  libraryLabel.append(librarySelect);
  appearanceLabel.textContent = "Appearance";
  appearanceLabel.append(appearanceSelect);
  libraryControls.append(libraryLabel, appearanceLabel);
  wrapper.append(header, appearanceSource, colorRow, libraryControls);
  addMaterialAutocomplete(colorNameWrapper, colorName, catalog.colors, (name) => {
    const match = catalog.colors.find((item) => item.name === name);
    if (match) colorPicker.value = match.hex;
  });
  update();
  const read = () => {
    if (toggle && !toggle.checked) return null;
    let appearance = null;
    if (appearanceSource.value === "library") {
      const library = loadedLibraries.find((item) => item.id === librarySelect.value);
      const selected = loadedAppearances.find((item) => item.id === appearanceSelect.value);
      if (!library || !selected) {
        throw new Error("Select a Fusion appearance library and appearance.");
      }
      appearance = {
        libraryId: library.id,
        libraryName: library.name,
        appearanceId: selected.id,
        appearanceName: selected.name,
      };
    }
    return { color: colorFromHex(colorName.value, colorPicker.value), appearance };
  };
  return { wrapper, toggle, appearanceSource, read, load, update };
}

function openMaterialOptions(harness, cableGroup = null, attachment = null) {
  const isCableGroup = cableGroup !== null;
  const isConnectionBranch = attachment !== null;
  const hasOverrides = isCableGroup || isConnectionBranch;
  const connection = isConnectionBranch ? harness.connections.find(
    (candidate) => candidate.connectionId === attachment.connectionId,
  ) : null;
  const settings = isConnectionBranch && connection
    ? cableEndAttachmentMaterials(cableGroup, connection, attachment)
    : (isCableGroup ? cableGroup.materials : harness.materialDefaults);
  const overrides = isConnectionBranch
    ? (attachment.visualOverrides || {}) : (isCableGroup ? cableGroup.materialOverrides : null);
  const originalMaterials = JSON.parse(JSON.stringify(hasOverrides ? overrides : settings));
  let hasAppliedChanges = false;
  let cancelInProgress = false;
  const catalog = currentState["catalog"] || {
    insulationMaterials: [], conductorMaterials: [], colors: [], stripePatterns: [],
  };
  const { dialog, form, heading, note, error, actions, cancel, save } = createOptionsDialog(
    "cable-options material-options",
  );
  const apply = document.createElement("button");
  heading.textContent = isConnectionBranch
    ? "Connection Materials"
    : (isCableGroup ? "Connected Cable Group Materials" : "Harness Materials");
  note.textContent = isConnectionBranch
    ? "Checked visual fields override this connection node’s immediate parent."
    : (isCableGroup
      ? "Checked visual fields override this harness for the connected cable group."
      : "These visual values are inherited by connected cable groups without overrides.");
  form.append(heading, note);

  const addOverrideToggle = (header, key, update) => {
    if (!hasOverrides) return null;
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    const text = document.createElement("span");
    checkbox.type = "checkbox";
    checkbox.checked = overrides[key] !== null && overrides[key] !== undefined;
    text.textContent = "Override";
    checkbox.addEventListener("change", update);
    label.append(checkbox, text);
    header.append(label);
    return checkbox;
  };

  const mainAppearance = createAppearanceEditor(
    { color: settings.mainColor, appearance: settings.appearance },
    "Main insulation appearance", catalog, error, addOverrideToggle, "mainColor",
  );
  form.append(mainAppearance.wrapper);

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

  const pullbackSettings = settings.pullback || {
    mode: "percent",
    value: 200,
    color: { name: "Copper", hex: "#B87333" },
    appearance: null,
  };
  const pullbackAppearance = createAppearanceEditor(
    { color: pullbackSettings.color, appearance: pullbackSettings.appearance },
    "Insulation Pullback", catalog, error, addOverrideToggle, "pullback",
  );
  const pullbackAmount = document.createElement("div");
  const pullbackModeLabel = document.createElement("label");
  const pullbackMode = document.createElement("select");
  const pullbackValueLabel = document.createElement("label");
  const pullbackValueText = document.createElement("span");
  const pullbackValue = document.createElement("input");
  pullbackAmount.className = "appearance-library-controls pullback-amount";
  pullbackModeLabel.textContent = "Measurement";
  [["percent", "Percent"], ["distance", "Distance"]].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    pullbackMode.append(option);
  });
  pullbackMode.value = pullbackSettings.mode;
  pullbackModeLabel.append(pullbackMode);
  pullbackValue.type = "number";
  pullbackValue.className = "filter";
  pullbackValue.min = "0";
  pullbackValue.step = "any";
  pullbackValue.value = `${pullbackSettings.value}`;
  const updatePullbackValueLabel = () => {
    pullbackValueText.textContent = pullbackMode.value === "percent"
      ? "Amount (%)" : "Distance (mm)";
  };
  pullbackValueLabel.append(pullbackValueText, pullbackValue);
  pullbackMode.addEventListener("change", updatePullbackValueLabel);
  updatePullbackValueLabel();
  pullbackAmount.append(pullbackModeLabel, pullbackValueLabel);
  pullbackAppearance.wrapper.insertBefore(
    pullbackAmount, pullbackAppearance.appearanceSource,
  );
  const updatePullbackInputs = () => {
    const disabled = Boolean(pullbackAppearance.toggle && !pullbackAppearance.toggle.checked);
    pullbackMode.disabled = disabled;
    pullbackValue.disabled = disabled;
  };
  pullbackAppearance.toggle?.addEventListener("change", updatePullbackInputs);
  pullbackAppearance.update();
  updatePullbackInputs();
  form.append(pullbackAppearance.wrapper);

  const weldSettings = settings.weld || {
    value: 150,
    color: { name: "Silver", hex: "#C0C0C0" },
    appearance: null,
  };
  const weldAppearance = createAppearanceEditor(
    { color: weldSettings.color, appearance: weldSettings.appearance },
    "Weld", catalog, error, addOverrideToggle, "weld",
  );
  const weldAmount = document.createElement("div");
  const weldValueLabel = document.createElement("label");
  const weldValue = document.createElement("input");
  weldAmount.className = "appearance-library-controls pullback-amount";
  weldValueLabel.textContent = "Amount (%)";
  weldValue.type = "number";
  weldValue.className = "filter";
  weldValue.min = "0";
  weldValue.step = "any";
  weldValue.value = `${weldSettings.value}`;
  weldValueLabel.append(weldValue);
  weldAmount.append(weldValueLabel);
  weldAppearance.wrapper.insertBefore(weldAmount, weldAppearance.appearanceSource);
  const updateWeldInputs = () => {
    weldValue.disabled = Boolean(weldAppearance.toggle && !weldAppearance.toggle.checked);
  };
  weldAppearance.toggle?.addEventListener("change", updateWeldInputs);
  weldAppearance.update();
  updateWeldInputs();
  form.append(weldAppearance.wrapper);

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
      const selectedMainAppearance = mainAppearance.read();
      const selectedPullbackAppearance = pullbackAppearance.read();
      const selectedWeldAppearance = weldAppearance.read();
      const pullbackValueNumber = Number(pullbackValue.value);
      const weldValueNumber = Number(weldValue.value);
      if (selectedPullbackAppearance !== null
          && (!Number.isFinite(pullbackValueNumber) || pullbackValueNumber < 0)) {
        error.textContent = "Pullback needs a nonnegative percent or distance.";
        return;
      }
      if (selectedWeldAppearance !== null
          && (!Number.isFinite(weldValueNumber) || weldValueNumber < 0)) {
        error.textContent = "Weld needs a nonnegative percentage.";
        return;
      }
      const materials = {
        insulationMaterial: isCableGroup && !isConnectionBranch
          ? overrides.insulationMaterial : settings.insulationMaterial,
        conductorMaterial: isCableGroup && !isConnectionBranch
          ? overrides.conductorMaterial : settings.conductorMaterial,
        shielding: isCableGroup && !isConnectionBranch
          ? overrides.shielding : settings.shielding,
        dielectricMaterial: isCableGroup && !isConnectionBranch
          ? overrides.dielectricMaterial : settings.dielectricMaterial,
        mainColor: selectedMainAppearance?.color ?? null,
        appearance: selectedMainAppearance?.appearance ?? null,
        stripes: hasOverrides && !stripeToggle.checked ? null : readStripes(),
        manufacturer: isCableGroup && !isConnectionBranch
          ? overrides.manufacturer : settings.manufacturer,
        partNumber: isCableGroup && !isConnectionBranch
          ? overrides.partNumber : settings.partNumber,
        notes: isCableGroup && !isConnectionBranch ? overrides.notes : settings.notes,
        pullback: selectedPullbackAppearance === null ? null : {
          mode: pullbackMode.value,
          value: pullbackValueNumber,
          color: selectedPullbackAppearance.color,
          appearance: selectedPullbackAppearance.appearance,
        },
        weld: selectedWeldAppearance === null ? null : {
          value: weldValueNumber,
          color: selectedWeldAppearance.color,
          appearance: selectedWeldAppearance.appearance,
        },
      };
      apply.disabled = true;
      cancel.disabled = true;
      save.disabled = true;
      const response = await send(
        isConnectionBranch
          ? "set_cable_end_attachment_visual_overrides"
          : (isCableGroup ? "set_cable_group_material_overrides" : "set_harness_material_defaults"),
        isConnectionBranch
          ? {
            harnessId: harness.harnessId,
            connectionId: attachment.connectionId,
            attachmentId: attachment.attachmentId,
            overrides: materials,
          }
          : (isCableGroup
          ? {
            harnessId: harness.harnessId,
            cableGroupId: cableGroup.cableGroupId,
            overrides: materials,
          }
          : { harnessId: harness.harnessId, materials }),
      );
      if (response.ok) {
        hasAppliedChanges = !closeAfter;
        error.textContent = closeAfter ? "" : "Applied.";
        if (closeAfter) dialog.close();
      } else error.textContent = response.error || "Could not save cable materials.";
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
        isConnectionBranch
          ? "set_cable_end_attachment_visual_overrides"
          : (isCableGroup ? "set_cable_group_material_overrides" : "set_harness_material_defaults"),
        isConnectionBranch
          ? {
            harnessId: harness.harnessId,
            connectionId: attachment.connectionId,
            attachmentId: attachment.attachmentId,
            overrides: originalMaterials,
          }
          : (isCableGroup
          ? {
            harnessId: harness.harnessId,
            cableGroupId: cableGroup.cableGroupId,
            overrides: originalMaterials,
          }
          : { harnessId: harness.harnessId, materials: originalMaterials }),
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
  void Promise.all([mainAppearance.load(), pullbackAppearance.load(), weldAppearance.load()]);
}
