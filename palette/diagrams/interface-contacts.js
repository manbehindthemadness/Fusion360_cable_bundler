/** Refresh an open contact diagram when Fusion sends an updated harness state. */
function refreshInterfaceContacts() {
  for (const [key, cached] of cachedContactGeometries) {
    if (cached.documentScope !== (currentState.contactDocumentScope || "")) continue;
    const harness = currentState.harnesses.find((item) => item.harnessId === cached.harnessId);
    if (!(harness?.interfaces || []).some((item) => item.interfaceId === cached.interfaceId)) {
      cachedContactGeometries.delete(key);
    }
  }
  const dialog = document.body.querySelector(".interface-contacts-popup");
  if (!dialog?.open) return;
  if (dialog.dataset.contactDocumentScope !== (currentState.contactDocumentScope || "")) {
    dialog.close();
    return;
  }
  if (dialog.cacheRebuildPending) return;
  const harness = currentState.harnesses.find((item) => item.harnessId === dialog.dataset.harnessId);
  const interfaceItem = (harness?.interfaces || []).find((item) => (
    item.interfaceId === dialog.dataset.interfaceId
  ));
  if (interfaceItem) updateInterfaceContactData(dialog, interfaceItem.contacts || []);
  else dialog.close();
}

/** Scope asynchronous contact reads to the document that opened the dialog. */
function interfaceContactRequest(dialog, extra = {}) {
  return {
    harnessId: dialog.dataset.harnessId,
    interfaceId: dialog.dataset.interfaceId,
    contactDocumentScope: dialog.dataset.contactDocumentScope,
    ...extra,
  };
}

/** A queued request from a closed project is no longer actionable. */
function closeStaleInterfaceContactRequest(dialog, response) {
  if (!response.stale) return false;
  if (dialog.open) dialog.close();
  return true;
}

/** Keep unresolved metadata out of the diagram while showing accessible load progress. */
function showInterfaceContactLoading(diagram, total, loaded = 0, failed = false) {
  let status = diagram.querySelector(".interface-contact-loading");
  if (!status) {
    status = document.createElement("div");
    status.className = "interface-contact-loading";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const label = document.createElement("span");
    const progress = document.createElement("progress");
    progress.setAttribute("aria-label", "Contact geometry loading progress");
    status.append(label, progress);
    diagram.append(status);
  }
  diagram.contactState.workspace.root.hidden = true;
  paintInterfaceContactSelection(diagram.contactState);
  diagram.querySelector(".interface-contact-details-editor")?.remove();
  diagram.setAttribute("aria-busy", `${!failed}`);
  status.children[0].textContent = failed
    ? "Unable to load contacts. Close and reopen this panel to retry."
    : `Loading contacts… ${loaded} / ${total}`;
  status.children[1].max = total;
  status.children[1].value = loaded;
  status.children[1].hidden = failed;
}

/** Reveal the workspace only when its geometry is ready to render. */
function hideInterfaceContactLoading(diagram) {
  diagram.querySelector(".interface-contact-loading")?.remove();
  diagram.contactState.workspace.root.hidden = false;
  paintInterfaceContactSelection(diagram.contactState);
  diagram.setAttribute("aria-busy", "false");
}

