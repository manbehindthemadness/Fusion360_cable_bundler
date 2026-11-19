# Construction history diagnostic

A shared, opt-in instrument for understanding feature origins and placement. The
viewer replays frozen stages; navigation never invokes a solver, audit or builder.
It runs offline without third-party JavaScript or network requests. Fusion's own
palette can follow the selected stage in one explicitly owned Custom Graphics
group. It creates no BRep bodies and changes no routing acceptance rules.

## What the viewer shows

Previous/Next, a scrubber, phase filtering and Play step through numbered stages.
The optional Loop checkbox repeats playback from the last to the first step in
the active phase filter. It starts unchecked; Pause stops repeating playback,
and clearing Loop restores stopping at the end. Manual navigation still stops Play.
Playback errors also stop Play/Loop. An active Fusion command or a different
active document pauses without permanently latching the viewer: return to the
original idle document and press Play or navigate manually. The browser returns
to the last native-confirmed stage after a pause. Valid acknowledgements clear
the pause message. Changed/deleted ownership, source drift, API and resource
failures remain latched; repeated requests preserve the first error unchanged.
Four synchronized views show isometric, XY, XZ and YZ projections. Drag the
isometric view to orbit, wheel to zoom, and use Fit/reset to restore the camera.
The selected feature is pink; new or changed geometry is orange; rejected-stage
geometry is red. Previous-step comparison is dashed. Entry frames use red for
forward material direction and green for positive width. Local primitive views
explicitly omit world connector targets; they are not additional complete routes.

Select a feature to read its source, parent identity, actual placement predecessor,
entry/exit frame, original primitive parameters and material interval in mm.
“Go to origin” opens its earliest available geometry. “From …” buttons follow its
ancestry or placement predecessor. The details panel also retains recorded cap
residuals, clearance rows, coordinates and decisions when supplied by an observer.
Three sampled material lanes illustrate surfaces; these are not contact proofs,
complete thickness meshes, native material-coordinate audits or valid solids.

Every stage distinguishes:

- **observed**: a frozen input, available output or an event published by execution;
- **reconstructed**: assembly derived from saved primitive/placement data, not the
  original order of discovery, optimization or native calls;
- **unavailable**: the source did not record that stage. No replacement geometry
  or inferred successful operation fills the gap.

A status-only event may retain its previous snapshot solely as context. Its banner
and `geometry_available: false` explicitly say this is not the current proposal.
Separate archived execution journals reset that context. Existing failure and
qualification classifications remain authoritative; playback grants no new pass.

## Shared recording contract

`Journal(path, run_id, provenance)` creates an exclusive append-only JSONL stream.
Use `define(id, label, kind, parents, source)` once per feature, then
`emit(phase, title, status, basis, scene, details)` at actual construction boundaries.
Close the journal in `finally`. Every event is detached from mutable caller data
and flushed before control returns. Recorder/I/O/resource errors propagate and
preserve the prefix. Do not silently continue a diagnostic after losing its trace.

The versioned `ribbon-construction-v1` schema uses mm and explicit local/world
geometry. Each display object contains a known feature identity, bounded sampled
polylines, optional orthonormal origin/forward/across frame, optional advancing
material interval and JSON details. Parents must already exist; cyclic ancestry
and conflicting feature redefinitions reject. Stable IDs are supplied by adapters,
not inferred by nearest position. Create new IDs when route topology or provenance
changes. Material fold/straight-slot ordinals are stable only within an explicitly
unchanged chain; no identity guarantee across inserted/deleted/replaced bends.

Phases: input, preplot, primitive, placement, bend, proposal, correction, audit,
output. Dispositions: reference, attempted, accepted, rejected, unresolved,
unavailable, error. “Accepted” retains the original caller's measured scope; it
never means full physical qualification merely because the record uses that word.
Include source/input hashes and run lineage in provenance. Original source-file
names and retained parameters establish provenance; the viewer cannot recover
creation call stacks that were not recorded.

