function openHarness(key) {
  const harness = currentState.harnesses.find((candidate) => harnessKey(candidate) === key);
  if (!harness) return;
  selectedHarnessKey = key;
  writeSession("wireBundler.selectedHarness", key);
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
  closeWireGroupDetails();
  closeCreateWiresPopup();
  selectedHarnessKey = "";
  removeSession("wireBundler.selectedHarness");
  ui.editorView.hidden = true;
  ui.libraryView.hidden = false;
  ui.editor.replaceChildren();
  clearValidationDisplay();
  ui.harnessFilter.focus();
}

function render(state) {
  const scrollTop = document.scrollingElement.scrollTop;
  currentState = state;
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
    closeCreateWiresPopup();
    selectedHarnessKey = "";
    removeSession("wireBundler.selectedHarness");
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
    writePreference("wireBundler.verboseDiagnostics", "false");
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
  if (Number.isFinite(height)) writeSession("wireBundler.noticeHeight", String(height));
}

let qaHoverTarget = null;

function qaHasReadableBox(node) {
  if (!node?.getBoundingClientRect) return false;
  if (node.getClientRects && node.getClientRects().length === 0) return false;
  const rect = node.getBoundingClientRect();
  return [rect.left, rect.top, rect.right, rect.bottom, rect.width, rect.height]
    .every(Number.isFinite) && rect.width >= 16 && rect.height >= 12;
}

function qaWireDialogFitsViewport(card) {
  const trigger = card.querySelector(".wire-options-button");
  if (!trigger?.dispatchEvent) return false;
  trigger.dispatchEvent(new window.Event("click"));
  const dialog = Array.from(document.body.children).reverse().find(
    (candidate) => candidate.open
      && candidate.className?.split(" ").includes("material-options"),
  );
  if (!dialog) return false;
  try {
    const rect = dialog.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement?.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement?.clientHeight || 0;
    const heading = dialog.querySelector("h2");
    const buttons = Array.from(dialog.querySelectorAll("button"));
    const actions = ["Cancel", "Apply", "Save"].map(
      (label) => buttons.find((button) => button.textContent === label),
    );
    const visibleControls = Array.from(
      dialog.querySelectorAll("input, select, textarea, button"),
    ).filter(qaHasReadableBox);
    return dialog.open
      && qaHasReadableBox(dialog)
      && viewportWidth > 0
      && viewportHeight > 0
      && rect.left >= -1
      && rect.top >= -1
      && rect.right <= viewportWidth + 1
      && rect.bottom <= viewportHeight + 1
      && dialog.scrollWidth <= dialog.clientWidth + 1
      && qaHasReadableBox(heading)
      && heading.textContent.startsWith("Wire options · ")
      && actions.every(qaHasReadableBox)
      && visibleControls.length >= 6;
  } finally {
    dialog.close();
  }
}

function qaWireCard(harnessId, wireId) {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === harnessId,
  );
  const wire = harness?.wires?.find((candidate) => candidate.wireId === wireId);
  if (!harness || !wire) return {};
  openHarness(harnessId);
  const routes = renderWireRoutes(harness);
  const card = Array.from(routes.querySelectorAll("div"))
    .find((candidate) => candidate.dataset.wireId === wireId);
  return { harness, wire, card };
}

function qaRelationshipEdgeGap(edge) {
  const siblings = Array.from(edge.parentElement?.children || [])
    .filter((candidate) => typeof candidate?.getBoundingClientRect === "function");
  const edgeIndex = siblings.indexOf(edge);
  if (edgeIndex <= 0 || edgeIndex >= siblings.length - 1) return Number.POSITIVE_INFINITY;
  const previousRect = siblings[edgeIndex - 1].getBoundingClientRect();
  const edgeRect = edge.getBoundingClientRect();
  const nextRect = siblings[edgeIndex + 1].getBoundingClientRect();
  return Math.max(
    0,
    edgeRect.left - previousRect.right,
    nextRect.left - edgeRect.right,
  );
}

