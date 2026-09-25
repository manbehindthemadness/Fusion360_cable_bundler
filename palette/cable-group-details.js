/** Render one cable end's controls in their terminal-to-pathway traversal order. */
function renderCableEndRoutingControls(harness, connection, end) {
  const content = document.createElement("div");
  const sequence = document.createElement("div");
  const addGuides = document.createElement("button");
  const addRefine = document.createElement("button");
  const controls = new Map(
    harness.controls.map((control) => [control.controlId, control]),
  );
  const routingItems = (connection.members || []).map((member) => ({
    id: member.memberId,
    label: `Guide ${member.index + 1}`,
    kind: "guide",
    hasLinkedGeometry: member.hasLinkedGeometry,
    edit: () => openInterpolationOptions(
      harness,
      "end",
      connection.connectionId,
      `Guide ${member.index + 1}`,
      member.interpolation,
      member.usesDefaults,
      member.memberId,
    ),
    highlight: () => highlightMember(
      harness, "connection", connection.connectionId, { memberIndex: member.index },
    ),
    remove: () => removeEndGuide(
      harness, connection.connectionId, member.memberId, `Guide ${member.index + 1}`,
    ),
    removeDisabled: connection.members.length === 1,
    removeTitle: connection.members.length === 1
      ? "A cable end must retain at least one guide"
      : `Remove Guide ${member.index + 1}`,
  }));
  end.orderedControlIds.forEach((controlId) => {
    const control = controls.get(controlId);
    const isRefine = control?.kind === "refine";
    routingItems.push({
      id: controlId,
      label: control?.name || "Missing control",
      kind: isRefine ? "refine" : "guide",
      hasLinkedGeometry: control?.hasLinkedGeometry,
      edit: isRefine
        ? () => editPathwayRefine(harness, control)
        : () => openInterpolationOptions(
          harness, "gate", controlId, control?.name || "Guide", control?.interpolation,
          control?.usesDefaults ?? true,
        ),
      highlight: () => highlightMember(harness, "control", controlId),
      remove: () => removeEndControl(
        harness, connection.connectionId, controlId, control?.name || "this control",
      ),
      removeDisabled: false,
      removeTitle: `Remove ${control?.name || "control"}`,
    });
  });
  content.className = "section-content";
  sequence.className = "sequence";
  routingItems.forEach((item, index) => {
    const row = memberRow(
      `${item.label} #${item.id.slice(0, 8)}`,
      item.highlight,
      [
        optionsButton(
          item.kind === "refine"
            ? "Move, rotate, or resize refine point"
            : "Guide interpolation options",
          item.edit,
          !item.id,
        ),
        actionButton("×", item.removeTitle, item.remove, item.removeDisabled, true),
      ],
      !item.hasLinkedGeometry,
    );
    const position = document.createElement("span");
    row.classList.add("has-sequence-position");
    position.className = "sequence-position";
    position.textContent = `${index + 1}`;
    position.setAttribute("aria-label", `Position ${index + 1}`);
    row.insertBefore(position, row.children[0]);
    row.children[1].title = `Click for ${item.kind} options`;
    sequence.append(row);
  });
  if (!routingItems.length) {
    sequence.append(emptyMessage("No end-owned routing controls."));
  }
  addGuides.type = "button";
  addGuides.className = "button compact";
  addGuides.textContent = "+ Add Guides";
  addGuides.addEventListener("click", () => appendEndGuides(harness, connection.connectionId));
  addRefine.type = "button";
  addRefine.className = "button compact";
  addRefine.textContent = "+ Add Refine Point";
  const pathway = harness.pathways.find((candidate) => candidate.pathwayId === end.pathwayId);
  addRefine.disabled = !pathway || !(pathway.orderedControlIds || []).length;
  addRefine.title = addRefine.disabled
    ? "Requires a pathway with a routing gate"
    : "";
  addRefine.addEventListener("click", () => addEndRefine(harness, connection.connectionId));
  content.append(sequence, addGuides, addRefine);
  const section = nestedSection(
    `end:${connection.connectionId}:routing`,
    "Routing Controls · Traversal Order",
    `${routingItems.length}`,
    content,
    () => highlightMember(harness, "connection", connection.connectionId),
  );
  section.open = true;
  section.classList.add("pathway-popup-entry");
  return section;
}

