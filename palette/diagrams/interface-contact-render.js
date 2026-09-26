/** Keep every contact at its actual in-plane position within an orientation group. */
function renderInterfaceContacts(diagram, contacts) {
  const workspace = ensureInterfaceContactWorkspace(diagram);
  const clusters = [];
  contacts.forEach((contact) => {
    const normal = contactOrientation(contact.normal || [0, 0, 1]);
    const cluster = clusters.find((candidate) => (
      candidate.normal.reduce((sum, value, index) => sum + value * normal[index], 0)
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
    const orientationName = outlines.find((item) => item.contact.orientationName)?.contact.orientationName
      || `Orientation ${index + 1}`;
    const headingText = `${orientationName} · ${outlines.length} contact${outlines.length === 1 ? "" : "s"}`;
    const labelLayout = layoutInterfaceContactLabels(
      outlines, geometryScale, minX, minY, width, height,
    );
    const clusterWidth = Math.max(220, headingText.length * 7 + 24, labelLayout.width);
    const unavailableCount = outlines.filter((item) => (
      !item.contact.linked || !item.loops.some((loop) => loop.length)
    )).length;
    const clusterHeight = Math.max(115, labelLayout.height + unavailableCount * 18 + 20);
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.dataset.orientationIndex = `${index}`;
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
        "data-named": `${Boolean(contact.assignedName || contact.pin)}`,
        role: "option", "aria-selected": "false", tabindex: "0",
      });
      const clearHover = workspace.harnessId && workspace.interfaceId
        ? hoverHighlight(contactGroup, () => highlightMember(
          { harnessId: workspace.harnessId }, "interface_contact", contact.contactId,
          { interfaceId: workspace.interfaceId },
        )) : null;
      const contactDescription = contact.assignedName || `Unnamed contact: ${contact.name}`;
      const accessibleLabel = contact.pin
        ? `${contactDescription} · Pin ${contact.pin}` : contactDescription;
      contactGroup.setAttribute("aria-label", accessibleLabel);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = contact.pin ? accessibleLabel
        : contact.assignedName || `Unnamed contact · ${contact.name}`;
      contactGroup.append(title);
      const positionedLoops = [];
      if (!contact.linked || !loops.length || !loops.some((loop) => loop.length)) {
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", offsetX + 12);
        label.setAttribute("y", labelLayout.height + 15 + unavailableIndex * 18);
        label.textContent = `${contact.name}${contact.pin ? ` · Pin ${contact.pin}` : ""} · unavailable`;
        contactGroup.append(label);
        positionedLoops.push([
          [offsetX + 12, labelLayout.height + 2 + unavailableIndex * 18],
          [offsetX + clusterWidth - 12, labelLayout.height + 2 + unavailableIndex * 18],
          [offsetX + clusterWidth - 12, labelLayout.height + 18 + unavailableIndex * 18],
          [offsetX + 12, labelLayout.height + 18 + unavailableIndex * 18],
        ]);
        unavailableIndex += 1;
        group.append(contactGroup);
        items.push({ id: contact.contactId, node: contactGroup, loops: positionedLoops,
          orientationIndex: index, clearHover });
        return;
      }
      const outlinePaths = [];
      loops.forEach((loop) => {
        if (!loop.length) return;
        const positioned = simplifyContactOutline(loop.map(([x, y]) => [
          offsetX + labelLayout.shiftX + 16 + (x - minX) * geometryScale,
          labelLayout.shiftY + 44 + (y - minY) * geometryScale,
        ]));
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
      let pinLabel = null;
      let labelBounds = null;
      let labelCenterY = null;
      const labelPlan = labelLayout.plans.get(contact.contactId);
      if (labelPlan?.kind === "inside") {
        const { bounds } = labelPlan;
        const x = offsetX + labelLayout.shiftX + (bounds.left + bounds.right) / 2;
        const y = labelLayout.shiftY + (bounds.top + bounds.bottom) / 2;
        labelCenterY = y;
        const both = Boolean(contact.assignedName && contact.pin);
        if (contact.assignedName) {
          nameLabel = svgElement("text", {
            x, y: y - (both ? 7 : 0),
            class: "interface-contact-label", "text-anchor": "middle",
            "dominant-baseline": "middle",
          });
          nameLabel.textContent = contact.assignedName;
          contactGroup.append(nameLabel);
        }
        if (contact.pin) {
          pinLabel = svgElement("text", {
            x, y: y + (both ? 7 : 0),
            class: "interface-contact-label", "text-anchor": "middle",
            "dominant-baseline": "middle",
          });
          pinLabel.textContent = `Pin ${contact.pin}`;
          contactGroup.append(pinLabel);
        }
        labelBounds = { width: bounds.right - bounds.left, height: bounds.bottom - bounds.top };
      } else if (labelPlan?.kind === "outside") {
        nameLabel = appendOutsideContactLabel(
          group, contactGroup, labelPlan, offsetX, labelLayout.shiftX, labelLayout.shiftY,
        );
      }
      group.append(contactGroup);
      items.push({ id: contact.contactId, node: contactGroup, loops: positionedLoops,
        orientationIndex: index, label: nameLabel, pinLabel, labelBounds, labelCenterY, clearHover });
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