function qaTopologyEdgeGap(edge, diagram) {
  if (typeof edge.getTotalLength !== "function"
      || typeof edge.getPointAtLength !== "function"
      || typeof edge.getScreenCTM !== "function") return Number.POSITIVE_INFINITY;
  const endpoint = edge.dataset.endpoint;
  const pathway = diagram.querySelector(
    `.relationship-topology-pathway[data-pathway-id="${edge.dataset.pathwayId}"]`,
  );
  const junction = diagram.querySelector(
    `.relationship-topology-junction[data-junction-id="${edge.dataset.junctionId}"]`,
  );
  if (!pathway || !junction) return Number.POSITIVE_INFINITY;
  const source = endpoint === "end" ? pathway : junction;
  const target = endpoint === "end" ? junction : pathway;
  const matrix = edge.getScreenCTM();
  if (!matrix) return Number.POSITIVE_INFINITY;
  const project = (point) => ({
    x: matrix.a * point.x + matrix.c * point.y + matrix.e,
    y: matrix.b * point.x + matrix.d * point.y + matrix.f,
  });
  const start = project(edge.getPointAtLength(0));
  const finish = project(edge.getPointAtLength(edge.getTotalLength()));
  const sourceRect = source.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const sideGap = (point, rectangle, side) => {
    if (!["left", "right", "top", "bottom"].includes(side)) {
      return Number.POSITIVE_INFINITY;
    }
    if (["left", "right"].includes(side)) {
      const sideX = side === "left" ? rectangle.left : rectangle.right;
      return Math.max(
        Math.abs(point.x - sideX),
        Math.max(0, rectangle.top - point.y, point.y - rectangle.bottom),
      );
    }
    const sideY = side === "top" ? rectangle.top : rectangle.bottom;
    return Math.max(
      Math.abs(point.y - sideY),
      Math.max(0, rectangle.left - point.x, point.x - rectangle.right),
    );
  };
  return Math.max(
    sideGap(start, sourceRect, edge.parentElement?.dataset.sourceSide),
    sideGap(finish, targetRect, edge.parentElement?.dataset.targetSide),
  );
}

function qaTopologyTraceObstructed(edge, diagram) {
  if (typeof edge.getTotalLength !== "function"
      || typeof edge.getPointAtLength !== "function"
      || typeof edge.getScreenCTM !== "function") return false;
  const matrix = edge.getScreenCTM();
  if (!matrix) return false;
  const nodes = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-node") || [],
  ).filter((node) => {
    if (node.dataset.pathwayId === edge.dataset.pathwayId) return false;
    return node.dataset.junctionId !== edge.dataset.junctionId;
  });
  const length = edge.getTotalLength();
  const sampleCount = Math.max(2, Math.ceil(length / 4));
  for (let index = 0; index <= sampleCount; index += 1) {
    const point = edge.getPointAtLength(length * index / sampleCount);
    const projected = {
      x: matrix.a * point.x + matrix.c * point.y + matrix.e,
      y: matrix.b * point.x + matrix.d * point.y + matrix.f,
    };
    if (nodes.some((node) => {
      const rectangle = node.getBoundingClientRect();
      return projected.x > rectangle.left + 1 && projected.x < rectangle.right - 1
        && projected.y > rectangle.top + 1 && projected.y < rectangle.bottom - 1;
    })) return true;
  }
  return false;
}

function qaRelationshipNodesOverlap(nodes) {
  return nodes.some((node, index) => {
    const rect = node.getBoundingClientRect();
    return nodes.slice(index + 1).some((other) => {
      const otherRect = other.getBoundingClientRect();
      return rect.left < otherRect.right - 1
        && rect.right > otherRect.left + 1
        && rect.top < otherRect.bottom - 1
        && rect.bottom > otherRect.top + 1;
    });
  });
}

