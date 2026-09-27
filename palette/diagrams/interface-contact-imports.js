/** Interface contact geometry and PCB import forms. */
/** Offer geometry-name import or a picked Interface's projected contact fields. */
function openInterfaceGeoImport(naming, diagram, harnessId, interfaceId) {
  const existing = naming.querySelector(".interface-contact-geo-import");
  if (existing) { existing.remove(); return; }
  const form = document.createElement("form");
  const title = document.createElement("div");
  const geometryLabel = document.createElement("label");
  const geometry = document.createElement("input");
  const importValuesLabel = document.createElement("label");
  const importValues = document.createElement("input");
  const importPinsLabel = document.createElement("label");
  const importPins = document.createElement("input");
  const interfaceLabel = document.createElement("label");
  const selectInterface = document.createElement("input");
  const apply = document.createElement("button");
  const cancel = document.createElement("button");
  form.className = "interface-contact-geo-import";
  form.setAttribute("role", "dialog");
  form.setAttribute("aria-label", "Geo Import options");
  title.textContent = "Geo Import";
  geometry.type = "radio";
  geometry.name = "geo-import-mode";
  geometry.value = "geometry";
  geometry.checked = true;
  geometryLabel.append(geometry, "Import geometry names");
  importValues.type = "checkbox";
  importValues.checked = readSessionCheckbox("cableBundler.geoImportValues", true);
  importValuesLabel.append(importValues, "Values");
  importPins.type = "checkbox";
  importPins.checked = readSessionCheckbox("cableBundler.geoImportPins", false);
  importPinsLabel.append(importPins, "Pins");
  selectInterface.type = "radio";
  selectInterface.name = "geo-import-mode";
  selectInterface.value = "interface";
  interfaceLabel.append(selectInterface, "Select Interface");
  const updateChoice = () => {
    writeSession("cableBundler.geoImportValues", String(importValues.checked));
    writeSession("cableBundler.geoImportPins", String(importPins.checked));
    apply.disabled = !importValues.checked && !importPins.checked;
    apply.textContent = geometry.checked ? "Apply" : "Pick Interface";
  };
  geometry.addEventListener("change", updateChoice);
  selectInterface.addEventListener("change", updateChoice);
  importValues.addEventListener("change", updateChoice);
  importPins.addEventListener("change", updateChoice);
  apply.type = "submit";
  apply.className = "button compact";
  apply.textContent = "Apply";
  apply.disabled = !importValues.checked && !importPins.checked;
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
    if (apply.disabled) return;
    apply.disabled = true;
    const pickInterface = selectInterface.checked;
    void send(pickInterface ? "copy_projected_interface_contacts" : "geo_import_interface_contacts", {
      harnessId, interfaceId, contactIds: [...diagram.contactState.selectedIds],
      ...(pickInterface ? {
        copyValues: importValues.checked, copyPins: importPins.checked,
      } : {
        importValues: importValues.checked, importPins: importPins.checked,
      }),
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not start Geo Import.");
      form.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { apply.disabled = false; });
  });
  form.append(title, geometryLabel, interfaceLabel, importValuesLabel, importPinsLabel,
    apply, cancel);
  naming.append(form);
}


