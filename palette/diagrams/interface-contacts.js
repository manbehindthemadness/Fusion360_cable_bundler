// Keep one bounded projection and vector-image snapshot across dialog closes.
const MAX_CONTACT_CACHE_BYTES = 4_000_000;
let cachedContactGeometry = null;

/** Track contact membership and the last geometry-changing Fusion command. */
function contactGeometryKey(contacts) {
  return JSON.stringify(contacts.map((item) => [item.contactId, item.geometryRevision]));
}

/** Reuse a snapshot only for the same Interface and geometry revision. */
function matchingContactCache(dialog, geometryKey) {
  const cached = cachedContactGeometry;
  return cached?.harnessId === dialog.dataset.harnessId
    && cached.interfaceId === dialog.dataset.interfaceId
    && cached.geometryKey === geometryKey ? cached : null;
}

/** Return sampled geometry when it fits alongside the rendered image. */
function restoredContactGeometry(dialog, geometryKey) {
  return matchingContactCache(dialog, geometryKey)?.contacts || null;
}

/** Bound retained outline data without holding Fusion objects. */
function rememberContactGeometry(dialog, geometryKey, contacts) {
  const size = JSON.stringify(contacts).length * 2;
  cachedContactGeometry = {
    harnessId: dialog.dataset.harnessId,
    interfaceId: dialog.dataset.interfaceId,
    geometryKey,
    contacts: size <= MAX_CONTACT_CACHE_BYTES ? contacts : null,
    signatures: contactSignatures(contacts),
    geometryBytes: size <= MAX_CONTACT_CACHE_BYTES ? size : 0,
  };
}

/** Retain only complete source fingerprints for a later model-change check. */
function contactSignatures(contacts) {
  if (!contacts.every((item) => typeof item.sourceSignature === "string")) return null;
  return Object.fromEntries(contacts.map((item) => [item.contactId, item.sourceSignature]));
}

/** Retain the finished vector image and hit-test outlines, not its old workspace. */
function rememberRenderedContactDiagram(dialog, geometryKey, displayKey) {
  const cached = matchingContactCache(dialog, geometryKey);
  const state = dialog.children[2].contactState;
  if (!cached) return;
  if (state.items.length > 512) {
    cached.rendered = null;
    return;
  }
  const outlineBytes = JSON.stringify(state.items.map((item) => item.loops)).length * 2;
  const markupBytes = state.svg.outerHTML
    ? state.svg.outerHTML.length * 2 : outlineBytes + state.items.length * 256;
  const imageBytes = outlineBytes + markupBytes;
  if (imageBytes > MAX_CONTACT_CACHE_BYTES) {
    cached.rendered = null;
    return;
  }
  if (imageBytes + cached.geometryBytes > MAX_CONTACT_CACHE_BYTES) {
    cached.contacts = null;
    cached.geometryBytes = 0;
  }
  cached.rendered = {
    displayKey, svg: state.svg, items: state.items,
    dimensions: {
      width: state.size.width, height: state.size.height,
      diagramWidth: state.diagramWidth, diagramHeight: state.diagramHeight,
    },
  };
}

/** Attach a cached vector image to a fresh workspace with fresh interaction state. */
function restoreRenderedContactDiagram(dialog, geometryKey, displayKey, contacts) {
  const rendered = matchingContactCache(dialog, geometryKey)?.rendered;
  if (!rendered || rendered.displayKey !== displayKey) return false;
  const state = dialog.children[2].contactState;
  updateInterfaceContactWorkspace(state, rendered.svg, rendered.items, contacts, rendered.dimensions);
  return true;
}

/** Preserve the picked face's viewing side while normalizing its surface normal. */
function contactOrientation(normal) {
  const length = Math.hypot(...normal);
  return length > 1e-9 ? normal.map((value) => value / length) : [0, 0, 1];
}

/** View contacts from the facing side, keeping the shared parent vertical axis down. */
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
    -point.reduce((sum, value, index) => sum + value * xAxis[index], 0),
    point.reduce((sum, value, index) => sum + value * yAxis[index], 0),
  ];
}

