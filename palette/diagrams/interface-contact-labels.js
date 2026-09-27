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
    outside.push({ contactId: contact.contactId, index, bounds, text, centerX, centerY,
      width: text.length * 6.5 + 4 });
  });
  outside.forEach((item) => {
    const nearest = outside.filter((other) => other !== item).sort((first, second) => (
      Math.hypot(first.centerX - item.centerX, first.centerY - item.centerY)
      - Math.hypot(second.centerX - item.centerX, second.centerY - item.centerY)
    ))[0];
    item.row = geometryWidth > geometryHeight || (nearest
      && Math.abs(nearest.centerX - item.centerX) >= Math.abs(nearest.centerY - item.centerY));
    if (!item.row) {
      item.side = item.centerX < (geometry.left + geometry.right) / 2 ? "left" : "right";
    }
  });
  const rowBands = [];
  outside.filter((item) => item.row).sort((first, second) => first.centerY - second.centerY)
    .forEach((item) => {
      const band = rowBands.find((candidate) => (
        item.bounds.top <= candidate.bottom + 1 && item.bounds.bottom >= candidate.top - 1
      ));
      if (band) {
        band.top = Math.min(band.top, item.bounds.top);
        band.bottom = Math.max(band.bottom, item.bounds.bottom);
        band.items.push(item);
      } else {
        rowBands.push({ top: item.bounds.top, bottom: item.bounds.bottom, items: [item] });
      }
    });
  rowBands.forEach((band) => {
    const side = rowBands.length === 1 || (band.top + band.bottom) / 2
      < (geometry.top + geometry.bottom) / 2 ? "top" : "bottom";
    band.items.forEach((item) => { item.side = side; });
  });
  for (const side of ["left", "right", "top", "bottom"]) {
    const lane = outside.filter((item) => item.side === side).sort((first, second) => (
      side === "left" || side === "right"
        ? first.centerY - second.centerY || first.index - second.index
        : first.centerX - second.centerX || first.index - second.index
    ));
    const rowMetrics = (side === "top" || side === "bottom" ? lane : []).map((item, index) => {
      const pitch = Math.min(
        index ? item.centerX - lane[index - 1].centerX : Infinity,
        index + 1 < lane.length ? lane[index + 1].centerX - item.centerX : Infinity,
      );
      const neighborGap = Math.min(
        index ? Math.max(0, item.bounds.left - lane[index - 1].bounds.right) : Infinity,
        index + 1 < lane.length
          ? Math.max(0, lane[index + 1].bounds.left - item.bounds.right) : Infinity,
      );
      const contactWidth = item.bounds.right - item.bounds.left;
      return { pitch, rotated: item.width > pitch - 6,
        fontSize: Math.min(11, Math.max(1, contactWidth + neighborGap / 2),
          Math.max(1, pitch - 1)) };
    });
    const sharedRotatedFont = Math.min(11, ...rowMetrics.filter((item) => item.rotated)
      .map((item) => item.fontSize));
    let occupiedUntil = -Infinity;
    lane.forEach((item, index) => {
      const box = { left: 0, right: 0, top: 0, bottom: 0 };
      let fontSize = null;
      let rotated = false;
      if (side === "left" || side === "right") {
        const pitch = Math.min(
          index ? item.centerY - lane[index - 1].centerY : Infinity,
          index + 1 < lane.length ? lane[index + 1].centerY - item.centerY : Infinity,
        );
        const lineHeight = Math.min(14, Math.max(1, pitch - 1));
        fontSize = Math.min(11, Math.max(1, lineHeight - 3));
        const width = item.text.length * (fontSize / 11) * 6.5 + 4;
        box.top = Math.max(item.centerY - lineHeight / 2, occupiedUntil + Math.min(1, pitch));
        box.bottom = box.top + lineHeight;
        box.left = side === "left" ? geometry.left - 8 - width : geometry.right + 8;
        box.right = box.left + width;
        occupiedUntil = box.bottom;
      } else {
        rotated = rowMetrics[index].rotated;
        if (rotated) {
          fontSize = sharedRotatedFont;
          const textHeight = item.text.length * (fontSize / 11) * 6.5 + 4;
          box.left = Math.max(item.centerX - fontSize / 2, occupiedUntil + 1);
          box.right = box.left + fontSize;
          box.top = side === "top" ? item.bounds.top - 8 - textHeight : item.bounds.bottom + 8;
          box.bottom = box.top + textHeight;
        } else {
          box.left = Math.max(item.centerX - item.width / 2, occupiedUntil + 6);
          box.right = box.left + item.width;
          box.top = side === "top" ? item.bounds.top - 22 : item.bounds.bottom + 8;
          box.bottom = box.top + 14;
        }
        occupiedUntil = box.right;
      }
      plans.set(item.contactId, { kind: "outside", text: item.text, side,
        bounds: item.bounds, box, fontSize, rotated });
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
  if (plan.rotated) {
    const angle = side === "top" ? -90 : 90;
    const pivotX = offsetX + shiftX + x;
    const pivotY = shiftY + (box.top + box.bottom) / 2;
    label.setAttribute("transform", `rotate(${angle} ${pivotX} ${pivotY})`);
  }
  label.textContent = text;
  if (plan.fontSize !== null) label.style.fontSize = `${plan.fontSize}px`;
  contactGroup.append(label);
  return label;
}