/** Fetch outlines only for the open dialog; coalesce requests and discard stale replies. */
function updateInterfaceContactData(dialog, contacts) {
  const diagram = dialog.children[2];
  dialog.contactMetadata = contacts;
  if (dialog.cacheRebuildPending) return;
  const geometryKey = contactGeometryKey(contacts);
  const displayKey = JSON.stringify(contacts.map((item) => (
    [item.contactId, item.name, item.assignedName, item.pin, item.orientationName]
  )));
  dialog.requestedGeometryKey = geometryKey;
  if (dialog.geometryValidationPending) return;
  const priorCache = currentContactGeometry(dialog);
  const priorKey = dialog.loadedGeometryKey || priorCache?.geometryKey;
  const signatures = dialog.contactSignatures || priorCache?.signatures;
  if (priorKey && priorKey !== geometryKey && signatures
    && contacts.length <= 1024 && Object.keys(signatures).length === contacts.length
    && contacts.every((item) => typeof signatures[item.contactId] === "string")) {
    dialog.geometryValidationPending = geometryKey;
    void send("get_interface_contact_signatures", interfaceContactRequest(dialog, {
      contactIds: contacts.map((item) => item.contactId),
    })).then((response) => {
      if (closeStaleInterfaceContactRequest(dialog, response)) return;
      if (!response.ok || !response.signatures) throw new Error(response.error || "Contact validation unavailable.");
      if (!dialog.open || contactGeometryKey(dialog.contactMetadata) !== geometryKey) return;
      const unchanged = contacts.every((item) => (
        typeof response.signatures[item.contactId] === "string"
        && response.signatures[item.contactId] === signatures[item.contactId]
      ));
      if (unchanged) {
        if (dialog.loadedGeometryKey === priorKey) dialog.loadedGeometryKey = geometryKey;
        if (priorCache?.geometryKey === priorKey) priorCache.geometryKey = geometryKey;
      } else {
        dialog.loadedGeometryKey = null;
        dialog.contactSignatures = null;
        forgetContactGeometry(dialog);
      }
    }).catch(() => {
      if (!dialog.open) return;
      dialog.loadedGeometryKey = null;
      dialog.contactSignatures = null;
      forgetContactGeometry(dialog);
    }).finally(() => {
      dialog.geometryValidationPending = null;
      if (dialog.open) updateInterfaceContactData(dialog, dialog.contactMetadata);
    });
    return;
  }
  if (currentContactGeometry(dialog) && !matchingContactCache(dialog, geometryKey)) {
    forgetContactGeometry(dialog);
  }
  if (dialog.loadedGeometryKey === geometryKey) {
    hideInterfaceContactLoading(diagram);
    const metadata = new Map(contacts.map((item) => [item.contactId, item]));
    diagram.contactState.contacts = diagram.contactState.contacts.map((item) => (
      { ...item, ...metadata.get(item.contactId) }
    ));
    if (dialog.contactDisplayKey !== displayKey) {
      const geometry = new Map(diagram.contactState.contacts.map((item) => [item.contactId, item]));
      if (contacts.every((item) => Array.isArray(geometry.get(item.contactId)?.loops))) {
        renderInterfaceContacts(diagram, contacts.map((item) => ({ ...geometry.get(item.contactId), ...item })));
        dialog.contactDisplayKey = displayKey;
        rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
      } else {
        dialog.loadedGeometryKey = null;
      }
    }
    if (dialog.loadedGeometryKey === geometryKey) return;
  }
  if (dialog.contactRequestPending) return;
  const cached = matchingContactCache(dialog, geometryKey);
  if (cached) {
    const metadata = new Map(contacts.map((item) => [item.contactId, item]));
    const currentContacts = cached.contacts?.map((item) => ({ ...item, ...metadata.get(item.contactId) }))
      || contacts;
    if (restoreRenderedContactDiagram(dialog, geometryKey, displayKey, currentContacts)) {
      dialog.loadedGeometryKey = geometryKey;
      dialog.contactDisplayKey = displayKey;
      dialog.contactSignatures = cached.signatures;
      return;
    }
    if (cached.contacts) {
      renderInterfaceContacts(diagram, currentContacts);
      rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
      dialog.loadedGeometryKey = geometryKey;
      dialog.contactDisplayKey = displayKey;
      dialog.contactSignatures = cached.signatures;
      return;
    }
  }
  if (!contacts.length || contacts.every((item) => Array.isArray(item.loops))) {
    hideInterfaceContactLoading(diagram);
    renderInterfaceContacts(diagram, contacts);
    rememberContactGeometry(dialog, geometryKey, contacts);
    rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
    dialog.loadedGeometryKey = geometryKey;
    dialog.contactDisplayKey = displayKey;
    dialog.contactSignatures = contactSignatures(contacts);
    return;
  }
  dialog.contactRequestPending = true;
  dialog.rebuildButton.disabled = true;
  showInterfaceContactLoading(diagram, contacts.length);
  void fetchInterfaceContactGeometry(dialog, contacts, geometryKey).then((response) => {
    if (!dialog.open || dialog.requestedGeometryKey !== geometryKey) return;
    if (!response.ok || !Array.isArray(response.contacts)) throw new Error(response.error || "Contact geometry unavailable.");
    const metadata = new Map(dialog.contactMetadata.map((item) => [item.contactId, item]));
    if (response.contacts.length !== metadata.size
      || response.contacts.some((item) => !metadata.has(item.contactId))) {
      throw new Error("Contact geometry no longer matches the saved Interface.");
    }
    rememberContactGeometry(dialog, geometryKey, response.contacts);
    hideInterfaceContactLoading(diagram);
    const renderStarted = Date.now();
    renderInterfaceContacts(diagram, response.contacts.map((item) => ({ ...item, ...metadata.get(item.contactId) })));
    const currentDisplayKey = JSON.stringify(dialog.contactMetadata.map((item) => (
      [item.contactId, item.name, item.assignedName, item.pin, item.orientationName]
    )));
    rememberRenderedContactDiagram(dialog, geometryKey, currentDisplayKey);
    const renderMs = Date.now() - renderStarted;
    dialog.loadedGeometryKey = geometryKey;
    dialog.contactDisplayKey = currentDisplayKey;
    dialog.contactSignatures = contactSignatures(response.contacts);
    if (developerModeEnabled) {
      void reportInterfaceContactCache(dialog, response, renderMs);
    }
  }).catch((error) => {
    if (dialog.open && dialog.requestedGeometryKey === geometryKey) {
      showInterfaceContactLoading(diagram, contacts.length, 0, true);
      appendNotice(String(error), true);
    }
  }).finally(() => {
    dialog.contactRequestPending = false;
    if (dialog.open && !dialog.cacheRebuildPending) dialog.rebuildButton.disabled = false;
    if (dialog.open && dialog.requestedGeometryKey !== geometryKey) {
      updateInterfaceContactData(dialog, dialog.contactMetadata);
    }
  });
}