/** Remove subpixel detail while retaining corners, winding, and separate holes. */
function simplifyContactOutline(points, tolerance = 0.3) {
  if (points.length < 4) return points;
  const distanceSquared = (first, second) => (
    (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2
  );
  const vertices = points.filter((point, index) => (
    !index || distanceSquared(point, points[index - 1]) > 1e-12
  ));
  if (vertices.length > 1 && distanceSquared(vertices[0], vertices.at(-1)) <= 1e-12) {
    vertices.pop();
  }
  if (vertices.length < 4) return vertices;
  let opposite = 1;
  for (let index = 2; index < vertices.length; index += 1) {
    if (distanceSquared(vertices[0], vertices[index])
      > distanceSquared(vertices[0], vertices[opposite])) opposite = index;
  }
  const simplifyChain = (chain) => {
    const keep = new Set([0, chain.length - 1]);
    const pending = [[0, chain.length - 1]];
    while (pending.length) {
      const [start, end] = pending.pop();
      const first = chain[start];
      const last = chain[end];
      const span = distanceSquared(first, last);
      let farthest = -1;
      let deviation = tolerance * tolerance;
      for (let index = start + 1; index < end; index += 1) {
        const point = chain[index];
        const fraction = span ? Math.max(0, Math.min(1,
          ((point[0] - first[0]) * (last[0] - first[0])
            + (point[1] - first[1]) * (last[1] - first[1])) / span)) : 0;
        const projected = [first[0] + fraction * (last[0] - first[0]),
          first[1] + fraction * (last[1] - first[1])];
        const error = distanceSquared(point, projected);
        if (error > deviation) {
          deviation = error;
          farthest = index;
        }
      }
      if (farthest >= 0) {
        keep.add(farthest);
        pending.push([start, farthest], [farthest, end]);
      }
    }
    return chain.filter((_point, index) => keep.has(index));
  };
  const first = simplifyChain(vertices.slice(0, opposite + 1));
  const second = simplifyChain([...vertices.slice(opposite), vertices[0]]);
  const simplified = [...first.slice(0, -1), ...second.slice(0, -1)];
  return simplified.length >= 3 ? simplified : vertices;
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
    const labelLayout = layoutInterfaceContactLabels(
      outlines, geometryScale, minX, minY, width, height,
    );
    const clusterWidth = Math.max(220, headingText.length * 7 + 24, labelLayout.width);
    const unavailableCount = outlines.filter((item) => (
      !item.contact.linked || !item.loops.some((loop) => loop.length)
    )).length;
    const clusterHeight = Math.max(115, labelLayout.height + unavailableCount * 18 + 20);
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
        items.push({ id: contact.contactId, node: contactGroup, loops: positionedLoops, clearHover });
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
      const labelPlan = labelLayout.plans.get(contact.contactId);
      if (labelPlan?.kind === "inside") {
        const { bounds } = labelPlan;
        const x = offsetX + labelLayout.shiftX + (bounds.left + bounds.right) / 2;
        const y = labelLayout.shiftY + (bounds.top + bounds.bottom) / 2;
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
        label: nameLabel, pinLabel, labelBounds, clearHover });
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
  if (cachedContactGeometry) {
    const cachedHarness = currentState.harnesses.find((item) => (
      item.harnessId === cachedContactGeometry.harnessId
    ));
    if (!(cachedHarness?.interfaces || []).some((item) => (
      item.interfaceId === cachedContactGeometry.interfaceId
    ))) cachedContactGeometry = null;
  }
  const dialog = document.body.querySelector(".interface-contacts-popup");
  if (!dialog?.open) return;
  if (dialog.cacheRebuildPending) return;
  const harness = currentState.harnesses.find((item) => item.harnessId === dialog.dataset.harnessId);
  const interfaceItem = (harness?.interfaces || []).find((item) => (
    item.interfaceId === dialog.dataset.interfaceId
  ));
  if (interfaceItem) updateInterfaceContactData(dialog, interfaceItem.contacts || []);
  else dialog.close();
}