/** Review PCB suggestions from a linked board or local file before applying names. */
function openInterfacePosImport(naming, harnessId, interfaceId) {
  const existing = naming.querySelector(".interface-contact-pos-import");
  if (existing) { existing.remove(); pendingBoardFilePreview = null; return; }
  const form = document.createElement("form");
  const message = document.createElement("div");
  const choices = document.createElement("div");
  const review = document.createElement("div");
  const projectLabel = document.createElement("label");
  const project = document.createElement("input");
  const loadBoard = document.createElement("button");
  const apply = document.createElement("button");
  const cancel = document.createElement("button");
  form.className = "interface-contact-pos-import";
  form.setAttribute("role", "dialog");
  form.setAttribute("aria-label", "Choose PCB for Pos Import");
  message.textContent = "Finding linked PCB files…";
  choices.className = "interface-contact-pos-import-choices";
  project.type = "checkbox";
  project.checked = readSessionCheckbox("cableBundler.posImportProject", true);
  project.addEventListener("change", () => {
    writeSession("cableBundler.posImportProject", String(project.checked));
  });
  projectLabel.append(project, "Project");
  projectLabel.title = "Match selected geometry by board X/Y, ignoring Z and board side.";
  loadBoard.type = "button";
  loadBoard.className = "button compact";
  loadBoard.textContent = "Load board";
  apply.type = "submit";
  apply.className = "button compact";
  apply.textContent = "Open and Review";
  apply.disabled = true;
  cancel.type = "button";
  cancel.className = "button compact";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => { form.remove(); pendingBoardFilePreview = null; });
  form.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    form.remove();
    pendingBoardFilePreview = null;
  });
  let preview = null;
  let applyingAutomatically = false;
  let linkedBoards = null;
  let loadingFile = false;
  const decisions = [];
  const restoreLinkedChoices = () => {
    message.textContent = linkedBoards === null ? "Finding linked PCB files…"
      : linkedBoards.length ? "Choose the linked 2D PCB to read pad names from:"
        : "No linked 2D PCB was found for this Interface. Use Load board for a local board file.";
    apply.disabled = !linkedBoards?.length;
  };
  const applyNames = (contactNames) => {
    apply.disabled = true;
    void send("pos_import_interface_contacts", {
      harnessId, interfaceId, contactNames,
    }).then((response) => {
      if (!response.ok) throw new Error(response.error || "Could not import PCB pad names.");
      form.remove();
    }).catch((error) => appendNotice(String(error), true))
      .finally(() => { apply.disabled = false; });
  };
  const showPreview = (response) => {
    if (naming.querySelector(".interface-contact-pos-import") !== form) return;
    if (response.cancelled) { restoreLinkedChoices(); return; }
    if (response.error || !Array.isArray(response.autoNames) || !Array.isArray(response.unresolved)) {
      appendNotice(response.error || "Could not read PCB pad names.", true);
      restoreLinkedChoices();
      return;
    }
    preview = response;
    project.disabled = true;
    loadBoard.disabled = true;
    const conflicts = response.unresolved.filter((contact) => (
      Array.isArray(contact.suggestions) && contact.suggestions.length
    ));
    if (!conflicts.length) {
      if (response.autoNames.length) {
        applyingAutomatically = true;
        applyNames(response.autoNames);
      } else {
        appendNotice("No PCB pad names matched these contacts.");
        form.remove();
      }
      return;
    }
    choices.hidden = true;
    message.textContent = `${response.autoNames.length} contacts matched automatically; `
      + `${conflicts.length} need review.`;
    review.className = "interface-contact-pos-import-review";
    conflicts.forEach((contact) => {
      const row = document.createElement("label");
      const title = document.createElement("span");
      const select = document.createElement("select");
      const manual = document.createElement("input");
      title.textContent = contact.currentName
        ? `${contact.label} · ${contact.currentName}` : contact.label;
      if (contact.currentName) {
        const keep = document.createElement("option");
        keep.value = "keep";
        keep.textContent = `Keep current: ${contact.currentName}`;
        select.append(keep);
      }
      const blank = document.createElement("option");
      blank.value = "blank";
      blank.textContent = "Leave blank";
      select.append(blank);
      select.value = contact.currentName ? "keep" : "blank";
      contact.suggestions.forEach((name, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = name;
        select.append(option);
      });
      const custom = document.createElement("option");
      custom.value = "custom";
      custom.textContent = "Type a name…";
      select.append(custom);
      manual.type = "text";
      manual.maxLength = 80;
      manual.placeholder = "Contact name";
      manual.hidden = true;
      select.addEventListener("change", () => { manual.hidden = select.value !== "custom"; });
      row.append(title, select, manual);
      review.append(row);
      decisions.push({ contact, select, manual });
    });
    apply.textContent = "Apply Names";
    apply.disabled = false;
  };
  loadBoard.addEventListener("click", () => {
    loadingFile = true;
    apply.disabled = true;
    loadBoard.disabled = true;
    message.textContent = "Choose a local board file…";
    pendingBoardFilePreview = (response) => {
      if (response.harnessId !== harnessId || response.interfaceId !== interfaceId) return;
      pendingBoardFilePreview = null;
      loadingFile = false;
      loadBoard.disabled = false;
      showPreview(response);
    };
    void send("load_brd_interface_contacts", { harnessId, interfaceId, project: project.checked })
      .then((response) => {
        if (!response.ok) throw new Error(response.error || "Could not open board picker.");
      }).catch((error) => {
        pendingBoardFilePreview = null;
        loadingFile = false;
        loadBoard.disabled = false;
        appendNotice(String(error), true);
        restoreLinkedChoices();
      });
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!preview) {
      const selected = Array.from(choices.querySelectorAll("input")).find((radio) => radio.checked);
      if (!selected) return;
      apply.disabled = true;
      void send("preview_pos_import_interface_contacts", {
        harnessId, interfaceId, boardVersionId: selected.value, project: project.checked,
      }).then((response) => {
        if (!response.ok) throw new Error(response.error || "Could not read PCB pad names.");
        showPreview(response);
      }).catch((error) => appendNotice(String(error), true))
        .finally(() => { if (!applyingAutomatically) apply.disabled = false; });
      return;
    }
    const contactNames = [...preview.autoNames];
    for (const { contact, select, manual } of decisions) {
      const name = select.value === "keep" ? contact.currentName
        : select.value === "blank" ? ""
        : select.value === "custom" ? manual.value.trim()
          : contact.suggestions[Number(select.value)];
      if (select.value === "custom" && !name) {
        appendNotice(`Enter a name for ${contact.label}, or choose Leave blank.`, true);
        return;
      }
      contactNames.push({ contactId: contact.contactId, name });
    }
    applyNames(contactNames);
  });
  form.append(message, choices, projectLabel, loadBoard, review, apply, cancel);
  naming.append(form);
  void send("get_pos_import_boards", { harnessId, interfaceId }).then((response) => {
    if (naming.querySelector(".interface-contact-pos-import") !== form) return;
    if (!response.ok) throw new Error(response.error || "Could not find linked PCB files.");
    const boards = Array.isArray(response.boards) ? response.boards : [];
    linkedBoards = boards;
    boards.forEach((board, index) => {
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "linked-board";
      radio.value = board.versionId;
      radio.checked = index === 0;
      label.textContent = board.name;
      label.prepend(radio);
      choices.append(label);
    });
    if (!loadingFile && !preview) restoreLinkedChoices();
  }).catch((error) => {
    if (naming.querySelector(".interface-contact-pos-import") === form) {
      message.textContent = String(error);
    }
  });
}