/** Report one cold-load cache decision and timing in developer mode. */
async function reportInterfaceContactCache(dialog, load, renderMs) {
  try {
    const response = await send("get_interface_contact_cache_status", interfaceContactRequest(dialog));
    if (closeStaleInterfaceContactRequest(dialog, response)) return;
    if (!dialog.open) return;
    if (!response.ok || !response.cache) throw new Error(response.error || "Cache status unavailable.");
    const cache = response.cache;
    const details = [
      `path ${load.cacheMode || "batches"}`,
      `before ${load.cacheBefore?.reason || "unknown"} / ${load.cacheBefore?.snapshot || "unknown"}`,
      `after ${cache.reason} / ${cache.snapshot}`,
      `${load.cacheHits} hits / ${load.cacheMisses} misses`,
    ];
    if (Number.isFinite(cache.entries)) details.push(`${cache.entries} entries`);
    if (cache.lastWrite) details.push(`last write ${cache.lastWrite}`);
    appendNotice(`Contact load ${(load.elapsedMs / 1000).toFixed(1)} s (${load.serverMs} ms backend) + render ${renderMs} ms. Cache: ${details.join(", ")}.`);
  } catch (error) {
    if (dialog.open) appendNotice(`Contact cache diagnostics failed: ${String(error)}`, true);
  }
}

/** Discard the current Interface snapshot and refill it through the progress loader. */
async function rebuildInterfaceContactCache(dialog) {
  if (dialog.cacheRebuildPending || dialog.contactRequestPending) return;
  const diagram = dialog.children[2];
  dialog.cacheRebuildPending = true;
  dialog.rebuildButton.disabled = true;
  showInterfaceContactLoading(diagram, dialog.contactMetadata.length);
  try {
    const response = await send("rebuild_interface_contacts_cache", interfaceContactRequest(dialog));
    if (closeStaleInterfaceContactRequest(dialog, response)) return;
    if (!response.ok) throw new Error(response.error || "Could not clear contact cache.");
    if (!dialog.open) return;
    forgetContactGeometry(dialog);
    dialog.loadedGeometryKey = null;
    dialog.contactDisplayKey = null;
    dialog.contactSignatures = null;
    dialog.requestedGeometryKey = null;
    dialog.cacheRebuildPending = false;
    updateInterfaceContactData(dialog, dialog.contactMetadata);
    if (!response.diskCacheAvailable) {
      appendNotice("Contact outlines rebuilt in memory; save the design to enable disk caching.");
    }
  } catch (error) {
    if (dialog.open) {
      hideInterfaceContactLoading(diagram);
      appendNotice(String(error), true);
    }
  } finally {
    dialog.cacheRebuildPending = false;
    if (dialog.open && !dialog.contactRequestPending) dialog.rebuildButton.disabled = false;
  }
}