/** Keep unresolved metadata out of the diagram while showing accessible load progress. */
function showInterfaceContactLoading(diagram, total, loaded = 0, failed = false) {
  let status = diagram.querySelector(".interface-contact-loading");
  if (!status) {
    status = document.createElement("div");
    status.className = "interface-contact-loading";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const label = document.createElement("span");
    const progress = document.createElement("progress");
    progress.setAttribute("aria-label", "Contact geometry loading progress");
    status.append(label, progress);
    diagram.append(status);
  }
  diagram.contactState.workspace.root.hidden = true;
  paintInterfaceContactSelection(diagram.contactState);
  diagram.querySelector(".interface-contact-details-editor")?.remove();
  diagram.setAttribute("aria-busy", `${!failed}`);
  status.children[0].textContent = failed
    ? "Unable to load contacts. Close and reopen this panel to retry."
    : `Loading contacts… ${loaded} / ${total}`;
  status.children[1].max = total;
  status.children[1].value = loaded;
  status.children[1].hidden = failed;
}

/** Reveal the workspace only when its geometry is ready to render. */
function hideInterfaceContactLoading(diagram) {
  diagram.querySelector(".interface-contact-loading")?.remove();
  diagram.contactState.workspace.root.hidden = false;
  paintInterfaceContactSelection(diagram.contactState);
  diagram.setAttribute("aria-busy", "false");
}