function qaInvalidTraceGroupCount(diagram) {
  const edges = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-edge") || [],
  );
  const ports = Array.from(
    diagram.querySelectorAll?.(".relationship-topology-port") || [],
  );
  const attribute = (node, name) => (
    node?.getAttribute?.(name) ?? node?.attributes?.[name] ?? ""
  );
  const portFor = (portId) => ports.find((port) => port.dataset.portId === portId);
  const invalidEdges = edges.filter((edge) => {
    const wireCount = Number.parseInt(edge.dataset.wireCount, 10);
    const mode = edge.dataset.renderMode;
    const lanes = Array.from(edge.querySelectorAll?.(".relationship-wire-lane") || []);
    const bundles = Array.from(edge.querySelectorAll?.(".relationship-wire-bundle") || []);
    const badges = Array.from(edge.querySelectorAll?.(".relationship-wire-count") || []);
    const wireIds = relationshipElementWireIds(edge);
    const expectedMode = wireCount === 0
      ? "structure" : wireCount <= TOPOLOGY_LANE_LIMIT ? "lanes" : "bundle";
    if (!Number.isInteger(wireCount) || wireCount < 0 || wireIds.size !== wireCount
        || mode !== expectedMode) return true;
    if (mode === "structure" && (lanes.length || bundles.length || badges.length)) return true;
    if (mode === "lanes") {
      const offsets = lanes.map((lane) => Number.parseFloat(lane.dataset.laneOffset));
      const expectedOffsets = lanes.map((_lane, index) => (
        (index - (wireCount - 1) / 2) * TOPOLOGY_LANE_SPACING
      ));
      if (lanes.length !== wireCount || bundles.length || badges.length
          || offsets.some((offset) => !Number.isFinite(offset))
          || offsets.some((offset, index) => offset !== expectedOffsets[index])) return true;
    }
    if (mode === "bundle" && (lanes.length || bundles.length !== 1 || badges.length !== 1)) {
      return true;
    }
    const sourcePort = portFor(edge.dataset.sourcePortId);
    const targetPort = portFor(edge.dataset.targetPortId);
    if (!sourcePort || !targetPort) return true;
    if (sourcePort.dataset.nodeId !== edge.dataset.sourceId
        || targetPort.dataset.nodeId !== edge.dataset.targetId
        || sourcePort.dataset.side !== edge.dataset.sourceSide
        || targetPort.dataset.side !== edge.dataset.targetSide) return true;
    if (mode !== "lanes") return false;
    return lanes.some((lane) => {
      const endpoints = [{
        x: Number.parseFloat(attribute(lane, "data-source-x")),
        y: Number.parseFloat(attribute(lane, "data-source-y")),
      }, {
        x: Number.parseFloat(attribute(lane, "data-target-x")),
        y: Number.parseFloat(attribute(lane, "data-target-y")),
      }];
      return [sourcePort, targetPort].some((port, index) => {
        const portLeft = Number.parseFloat(attribute(port, "x"));
        const portTop = Number.parseFloat(attribute(port, "y"));
        const portWidth = Number.parseFloat(attribute(port, "width"));
        const portHeight = Number.parseFloat(attribute(port, "height"));
        const laneX = endpoints[index].x;
        const laneY = endpoints[index].y;
        return laneX < portLeft || laneX > portLeft + portWidth
          || laneY < portTop || laneY > portTop + portHeight;
      });
    });
  });
  return Number(invalidEdges.length);
}

