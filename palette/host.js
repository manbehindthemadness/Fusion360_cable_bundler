function openHarness(key) {
  const harness = currentState.harnesses.find((candidate) => harnessKey(candidate) === key);
  if (!harness) return;
  selectedHarnessKey = key;
  writeSession("cableBundler.selectedHarness", key);
  ui.libraryView.hidden = true;
  ui.editorView.hidden = false;
  renderEditor(harness);
  window.scrollTo(0, 0);
}

function closeEditor() {
  send("clear_highlight").catch(() => {});
  resetMasterDiagramSizing();
  closePathwayPopup();
  closeJunctionRelationships();
  closeCableGroupDetails();
  closeCreateCablesPopup();
  selectedHarnessKey = "";
  removeSession("cableBundler.selectedHarness");
  ui.editorView.hidden = true;
  ui.libraryView.hidden = false;
  ui.editor.replaceChildren();
  clearValidationDisplay();
  ui.harnessFilter.focus();
}

function render(state) {
  const scrollTop = document.scrollingElement.scrollTop;
  currentState = state;
  applyPaletteTheme(state.theme);
  appendNotice(state.notice);
  renderLibrary();
  const selected = state.harnesses.find(
    (harness) => harnessKey(harness) === selectedHarnessKey,
  );
  if (selected) {
    ui.libraryView.hidden = true;
    ui.editorView.hidden = false;
    renderEditor(selected);
  } else {
    resetMasterDiagramSizing();
    closePathwayPopup();
    closeJunctionRelationships();
    closeCreateCablesPopup();
    selectedHarnessKey = "";
    removeSession("cableBundler.selectedHarness");
    ui.editorView.hidden = true;
    ui.libraryView.hidden = false;
    clearValidationDisplay();
  }
  window.requestAnimationFrame(() => window.scrollTo(0, scrollTop));
}

function appendNotice(message, isError = false) {
  if (!message) return;
  const previous = ui.notice.children[ui.notice.children.length - 1];
  if (previous?.dataset.message === message
      && previous.className.includes(isError ? "error" : "notice-entry")) return;
  const entry = document.createElement("div");
  entry.className = `notice-entry${isError ? " error" : ""}`;
  entry.dataset.message = message;
  updateNoticeEntry(entry);
  ui.notice.append(entry);
  ui.notice.scrollTop = ui.notice.scrollHeight;
}

function updateNoticeEntry(entry) {
  const marker = " Routing diagnostic: ";
  const message = entry.dataset.message || "";
  const markerIndex = message.indexOf(marker);
  entry.textContent = markerIndex >= 0 && !ui.verboseDiagnostics.checked
    ? message.slice(0, markerIndex)
    : message;
}

function setDeveloperMode(enabled) {
  developerModeEnabled = enabled;
  ui.developerMode.checked = enabled;
  ui.verboseDiagnostics.disabled = !enabled;
  writePreference(DEVELOPER_MODE_STORAGE_KEY, String(enabled));
  if (enabled) {
    writePreference(DEVELOPER_CONSENT_STORAGE_KEY, DEVELOPER_MODE_DISCLOSURE_VERSION);
  } else {
    ui.verboseDiagnostics.checked = false;
    writePreference("cableBundler.verboseDiagnostics", "false");
  }
  Array.from(ui.notice.children).forEach(updateNoticeEntry);
}

function openDeveloperConsent() {
  ui.developerMode.checked = developerModeEnabled;
  ui.developerConsentAgreement.checked = false;
  ui.developerConsentEnable.disabled = true;
  ui.developerConsent.showModal();
}

function closeDeveloperConsent() {
  ui.developerConsent.close();
}

function persistNoticeHeight() {
  if (!ui.notice.getBoundingClientRect) return;
  const height = Math.round(ui.notice.getBoundingClientRect().height);
  if (Number.isFinite(height)) writeSession("cableBundler.noticeHeight", String(height));
}

function waitForFusionHost() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const timer = window.setInterval(() => {
      const fusionHost = window["adsk"];
      if (fusionHost && fusionHost.fusionSendData) {
        window.clearInterval(timer);
        resolve(fusionHost);
        return;
      }
      attempts += 1;
      if (attempts >= 50) {
        window.clearInterval(timer);
        reject(new Error("Fusion did not initialize the palette bridge."));
      }
    }, 100);
  });
}

async function send(action, payload = {}) {
  const fusionHost = await waitForFusionHost();
  const response = await fusionHost.fusionSendData(action, JSON.stringify(payload));
  return JSON.parse(response);
}

