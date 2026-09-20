/** Shared palette DOM references, storage, and session state. */

const ui = {
  back: document.getElementById("back"),
  create: document.getElementById("create"),
  editor: document.getElementById("editor"),
  editorView: document.getElementById("editor-view"),
  harnessFilter: document.getElementById("harness-filter"),
  libraryView: document.getElementById("library-view"),
  list: document.getElementById("harnesses"),
  notice: document.getElementById("notice"),
  validationOutput: document.getElementById("validation-output"),
  validationEventsStatus: document.getElementById("validation-events-status"),
  developerMode: document.getElementById("developer-mode"),
  developerConsent: document.getElementById("developer-consent"),
  developerConsentForm: document.getElementById("developer-consent-form"),
  developerConsentAgreement: document.getElementById("developer-consent-agreement"),
  developerConsentCancel: document.getElementById("developer-consent-cancel"),
  developerConsentEnable: document.getElementById("developer-consent-enable"),
  verboseDiagnostics: document.getElementById("verbose-diagnostics"),
};

function readSession(key) {
  try { return window.sessionStorage.getItem(key); }
  catch (_error) { return null; }
}

function writeSession(key, value) {
  try { window.sessionStorage.setItem(key, value); }
  catch (_error) { /* Palette storage is an optional convenience. */ }
}

function removeSession(key) {
  try { window.sessionStorage.removeItem(key); }
  catch (_error) { /* Palette storage is an optional convenience. */ }
}

function readPreference(key) {
  try { return window.localStorage.getItem(key); }
  catch (_error) { return null; }
}

function writePreference(key, value) {
  try { window.localStorage.setItem(key, value); }
  catch (_error) { /* Palette storage is an optional convenience. */ }
}

let currentState = { harnesses: [], notice: "" };
let selectedHarnessKey = readSession("cableBundler.selectedHarness") || "";
let openPathwayPopupId = "";
let openJunctionPopupId = "";
let openCableGroupDetailsState = null;
let configurationPopupParentState = null;
let openCreateCablesPopupState = null;
let masterDiagramResizeObserver = null;
const routeFilters = new Map();
const relationshipFilters = new Map();
const relationshipDiagramViews = new Map();
const relationshipEndListOverrides = new Map();
const DEFAULT_RELATIONSHIP_COLLAPSE_LIMIT = 7;
const MIN_RELATIONSHIP_COLLAPSE_LIMIT = 1;
const MAX_RELATIONSHIP_COLLAPSE_LIMIT = 999;
const DEVELOPER_MODE_DISCLOSURE_VERSION = "1";
const DEVELOPER_MODE_STORAGE_KEY = "cableBundler.developerMode";
const DEVELOPER_CONSENT_STORAGE_KEY = "cableBundler.developerConsentVersion";
const storedExpandedSections = readSession("cableBundler.expandedSections");
let hasStoredExpansionState = storedExpandedSections !== null;
let expandedSectionIds = [];
try {
  expandedSectionIds = JSON.parse(storedExpandedSections || "[]");
  if (!Array.isArray(expandedSectionIds)) expandedSectionIds = [];
} catch (_error) {
  expandedSectionIds = [];
}
const expandedSections = new Set(expandedSectionIds);
let developerModeEnabled = readPreference(DEVELOPER_MODE_STORAGE_KEY) === "true"
  && readPreference(DEVELOPER_CONSENT_STORAGE_KEY) === DEVELOPER_MODE_DISCLOSURE_VERSION;
if (!developerModeEnabled) writePreference(DEVELOPER_MODE_STORAGE_KEY, "false");
ui.developerMode.checked = developerModeEnabled;
ui.verboseDiagnostics.checked = developerModeEnabled
  && readPreference("cableBundler.verboseDiagnostics") === "true";
ui.verboseDiagnostics.disabled = !developerModeEnabled;
ui.validationOutput.hidden = true;
const storedNoticeHeight = Number(readSession("cableBundler.noticeHeight"));
if (Number.isFinite(storedNoticeHeight) && storedNoticeHeight >= 72) {
  ui.notice.style.height = `${Math.min(600, storedNoticeHeight)}px`;
}

function harnessKey(harness) {
  return harness.harnessId || `component:${harness.componentName}`;
}

function relationshipCollapseStorageKey(harness) {
  return `cableBundler.relationshipCollapseLimit:${harnessKey(harness)}`;
}

function clampRelationshipCollapseLimit(value) {
  const parsed = Math.round(Number(value));
  if (!Number.isFinite(parsed)) return DEFAULT_RELATIONSHIP_COLLAPSE_LIMIT;
  return Math.min(
    MAX_RELATIONSHIP_COLLAPSE_LIMIT,
    Math.max(MIN_RELATIONSHIP_COLLAPSE_LIMIT, parsed),
  );
}

function relationshipCollapseLimit(harness) {
  const stored = readSession(relationshipCollapseStorageKey(harness));
  return stored === null
    ? DEFAULT_RELATIONSHIP_COLLAPSE_LIMIT
    : clampRelationshipCollapseLimit(stored);
}


