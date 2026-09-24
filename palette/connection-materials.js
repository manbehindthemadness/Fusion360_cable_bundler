/** Connection-node material inheritance and property-dialog behavior. */
/* global currentState */

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

const CABLE_END_MATERIAL_OVERRIDE_KEYS = [
  "insulationMaterial", "conductorMaterial", "shielding", "dielectricMaterial",
  "manufacturer", "partNumber", "mainColor", "appearance", "stripes", "pullback", "weld",
];

/** Apply eligible branch overrides while enforcing shielding-dependent dielectric inheritance. */
function resolveCableEndMaterialOverrides(inherited, overrides, divided) {
  const keys = divided
    ? CABLE_END_MATERIAL_OVERRIDE_KEYS
    : ["shielding", "dielectricMaterial", "pullback", "weld"];
  const resolved = {
    ...inherited,
    ...Object.fromEntries(
      keys
        .filter((key) => overrides[key] !== null && overrides[key] !== undefined)
        .map((key) => [key, overrides[key]]),
    ),
  };
  return {
    ...resolved,
    dielectricMaterial: resolved.shielding?.trim() ? resolved.dielectricMaterial : "",
  };
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
  return resolveCableEndMaterialOverrides(inherited, overrides, siblings.length > 1);
}

/** Resolve construction values owned by one branch under the domain inheritance rules. */
function cableEndAttachmentMaterials(cableGroup, connection, attachment) {
  const inherited = cableEndAttachmentParentMaterials(cableGroup, connection, attachment);
  const siblings = cableEndAttachmentSiblings(connection, attachment);
  const overrides = attachment.visualOverrides || {};
  return resolveCableEndMaterialOverrides(inherited, overrides, siblings.length > 1);
}

/** Append one inherited text value with an explicit override toggle. */
function appendMaterialOverrideControl(form, inherited, overrides, key, labelText, suggestions) {
  const values = { [key]: overrides[key] ?? inherited[key] };
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
    if (!toggle.checked) input.value = inherited[key];
  };
  toggle.addEventListener("change", update);
  toggleLabel.append(toggle, toggleText);
  header.append(toggleLabel);
  update();
  form.append(wrapper);
  return { input, toggle, wrapper };
}

/** Append shielding and its conditionally available dielectric override. */
function appendShieldingOverrideControls(form, inherited, overrides) {
  const shielding = appendMaterialOverrideControl(
    form, inherited, overrides, "shielding", "Shielding", [],
  );
  const dielectricMaterial = appendMaterialOverrideControl(
    form, inherited, overrides, "dielectricMaterial", "Dielectric Material", [],
  );
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
    materialControls[key] = appendMaterialOverrideControl(
      form, inheritedMaterials, overrides, key, labelText, suggestions,
    );
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
    const diameterMm = persistedLengthValue(diameter.value, units);
    if (!Number.isFinite(diameterMm) || diameterMm <= 0) {
      error.textContent = "Diameter must be a positive number.";
      return;
    }
    let conductorDiameterMm;
    try {
      conductorDiameterMm = conductorDiameter.read();
    } catch (failure) {
      error.textContent = failure.message;
      return;
    }
    const combinedDiameter = siblings.reduce((total, candidate) => {
      if (candidate.attachmentId === attachment.attachmentId) return total + diameterMm;
      return total + (candidate.visualOverrides?.diameterMm ?? inheritedDiameter);
    }, 0);
    if (combinedDiameter > parentDiameter + 1e-9) {
      error.textContent = "Connection diameters cannot collectively exceed the parent cable diameter.";
      return;
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
      error.textContent = "Enabled material overrides must not be empty.";
      return;
    }
    cancel.disabled = true;
    save.disabled = true;
    try {
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
