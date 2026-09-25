/** Normalize and canonicalize a surface normal so opposite faces share a cluster. */
function contactOrientation(normal) {
  const length = Math.hypot(...normal);
  const unit = length > 1e-9 ? normal.map((value) => value / length) : [0, 0, 1];
  const major = unit.find((value) => Math.abs(value) > 1e-6);
  return major < 0 ? unit.map((value) => -value) : unit;
}

/** Project a model point into a consistent in-plane frame for one cluster. */
function contactPlanePoint(point, normal) {
  const reference = Math.abs(normal[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0];
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
  diagram.replaceChildren();
  if (!contacts.length) return;
  const clusters = [];
  contacts.forEach((contact) => {
    const normal = contactOrientation(contact.normal || [0, 0, 1]);
    const cluster = clusters.find((candidate) => Math.abs(
      candidate.normal.reduce((sum, value, index) => sum + value * normal[index], 0),
    ) > 0.9999);
    if (cluster) cluster.contacts.push(contact);
    else clusters.push({ normal, contacts: [contact] });
  });
  let offsetX = 18;
  let totalHeight = 140;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Interface contacts grouped by orientation");
  clusters.forEach((cluster, index) => {
    const outlines = cluster.contacts.map((contact) => ({
      contact,
      loops: (contact.loops || []).map((loop) => loop.map((point) => (
        contactPlanePoint(point, cluster.normal)
      ))),
    }));
    const coordinates = outlines.flatMap((item) => item.loops.flat());
    const xValues = coordinates.map((point) => point[0]);
    const yValues = coordinates.map((point) => point[1]);
    const minX = xValues.length ? Math.min(...xValues) : 0;
    const minY = yValues.length ? Math.min(...yValues) : 0;
    const width = xValues.length ? Math.max(...xValues) - minX : 0;
    const height = yValues.length ? Math.max(...yValues) - minY : 0;
    const clusterWidth = Math.max(145, width + 32);
    const clusterHeight = Math.max(115, height + 50);
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
    heading.textContent = `Orientation ${index + 1} · ${cluster.contacts.length} contact${cluster.contacts.length === 1 ? "" : "s"}`;
    group.append(heading);
    outlines.forEach(({ contact, loops }) => {
      if (!contact.linked || !loops.length || !loops.some((loop) => loop.length)) {
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", offsetX + 12);
        label.setAttribute("y", 50);
        label.textContent = `${contact.name} · unavailable`;
        group.append(label);
        return;
      }
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = contact.name;
      group.append(title);
      loops.forEach((loop) => {
        if (!loop.length) return;
        const positioned = loop.map(([x, y]) => [
          offsetX + 16 + x - minX, 44 + y - minY,
        ]);
        if (positioned.length === 1) {
          const marker = document.createElementNS("http://www.w3.org/2000/svg", "circle");
          marker.setAttribute("cx", positioned[0][0]);
          marker.setAttribute("cy", positioned[0][1]);
          marker.setAttribute("r", 3);
          marker.setAttribute("class", "interface-contact-point");
          group.append(marker);
        } else {
          const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
          path.setAttribute("d", positioned.map(([x, y], pointIndex) => (
            `${pointIndex ? "L" : "M"}${x} ${y}`
          )).join(" ") + (contact.kind === "circular_edge" ? "" : " Z"));
          path.setAttribute("class", "interface-contact-outline");
          group.append(path);
        }
      });
    });
    svg.append(group);
    offsetX += clusterWidth + 18;
    totalHeight = Math.max(totalHeight, clusterHeight + 20);
  });
  svg.setAttribute("viewBox", `0 0 ${offsetX} ${totalHeight}`);
  svg.style.width = `${Math.max(600, offsetX * 2)}px`;
  svg.style.height = `${Math.max(300, totalHeight * 2)}px`;
  diagram.append(svg);
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
  ["Manual Select", "Row Select", "Plane Select"].forEach((label, index) => {
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
  diagram.className = "interface-contacts-diagram";
  diagram.setAttribute("role", "region");
  diagram.setAttribute("aria-label", "Contact diagram");
  renderInterfaceContacts(diagram, interfaceItem.contacts || []);
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  actions.append(close);
  dialog.append(title, modes, diagram, actions);
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}