function qaObserveRelationshipDiagram() {
  const selectedHarness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  const hasDiagramNode = (candidate) => (
    candidate?.pathways?.length || candidate?.junctions?.length
  );
  const harness = hasDiagramNode(selectedHarness)
    ? selectedHarness : currentState.harnesses.find(hasDiagramNode);
  if (!harness) {
    void send("qa_diagram_observation", {
      status: "skipped",
      connectorCount: 0,
      maximumEndpointGap: 0,
      obstructedTraceCount: 0,
      portCount: 0,
      invalidTraceGroupCount: 0,
      contractVersion: RELATIONSHIP_DIAGRAM_CONTRACT_VERSION,
      layout: RELATIONSHIP_DIAGRAM_LAYOUT,
    }).catch(() => {});
    return "OK";
  }
  openHarness(harnessKey(harness));
  const section = ui.editor.querySelector('[data-section="master-relationship-graphic"]');
  if (section) section.open = true;
  const filter = Array.from(section?.querySelectorAll("input") || []).find(
    (candidate) => candidate.getAttribute?.("aria-label") === "Filter master relationship graphic"
      || candidate.attributes?.["aria-label"] === "Filter master relationship graphic",
  );
  if (filter?.value) {
    filter.value = "";
    filter.dispatchEvent(new window.Event("input"));
  }
  window.requestAnimationFrame(() => {
    const diagram = ui.editor.querySelector(".relationship-map");
    const workspace = diagram?.querySelector?.(".block-diagram-workspace");
    const pathwayGroups = Array.from(
      diagram?.querySelectorAll?.(".relationship-pathway-group") || [],
    );
    const pathwayHubs = Array.from(
      diagram?.querySelectorAll?.(".relationship-pathway-hub") || [],
    );
    const junctionHubs = Array.from(
      diagram?.querySelectorAll?.(".relationship-junction-hub") || [],
    );
    const connectorEdges = [
      ...Array.from(diagram?.querySelectorAll?.(".relationship-connector") || []),
      ...Array.from(diagram?.querySelectorAll?.(".relationship-chain-link") || []),
    ];
    const topologyEdges = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-edges .structural-trace") || [],
    );
    const topologyNodes = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-node") || [],
    );
    const topologyPorts = Array.from(
      diagram?.querySelectorAll?.(".relationship-topology-port") || [],
    );
    const paths = Array.from(diagram?.querySelectorAll?.("path") || []);
    const connectorCount = paths.length;
    const endpointGaps = [
      ...connectorEdges.map(qaRelationshipEdgeGap),
      ...topologyEdges.map((edge) => qaTopologyEdgeGap(edge, diagram)),
    ];
    const maximumEndpointGap = endpointGaps.length ? Math.max(...endpointGaps) : 0;
    const obstructedTraceCount = topologyEdges.filter(
      (edge) => qaTopologyTraceObstructed(edge, diagram),
    ).length;
    const invalidTraceGroupCount = qaInvalidTraceGroupCount(diagram);
    const contractVersion = diagram?.dataset.diagramContractVersion || "";
    const layout = diagram?.dataset.diagramLayout || "";
    const passed = Boolean(workspace)
      && pathwayGroups.length === harness.pathways.length
      && pathwayHubs.length === harness.pathways.length
      && junctionHubs.length === (harness.junctions || []).length
      && (harness.pathways.length === 0 || connectorEdges.length > 0)
      && maximumEndpointGap <= 1
      && obstructedTraceCount === 0
      && (topologyEdges.length === 0 || topologyPorts.length > 0)
      && invalidTraceGroupCount === 0
      && !qaRelationshipNodesOverlap(topologyNodes)
      && contractVersion === RELATIONSHIP_DIAGRAM_CONTRACT_VERSION
      && layout === RELATIONSHIP_DIAGRAM_LAYOUT
      && paths.every((path) => Boolean(path.getAttribute?.("d") || path.attributes?.d));
    section?.scrollIntoView({ block: "center" });
    void send("qa_diagram_observation", {
      status: passed ? "passed" : "failed",
      connectorCount,
      maximumEndpointGap,
      obstructedTraceCount,
      portCount: topologyPorts.length,
      invalidTraceGroupCount,
      contractVersion,
      layout,
    }).catch(() => {});
  });
  return "OK";
}
function handleQaProbe(data) {
  if (!developerModeEnabled) return "DENIED";
  let payload;
  try {
    payload = JSON.parse(data);
  } catch (_error) {
    return "INVALID";
  }
  const validText = (value) => typeof value === "string" && value.length > 0
    && value.length <= 160;
  if (payload?.operation === "leave_hover") {
    if (!qaHoverTarget) return "MISMATCH";
    qaHoverTarget.dispatchEvent(new window.Event("mouseleave"));
    qaHoverTarget = null;
    return "OK";
  }
  if (payload?.operation === "observe_relationship_diagram") {
    return qaObserveRelationshipDiagram();
  }
  if (!validText(payload?.harnessId) || !validText(payload?.wireId)) return "INVALID";
  const { wire, card } = qaWireCard(payload.harnessId, payload.wireId);
  if (!wire || !card) return "MISMATCH";
  if (payload.operation === "observe_wire") {
    if (!validText(payload.expectedLabel)
        || wireLabel(wire) !== payload.expectedLabel) return "MISMATCH";
    const label = card.querySelector(".member-reference");
    if (ui.editorView.hidden || !ui.libraryView.hidden
        || label?.textContent !== payload.expectedLabel) return "MISMATCH";
    void send("clear_highlight").catch(() => {});
    return "OK";
  }
  if (payload.operation === "observe_wire_dialog") {
    if (!qaWireDialogFitsViewport(card)) return "MISMATCH";
    void send("clear_highlight").catch(() => {});
    return "OK";
  }
  let target = null;
  if (payload.operation === "hover_wire") {
    target = card.children[0];
  } else if (payload.operation === "hover_connection"
      && ["start", "end"].includes(payload.endpoint)) {
    target = Array.from(card.querySelectorAll("g"))
      .find((candidate) => candidate.dataset.endpoint === payload.endpoint);
  } else if (payload.operation === "hover_pathway" && validText(payload.pathwayId)) {
    target = Array.from(card.querySelectorAll("g"))
      .find((candidate) => candidate.dataset.pathwayId === payload.pathwayId);
  } else {
    return "INVALID";
  }
  if (!target?.dispatchEvent) return "MISMATCH";
  qaHoverTarget = target;
  target.dispatchEvent(new window.Event("mouseenter"));
  return "OK";
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
  if (!harness || harness.status === "damaged" || !harness.wires?.length) return;
  if (!window.confirm("Build wire solids? This replaces previous generated wire components, including manual edits inside them.")) return;
  return mutate("generate_solids", { harnessId: harness.harnessId, replaceExisting: true }, "Generating wire solids…");
}