function generateSolids() {
  const harness = currentState.harnesses.find((item) => harnessKey(item) === selectedHarnessKey);
  if (!harness || harness.status === "damaged" || !(harness.cableGroups || []).length) return;
  return mutate("generate_solids", { harnessId: harness.harnessId, replaceExisting: true }, "Generating cable solids…");
}

function clearSolids() {
  const harness = currentState.harnesses.find((item) => harnessKey(item) === selectedHarnessKey);
  if (!harness || harness.status === "damaged") return;
  return mutate("clear_solids", { harnessId: harness.harnessId }, "Clearing cable solids…");
}

async function refresh() {
  try {
    render(await send("get_state"));
  } catch (error) {
    appendNotice(error.message, true);
  }
}

let paletteThemePollInFlight = false;

async function pollFusionTheme() {
  if (paletteThemeMode !== "device" || paletteThemePollInFlight) return;
  paletteThemePollInFlight = true;
  try {
    const response = await send("get_theme");
    if (response.ok) applyPaletteTheme(response.theme);
  } catch (_error) {
    // Initial state loading reports bridge errors; recurring theme checks stay quiet.
  } finally {
    paletteThemePollInFlight = false;
  }
}

async function createHarness() {
  appendNotice("Opening Create Harness…");
  try {
    const response = await send("create_harness");
    if (!response.ok) {
      appendNotice(response.error || "Create Harness could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function mutate(action, payload, progress) {
  appendNotice(progress);
  try {
    const response = await send(action, payload);
    if (!response.ok) {
      appendNotice(response.error || "The harness edit could not be completed.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function highlightMember(harness, memberType, memberId, extra = {}) {
  try {
    const response = await send("highlight_member", {
      harnessId: harness.harnessId,
      memberType,
      memberId,
      ...extra,
    });
    if (!response.ok) {
      appendNotice(response.error || "Linked geometry could not be highlighted.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function appendPathwayGates(harness, pathway) {
  appendNotice(`Selecting additional gates for ${pathway.name}…`);
  try {
    const response = await send("append_pathway_gates", {
      harnessId: harness.harnessId,
      pathwayId: pathway.pathwayId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Add Gates could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function addPathwayRefine(harness, pathway) {
  appendNotice(`Select a refine location on ${pathway.name}…`);
  try {
    const response = await send("add_pathway_refine", {
      harnessId: harness.harnessId,
      pathwayId: pathway.pathwayId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Add Refine Point could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function appendEndGuides(harness, connectionId) {
  appendNotice("Select additional guides for this end…");
  try {
    const response = await send("append_end_guides", {
      harnessId: harness.harnessId,
      connectionId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Add Guides could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function addEndRefine(harness, connectionId) {
  appendNotice("Select a refine location on this end’s routing span…");
  try {
    const response = await send("add_end_refine", {
      harnessId: harness.harnessId,
      connectionId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Add Refine Point could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function segmentPathway(harness, pathway) {
  appendNotice(`Select an interior control on ${pathway.name}…`);
  try {
    const response = await send("segment_pathway", {
      harnessId: harness.harnessId,
      pathwayId: pathway.pathwayId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Segment Pathway could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function editPathwayRefine(harness, control) {
  appendNotice(`Editing ${control.name || "refine point"}…`);
  try {
    const response = await send("edit_pathway_refine", {
      harnessId: harness.harnessId,
      controlId: control.controlId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Edit Refine Point could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

function removeGate(harness, pathway, controlId, name) {
  if (!window.confirm(`Remove ${name} from ${pathway.name}?`)) return;
  void mutate(
    "remove_pathway_gate",
    { harnessId: harness.harnessId, pathwayId: pathway.pathwayId, controlId },
    "Removing gate…",
  );
}

function removePathway(harness, pathway) {
  const deletedPathwayIds = relationshipPathwayDeletionIds(harness, pathway.pathwayId);
  const deletedEnds = (harness.standaloneEnds || []).filter(
    (end) => deletedPathwayIds.has(end.pathwayId),
  );
  const affectedGroups = (harness.cableGroups || []).filter((group) => (
    (group.routeLegs || []).some((leg) => (
      (leg.pathwayIds || []).some((pathwayId) => deletedPathwayIds.has(pathwayId))
    ))
  ));
  const descendantCount = deletedPathwayIds.size - 1;
  const pathwayLabel = pathway.name || "this pathway";
  const warning = [
    `Delete ${pathwayLabel} and ${descendantCount} descendant ${descendantCount === 1 ? "pathway" : "pathways"}?`,
    `This also deletes ${deletedEnds.length} standalone ${deletedEnds.length === 1 ? "end" : "ends"} and updates ${affectedGroups.length} cable ${affectedGroups.length === 1 ? "group" : "groups"}.`,
    "This action can be undone in Fusion.",
  ].join(" ");
  if (!window.confirm(warning)) return;
  void mutate(
    "remove_pathway",
    { harnessId: harness.harnessId, pathwayId: pathway.pathwayId },
    `Deleting ${pathwayLabel}…`,
  );
}

function removeJunction(harness, junction) {
  const junctionLabel = junction.name || "this junction";
  const warning = [
    `Delete ${junctionLabel}?`,
    "Connected pathways, cable groups, and neighboring junctions will be kept.",
    "This action can be undone in Fusion.",
  ].join(" ");
  if (!window.confirm(warning)) return;
  void mutate(
    "remove_junction",
    { harnessId: harness.harnessId, junctionId: junction.junctionId },
    `Deleting ${junctionLabel}…`,
  );
}

async function addPathway() {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged") return;
  appendNotice("Opening Add Pathway…");
  try {
    const response = await send("add_pathway", { harnessId: harness.harnessId });
    if (!response.ok) {
      appendNotice(response.error || "Add Pathway could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function addJunction() {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged") return;
  appendNotice("Select an unused sketch profile for the junction…");
  try {
    const response = await send("add_junction", { harnessId: harness.harnessId });
    if (!response.ok) {
      appendNotice(response.error || "Add Junction could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function addEnd() {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged" || !harness.pathways.length) return;
  appendNotice("Select ordered end guides, then one pathway end…");
  try {
    const response = await send("add_end", { harnessId: harness.harnessId });
    if (!response.ok) {
      appendNotice(response.error || "Add End could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function addJunctionRelationship(junctionId) {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged") return;
  appendNotice("Select pathway-ending geometry…");
  try {
    const response = await send("add_junction_relationship", {
      harnessId: harness.harnessId,
      junctionId,
    });
    if (!response.ok) {
      appendNotice(response.error || "Add Relationship could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function previewRoutes() {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged" || !(harness.cableGroups || []).length) return;
  appendNotice("Solving route preview…");
  try {
    const response = await send("preview_routes", { harnessId: harness.harnessId });
    if (!response.ok) {
      appendNotice(response.error || "Routes could not be previewed.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function clearPreview() {
  try {
    const response = await send("clear_preview");
    if (!response.ok) {
      appendNotice(response.error || "Route preview could not be cleared.", true);
    } else {
      appendNotice(response.notice);
      await refresh();
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

function activatePreview() {
  return previewRoutes();
}

function setPreviewEnabled(enabled) {
  return enabled ? activatePreview() : clearPreview();
}

function setSolidsEnabled(enabled) {
  return enabled ? generateSolids() : clearSolids();
}

ui.back.addEventListener("click", closeEditor);
ui.create.addEventListener("click", createHarness);
ui.harnessFilter.addEventListener("input", renderLibrary);
ui.developerMode.addEventListener("change", () => {
  if (ui.developerMode.checked) {
    openDeveloperConsent();
  } else {
    setDeveloperMode(false);
  }
});
ui.developerConsentAgreement.addEventListener("change", () => {
  ui.developerConsentEnable.disabled = !ui.developerConsentAgreement.checked;
});
ui.developerConsentCancel.addEventListener("click", closeDeveloperConsent);
ui.developerConsentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!ui.developerConsentAgreement.checked) return;
  setDeveloperMode(true);
  closeDeveloperConsent();
});
ui.developerConsent.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeDeveloperConsent();
});
ui.developerConsent.addEventListener("close", () => {
  ui.developerMode.checked = developerModeEnabled;
  ui.developerConsentAgreement.checked = false;
  ui.developerConsentEnable.disabled = true;
});
ui.verboseDiagnostics.addEventListener("change", () => {
  if (!developerModeEnabled) {
    ui.verboseDiagnostics.checked = false;
    writePreference("cableBundler.verboseDiagnostics", "false");
    return;
  }
  writePreference("cableBundler.verboseDiagnostics", String(ui.verboseDiagnostics.checked));
  Array.from(ui.notice.children).forEach(updateNoticeEntry);
});
ui.notice.addEventListener("mouseup", persistNoticeHeight);
window.fusionJavaScriptHandler = { handle(action, data) {
  if (action === "state") render(JSON.parse(data));
  if (action === "qa_probe") return handleQaProbe(data);
  return "OK";
}};
if (typeof window.setInterval === "function") {
  window.setInterval(() => void pollFusionTheme(), 10000);
}
void refresh();