Limits:512stages,1024features,300000sampled points,32MiB journal, at most256objects
per stage and64paths per object. Material adapter:32pieces/33samples per lane.
Limits preserve a prefix and raise, never renew automatically. Frozen capture and
each live display update have10-second wall bounds. Launch RSS must be below
3.8GiB, sampled RSS below4GiB, actual system free memory at least10%. The optional
observer adds sampling/serialization/I/O overhead; charge it to the caller's
aggregate wall/CPU budget and report diagnostic timing separately. The0.4-second
recovery CPU target and warning-only testing policy remain unchanged.

`load(path)` validates a bounded complete-line prefix. A truncated final record
rejects rather than silently dropping an interrupted observation. Preserve such a
file for review. `export(path, new_html_path)` writes a self-contained artifact;
existing evidence is never overwritten. Markup in recorded labels is escaped.

## Existing solver and experiment adapters

`construction.sampled.capture_shape(journal, ribbon_shape, identity)` reads existing
application `RibbonShape` frames and final conductor lanes without modifying the
production solver. Internal fold discovery is explicitly unavailable: final
sampled lanes cannot reveal the original primitive decisions.

`experiments.experiment_ribbon_construction_diagnostic.adapter` supports existing
material-route experiments:

- `inputs(journal, route)` retains fixed A/B frames and an explicitly reconstructed
  chord/3 endpoint pre-plot. This does not assert the original solve used it.
- `assembly(journal, route, chain_id, context)` shows unrolled reference blanks,
  actual local finite-radius primitives and successive saved world placements,
  ending with the complete retained material snapshot. All assembly operations
  are labeled reconstructed; partial prefixes are not complete outputs.
- `EventBridge(journal, context, downstream=original_record)` can replace the
  existing selected solver's `record` callback while preserving the original
  callback first. Its `route` snapshots become observed geometry. Other events
  remain status/details only. It does not monkey-patch or reload a solver.
  The selected worker continues using its existing pinned sources; integrating
  the bridge into a locked campaign requires a newly frozen diagnostic plan.
- Supply `stable_chain="…"` only when unchanged ordered topology is established.
  Otherwise snapshots receive independent IDs and no correspondence is claimed.

For actual placement origins, `experiments.experiment_ribbon_construction_diagnostic.origin`
adapts optional `trace=` hooks on `terminal_approaches.chains/bridge` and `Frontier`.
The hooks publish computed inputs, approach handles, common bridge frame, returned
rotation factors, declared chains, completed LPs and executed separation branches.
The adapter retains the affine equations/whole-material support rows used in each
model, and samples actual LP coordinates through that same model. `route_scene`
can take a previously defined `origin` feature to link its first fold to the
declared chain and its rotation-factor parents. No saved route initializes this
capture. The observer does not select roots or change angles/lengths/acceptance;
recorder failures propagate and capture time stays within caller resource limits.

Run one explicitly scoped, endpoint-only diagnostic with:

```sh
uv run python -m experiments.experiment_ribbon_construction_diagnostic.origin_run \
  --input artifacts/verification/PREPARED/endpoint-input.json \
  --output artifacts/verification/NEW_ORIGIN_CAPTURE
```

The input has exactly `targets` (the ordered `Targets` fields) and `radius_mm`.
Route-shaped payloads reject. The output directory must not exist. This executes
the current unselected terminal-construction experiment once: at most eight
algebraic roots/six bends, 64 LP nodes/4096 active intersections, 10-second
preparation/2-second allocation/30-second outer wall. CPU misses against 0.4 seconds
are recorded; memory, cancellation, recorder and source errors remain hard stops.
The shared journal limits still apply. Obtain/freeze the applicable scope before
running; this command does not authorize additional experiments.

Local factor displays have **no world placement yet**. Zero-travel model templates
are explicitly unclosed equation references. LP allocations may close both caps
while failing separation rows; their recorded disposition remains visible. A
selected inspection allocation is not a qualified output. These are observed
decision boundaries and sampled geometry, not every arithmetic operation inside
rotation factoring/LP enumeration. Native builds and independent audits are absent.