/** Yield to Fusion between bounded batches; closing or superseding stops further work. */
async function fetchInterfaceContactGeometry(dialog, contacts, geometryKey) {
  const started = Date.now();
  if (contacts.length > 16 && contacts.length <= 1024) {
    const warm = await send("get_interface_contacts_cached", interfaceContactRequest(dialog, {
      contactIds: contacts.map((item) => item.contactId),
    }));
    if (closeStaleInterfaceContactRequest(dialog, warm)) return { ok: true, contacts: [] };
    if (!warm.ok) throw new Error(warm.error || "Contact cache unavailable.");
    if (warm.cacheComplete) {
      return { ok: true, contacts: warm.contacts, cacheBefore: { reason: "eligible", snapshot: "present" },
        cacheHits: warm.contacts.length, cacheMisses: 0, serverMs: warm.serverMs || 0,
        cacheMode: "single warm read", elapsedMs: Date.now() - started };
    }
  }
  const resolved = [];
  let cacheBefore = null;
  let cacheHits = 0;
  let cacheMisses = 0;
  let serverMs = 0;
  for (let offset = 0; offset < contacts.length; offset += 8) {
    if (!dialog.open || dialog.requestedGeometryKey !== geometryKey) return { ok: true, contacts: [] };
    const response = await send("get_interface_contacts", interfaceContactRequest(dialog, {
      contactIds: contacts.slice(offset, offset + 8).map((item) => item.contactId),
      diagnostics: developerModeEnabled,
      diagnosticFirstBatch: offset === 0,
    }));
    if (closeStaleInterfaceContactRequest(dialog, response)) return { ok: true, contacts: [] };
    if (!response.ok || !Array.isArray(response.contacts)) throw new Error(response.error || "Contact geometry unavailable.");
    if (response.cacheBefore) cacheBefore = response.cacheBefore;
    cacheHits += response.cacheStats?.hits || 0;
    cacheMisses += response.cacheStats?.misses || 0;
    serverMs += response.serverMs || 0;
    resolved.push(...response.contacts);
    if (dialog.open && dialog.requestedGeometryKey === geometryKey) {
      showInterfaceContactLoading(dialog.children[2], contacts.length, Math.min(offset + 8, contacts.length));
    }
  }
  return { ok: true, contacts: resolved, cacheBefore, cacheHits, cacheMisses, cacheMode: "batches",
    serverMs, elapsedMs: Date.now() - started };
}