/** Fetch outlines only for the open dialog; coalesce requests and discard stale replies. */
function updateInterfaceContactData(dialog, contacts) {
  const diagram = dialog.children[2];
  dialog.contactMetadata = contacts;
  if (dialog.cacheRebuildPending) return;
  const geometryKey = contactGeometryKey(contacts);
  const displayKey = JSON.stringify(contacts.map((item) => [item.contactId, item.name, item.assignedName, item.pin]));
  dialog.requestedGeometryKey = geometryKey;
  if (dialog.geometryValidationPending) return;
  const priorCache = cachedContactGeometry?.harnessId === dialog.dataset.harnessId
    && cachedContactGeometry.interfaceId === dialog.dataset.interfaceId ? cachedContactGeometry : null;
  const priorKey = dialog.loadedGeometryKey || priorCache?.geometryKey;
  const signatures = dialog.contactSignatures || priorCache?.signatures;
  if (priorKey && priorKey !== geometryKey && signatures
    && contacts.length <= 1024 && Object.keys(signatures).length === contacts.length
    && contacts.every((item) => typeof signatures[item.contactId] === "string")) {
    dialog.geometryValidationPending = geometryKey;
    void send("get_interface_contact_signatures", {
      harnessId: dialog.dataset.harnessId, interfaceId: dialog.dataset.interfaceId,
      contactIds: contacts.map((item) => item.contactId),
    }).then((response) => {
      if (!response.ok || !response.signatures) throw new Error(response.error || "Contact validation unavailable.");
      if (!dialog.open || contactGeometryKey(dialog.contactMetadata) !== geometryKey) return;
      const unchanged = contacts.every((item) => (
        typeof response.signatures[item.contactId] === "string"
        && response.signatures[item.contactId] === signatures[item.contactId]
      ));
      if (unchanged) {
        if (dialog.loadedGeometryKey === priorKey) dialog.loadedGeometryKey = geometryKey;
        if (priorCache?.geometryKey === priorKey) priorCache.geometryKey = geometryKey;
      } else {
        dialog.loadedGeometryKey = null;
        dialog.contactSignatures = null;
        cachedContactGeometry = null;
      }
    }).catch(() => {
      if (!dialog.open) return;
      dialog.loadedGeometryKey = null;
      dialog.contactSignatures = null;
      cachedContactGeometry = null;
    }).finally(() => {
      dialog.geometryValidationPending = null;
      if (dialog.open) updateInterfaceContactData(dialog, dialog.contactMetadata);
    });
    return;
  }
  if (cachedContactGeometry && !matchingContactCache(dialog, geometryKey)) {
    cachedContactGeometry = null;
  }
  if (dialog.loadedGeometryKey === geometryKey) {
    hideInterfaceContactLoading(diagram);
    const metadata = new Map(contacts.map((item) => [item.contactId, item]));
    diagram.contactState.contacts = diagram.contactState.contacts.map((item) => (
      { ...item, ...metadata.get(item.contactId) }
    ));
    if (dialog.contactDisplayKey !== displayKey) {
      const geometry = new Map(diagram.contactState.contacts.map((item) => [item.contactId, item]));
      if (contacts.every((item) => Array.isArray(geometry.get(item.contactId)?.loops))) {
        renderInterfaceContacts(diagram, contacts.map((item) => ({ ...geometry.get(item.contactId), ...item })));
        dialog.contactDisplayKey = displayKey;
        rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
      } else {
        dialog.loadedGeometryKey = null;
      }
    }
    if (dialog.loadedGeometryKey === geometryKey) return;
  }
  if (dialog.contactRequestPending) return;
  const cached = matchingContactCache(dialog, geometryKey);
  if (cached) {
    const metadata = new Map(contacts.map((item) => [item.contactId, item]));
    const currentContacts = cached.contacts?.map((item) => ({ ...item, ...metadata.get(item.contactId) }))
      || contacts;
    if (restoreRenderedContactDiagram(dialog, geometryKey, displayKey, currentContacts)) {
      dialog.loadedGeometryKey = geometryKey;
      dialog.contactDisplayKey = displayKey;
      dialog.contactSignatures = cached.signatures;
      return;
    }
    if (cached.contacts) {
      renderInterfaceContacts(diagram, currentContacts);
      rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
      dialog.loadedGeometryKey = geometryKey;
      dialog.contactDisplayKey = displayKey;
      dialog.contactSignatures = cached.signatures;
      return;
    }
  }
  if (!contacts.length || contacts.every((item) => Array.isArray(item.loops))) {
    hideInterfaceContactLoading(diagram);
    renderInterfaceContacts(diagram, contacts);
    rememberContactGeometry(dialog, geometryKey, contacts);
    rememberRenderedContactDiagram(dialog, geometryKey, displayKey);
    dialog.loadedGeometryKey = geometryKey;
    dialog.contactDisplayKey = displayKey;
    dialog.contactSignatures = contactSignatures(contacts);
    return;
  }
  dialog.contactRequestPending = true;
  dialog.rebuildButton.disabled = true;
  showInterfaceContactLoading(diagram, contacts.length);
  void fetchInterfaceContactGeometry(dialog, contacts, geometryKey).then((response) => {
    if (!dialog.open || dialog.requestedGeometryKey !== geometryKey) return;
    if (!response.ok || !Array.isArray(response.contacts)) throw new Error(response.error || "Contact geometry unavailable.");
    const metadata = new Map(dialog.contactMetadata.map((item) => [item.contactId, item]));
    if (response.contacts.length !== metadata.size
      || response.contacts.some((item) => !metadata.has(item.contactId))) {
      throw new Error("Contact geometry no longer matches the saved Interface.");
    }
    rememberContactGeometry(dialog, geometryKey, response.contacts);
    hideInterfaceContactLoading(diagram);
    const renderStarted = Date.now();
    renderInterfaceContacts(diagram, response.contacts.map((item) => ({ ...item, ...metadata.get(item.contactId) })));
    const currentDisplayKey = JSON.stringify(dialog.contactMetadata.map((item) => (
      [item.contactId, item.name, item.assignedName, item.pin]
    )));
    rememberRenderedContactDiagram(dialog, geometryKey, currentDisplayKey);
    const renderMs = Date.now() - renderStarted;
    dialog.loadedGeometryKey = geometryKey;
    dialog.contactDisplayKey = currentDisplayKey;
    dialog.contactSignatures = contactSignatures(response.contacts);
    if (developerModeEnabled) {
      void reportInterfaceContactCache(dialog, response, renderMs);
    }
  }).catch((error) => {
    if (dialog.open && dialog.requestedGeometryKey === geometryKey) {
      showInterfaceContactLoading(diagram, contacts.length, 0, true);
      appendNotice(String(error), true);
    }
  }).finally(() => {
    dialog.contactRequestPending = false;
    if (dialog.open && !dialog.cacheRebuildPending) dialog.rebuildButton.disabled = false;
    if (dialog.open && dialog.requestedGeometryKey !== geometryKey) {
      updateInterfaceContactData(dialog, dialog.contactMetadata);
    }
  });
}