Checkpoint3403 captured one retained E layout from endpoints: 44 observed stages,
four roots relaxed, 23 nodes/1189 intersections before the unchanged two-second
allocation wall stop. The 49.615928 mm inspection route did not satisfy all supplied
separation rows. Combined preparation/allocation CPU was 1.288035 seconds, including
observer work (0.888035 over target). No retry, native build, independent physical
audit or fresh coverage followed. Prior 3394 geometry/evidence remains unchanged.
The registered host opens the new frozen trace at the connector-only first stage;
the previous exact owner is hidden as its sole immediate comparison. Native
draws of handles/shared frame and return to the first stage passed; all four page
views rendered and the live screenshot was inspected. This turn did not repeat
browser-button navigation testing. Twenty-five focused Python tests, changed-file
Ruff/format and IDE diagnostics passed. Evidence is under `resume3403/`.

The waypoint experiment now has optional `trace=` callbacks on `run(...)` and
`ClearanceMotion(...)`. For a newly approved diagnostic, send ordinary `record`
events and both trace callbacks to the SAME bridge. Raw proposals appear before
restoration; actual correction states and halving trials carry coordinates, cap
position components in mm, rotation vectors in radians, selected plane gaps and
violations, step vectors and explicit decline/limit events. No observer is enabled
by default. Analytical checks compare results and work counts with capture off/on.
This wiring has not yet been exercised on a new gym solve;3396cannot acquire
missing intermediate evidence retroactively.

Other algorithms can emit the same feature/scene contract directly. A native
builder can publish its observed source-body identity and sampled result with
explicit correspondence. Native construction hooks and full BRep/material-map
capture are not implemented by this first version and must remain unavailable
unless a caller actually supplies that evidence.

## Saved-evidence command

Discover the project SDK before invocation, strip inherited Python environment
variables, and choose a NEW output directory under ignored artifacts:

```sh
env -u PYTHONHOME -u PYTHONPATH uv run python -m experiments.experiment_ribbon_construction_diagnostic \
  --route artifacts/verification/resume3394/route.json \
  --events artifacts/verification/resume3395/events.jsonl artifacts/verification/resume3396/events.jsonl \
  --chain E-four-hinge --output artifacts/verification/NEW_CONSTRUCTION_CAPTURE
```

This command only imports/restores frozen data and samples display geometry. It
never runs routing or physical audits. Open the exported `viewer.html` offline.
For Fusion, provide an EMPTY explicitly owned component tagged with
`ribbonConstruction/run = trace header run_id`, in the same idle document, and
retain `host.Viewer(component, document_id, journal_path, html_path).show()`.
The viewer deletes only its own prior display group; owner cleanup belongs to the
caller after exact ownership review. A host/source failure latches navigation.
No solver modules are reloaded. Current plus one immediate comparison is the live
retention limit; preserve unknown/user geometry.

The checked **Auto-zoom** option fits the Fusion camera on step changes and lets
the four browser views choose their stage framing. Uncheck it to retain the current
framing while stepping, playing or selecting features. Browser orbit/wheel zoom
still work, and **Fit / reset view** explicitly reframes the browser views. Fusion's
own manual Fit remains available. The preference is presentation-only and defaults
on when opening the page; legacy navigation messages retain their prior policy.

An interactive palette needs a persistent Fusion host, not just a retained Python
object. An add-in already provides that lifetime. Standalone scripts must run
through Fusion's script manager and call `adsk.autoTerminate(False)` before
returning; launching `Viewer.show()` from a short-lived MCP invocation does not
establish interactive event handling. See the working inspection API's existing
host-lifetime requirement and Autodesk's
[script lifetime documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Commands_UM.htm).

`experiments/experiment_ribbon_construction_host/` is a registered script bundle
for an explicitly prepared viewer. Its request is
`artifacts/verification/construction-host-request.json`, containing exactly
`owner_module` (a retained `ribbon_construction_history_*` module with `VIEWER`),
`directory` (a new receipt directory under artifacts/verification) and `sources`
(repository-relative paths mapped to SHA256 digests). It validates the owner and
pins, recreates only that viewer's palette, retains its callbacks and stays alive
until Close or script Stop. Stop deletes only the palette, retaining the frozen
journal and owned graphics. Use a fresh receipt directory for another launch.

## Checkpoint3397 evidence

One historical gym E layout,37stages/11066points/818823journal bytes. Capture
0.096804CPU/0.114470wall seconds, including display sampling/export, no search.
No new independent validation configurations, native builds or physical audits.
3394's material snapshot supplies reconstructed assembly;3395and3396journals
supply observed recorded dispositions.3396intermediate corrections are absent.

