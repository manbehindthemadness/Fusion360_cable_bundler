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
  const contactBounds = [];
  outlines.forEach(({ contact, loops }, index) => {
    const bounds = contactLabelBounds(loops, scale, minX, minY);
    if (bounds) contactBounds.push({ contactId: contact.contactId, bounds,
      centerX: (bounds.left + bounds.right) / 2,
      centerY: (bounds.top + bounds.bottom) / 2 });
    const value = contact.assignedName || "";
    const pin = contact.pin || "";
    if ((!value && !pin) || !bounds) return;
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
    const nearest = contactBounds.filter((other) => other.contactId !== item.contactId)
      .sort((first, second) => (
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
    const rowMetrics = (side === "top" || side === "bottom" ? lane : []).map((item) => {
      const rowNeighbors = contactBounds.filter((other) => other.contactId !== item.contactId
        && other.bounds.top <= item.bounds.bottom + 1
        && other.bounds.bottom >= item.bounds.top - 1);
      const leftNeighbor = rowNeighbors.filter((other) => other.centerX < item.centerX)
        .sort((first, second) => second.centerX - first.centerX)[0];
      const rightNeighbor = rowNeighbors.filter((other) => other.centerX > item.centerX)
        .sort((first, second) => first.centerX - second.centerX)[0];
      const pitch = Math.min(
        leftNeighbor ? item.centerX - leftNeighbor.centerX : Infinity,
        rightNeighbor ? rightNeighbor.centerX - item.centerX : Infinity,
      );
      const neighborGap = Math.min(
        leftNeighbor ? Math.max(0, item.bounds.left - leftNeighbor.bounds.right) : Infinity,
        rightNeighbor ? Math.max(0, rightNeighbor.bounds.left - item.bounds.right) : Infinity,
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
      plans.set(item.contactId, { kind: "outside", contactId: item.contactId, text: item.text, side,
        bounds: item.bounds, box, fontSize, rotated });
    });
  }
  const boxes = outside.map((item) => plans.get(item.contactId).box);
  const shiftX = Math.max(0, 16 - Math.min(geometry.left, ...boxes.map((box) => box.left)));
  const shiftY = Math.max(0, 44 - Math.min(geometry.top, ...boxes.map((box) => box.top)));
  const width = Math.max(geometry.right, ...boxes.map((box) => box.right)) + shiftX + 16;
  const height = Math.max(geometry.bottom, ...boxes.map((box) => box.bottom)) + shiftY + 6;
  return { plans, contactBounds, shiftX, shiftY, width, height };
}

/** Test whether a line enters a contact's slightly expanded bounding box. */
function labelLeaderCrossesContact(start, end, bounds) {
  let near = 0;
  let far = 1;
  for (const [axis, low, high] of [
    [0, bounds.left - 1, bounds.right + 1],
    [1, bounds.top - 1, bounds.bottom + 1],
  ]) {
    const delta = end[axis] - start[axis];
    if (Math.abs(delta) < 1e-9) {
      if (start[axis] <= low || start[axis] >= high) return false;
      continue;
    }
    const entry = (low - start[axis]) / delta;
    const exit = (high - start[axis]) / delta;
    near = Math.max(near, Math.min(entry, exit));
    far = Math.min(far, Math.max(entry, exit));
    if (near >= far) return false;
  }
  return near < 1 && far > 0;
}

/** Prefer a short clear leader; omit it when all simple detours cross pads. */
function contactLabelLeaderPoints(start, end, side, obstacles) {
  const crosses = (points) => points.slice(1).some((point, index) => obstacles.some(({ bounds }) => (
    labelLeaderCrossesContact(points[index], point, bounds)
  )));
  if (!crosses([start, end])) return [start, end];
  const horizontal = side === "left" || side === "right";
  const relevant = obstacles.filter(({ bounds }) => labelLeaderCrossesContact(start, end, bounds));
  const detours = horizontal
    ? [Math.min(...relevant.map(({ bounds }) => bounds.top)) - 3,
      Math.max(...relevant.map(({ bounds }) => bounds.bottom)) + 3,
      Math.min(...obstacles.map(({ bounds }) => bounds.top)) - 3,
      Math.max(...obstacles.map(({ bounds }) => bounds.bottom)) + 3]
    : [Math.min(...relevant.map(({ bounds }) => bounds.left)) - 3,
      Math.max(...relevant.map(({ bounds }) => bounds.right)) + 3,
      Math.min(...obstacles.map(({ bounds }) => bounds.left)) - 3,
      Math.max(...obstacles.map(({ bounds }) => bounds.right)) + 3];
  const routes = detours.map((coordinate) => horizontal
    ? [start, [start[0], coordinate], [end[0], coordinate], end]
    : [start, [coordinate, start[1]], [coordinate, end[1]], end])
    .filter((points) => !crosses(points));
  routes.sort((first, second) => {
    const length = (points) => points.slice(1).reduce((sum, point, index) => (
      sum + Math.hypot(point[0] - points[index][0], point[1] - points[index][1])
    ), 0);
    return length(first) - length(second);
  });
  return routes[0] || null;
}

/** Add a short leader and one outside line without making either a hit target. */
function appendOutsideContactLabel(group, contactGroup, plan, offsetX, shiftX, shiftY, contactBounds) {
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
  const obstacles = contactBounds.filter((item) => item.contactId !== plan.contactId);
  const leader = contactLabelLeaderPoints(start, end, side, obstacles);
  if (leader) group.append(svgElement("path", {
    class: "interface-contact-label-leader",
    d: leader.map(([x, y], index) => `${index ? "L" : "M"}${offsetX + shiftX + x} ${shiftY + y}`)
      .join(" "),
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
