/** Preserve the picked face's viewing side while normalizing its surface normal. */
function contactOrientation(normal) {
  const length = Math.hypot(...normal);
  return length > 1e-9 ? normal.map((value) => value / length) : [0, 0, 1];
}

/** View a cluster in its shared parent frame with the board's observed down axis. */
function contactPlanePoint(point, normal, parentAxes = null) {
  const validAxes = Array.isArray(parentAxes) && parentAxes.length === 3
    && parentAxes.every((axis) => Array.isArray(axis) && axis.length === 3
      && axis.every(Number.isFinite) && Math.hypot(...axis) > 1e-9);
  const axes = validAxes ? parentAxes.map(contactOrientation) : [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const alignment = normal.reduce((sum, value, index) => sum + value * axes[2][index], 0);
  const reference = Math.abs(alignment) < 0.9 ? axes[2] : axes[1];
  const u = [
    reference[1] * normal[2] - reference[2] * normal[1],
    reference[2] * normal[0] - reference[0] * normal[2],
    reference[0] * normal[1] - reference[1] * normal[0],
  ];
  const length = Math.hypot(...u);
  const xAxis = u.map((value) => value / length);
  const yAxis = [
    normal[1] * xAxis[2] - normal[2] * xAxis[1],
    normal[2] * xAxis[0] - normal[0] * xAxis[2],
    normal[0] * xAxis[1] - normal[1] * xAxis[0],
  ];
  return [
    point.reduce((sum, value, index) => sum + value * xAxis[index], 0),
    point.reduce((sum, value, index) => sum + value * yAxis[index], 0),
  ];
}

/** Keep every contact at its actual in-plane position within an orientation group. */
function renderInterfaceContacts(diagram, contacts) {
  const workspace = ensureInterfaceContactWorkspace(diagram);
  const clusters = [];
  contacts.forEach((contact) => {
    const normal = contactOrientation(contact.normal || [0, 0, 1]);
    const cluster = clusters.find((candidate) => Math.abs(
      candidate.normal.reduce((sum, value, index) => sum + value * normal[index], 0),
    ) > 0.9999);
    if (cluster) cluster.contacts.push(contact);
    else clusters.push({ normal, parentAxes: contact.parentAxes, contacts: [contact] });
  });
  const layouts = clusters.map((cluster) => {
    const outlines = cluster.contacts.map((contact) => ({
      contact,
      loops: (contact.loops || []).map((loop) => loop.map((point) => (
        contactPlanePoint(point, cluster.normal, cluster.parentAxes)
      ))),
    }));
    const coordinates = outlines.flatMap((item) => item.loops.flat());
    const xValues = coordinates.map((point) => point[0]);
    const yValues = coordinates.map((point) => point[1]);
    const minX = xValues.length ? Math.min(...xValues) : 0;
    const minY = yValues.length ? Math.min(...yValues) : 0;
    return {
      outlines, minX, minY,
      width: xValues.length ? Math.max(...xValues) - minX : 0,
      height: yValues.length ? Math.max(...yValues) - minY : 0,
    };
  });
  // One shared model-to-display scale preserves size comparisons between clusters.
  const largestSpan = Math.max(0, ...layouts.flatMap((layout) => [layout.width, layout.height]));
  const geometryScale = largestSpan > 1e-9 ? 260 / largestSpan : 1;
  let offsetX = 18;
  let totalHeight = 140;
  const items = [];
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "listbox");
  svg.setAttribute("aria-multiselectable", "true");
  svg.setAttribute("aria-label", "Interface contacts grouped by orientation");
  layouts.forEach(({ outlines, minX, minY, width, height }, index) => {
    const headingText = `Orientation ${index + 1} · ${outlines.length} contact${outlines.length === 1 ? "" : "s"}`;
    const clusterWidth = Math.max(220, headingText.length * 7 + 24, width * geometryScale + 32);
    const unavailableCount = outlines.filter((item) => (
      !item.contact.linked || !item.loops.some((loop) => loop.length)
    )).length;
    const clusterHeight = Math.max(115, height * geometryScale + 50, unavailableCount * 18 + 50);
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    background.setAttribute("x", offsetX);
    background.setAttribute("y", 10);
    background.setAttribute("width", clusterWidth);
    background.setAttribute("height", clusterHeight);
    background.setAttribute("class", "interface-contact-cluster");
    group.append(background);
    const heading = document.createElementNS("http://www.w3.org/2000/svg", "text");
    heading.setAttribute("x", offsetX + 12);
    heading.setAttribute("y", 30);
    heading.setAttribute("class", "interface-contact-heading");
    heading.textContent = headingText;
    group.append(heading);
    let unavailableIndex = 0;
    outlines.forEach(({ contact, loops }) => {
      const contactGroup = svgElement("g", {
        class: "interface-contact-item", "data-contact-id": contact.contactId,
        "data-named": `${Boolean(contact.assignedName)}`,
        role: "option", "aria-selected": "false", tabindex: "0",
      });
      contactGroup.setAttribute("aria-label", contact.assignedName || `Unnamed contact: ${contact.name}`);
      contactGroup.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        selectInterfaceContactIds(workspace, [contact.contactId], event);
      });
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = contact.assignedName || `Unnamed contact · ${contact.name}`;
      contactGroup.append(title);
      const positionedLoops = [];
      if (!contact.linked || !loops.length || !loops.some((loop) => loop.length)) {
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", offsetX + 12);
        label.setAttribute("y", 50 + unavailableIndex * 18);
        label.textContent = `${contact.name} · unavailable`;
        contactGroup.append(label);
        positionedLoops.push([
          [offsetX + 12, 37 + unavailableIndex * 18],
          [offsetX + clusterWidth - 12, 37 + unavailableIndex * 18],
          [offsetX + clusterWidth - 12, 53 + unavailableIndex * 18],
          [offsetX + 12, 53 + unavailableIndex * 18],
        ]);
        unavailableIndex += 1;
        group.append(contactGroup);
        items.push({ id: contact.contactId, node: contactGroup, loops: positionedLoops });
        return;
      }
      const outlinePaths = [];
      loops.forEach((loop) => {
        if (!loop.length) return;
        const positioned = loop.map(([x, y]) => [
          offsetX + 16 + (x - minX) * geometryScale,
          44 + (y - minY) * geometryScale,
        ]);
        positionedLoops.push(positioned);
        if (positioned.length === 1) {
          const marker = document.createElementNS("http://www.w3.org/2000/svg", "circle");
          marker.setAttribute("cx", positioned[0][0]);
          marker.setAttribute("cy", positioned[0][1]);
          marker.setAttribute("r", 3);
          marker.setAttribute("class", "interface-contact-point");
          contactGroup.append(marker);
        } else {
          outlinePaths.push(positioned.map(([x, y], pointIndex) => (
            `${pointIndex ? "L" : "M"}${x} ${y}`
          )).join(" ") + " Z");
        }
      });
      if (outlinePaths.length) {
        contactGroup.append(svgElement("path", {
          d: outlinePaths.join(" "), class: "interface-contact-outline", "fill-rule": "evenodd",
        }));
      }
      let nameLabel = null;
      let labelBounds = null;
      if (contact.assignedName && positionedLoops.length) {
        const vertices = positionedLoops.flat();
        const xs = vertices.map((point) => point[0]);
        const ys = vertices.map((point) => point[1]);
        const left = Math.min(...xs);
        const right = Math.max(...xs);
        const top = Math.min(...ys);
        const bottom = Math.max(...ys);
        nameLabel = svgElement("text", {
          x: (left + right) / 2, y: (top + bottom) / 2,
          class: "interface-contact-label", "text-anchor": "middle",
          "dominant-baseline": "middle",
        });
        nameLabel.textContent = contact.assignedName;
        labelBounds = { width: right - left, height: bottom - top };
        contactGroup.append(nameLabel);
      }
      group.append(contactGroup);
      items.push({ id: contact.contactId, node: contactGroup, loops: positionedLoops,
        label: nameLabel, labelBounds });
    });
    svg.append(group);
    offsetX += clusterWidth + 18;
    totalHeight = Math.max(totalHeight, clusterHeight + 20);
  });
  const width = offsetX;
  const height = totalHeight;
  svg.setAttribute("viewBox", `0 0 ${offsetX} ${totalHeight}`);
  svg.style.width = `${width}px`;
  svg.style.height = `${height}px`;
  updateInterfaceContactWorkspace(workspace, svg, items, contacts, { width, height,
    diagramWidth: offsetX, diagramHeight: totalHeight });
}

