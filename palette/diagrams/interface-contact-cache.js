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
