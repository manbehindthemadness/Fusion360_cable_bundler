/** Contact-level pan, zoom, box selection, and freeform lasso interaction. */

/** Test whether a point lies on the finite line segment joining two vertices. */
function contactPointOnSegment(point, start, end) {
  const cross = (point[0] - start[0]) * (end[1] - start[1])
    - (point[1] - start[1]) * (end[0] - start[0]);
  return Math.abs(cross) < 1e-7
    && point[0] >= Math.min(start[0], end[0]) - 1e-7
    && point[0] <= Math.max(start[0], end[0]) + 1e-7
    && point[1] >= Math.min(start[1], end[1]) - 1e-7
    && point[1] <= Math.max(start[1], end[1]) + 1e-7;
}

/** Include polygon boundaries when testing a selection shape. */
function contactPointInPolygon(point, polygon) {
  if (polygon.length < 3) return false;
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length;
    previous = index, index += 1) {
    const first = polygon[previous];
    const second = polygon[index];
    if (contactPointOnSegment(point, first, second)) return true;
    if ((first[1] > point[1]) !== (second[1] > point[1])
      && point[0] < (second[0] - first[0]) * (point[1] - first[1])
        / (second[1] - first[1]) + first[0]) inside = !inside;
  }
  return inside;
}

/** Detect an outline crossing a selection boundary, including edge touches. */
function contactSegmentsIntersect(firstStart, firstEnd, secondStart, secondEnd) {
  const side = (a, b, c) => (
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
  );
  const a = side(firstStart, firstEnd, secondStart);
  const b = side(firstStart, firstEnd, secondEnd);
  const c = side(secondStart, secondEnd, firstStart);
  const d = side(secondStart, secondEnd, firstEnd);
  if (a * b < 0 && c * d < 0) return true;
  return (Math.abs(a) < 1e-7 && contactPointOnSegment(secondStart, firstStart, firstEnd))
    || (Math.abs(b) < 1e-7 && contactPointOnSegment(secondEnd, firstStart, firstEnd))
    || (Math.abs(c) < 1e-7 && contactPointOnSegment(firstStart, secondStart, secondEnd))
    || (Math.abs(d) < 1e-7 && contactPointOnSegment(firstEnd, secondStart, secondEnd));
}

/** Select one whole contact when any of its outlines meets the drag area. */
function contactIntersectsArea(item, area) {
  if (area.length < 3) return false;
  if (item.loops.some((loop) => loop.some((point) => contactPointInPolygon(point, area)))) {
    return true;
  }
  if (area.some((point) => {
    let inside = false;
    item.loops.forEach((loop) => {
      if (loop.length >= 3 && contactPointInPolygon(point, loop)) inside = !inside;
    });
    return inside;
  })) return true;
  return item.loops.some((loop) => {
    if (loop.length < 2) return false;
    return loop.some((point, index) => {
      const next = loop[(index + 1) % loop.length];
      return area.some((vertex, areaIndex) => contactSegmentsIntersect(
        point, next, vertex, area[(areaIndex + 1) % area.length],
      ));
    });
  });
}

/** Convert a pointer position through pan/zoom into the SVG diagram plane. */
function contactDiagramPoint(state, event) {
  const bounds = state.svg.getBoundingClientRect();
  return [
    (event.clientX - bounds.left) * state.diagramWidth / Math.max(1, bounds.width),
    (event.clientY - bounds.top) * state.diagramHeight / Math.max(1, bounds.height),
  ];
}

/** Find an individual contact from any of its SVG descendants. */
function contactIdAtTarget(target, viewport) {
  let node = target;
  while (node && node !== viewport) {
    if (node.dataset?.contactId) return node.dataset.contactId;
    node = node.parentElement;
  }
  return null;
}

/** Paint current selection without rebuilding outlines or losing pan/zoom. */
function paintInterfaceContactSelection(state) {
  state.items.forEach((item) => {
    const selected = state.selectedIds.has(item.id);
    item.node.dataset.selected = `${selected}`;
    item.node.setAttribute("aria-selected", `${selected}`);
  });
  state.count.textContent = `${state.selectedIds.size} selected`;
}

/** Keep names legible in screen pixels once their pad has enough room. */
function paintInterfaceContactLabels(state) {
  state.items.forEach((item) => {
    if (!item.label || !item.labelBounds) return;
    const scale = state.viewScale || 1;
    item.label.style.fontSize = `${11 / scale}px`;
    const fits = item.labelBounds.width * scale >= item.label.textContent.length * 6 + 8
      && item.labelBounds.height * scale >= 14;
    item.label.style.display = fits ? "" : "none";
  });
}

/** Apply replacement, additive, or toggle selection semantics. */
function selectInterfaceContactIds(state, ids, event) {
  if (!event.shiftKey && !event.ctrlKey && !event.metaKey) state.selectedIds.clear();
  ids.forEach((id) => {
    if ((event.ctrlKey || event.metaKey) && state.selectedIds.has(id)) {
      state.selectedIds.delete(id);
    } else {
      state.selectedIds.add(id);
    }
  });
  paintInterfaceContactSelection(state);
}

/** Return the four corners of a drag box in either drag direction. */
function contactBox(start, end) {
  const left = Math.min(start[0], end[0]);
  const right = Math.max(start[0], end[0]);
  const top = Math.min(start[1], end[1]);
  const bottom = Math.max(start[1], end[1]);
  return [[left, top], [right, top], [right, bottom], [left, bottom]];
}