/** Close the active cable-end routing panel. */
function closeCableEndRoutingPopup(preserveParent = false) {
  const dialog = document.body.querySelector(".cable-end-routing-popup");
  openCableEndRoutingPopupId = "";
  if (!preserveParent) configurationPopupParentState = null;
  dialog?.remove();
  if (dialog?.open) dialog.close();
}

/** Open a refresh-stable routing-control panel for one physical cable end. */
function openCableEndRoutingPopup(harness, connectionId) {
  retainConfigurationPopupParent(harness);
  closePathwayPopup(true);
  closeJunctionRelationships(true);
  closeCableGroupDetails();
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const end = (harness.standaloneEnds || []).find(
    (candidate) => candidate.connectionId === connectionId,
  );
  const prior = document.body.querySelector(".cable-end-routing-popup");
  if (prior) {
    prior.remove();
    if (prior.open) prior.close();
  }
  if (!connection || !end) {
    openCableEndRoutingPopupId = "";
    restoreConfigurationPopupParent();
    return;
  }
  openCableEndRoutingPopupId = connectionId;
  const dialog = document.createElement("dialog");
  const actions = document.createElement("div");
  const close = document.createElement("button");
  const connectionName = connection.name || "Unnamed cable end";
  dialog.className = "cable-end-routing-popup";
  dialog.setAttribute("aria-label", `Cable end routing controls: ${connectionName}`);
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    const isCurrent = document.body.querySelector(".cable-end-routing-popup") === dialog;
    if (isCurrent) openCableEndRoutingPopupId = "";
    dialog.remove();
    if (isCurrent) restoreConfigurationPopupParent();
  });
  actions.append(close);
  dialog.append(renderCableEndRoutingControls(harness, connection, end), actions);
  document.body.append(dialog);
  dialog.showModal();
}

/** Render the supplied plug artwork as a standalone terminal-connection icon. */
function renderPhysicalConnectionIcon(node, connected) {
  const state = connected ? "connected" : "disconnected";
  const icon = svgElement("g", {
    class: `connection-physical-indicator ${state}`,
    role: "img",
    "aria-label": `Physical connection ${state}`,
  });
  const graphic = svgElement("svg", {
    x: node.x + node.width / 2 - 18,
    y: node.y + node.height / 2 - 18,
    width: 24,
    height: 24,
    viewBox: "-2 -2 52 52",
    preserveAspectRatio: "xMidYMid meet",
    "aria-hidden": "true",
  });
  graphic.append(
    svgElement("path", {
      class: "plug-body",
      transform: "rotate(45 24 24)",
      d: "M16 28 H32 V33 C32 37 30 40 26 41 V47 H22 V41 "
        + "C18 40 16 37 16 33 Z",
    }),
    svgElement("path", {
      class: "plug-body",
      transform: "rotate(45 24 24)",
      d: "M16 19 V16 C16 12 18 9 22 8 V1 H26 V8 "
        + "C30 9 32 12 32 16 V19 Z",
    }),
    svgElement("path", {
      class: "plug-body",
      transform: "rotate(45 24 24)",
      d: "M18 28 V24 A2 2 0 0 1 22 24 V28 "
        + "M26 28 V24 A2 2 0 0 1 30 24 V28",
    }),
  );
  const title = svgElement("title");
  title.textContent = `Physical connection ${state}`;
  icon.append(graphic, title);
  return icon;
}

