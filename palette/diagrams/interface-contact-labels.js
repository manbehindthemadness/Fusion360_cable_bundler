/** Plan readable Value and Pin labels without changing relative contact positions. */

/** Return a projected contact's bounding box in diagram coordinates. */
function contactLabelBounds(loops, scale, minX, minY) {
  const bounds = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity };
  loops.forEach((loop) => loop.forEach(([x, y]) => {
    const px = 16 + (x - minX) * scale;
    const py = 44 + (y - minY) * scale;
    bounds.left = Math.min(bounds.left, px);
    bounds.right = Math.max(bounds.right, px);
    bounds.top = Math.min(bounds.top, py);
    bounds.bottom = Math.max(bounds.bottom, py);
  }));
  return Number.isFinite(bounds.left) ? bounds : null;
}

/** Reserve outside lanes for compact contacts and two-line interiors for roomy ones. */
function layoutInterfaceContactLabels(outlines, scale, minX, minY, geometryWidth, geometryHeight) {
  const geometry = {
    left: 16, right: 16 + geometryWidth * scale,
    top: 44, bottom: 44 + geometryHeight * scale,
  };
  const plans = new Map();
  const outside = [];
  const vertical = geometryHeight >= geometryWidth;
  outlines.forEach(({ contact, loops }, index) => {
    const value = contact.assignedName || "";
    const pin = contact.pin || "";
    if (!value && !pin) return;
    const bounds = contactLabelBounds(loops, scale, minX, minY);
    if (!bounds) return;
    const insideLines = [value, pin && `Pin ${pin}`].filter(Boolean);
    const insideWidth = Math.max(...insideLines.map((line) => line.length * 6.5)) + 8;
    const insideHeight = insideLines.length * 14 + 8;
    if (bounds.right - bounds.left >= insideWidth
      && bounds.bottom - bounds.top >= insideHeight) {
      plans.set(contact.contactId, { kind: "inside", bounds, value, pin });
      return;
    }
    const text = pin ? `Pin ${pin}${value ? ` · ${value}` : ""}` : value;
    const centerX = (bounds.left + bounds.right) / 2;
    const centerY = (bounds.top + bounds.bottom) / 2;
    const side = vertical
      ? (centerX < (geometry.left + geometry.right) / 2 ? "left" : "right")
      : (centerY < (geometry.top + geometry.bottom) / 2 ? "top" : "bottom");
    outside.push({ contactId: contact.contactId, index, bounds, text, side,
      centerX, centerY, width: text.length * 6.5 + 4 });
  });
  for (const side of ["left", "right", "top", "bottom"]) {
    const lane = outside.filter((item) => item.side === side).sort((first, second) => (
      vertical ? first.centerY - second.centerY || first.index - second.index
        : first.centerX - second.centerX || first.index - second.index
    ));
    let occupiedUntil = -Infinity;
    lane.forEach((item) => {
      const box = { left: 0, right: 0, top: 0, bottom: 0 };
      if (vertical) {
        box.top = Math.max(item.centerY - 7, occupiedUntil + 2);
        box.bottom = box.top + 14;
        box.left = side === "left" ? geometry.left - 8 - item.width : geometry.right + 8;
        box.right = box.left + item.width;
        occupiedUntil = box.bottom;
      } else {
        box.left = Math.max(item.centerX - item.width / 2, occupiedUntil + 6);
        box.right = box.left + item.width;
        box.top = side === "top" ? geometry.top - 22 : geometry.bottom + 8;
        box.bottom = box.top + 14;
        occupiedUntil = box.right;
      }
      plans.set(item.contactId, { kind: "outside", text: item.text, side,
        bounds: item.bounds, box });
    });
  }
  const boxes = outside.map((item) => plans.get(item.contactId).box);
  const shiftX = Math.max(0, 16 - Math.min(geometry.left, ...boxes.map((box) => box.left)));
  const shiftY = Math.max(0, 44 - Math.min(geometry.top, ...boxes.map((box) => box.top)));
  const width = Math.max(geometry.right, ...boxes.map((box) => box.right)) + shiftX + 16;
  const height = Math.max(geometry.bottom, ...boxes.map((box) => box.bottom)) + shiftY + 6;
  return { plans, shiftX, shiftY, width, height };
}

/** Add a short leader and one outside line without making either a hit target. */
function appendOutsideContactLabel(group, contactGroup, plan, offsetX, shiftX, shiftY) {
  const { box, bounds, side, text } = plan;
  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  const start = side === "left" ? [bounds.left, centerY]
    : side === "right" ? [bounds.right, centerY]
      : side === "top" ? [centerX, bounds.top] : [centerX, bounds.bottom];
  const end = side === "left" ? [box.right + 2, (box.top + box.bottom) / 2]
    : side === "right" ? [box.left - 2, (box.top + box.bottom) / 2]
      : side === "top" ? [(box.left + box.right) / 2, box.bottom + 2]
        : [(box.left + box.right) / 2, box.top - 2];
  group.append(svgElement("path", {
    class: "interface-contact-label-leader",
    d: `M${offsetX + shiftX + start[0]} ${shiftY + start[1]} L${offsetX + shiftX + end[0]} ${shiftY + end[1]}`,
  }));
  const x = side === "left" ? box.right - 2 : side === "right" ? box.left + 2
    : (box.left + box.right) / 2;
  const label = svgElement("text", {
    x: offsetX + shiftX + x,
    y: shiftY + (box.top + box.bottom) / 2,
    class: "interface-contact-label interface-contact-label-outside",
    "text-anchor": side === "left" ? "end" : side === "right" ? "start" : "middle",
    "dominant-baseline": "middle",
  });
  label.textContent = text;
  contactGroup.append(label);
  return label;
}