/** Draw only the temporary selection area; contact geometry remains unchanged. */
function paintInterfaceContactDrag(state) {
  const drag = state.drag;
  if (!drag?.moved) return;
  if (!drag.overlay) {
    drag.overlay = svgElement(state.mode === "box" ? "rect" : "path", {
      class: "interface-contact-selection-area",
    });
    state.svg.append(drag.overlay);
  }
  if (state.mode === "box") {
    const area = contactBox(drag.start, drag.points[drag.points.length - 1]);
    drag.overlay.setAttribute("x", area[0][0]);
    drag.overlay.setAttribute("y", area[0][1]);
    drag.overlay.setAttribute("width", area[1][0] - area[0][0]);
    drag.overlay.setAttribute("height", area[2][1] - area[1][1]);
  } else {
    drag.overlay.setAttribute("d", drag.points.map(([x, y], index) => (
      `${index ? "L" : "M"}${x} ${y}`
    )).join(" ") + " Z");
  }
}

/** Wire pointer gestures to contact IDs, leaving middle-button pan to the shared workspace. */
function enableInterfaceContactSelection(state) {
  const viewport = state.workspace.viewport;
  viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || state.mode === "pan") return;
    event.preventDefault();
    viewport.focus();
    const point = contactDiagramPoint(state, event);
    state.drag = {
      pointerId: event.pointerId, start: point, startClient: [event.clientX, event.clientY],
      points: [point], targetId: contactIdAtTarget(event.target, viewport), moved: false,
      overlay: null,
    };
    viewport.setPointerCapture?.(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    const drag = state.drag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (!drag.moved && Math.hypot(
      event.clientX - drag.startClient[0], event.clientY - drag.startClient[1],
    ) < 4) return;
    drag.moved = true;
    event.preventDefault();
    drag.points.push(contactDiagramPoint(state, event));
    paintInterfaceContactDrag(state);
  });
  const finish = (event) => {
    const drag = state.drag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    viewport.releasePointerCapture?.(event.pointerId);
    drag.overlay?.remove();
    state.drag = null;
    if (event.type === "pointercancel") return;
    if (!drag.moved) {
      selectInterfaceContactIds(state, drag.targetId ? [drag.targetId] : [], event);
      if (drag.targetId && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
        state.onEditContact?.(drag.targetId, event);
      }
      return;
    }
    const end = contactDiagramPoint(state, event);
    const area = state.mode === "box" ? contactBox(drag.start, end) : [...drag.points, end];
    const selected = state.items.filter((item) => contactIntersectsArea(item, area))
      .map((item) => item.id);
    selectInterfaceContactIds(state, selected, event);
  };
  viewport.addEventListener("pointerup", finish);
  viewport.addEventListener("pointercancel", finish);
  viewport.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    state.selectedIds.clear();
    paintInterfaceContactSelection(state);
  });
}

/** Build the reusable workspace once so refreshes retain navigation and selection. */
function ensureInterfaceContactWorkspace(diagram) {
  if (diagram.contactState) return diagram.contactState;
  const size = { width: 600, height: 300 };
  let state = null;
  const workspace = createBlockDiagramWorkspace("Contact diagram", {
    contentSize: size, minScale: 0.2,
    panWithPrimaryButton: () => state.mode === "pan",
    onViewChange: ({ scale }) => {
      state.viewScale = scale;
      paintInterfaceContactLabels(state);
    },
  });
  const toolbar = workspace.root.children[0];
  const tools = document.createElement("div");
  const count = document.createElement("output");
  const modeButtons = [];
  state = {
    workspace, size, count, items: [], selectedIds: new Set(), mode: "box",
    svg: null, diagramWidth: 600, diagramHeight: 300, drag: null, hasContacts: false,
    contacts: [], viewScale: 1, onEditContact: null,
  };
  tools.className = "interface-contact-tools";
  tools.setAttribute("role", "group");
  tools.setAttribute("aria-label", "Contact diagram tool");
  [["Pan", "pan"], ["Box", "box"], ["Freeform", "freeform"]].forEach(([label, mode]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.title = mode === "pan" ? "Drag to pan" : `Drag to ${label.toLowerCase()} select contacts`;
    button.setAttribute("aria-pressed", `${mode === state.mode}`);
    button.addEventListener("click", () => {
      state.mode = mode;
      modeButtons.forEach((candidate) => candidate.setAttribute(
        "aria-pressed", `${candidate === button}`,
      ));
    });
    modeButtons.push(button);
    tools.append(button);
  });
  count.className = "interface-contact-count";
  count.textContent = "0 selected";
  count.setAttribute("aria-live", "polite");
  toolbar.prepend(tools);
  toolbar.append(count);
  workspace.root.classList.add("interface-contact-workspace");
  diagram.replaceChildren(workspace.root);
  diagram.contactState = state;
  enableInterfaceContactSelection(state);
  return state;
}

/** Swap diagram content while preserving the selected contact IDs and current view. */
function updateInterfaceContactWorkspace(state, svg, items, contacts, dimensions) {
  state.drag?.overlay?.remove();
  state.drag = null;
  state.svg = svg;
  state.items = items;
  state.contacts = contacts;
  state.diagramWidth = dimensions.diagramWidth;
  state.diagramHeight = dimensions.diagramHeight;
  state.size.width = dimensions.width;
  state.size.height = dimensions.height;
  state.workspace.stage.replaceChildren(svg);
  const available = new Set(contacts.map((contact) => contact.contactId));
  state.selectedIds = new Set([...state.selectedIds].filter((id) => available.has(id)));
  paintInterfaceContactSelection(state);
  paintInterfaceContactLabels(state);
  if (!state.hasContacts && contacts.length) state.workspace.fit();
  state.hasContacts = contacts.length > 0;
}