function clearSolids() {
  const harness = currentState.harnesses.find((item) => harnessKey(item) === selectedHarnessKey);
  if (!harness || harness.status === "damaged") return;
  if (!window.confirm("Clear generated wire solids? This removes manual edits inside generated wire components.")) return;
  return mutate("clear_solids", { harnessId: harness.harnessId }, "Clearing wire solids…");
}

async function refresh() {
  try {
    render(await send("get_state"));
  } catch (error) {
    appendNotice(error.message, true);
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
  const deletedWires = harness.wires.filter((wire) => wire.orderedPathwayIds.some(
    (pathwayId) => deletedPathwayIds.has(pathwayId),
  ));
  const deletedEnds = (harness.standaloneEnds || []).filter(
    (end) => deletedPathwayIds.has(end.pathwayId),
  );
  const descendantCount = deletedPathwayIds.size - 1;
  const pathwayLabel = pathway.name || "this pathway";
  const warning = [
    `Delete ${pathwayLabel} and ${descendantCount} descendant ${descendantCount === 1 ? "pathway" : "pathways"}?`,
    `This also deletes ${deletedWires.length} ${deletedWires.length === 1 ? "wire" : "wires"} and ${deletedEnds.length} standalone ${deletedEnds.length === 1 ? "end" : "ends"}.`,
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
    "Connected pathways, wires, and neighboring junctions will be kept.",
    "This action can be undone in Fusion.",
  ].join(" ");
  if (!window.confirm(warning)) return;
  void mutate(
    "remove_junction",
    { harnessId: harness.harnessId, junctionId: junction.junctionId },
    `Deleting ${junctionLabel}…`,
  );
}

function removeWirePair(harness, wire) {
  if (!window.confirm(`Remove wire #${wire.wireNumber} and both connection assignments?`)) return;
  void mutate(
    "remove_wire",
    { harnessId: harness.harnessId, wireId: wire.wireId },
    `Removing wire #${wire.wireNumber}…`,
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

async function addWires(pathwayId = null) {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged" || !harness.pathways.length) return;
  appendNotice("Opening Add Wires…");
  try {
    const response = await send("add_wires", { harnessId: harness.harnessId, pathwayId });
    if (!response.ok) {
      appendNotice(response.error || "Add Wires could not be opened.", true);
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
}

async function previewRoutes() {
  const harness = currentState.harnesses.find(
    (candidate) => harnessKey(candidate) === selectedHarnessKey,
  );
  if (!harness || harness.status === "damaged" || !(harness.wireGroups || []).length) return;
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
    }
  } catch (error) {
    appendNotice(error.message, true);
  }
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
    writePreference("wireBundler.verboseDiagnostics", "false");
    return;
  }
  writePreference("wireBundler.verboseDiagnostics", String(ui.verboseDiagnostics.checked));
  Array.from(ui.notice.children).forEach(updateNoticeEntry);
});
ui.notice.addEventListener("mouseup", persistNoticeHeight);
window.fusionJavaScriptHandler = { handle(action, data) {
  if (action === "state") render(JSON.parse(data));
  if (action === "qa_probe") return handleQaProbe(data);
  return "OK";
}};
void refresh();