/** Report one cold-load cache decision and timing in developer mode. */
async function reportInterfaceContactCache(dialog, load, renderMs) {
  try {
    const response = await send("get_interface_contact_cache_status", {
      harnessId: dialog.dataset.harnessId, interfaceId: dialog.dataset.interfaceId,
    });
    if (!dialog.open) return;
    if (!response.ok || !response.cache) throw new Error(response.error || "Cache status unavailable.");
    const cache = response.cache;
    const details = [
      `path ${load.cacheMode || "batches"}`,
      `before ${load.cacheBefore?.reason || "unknown"} / ${load.cacheBefore?.snapshot || "unknown"}`,
      `after ${cache.reason} / ${cache.snapshot}`,
      `${load.cacheHits} hits / ${load.cacheMisses} misses`,
    ];
    if (Number.isFinite(cache.entries)) details.push(`${cache.entries} entries`);
    if (cache.lastWrite) details.push(`last write ${cache.lastWrite}`);
    appendNotice(`Contact load ${(load.elapsedMs / 1000).toFixed(1)} s (${load.serverMs} ms backend) + render ${renderMs} ms. Cache: ${details.join(", ")}.`);
  } catch (error) {
    if (dialog.open) appendNotice(`Contact cache diagnostics failed: ${String(error)}`, true);
  }
}

/** Discard the current Interface snapshot and refill it through the progress loader. */
async function rebuildInterfaceContactCache(dialog) {
  if (dialog.cacheRebuildPending || dialog.contactRequestPending) return;
  const diagram = dialog.children[2];
  dialog.cacheRebuildPending = true;
  dialog.rebuildButton.disabled = true;
  showInterfaceContactLoading(diagram, dialog.contactMetadata.length);
  try {
    const response = await send("rebuild_interface_contacts_cache", {
      harnessId: dialog.dataset.harnessId, interfaceId: dialog.dataset.interfaceId,
    });
    if (!response.ok) throw new Error(response.error || "Could not clear contact cache.");
    if (!dialog.open) return;
    cachedContactGeometry = null;
    dialog.loadedGeometryKey = null;
    dialog.contactDisplayKey = null;
    dialog.contactSignatures = null;
    dialog.requestedGeometryKey = null;
    dialog.cacheRebuildPending = false;
    updateInterfaceContactData(dialog, dialog.contactMetadata);
    if (!response.diskCacheAvailable) {
      appendNotice("Contact outlines rebuilt in memory; save the design to enable disk caching.");
    }
  } catch (error) {
    if (dialog.open) {
      hideInterfaceContactLoading(diagram);
      appendNotice(String(error), true);
    }
  } finally {
    dialog.cacheRebuildPending = false;
    if (dialog.open && !dialog.contactRequestPending) dialog.rebuildButton.disabled = false;
  }
}