/** Render the routed pathways, junctions, and physical ends for one group. */
function renderCableGroupDetailsGraphic(harness, group, focusedConnectionId, showContextMenu) {
  const topology = layoutCableGroupDetailsTopology(
    cableGroupDetailsTopology(harness, group), focusedConnectionId,
  );
  const associationBadges = cableGroupDetailsAssociationBadges(harness);
  const svg = svgElement("svg", {
    class: "cable-group-details-svg",
    width: topology.width,
    height: topology.height,
    viewBox: `0 0 ${topology.width} ${topology.height}`,
    role: "group",
    "aria-label": "Connected cable route",
  });
  routeCableGroupDetailsEdges(topology).forEach((edge) => {
    svg.append(svgElement("path", {
      class: "cable-group-route-link",
      d: edge.d,
      "data-start-node-id": edge.start.id,
      "data-end-node-id": edge.end.id,
      "data-start-y": edge.startY,
      "data-end-y": edge.endY,
    }));
  });
  topology.nodes.forEach((node) => {
    const isFocused = node.id === `connection:${focusedConnectionId}`;
    const groupNode = svgElement("g", {
      class: `cable-group-details-node ${node.kind}${isFocused ? " focused" : ""}`,
      tabindex: "0",
      role: node.kind === "attachment" ? "group" : "button",
      "aria-label": `${node.kind}: ${node.label}`,
      "data-node-id": node.id,
      "data-depth": node.depth,
    });
    const shape = svgElement("rect", {
      class: `relationship-node ${node.kind}`,
      x: node.x - node.width / 2,
      y: node.y - node.height / 2,
      width: node.width,
      height: node.height,
      rx: node.kind === "pathway" ? 20 : 7,
    });
    const label = svgElement("text", {
      class: "relationship-node-label",
      x: node.x,
      y: node.y + 3,
    });
    const kind = svgElement("text", {
      class: "relationship-node-kind",
      x: node.x,
      y: node.y - 25,
    });
    const title = svgElement("title");
    label.textContent = node.label;
    if (node.kind === "connection") {
      kind.textContent = `Cable End · ${node.item?.attachment ? "Attached" : "Detached"}`;
    } else if (node.kind === "attachment") {
      groupNode.dataset.connectionId = node.item.connectionId;
      groupNode.dataset.attachmentId = node.item.attachmentId;
      kind.textContent = node.item.connected ? "Connected" : "Disconnected";
      groupNode.dataset.connected = node.item.connected ? "true" : "false";
      const connection = harness.connections.find(
        (candidate) => candidate.connectionId === node.item.connectionId,
      );
      const hasChildren = (connection?.attachments || []).some(
        (candidate) => candidate.parentAttachmentId === node.item.attachmentId,
      );
      groupNode.dataset.physicalConnection = hasChildren ? "false" : "true";
      if (!hasChildren) {
        groupNode.append(renderPhysicalConnectionIcon(node, node.item.connected));
        const association = associationBadges.get(node.item.attachmentId);
        if (association) {
          const number = `${association.number}`;
          const badgeWidth = Math.max(18, number.length * 8 + 10);
          const badgeX = node.x - node.width / 2 - 4;
          const badgeY = node.y + node.height / 2 - 15;
          const memberBadge = svgElement("g", {
            class: "connection-association-indicator",
            role: "img",
            "aria-label": `Connection group ${number}`,
            "data-association-id": association.associationId,
            "data-group-number": number,
          });
          memberBadge.append(
            svgElement("rect", {
              x: badgeX, y: badgeY, width: badgeWidth, height: 18,
              rx: 9, fill: association.color,
            }),
            svgElement("text", {
              x: badgeX + badgeWidth / 2, y: badgeY + 12,
            }),
            svgElement("title"),
          );
          memberBadge.children[1].textContent = number;
          memberBadge.children[2].textContent = `Connection group ${number}`;
          groupNode.append(memberBadge);
        }
      }
      const shielding = connection
        ? cableEndAttachmentMaterials(group, connection, node.item).shielding : "";
      const hasShielding = typeof shielding === "string" && shielding.trim() !== "";
      const shieldingConnected = node.item.shieldingTarget?.connected === true;
      groupNode.dataset.shielding = hasShielding
        ? (shieldingConnected ? "connected" : "disconnected") : "none";
      if (hasShielding) {
        const shieldingStatus = shieldingConnected ? "connected" : "disconnected";
        const indicator = svgElement("g", {
          class: `connection-shielding-indicator ${shieldingStatus}`,
          role: "img",
          "aria-label": `Shielding ${shieldingStatus}`,
        });
        const indicatorCircle = svgElement("circle", {
          cx: node.x + node.width / 2 - 10,
          cy: node.y - node.height / 2 + 10,
          r: 8,
        });
        const indicatorLabel = svgElement("text", {
          x: node.x + node.width / 2 - 10,
          y: node.y - node.height / 2 + 13,
        });
        const indicatorTitle = svgElement("title");
        indicatorLabel.textContent = shieldingConnected ? "S+" : "S−";
        indicatorTitle.textContent = `Shielding ${shieldingStatus}`;
        indicator.append(indicatorCircle, indicatorLabel, indicatorTitle);
        groupNode.append(indicator);
      }
    } else {
      kind.textContent = node.kind;
    }
    title.textContent = node.label;
    shape.append(title);
    groupNode.prepend(shape, label, kind);
    if (node.kind === "connection") {
      const connectionId = node.id.slice("connection:".length);
      groupNode.dataset.connectionId = connectionId;
      hoverHighlight(groupNode, () => highlightMember(harness, "connection", connectionId));
      const activate = () => openCableEndRoutingPopup(harness, connectionId);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      groupNode.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, cableGroupDetailsEndContextItems(harness, node.item));
      });
    } else if (node.kind === "attachment") {
      hoverHighlight(groupNode, () => highlightMember(
        harness, "attachment", node.item.attachmentId,
        { connectionId: node.item.connectionId },
      ));
      groupNode.addEventListener("contextmenu", (event) => {
        event.stopPropagation();
        showContextMenu(event, cableGroupAttachmentContextItems(harness, group, node.item));
      });
    } else if (node.kind === "pathway") {
      const pathwayId = node.id.slice("pathway:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "pathway_gates", pathwayId));
      const activate = () => activatePathwayNode(harness, node.item);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      if (node.item) {
        groupNode.addEventListener("contextmenu", (event) => {
          event.stopPropagation();
          const anchor = { nodeKind: "pathway", nodeId: pathwayId };
          showContextMenu(event, [
            {
              label: "Associate",
              action: () => beginCableGroupAttachmentAssociation(harness, anchor),
              disabled: connectionAssociationCandidates(harness, anchor).length === 0,
              title: "Select another route node to associate its terminal connections",
            },
            ...pathwayNodeContextItems(harness, node.item),
          ]);
        });
      }
    } else {
      const junctionId = node.id.slice("junction:".length);
      hoverHighlight(groupNode, () => highlightMember(harness, "junction", junctionId));
      const activate = () => activateJunctionNode(harness, node.item);
      groupNode.addEventListener("click", activate);
      groupNode.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        activate();
      });
      if (node.item) {
        groupNode.addEventListener("contextmenu", (event) => {
          event.stopPropagation();
          const anchor = { nodeKind: "junction", nodeId: junctionId };
          showContextMenu(event, [
            {
              label: "Associate",
              action: () => beginCableGroupAttachmentAssociation(harness, anchor),
              disabled: connectionAssociationCandidates(harness, anchor).length === 0,
              title: "Select another route node to associate its terminal connections",
            },
            ...junctionNodeContextItems(harness, node.item),
          ]);
        });
      }
    }
    svg.append(groupNode);
  });
  const workspace = createBlockDiagramWorkspace("Zoomable connected cable route", {
    contentSize: { width: topology.width, height: topology.height },
    minScale: 0.01,
  });
  workspace.root.classList.add("cable-group-details-graphic");
  workspace.stage.append(svg);
  return workspace;
}