/** Refresh an open contact diagram when Fusion sends an updated harness state. */
function refreshInterfaceContacts() {
  const dialog = document.body.querySelector(".interface-contacts-popup");
  if (!dialog?.open) return;
  const harness = currentState.harnesses.find((item) => item.harnessId === dialog.dataset.harnessId);
  const interfaceItem = (harness?.interfaces || []).find((item) => (
    item.interfaceId === dialog.dataset.interfaceId
  ));
  if (interfaceItem) renderInterfaceContacts(dialog.children[2], interfaceItem.contacts || []);
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
  const buttons = [];

  dialog.className = "interface-contacts-popup";
  dialog.dataset.harnessId = harness.harnessId;
  dialog.dataset.interfaceId = interfaceItem.interfaceId;
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
      if (index === 0) {
        void send("select_interface_contacts", {
          harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId,
        }).catch((error) => appendNotice(String(error), true));
      }
    });
    buttons.push(button);
    modes.append(button);
  });
  toolbar.className = "interface-contacts-toolbar";
  naming.className = "interface-contacts-naming";
  naming.setAttribute("role", "group");
  naming.setAttribute("aria-label", "Contact naming");
  [["Pos Import", "pos_import_interface_contacts"],
    ["Load brd", "load_brd_interface_contacts"]].forEach(([label, action]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button compact";
    button.textContent = label;
    button.addEventListener("click", () => {
      void send(action, {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId,
      }).catch((error) => appendNotice(String(error), true));
    });
    naming.append(button);
  });
  toolbar.append(modes, naming);
  diagram.className = "interface-contacts-diagram";
  diagram.setAttribute("role", "region");
  diagram.setAttribute("aria-label", "Contact diagram");
  renderInterfaceContacts(diagram, interfaceItem.contacts || []);
  diagram.contactState.harnessId = harness.harnessId;
  diagram.contactState.interfaceId = interfaceItem.interfaceId;
  diagram.contactState.onEditContact = (contactId, event) => {
    openInterfaceContactNameEditor(diagram, diagram.contactState, contactId, event);
  };
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  actions.append(close);
  dialog.append(title, toolbar, diagram, actions);
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
  window.requestAnimationFrame(() => {
    if (dialog.open) diagram.contactState.workspace.fit();
  });
}