/** Review linked PCB suggestions before applying ordinary contact names. */
function openInterfacePosImport(naming, harnessId, interfaceId) {
  const existing = naming.querySelector(".interface-contact-pos-import");
  if (existing) { existing.remove(); return; }
  const form = document.createElement("form");
  const message = document.createElement("div");
  const choices = document.createElement("div");
  const review = document.createElement("div");
  const apply = document.createElement("button");
  const cancel = document.createElement("button");
  form.className = "interface-contact-pos-import";
  form.setAttribute("role", "dialog");
  form.setAttribute("aria-label", "Choose linked PCB for Pos Import");
  message.textContent = "Finding linked PCB files…";
  choices.className = "interface-contact-pos-import-choices";
  apply.type = "submit";
  apply.className = "button compact";
  apply.textContent = "Open and Review";
  apply.disabled = true;
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
  let preview = null;
  let applyingAutomatically = false;
  const decisions = [];
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
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!preview) {
      const selected = Array.from(choices.querySelectorAll("input")).find((radio) => radio.checked);
      if (!selected) return;
      apply.disabled = true;
      void send("preview_pos_import_interface_contacts", {
        harnessId, interfaceId, boardVersionId: selected.value,
      }).then((response) => {
        if (!response.ok) throw new Error(response.error || "Could not read PCB pad names.");
        if (naming.querySelector(".interface-contact-pos-import") !== form) return;
        preview = response;
        const conflicts = response.unresolved.filter((contact) => (
          Array.isArray(contact.suggestions) && contact.suggestions.length
        ));
        if (!conflicts.length) {
          if (response.autoNames.length) {
            applyingAutomatically = true;
            applyNames(response.autoNames);
          }
          else {
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
  form.append(message, choices, review, apply, cancel);
  naming.append(form);
  void send("get_pos_import_boards", { harnessId, interfaceId }).then((response) => {
    if (naming.querySelector(".interface-contact-pos-import") !== form) return;
    if (!response.ok) throw new Error(response.error || "Could not find linked PCB files.");
    const boards = Array.isArray(response.boards) ? response.boards : [];
    message.textContent = boards.length
      ? "Choose the linked 2D PCB to read pad names from:"
      : "No linked 2D PCB was found for this Interface. Use Load brd for a local board file.";
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
    apply.disabled = !boards.length;
  }).catch((error) => {
    if (naming.querySelector(".interface-contact-pos-import") === form) {
      message.textContent = String(error);
    }
  });
}

/** Open the contact-selection workspace for one Interface. */
function openInterfaceContacts(harness, interfaceItem) {
  const previous = document.body.querySelector(".interface-contacts-popup");
  if (previous?.open) previous.close();
  const dialog = document.createElement("dialog");
  const title = document.createElement("h2");
  const modes = document.createElement("div");
  const toolbar = document.createElement("div");
  const naming = document.createElement("div");
  const diagram = document.createElement("div");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const rebuild = document.createElement("button");
  const remove = document.createElement("button");
  const buttons = [];

  dialog.className = "interface-contacts-popup";
  dialog.dataset.harnessId = harness.harnessId;
  dialog.dataset.interfaceId = interfaceItem.interfaceId;
  dialog.dataset.contactDocumentScope = currentState.contactDocumentScope || "";
  dialog.setAttribute("aria-label", `Select Contacts: ${interfaceItem.name}`);
  title.textContent = `Select Contacts · ${interfaceItem.name}`;
  modes.className = "interface-contacts-modes";
  modes.setAttribute("role", "group");
  modes.setAttribute("aria-label", "Contact selection mode");
  ["Manual", "Row", "Plane"].forEach((label, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button compact";
    button.textContent = label;
    button.setAttribute("aria-pressed", `${index === 0}`);
    button.addEventListener("click", () => {
      buttons.forEach((candidate) => {
        candidate.setAttribute("aria-pressed", `${candidate === button}`);
      });
      void send("select_interface_contacts", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId,
        mode: ["manual", "row", "plane"][index],
      }).catch((error) => appendNotice(String(error), true));
    });
    buttons.push(button);
    modes.append(button);
  });
  remove.type = "button";
  remove.className = "button compact";
  remove.textContent = "Delete";
  remove.title = "Delete selected contacts from this Interface (Del)";
  remove.disabled = true;
  modes.append(remove);
  toolbar.className = "interface-contacts-toolbar";
  naming.className = "interface-contacts-naming";
  naming.setAttribute("role", "group");
  naming.setAttribute("aria-label", "Contact naming");
  const autoPin = document.createElement("button");
  autoPin.type = "button";
  autoPin.className = "button compact";
  autoPin.textContent = "Auto Pin";
  autoPin.addEventListener("click", () => openInterfaceAutoPin(
    naming, diagram, harness.harnessId, interfaceItem.interfaceId,
  ));
  naming.append(autoPin);
  const posImport = document.createElement("button");
  posImport.type = "button";
  posImport.className = "button compact";
  posImport.textContent = "Pos Import";
  posImport.addEventListener("click", () => openInterfacePosImport(
    naming, harness.harnessId, interfaceItem.interfaceId,
  ));
  [["Geo Import", "geo_import_interface_contacts"],
    ["Load brd", "load_brd_interface_contacts"]].forEach(([label, action]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button compact";
    button.textContent = label;
    button.addEventListener("click", () => {
      void send(action, {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId,
        ...(action === "geo_import_interface_contacts"
          ? { contactIds: [...diagram.contactState.selectedIds] } : {}),
      }).catch((error) => appendNotice(String(error), true));
    });
    naming.append(button);
  });
  naming.insertBefore(posImport, naming.children[2]);
  toolbar.append(modes, naming);
  diagram.className = "interface-contacts-diagram";
  diagram.setAttribute("role", "region");
  diagram.setAttribute("aria-label", "Contact diagram");
  renderInterfaceContacts(diagram, []);
  diagram.contactState.harnessId = harness.harnessId;
  diagram.contactState.interfaceId = interfaceItem.interfaceId;
  diagram.contactState.deleteButton = remove;
  diagram.contactState.onDeleteContacts = async (ids = null) => {
    const state = diagram.contactState;
    const contactIds = ids || [...state.selectedIds];
    if (!dialog.open || !state || state.deleting || state.clearing || state.workspace.root.hidden
      || !contactIds.length) return;
    state.deleting = true;
    paintInterfaceContactSelection(state);
    try {
      const response = await send("remove_interface_contacts", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId, contactIds,
      });
      if (!response.ok) throw new Error(response.error || "Could not delete selected contacts.");
      contactIds.forEach((id) => state.selectedIds.delete(id));
    } catch (error) {
      if (dialog.open) appendNotice(String(error), true);
    } finally {
      if (dialog.open && diagram.contactState === state) {
        state.deleting = false;
        paintInterfaceContactSelection(state);
      }
    }
  };
  diagram.contactState.onClearPins = async (ids = null) => {
    const state = diagram.contactState;
    const contactIds = ids || [...state.selectedIds];
    if (!dialog.open || !state || state.deleting || state.clearing || state.workspace.root.hidden
      || !contactIds.length) return;
    state.clearing = true;
    paintInterfaceContactSelection(state);
    try {
      const response = await send("clear_interface_contact_pins", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId, contactIds,
      });
      if (!response.ok) throw new Error(response.error || "Could not clear selected pins.");
    } catch (error) {
      if (dialog.open) appendNotice(String(error), true);
    } finally {
      if (dialog.open && diagram.contactState === state) {
        state.clearing = false;
        paintInterfaceContactSelection(state);
      }
    }
  };
  diagram.contactState.onClearValues = async (ids = null) => {
    const state = diagram.contactState;
    const contactIds = ids || [...state.selectedIds];
    if (!dialog.open || !state || state.deleting || state.clearing || state.workspace.root.hidden
      || !contactIds.length) return;
    state.clearing = true;
    paintInterfaceContactSelection(state);
    try {
      const response = await send("clear_interface_contact_values", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId, contactIds,
      });
      if (!response.ok) throw new Error(response.error || "Could not clear selected values.");
    } catch (error) {
      if (dialog.open) appendNotice(String(error), true);
    } finally {
      if (dialog.open && diagram.contactState === state) {
        state.clearing = false;
        paintInterfaceContactSelection(state);
      }
    }
  };
  remove.addEventListener("click", () => { void diagram.contactState?.onDeleteContacts?.(); });
  diagram.contactState.onEditContact = (contactId, event) => {
    openInterfaceContactEditor(diagram, diagram.contactState, contactId, event);
  };
  diagram.contactState.onEditOrientation = (orientation, event) => {
    openInterfaceOrientationEditor(diagram, diagram.contactState, orientation, event);
  };
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  rebuild.type = "button";
  rebuild.className = "button";
  rebuild.textContent = "Rebuild Cache";
  rebuild.title = "Discard this Interface's cached outlines and resample them from Fusion";
  rebuild.addEventListener("click", () => { void rebuildInterfaceContactCache(dialog); });
  dialog.rebuildButton = rebuild;
  actions.append(close, rebuild);
  dialog.append(title, toolbar, diagram, actions);
  dialog.addEventListener("close", () => {
    diagram.contactState.showContextMenu.close();
    diagram.contactState.items.forEach((item) => item.clearHover?.());
    // A cached SVG must not retain the old workspace's event handlers and state.
    if (currentContactGeometry(dialog)?.rendered?.svg === diagram.contactState.svg) {
      diagram.contactState.workspace.stage.replaceChildren();
    }
    dialog.contactMetadata = [];
    diagram.contactState = null;
    diagram.replaceChildren();
    dialog.remove();
  });
  document.body.append(dialog);
  dialog.showModal();
  updateInterfaceContactData(dialog, interfaceItem.contacts || []);
  window.requestAnimationFrame(() => {
    if (dialog.open && !diagram.contactState.workspace.root.hidden) diagram.contactState.workspace.fit();
  });
}
