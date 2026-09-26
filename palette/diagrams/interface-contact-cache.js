// Keep bounded projection and vector-image snapshots across document switches.
const MAX_CONTACT_CACHE_BYTES = 4_000_000;
const MAX_CONTACT_CACHE_TOTAL_BYTES = 8_000_000;
const MAX_CONTACT_CACHE_SNAPSHOTS = 4;
const cachedContactGeometries = new Map();

/** Include the saved document version so copied Interfaces cannot share geometry. */
function contactSnapshotKey(dialog) {
  return JSON.stringify([
    dialog.dataset.contactDocumentScope || "",
    dialog.dataset.harnessId,
    dialog.dataset.interfaceId,
  ]);
}

/** Find the snapshot belonging to one Interface without retaining Fusion objects. */
function currentContactGeometry(dialog) {
  const key = contactSnapshotKey(dialog);
  const cached = cachedContactGeometries.get(key) || null;
  if (cached) {
    cachedContactGeometries.delete(key);
    cachedContactGeometries.set(key, cached);
  }
  return cached;
}

/** Discard one Interface while leaving other documents' snapshots intact. */
function forgetContactGeometry(dialog) {
  cachedContactGeometries.delete(contactSnapshotKey(dialog));
}

/** Cap total palette memory after updating the most recently used snapshot. */
function trimContactGeometryCache() {
  const bytes = () => [...cachedContactGeometries.values()]
    .reduce((total, cached) => total + (cached.cacheBytes || 0), 0);
  while (cachedContactGeometries.size > MAX_CONTACT_CACHE_SNAPSHOTS
    || bytes() > MAX_CONTACT_CACHE_TOTAL_BYTES) {
    cachedContactGeometries.delete(cachedContactGeometries.keys().next().value);
  }
}

/** Track contact membership and the last geometry-changing Fusion command. */
function contactGeometryKey(contacts) {
  return JSON.stringify(contacts.map((item) => [item.contactId, item.geometryRevision]));
}

/** Reuse a snapshot only for the same Interface and geometry revision. */
function matchingContactCache(dialog, geometryKey) {
  const cached = currentContactGeometry(dialog);
  return cached?.geometryKey === geometryKey ? cached : null;
}

/** Return sampled geometry when it fits alongside the rendered image. */
function restoredContactGeometry(dialog, geometryKey) {
  return matchingContactCache(dialog, geometryKey)?.contacts || null;
}

/** Bound retained outline data without holding Fusion objects. */
function rememberContactGeometry(dialog, geometryKey, contacts) {
  const size = JSON.stringify(contacts).length * 2;
  cachedContactGeometries.set(contactSnapshotKey(dialog), {
    documentScope: dialog.dataset.contactDocumentScope || "",
    harnessId: dialog.dataset.harnessId,
    interfaceId: dialog.dataset.interfaceId,
    geometryKey,
    contacts: size <= MAX_CONTACT_CACHE_BYTES ? contacts : null,
    signatures: contactSignatures(contacts),
    geometryBytes: size <= MAX_CONTACT_CACHE_BYTES ? size : 0,
    cacheBytes: size <= MAX_CONTACT_CACHE_BYTES ? size : 0,
  });
  trimContactGeometryCache();
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
    cached.cacheBytes = cached.geometryBytes;
    return;
  }
  const outlineBytes = JSON.stringify(state.items.map((item) => item.loops)).length * 2;
  const markupBytes = state.svg.outerHTML
    ? state.svg.outerHTML.length * 2 : outlineBytes + state.items.length * 256;
  const imageBytes = outlineBytes + markupBytes;
  if (imageBytes > MAX_CONTACT_CACHE_BYTES) {
    cached.rendered = null;
    cached.cacheBytes = cached.geometryBytes;
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
  cached.cacheBytes = cached.geometryBytes + imageBytes;
  trimContactGeometryCache();
}

/** Attach a cached vector image to a fresh workspace with fresh interaction state. */
function restoreRenderedContactDiagram(dialog, geometryKey, displayKey, contacts) {
  const rendered = matchingContactCache(dialog, geometryKey)?.rendered;
  if (!rendered || rendered.displayKey !== displayKey) return false;
  const state = dialog.children[2].contactState;
  updateInterfaceContactWorkspace(state, rendered.svg, rendered.items, contacts, rendered.dimensions);
  return true;
}