The Fusion palette opened at1120x870 in the same idle scratch. One trace group,
zero BReps/sketches; prior rejected3395retained hidden, exact obsolete3394owner
retired only after receipt verification. First display and later host readback show
no host error. Native palette visibility does not establish browser paint/control
success. Computer-use startup failed, so live visual/control verification is
awaiting the user's observation; do not claim it passed.

Verification:20focused Python tests (trace integrity, provenance, source geometry,
application/material adapters, observer neutrality and existing hinge contracts),
Ruff check/format, changed-code IDE checks, and
`node tests/construction_history_viewer.test.mjs`. The Node test executes the real
viewer controller with a fake DOM/canvas and checks four paint paths, navigation,
origin, filtering, playback and Fusion messages. It is not a real browser render.
Selected/production routing and the generalized-solver qualification state remain
unchanged. Plan, frozen capture and live receipts: artifacts/verification/resume3397/.

## Checkpoint3398: initial embedded-browser layout — live issue still open

User reports rendering starts only after collapsing/reopening. Moved the existing
spatial inspector's native layout policy into shared
`devtools/ribbon_analysis/palette_layout.py`; its old module retains compatibility
exports. The construction host now applies final dimensions after visibility,
uses different creation/final dimensions, and wraps its original selection bridge
with the same single-refresh layout observer under `construction_layout`.
The HTML redraws on load, resize and visibility, reports actual four-canvas sizes,
and waits at most40x100ms for a late Fusion bridge. Trace fingerprint binds reports
to the original journal. No route, search, acceptance or physical geometry changed.

24focused Python checks pass (shared spatial-policy compatibility plus construction
history), Node controller regression passes zero-size/load/visibility recovery,
late bridge and retained fragment selection, Ruff/format and IDE checks clear.
Initial logs contained no matching palette/JavaScript exception. User's observed
failure remains stronger evidence than native `isVisible` alone.

Two separately frozen presentation launches returned ZERO browser reports; one
allowed explicit surface refresh and restoration of the original raw local-file
path also produced no acknowledgement. Preserve all attempts under resume3398;
no further automatic palette launch or resize is scheduled. Current browser page
is resume3398/viewer2.html, raw local path, with unchanged3397trace. The loaded
viewer retains step0, one graphics group and no host error. Current source host
uses an encoded URI/fragment for future launches; the live raw-path correction is
separately recorded and neither path has established a successful first paint.
Do not call this fixed or a successful UI verification.

Computer use now reaches Fusion's main window but does not expose the floating
palette there. Main-window screenshot and Window menu did not establish its
visible state. A new async question asks whether the user sees the dialog rendered,
blank, or absent. Pause dependent UI changes pending that observation. No numerical
modules reloaded, native bodies, solver replays or physical audits. Earlier3397
receipts and original page remain unchanged;3398archives presentation source before
each revision and records explicit source re-pinning of unchanged guard/draw code.

## Checkpoint3399: blank confirmed; minimal page also unacknowledged

User confirmed the palette is blank. One self-contained static HTML/canvas page
was loaded in the existing palette to test page execution and the existing bridge
without viewer dependencies. It returned no layout report, including after one
separated hide/show pulse. The original3398/viewer2.html was restored; step0 and
the single graphics group remain unchanged. Receipts are under
`artifacts/verification/resume3399/`. No maintained executable source changed.

This does not distinguish failed page initialization from a failed bridge. Stop
further speculative layout edits. Request a saved-work Fusion restart before one
frozen-viewer startup check; the live UI remains unresolved and unverified.
No numerical reload, solve, native build or physical audit occurred.

## Checkpoint3400: match working routing-diagnostics startup

The user directed comparing existing working tools before restarting Fusion.
The existing routing-diagnostics HTML rendered normally in this session using its
raw resolved path and right-docked startup, confirmed by the user. Docking the
old construction palette alone did not establish a browser acknowledgement.
Recreating the construction palette with that same startup also rendered
immediately without collapse/reopen, confirmed by the user.

`host.Viewer.show()` now uses a raw resolved local path,620x800 initial bounds,
vertical docking option, right docking and visibility last. It no longer creates
a floating palette with an encoded URI/fragment or resizes after showing it.
The successful combined sequence does not isolate which difference caused the
original blank window. The same frozen page, trace and graphics were retained.
The temporary read-only comparison palette was retired; no numerical modules
were reloaded and no solve, native build or physical audit ran.