/** Yield to Fusion between bounded batches; closing or superseding stops further work. */
async function fetchInterfaceContactGeometry(dialog, contacts, geometryKey) {
  const started = Date.now();
  if (contacts.length > 16 && contacts.length <= 1024) {
    const warm = await send("get_interface_contacts_cached", {
      harnessId: dialog.dataset.harnessId, interfaceId: dialog.dataset.interfaceId,
      contactIds: contacts.map((item) => item.contactId),
    });
    if (!warm.ok) throw new Error(warm.error || "Contact cache unavailable.");
    if (warm.cacheComplete) {
      return { ok: true, contacts: warm.contacts, cacheBefore: { reason: "eligible", snapshot: "present" },
        cacheHits: warm.contacts.length, cacheMisses: 0, serverMs: warm.serverMs || 0,
        cacheMode: "single warm read", elapsedMs: Date.now() - started };
    }
  }
  const resolved = [];
  let cacheBefore = null;
  let cacheHits = 0;
  let cacheMisses = 0;
  let serverMs = 0;
  for (let offset = 0; offset < contacts.length; offset += 8) {
    if (!dialog.open || dialog.requestedGeometryKey !== geometryKey) return { ok: true, contacts: [] };
    const response = await send("get_interface_contacts", {
      harnessId: dialog.dataset.harnessId, interfaceId: dialog.dataset.interfaceId,
      contactIds: contacts.slice(offset, offset + 8).map((item) => item.contactId),
      diagnostics: developerModeEnabled,
      diagnosticFirstBatch: offset === 0,
    });
    if (!response.ok || !Array.isArray(response.contacts)) throw new Error(response.error || "Contact geometry unavailable.");
    if (response.cacheBefore) cacheBefore = response.cacheBefore;
    cacheHits += response.cacheStats?.hits || 0;
    cacheMisses += response.cacheStats?.misses || 0;
    serverMs += response.serverMs || 0;
    resolved.push(...response.contacts);
    if (dialog.open && dialog.requestedGeometryKey === geometryKey) {
      showInterfaceContactLoading(dialog.children[2], contacts.length, Math.min(offset + 8, contacts.length));
    }
  }
  return { ok: true, contacts: resolved, cacheBefore, cacheHits, cacheMisses, cacheMode: "batches",
    serverMs, elapsedMs: Date.now() - started };
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
  const rebuild = document.createElement("button");
  const remove = document.createElement("button");
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
      void send("select_interface_contacts", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId,
        mode: ["manual", "row", "plane"][index],
      }).catch((error) => appendNotice(String(error), true));
    });
    buttons.push(button);
    modes.append(button);
  });
  remove.type = "button";
  remove.className = "button compact";
  remove.textContent = "Delete";
  remove.title = "Delete selected contacts from this Interface (Del)";
  remove.disabled = true;
  modes.append(remove);
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
  renderInterfaceContacts(diagram, []);
  diagram.contactState.harnessId = harness.harnessId;
  diagram.contactState.interfaceId = interfaceItem.interfaceId;
  diagram.contactState.deleteButton = remove;
  diagram.contactState.onDeleteContacts = async () => {
    const state = diagram.contactState;
    if (!dialog.open || !state || state.deleting || state.workspace.root.hidden
      || !state.selectedIds.size) return;
    const contactIds = [...state.selectedIds];
    state.deleting = true;
    paintInterfaceContactSelection(state);
    try {
      const response = await send("remove_interface_contacts", {
        harnessId: harness.harnessId, interfaceId: interfaceItem.interfaceId, contactIds,
      });
      if (!response.ok) throw new Error(response.error || "Could not delete selected contacts.");
      contactIds.forEach((id) => state.selectedIds.delete(id));
    } catch (error) {
      if (dialog.open) appendNotice(String(error), true);
    } finally {
      if (dialog.open && diagram.contactState === state) {
        state.deleting = false;
        paintInterfaceContactSelection(state);
      }
    }
  };
  remove.addEventListener("click", () => { void diagram.contactState?.onDeleteContacts?.(); });
  diagram.contactState.onEditContact = (contactId, event) => {
    openInterfaceContactEditor(diagram, diagram.contactState, contactId, event);
  };
  actions.className = "pathway-popup-actions";
  close.type = "button";
  close.className = "button";
  close.textContent = "Close";
  close.addEventListener("click", () => dialog.close());
  rebuild.type = "button";
  rebuild.className = "button";
  rebuild.textContent = "Rebuild Cache";
  rebuild.title = "Discard this Interface's cached outlines and resample them from Fusion";
  rebuild.addEventListener("click", () => { void rebuildInterfaceContactCache(dialog); });
  dialog.rebuildButton = rebuild;
  actions.append(close, rebuild);
  dialog.append(title, toolbar, diagram, actions);
  dialog.addEventListener("close", () => {
    diagram.contactState.items.forEach((item) => item.clearHover?.());
    // A cached SVG must not retain the old workspace's event handlers and state.
    if (cachedContactGeometry?.rendered?.svg === diagram.contactState.svg) {
      diagram.contactState.workspace.stage.replaceChildren();
    }
    dialog.contactMetadata = [];
    diagram.contactState = null;
    diagram.replaceChildren();
    dialog.remove();
  });
  document.body.append(dialog);
  dialog.showModal();
  updateInterfaceContactData(dialog, interfaceItem.contacts || []);
  window.requestAnimationFrame(() => {
    if (dialog.open && !diagram.contactState.workspace.root.hidden) diagram.contactState.workspace.fit();
  });
}