The user's Next-step check then showed browser-only advancement and an unexpected
end of JSON input error. The browser had parsed an empty acknowledgement as JSON.
It now rejects empty/invalid acknowledgements explicitly and uses a bounded
read-only readiness handshake; startup readiness does not run geometry itself.
A raw native observer received events while the original registered policy did
not. A fresh native relay forwarded them to the existing policy successfully.
The host now retains a fresh native adapter separately from the reusable policy.
After updating the frozen page, a later callback rebind was needed before native
readback showed one valid four-view report, no host error and step0. The precise
registration/lifecycle cause remains unisolated, and cold startup of the final
combined source has not been checked. A second user viewport-navigation check is
pending. Page3400/viewer.html and presentation_host_3400 are current; numerical
modules and geometry guard/draw have not been reloaded.

28focused checks pass; Node checks cover empty acknowledgement, bounded readiness
exhaustion and reconnection. Ruff/format and all changed-code IDE diagnostics are
clear. A local pass is not native callback lifecycle validation.
Receipts and the previous host source are under `artifacts/verification/resume3400/`.

## Checkpoint3401: restart exposes the missing persistent host

After Fusion restart, the final3400 source rendered immediately but the user
confirmed browser-only navigation and the explicit empty-acknowledgement error.
Re-registering the same callback after paint produced a valid layout report;
moving registration after visibility alone did not restore startup. That order
change was reverted exactly. Neither callback replacement nor a local test pass
proved a usable cold startup.

The existing inspection API already documented the standalone script-lifetime
requirement. The earlier MCP launcher omitted it. The new registered script host
uses `adsk.autoTerminate(False)` and keeps the viewer and cleanup handler alive.
Native readback now shows the script running after return, four layout reports
and all four canvases painted without manual rebinding, no host error and step0.
The user's final Next-step/viewport confirmation remains pending. Native palette
close/Stop cleanup is unit-tested but not live-tested in this retained session.

31focused tests pass; final test-only fixture edits were rechecked with3tests.
New script/test Ruff checks and IDE inspections are clear. Current host.py exactly
matches the3400 parent; no remaining startup-order edit. The live design is now
e77672c7-0815-4864-ba2d-447a29ad954f with one owned trace component and one graphics
group. The old hidden comparison was not restored. No solve, BRep construction,
physical audit or numerical reload occurred. Setup initially lacked the repository
on sys.path; that pre-mutation failure and the finite failed startup probe are
preserved with all other receipts under `artifacts/verification/resume3401/`.

## Checkpoint3402: optional auto-zoom and readable backgrounds

User confirmed interactive playback with "yay"; native readback then showed step5,
selected E-four-hinge/S0, six layout reports and no host error. User requested an
auto-zoom checkbox and better main-window text contrast. The checkbox controls
native camera fitting through a strict optional boolean in the selection message;
unchecked browser views retain their last framing across local/world changes.
The panel body/main/aside/stage now explicitly use the existing dark palette so
Fusion/browser defaults cannot leave pale text on a white background. The current
Fusion lighting environment was changed from Photo Booth(2) to Dark Sky(0), under
the user's background request; this is not an automatic solver or viewer setting.

One registered host Stop/restart applied an explicit presentation-only class
revision, archived sources/pins and a fresh frozen page. Old evidence is unchanged.
The restarted page begins at step0.24focused Python checks and Node controller
checks pass; final test-format-only cleanup rechecked the10bridge cases. Changed
Python Ruff/format and all six changed-code IDE inspections are clear.
Two frozen step replays (next and back) with auto-zoom disabled left native eye,
target, up, extent and camera type exactly unchanged. This tests native camera
behavior; the Node test verifies checkbox transport and browser framing/manual fit.
Live computer-use screenshot shows the checkbox and readable dark panel; the saved
native canvas capture confirms label contrast. An initial camera-check getter
mistake stopped before either replay and is preserved separately. No solve, BRep
construction, physical audit or numerical reload occurred. Receipts3402 retain all
source revisions, launch, camera check and canvas image.
