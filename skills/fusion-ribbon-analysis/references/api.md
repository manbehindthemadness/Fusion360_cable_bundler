# Candidate and evidence API

## Recorded search and section inspection

For the user-directed endpoint-only environment preview, see the
[Rubik test gym](gym.md). It deliberately contains no preselected cable route,
solver invocation or newly imposed physical rule.

Use `devtools.ribbon_analysis.inspection` for new diagnostic investigations. It
keeps independent solver dispositions, frozen geometry and append-only search
history separate from the legacy evidence/acceptance display below. The current
experiment's inherited macaroni and collision acceptance claims were withdrawn.
New compatible-chart runs use the [percentage pinch rule](pinch.md), initially
99.6%. This controls positive local thickness clearance; global collision and
complete physical acceptance remain separate. Legacy records keep their old rule.

```python
from pathlib import Path
from devtools.ribbon_analysis.inspection.fusion_view import DiagnosticViewer

# Supply a component/document explicitly owned by this experiment.
view = DiagnosticViewer(owned_component, owned_document, Path(manifest_path))
view.show()
# Keep `view` alive for the palette's event handlers.
```

The local palette and Fusion browser represent every registered method, including
unrun and stopped methods. Historical families are listed with source locations;
they are not automatically executed. Select a final/reference result or any stored
search proposal, then move the section slider. Each section has a separate browser
component. X lies across the section, Y through thickness, and positive Z follows
the actual positive path derivative; X cross Y equals Z. The frame does not depend
on a Frenet normal at an inflection. Drag the palette preview to orbit and scroll
to zoom. Layer controls affect both the palette and the owned Fusion geometry.
The overview shows at most nine section outlines, including both ends and the
selected section. The slider retains every recorded inspection position; selecting
an intermediate sample replaces the nearest interior overview outline.

Wait for **Connected to Fusion** before using the selection controls. The palette
waits for the browser bridge and requires a native acknowledgement; **Reconnect**
reads the current state after a failed connection. Only this read-only handshake
may retry an empty initial response; selection/visibility requests are not repeated
after a timeout. Loading and unrun-method empty states are separate. The HTML is a
complete document with explicit head/body elements and is loaded as a local file.
Native messages use the `ribbon_inspection_` namespace and cast SDK HTML arguments;
SDK `response` notifications do not dispatch another request. See
[Autodesk's palette communication documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Palettes_UM.htm).
Standalone script hosts must remain alive (`adsk.autoTerminate(False)`) and retain
the viewer/handler; an add-in already supplies the persistent host. For bridge QA,
`sendInfoToHTML("diagnostic_request", json.dumps({"action": ..., "data": ...}))`
uses the same JavaScript request function as the controls. Observe native request
counters and actual scene changes; calling Python `dispatch` directly does not
verify this bridge. Automated pointer input remains a separate check.

The **Solver panels in Fusion** layer displays the selected recorded method,
settings, score, available coefficients, rule measurements and centre/edge bend
plot as Custom Graphics. Panels face the camera; physical radius circles retain
their real bend planes. Final-result metadata also remains in a hidden native
Solver details sketch inside the method component. Search proposals use their
own recorded coefficients; older records without them say unavailable.
**Constraint shapes (both views)** starts enabled and shows identical sampled
bend circles and the actual-end-to-target segment in the palette and Fusion.
For percentage-policy records, red circles show minimum bend diameters and blue
circles show actual curvature, all at the selected corresponding material station
in their real bend planes. The centre reference lies between the two edges under
the compatible geometry. The section slider moves all three pairs together.
Legacy records explicitly retain their historical unrelated red limits and
independently located worst-point blue circles; they are not relabelled as pinch.
The green segment joins the recorded endpoint to its fixed target. Very large
actual circles (over eight reference radii) are explicitly omitted while their
measurements remain listed; straight guides have no osculating circle. Palette
framing includes visible shape extents. Neither visibility toggle relaxes a rule.

Historical baseline/ablation comparisons remain selectable. **Matched baseline in
Fusion** shows grey baseline-result guides, and **View paired baseline** selects
its full record. Recorded disabled rules and independent measurements retain their
original meaning. New rule comparisons are unavailable after the user-directed
retirement of path search and all seed-based discovery on 2026-10-30.

For one conductor, the profile is one circle of the declared diameter. For wider
ribbons, captures contain open material rulings until the actual bonded contour
is supplied. **Thickness envelope** starts enabled in both views and displays one
translucent teal shell at the recorded diameter, without thickness exaggeration.
For a single conductor it joins recorded circular sections. For a ribbon it
extrudes each material ruling by +/-D/2 along its recorded local Y; this rectangular
nominal envelope is explicitly separate from the unresolved bonded outer contour.
Both renderers use the same millimetre vertices, triangles, sparse boundary lines
and opacity. End faces close the display mesh; no native solid or per-conductor
body is created. The caption reports thickness and profile assumptions. Hide it
independently to inspect centre/edge paths and bend circles. The shell follows
the selected result or proposal, including failed paths, without repairing overlap.
Inter-section triangles are sampled visual interpolation, not collision proofs.
The rule table distinguishes measured, failed, legacy, unmeasured and inapplicable
observations and never supplies an overall physical PASS. Observations belong to
the final/reference geometry; individual historical proposals remain unaudited.

```python
from devtools.ribbon_analysis.inspection.capture import SearchRecorder

recorder = SearchRecorder(history_path, "solver-identity", checkpoint)
with recorder.recording():
    result = solver(fixed_targets, checkpoint)
```

The compatible and unit-rotation transport entry points record every completed
transport within this explicit context, including finite-difference probes and
rejected trials. The bounded box fitter also records objective scores, coordinates
and actual trial decisions. Other solver implementations need an explicit adapter
calling `transported(path, integration_grid)`; an inventory entry alone does not
instrument a solver. Recording leaves coordinates and fitting decisions unchanged,
but its overhead consumes the scheduling budget and is reported as a subset.
Path/control-point/byte ceilings raise rather than dropping proposals. Every path
is flushed and fsynced before the next proposal; no record survives all possible
hardware failures by guarantee. JSON content digests detect geometry tampering,
not physical validity. Replay seeks a single indexed snapshot without solving.

The development controller now supplies example and gym selection only. Its old
launch API rejects every retired method before creating a directory, plan or SDK
subprocess. The direct adapter and standalone worker also reject stale requests;
explicit historical settings do not re-enable discovery. The batch runner authors
its fixed reference only, with zero search evaluations and all historical methods
marked unattempted. Recovery and JSONL replay remain available.

```python
from experiments.experiment_ribbon_diagnostic_viewer.controller import ProcedureController

runner = ProcedureController(Path(project_python_executable), Path(owned_run_directory))
view = DiagnosticViewer(owned_component, owned_document, Path(manifest_path), runner=runner)
view.show()
```

**Historical methods** lists the retired procedures without run/settings controls.
Generalized/broad search, ordinary refinement, redistribution, terminal tightening,
combined refinement, compatible shooting, director shooting and family/contact-guided
search all depended on seeds and are removed from active diagnostic execution.
Historical source modules remain for interpreting old evidence and their shared
geometry implementations; they are not a fallback for the current solver.
No replacement endpoint solver is implemented yet. Macaroni/pinch and structural
no-lateral-bending geometry remain available, and sweep-profile creation, conductor
identity/order and native geometry construction are unchanged. See [pinch.md](pinch.md).

The **Diagnostic example** selector keeps the original single-conductor S/lateral90
alongside a three-conductor spatial reversal. Each example retains its own session,
selected section and imported histories. An active job must stop and be collected
before switching. Supply existing references with the controller's optional
`references={"single": original_manifest, "ribbon": companion_manifest}` argument;
otherwise examples are authored once into new source-pinned archive directories.
The ribbon uses actual director-field material guides and open rulings, with no
invented bonded contour or individual conductor solids. Its analytic worst
material-guide radius is3D at100% utilization and material progress stays positive;
this does not establish full-thickness clearance or the missing radius/flex policy.

**Play search / Pause search** advances recorded paths through the same acknowledged
selection handler as the slider; it does not run numerical search. The **Macaroni /
centre and edge bending** panel measures the currently selected frozen cubics,
including proposals. Its radius values, measured centre/tighter-edge ratio and65point
curvature plot follow the section marker. The dashed3Dline is an explicit historical
material-guide reference, not the unresolved allowable centre/edge ratio, radius
scalar or clearance-flex contract. Straight/undefined radii remain explicit; sampled
cubic measurements do not certify continuous physical compliance.
For bridge QA, `sendInfoToHTML("diagnostic_playback", "true")` starts the same
playback function as the button and `"false"` pauses it. Observe actual native
proposal-selection requests and changing frozen geometry; this does not verify
physical pointer interaction. Native replay can recreate its own invalidated
method/scene handles after an external transaction rollback while retaining archives.

The first registered development fixture is a 1.5mm single circular conductor in
a compound S-bend whose heading changes 90 degrees laterally during the S. Its
analytic peak curvature attains the retained single-conductor limit, radius=3D
(4.5mm). The authored fixture, measured cubic interpolation and native geometry
are separate evidence. This does not define the unresolved wide-ribbon radius
ratio/scalar/flex policy. Future fixtures must explicitly declare the applicable
radius scalar and target utilization, using 100% utilization by default rather
than silently choosing loose curves; measure and retain actual utilization.

Run its bounded recording with the configured project SDK:

```text
uv run python -m experiments.experiment_ribbon_diagnostic_viewer.runner --output artifacts/verification/<unused-directory>
```

The frozen plan precedes search. `reference.json` survives independently of the
final `manifest.json`; `.jsonl` files retain completed proposals in explicit order.
After an interruption, recover without solving or replacing evidence:

```text
uv run python -m experiments.experiment_ribbon_diagnostic_viewer.runner --recover artifacts/verification/<interrupted-directory>
```

Recovery writes a uniquely named manifest, preserves any incomplete final JSONL
line in place, and marks recovered paths as interrupted/unaudited. A malformed
complete event still rejects. Keep the manifest and its relative history files
together. An interrupted reference write or failed storage cannot be recovered
from nonexistent evidence. Native construction and complete compliance remain
unmeasured until separately attempted and audited.

For a new25/25/50test matrix,use the host-only generator described in
[case generation](case-generation.md). Its `candidate_for` adapter connects a
solved or partially solved path to an exact frozen boundary case;no-path outcomes
remain separate dispositions rather than disappearing from coverage.

Import from the repository root, using its configured Python environment for
host work. In a Fusion MCP script, add the resolved repository root to `sys.path`
only if it is absent. Never install a PyPI substitute for Fusion's `adsk`.

```python
from devtools.ribbon_analysis.api import Candidate, analyze

candidate = Candidate(
    identifier="route-42-before-closure",
    path=stable_path,
    targets=fixed_targets,
    source="solver revision and frozen-input digest",
    primary="material J",  # or "center macaroni"
)
evidence = analyze(candidate, intervals=512)
data = evidence.inspect(kind="material J", trace_number=1)
```

`stable_path` implements `contracts.RibbonPath`:

- `field.lines`, `field.diameter_mm`, `field.half_width_mm` are fixed dimensions.
- `field.sample(u)` returns `(k, eta, eta_s)`: signed center curvature per mm,
  material-ruling slope and its derivative per material mm, for normalized `u`.
- `lane(u, offset_mm)` returns `(Vector3 position_mm, Vector3 derivative_wrt_u)`.
  The derivative is the actual path derivative, not an assumed unit-speed field.
- The caller keeps this object stable until `analyze` returns. The returned
  evidence retains no reference to the solver/path object.

Targets expose `name`, `start`, `end`, `start_tangent`, `end_tangent`,
`start_width`, `end_width`, `lines`, `diameter_mm`. Points are in mm, tangent
and width axes are perpendicular unit vectors, and conductor order is explicit.
`Targets.capture` validates/copies these fields. A forward-authored fixture's
target poses are fixture outputs, not an independently solved boundary challenge.
The development tool currently supports 1–128 conductors and 16–1024 analysis
intervals; these workload bounds do not classify larger ribbons as infeasible.

The interface describes the current developable material-field model. Do not
adapt an unrelated curve by inventing `eta_s` merely to obtain a clean display.
Use the lower-level `Series`/`regions` API for separately measured data, or adapt
actual cubic conductor paths through `traces.TracePath` and `tubes.inspect_trace`.

## Meaning of the evidence

`Evidence` stores ID/source, copied targets, primary metric, immutable sampled
`Series`, `Region` intervals, three frozen cubic guides, stage timings and a
content fingerprint. The source token is supplied by the caller; the content
fingerprint does not certify that token's source code or physical model.
Freeze source fingerprints separately with `provenance.source_fingerprints()`.
Loaded module stamps detect on-disk edits before reusing a cached Fusion runtime.

`inspect` returns the same interval records shown in Fusion, plus min/max
stations even for clean baselines, missing-sample counts and interpretation.
`trace_number=-1` is A boundary, `-2` B boundary, `0` center; positive IDs are
ordered conductors. Region entry/exit brackets are adjacent sample intervals,
not exact roots or a continuous certificate. Missing data splits regions.

Current inherited prototype metrics:

| Metric | Red condition | Amber display margin |
|---|---|---|
| Center macaroni | `abs(k) * hypot(half_width, diameter/2) > 0.8` | within 0.08 below limit |
| Material map | `J = 1 + q*eta_s <= 0` | `0 < J <= 0.1` |
| Regular lane curvature | `3*diameter*abs(k)/J > 1`, only while `J > 1e-9` | within 0.1 below limit |

These are the inherited model/policy checks, not calibrated universal laws.
Nonpositive/tiny J makes the lane-curvature formula unavailable; missing values
do not become passes. Amber margins aid display and never relax hard limits.
The proposed full-width bound at both boundary curves remains a separate
diagnostic, not an adopted rule. Tube checks also retain sampled fixed-target
errors and the historical five-width sphere policy. Keep metric scopes distinct.

`edge_metrics.boundary_macaroni(path, intervals=512)` optionally returns two frozen
`proposed edge macaroni` series (`-1` A, `-2` B). Append these and their
`regions.regions(series)` before `api.freeze` to share extra boundary witnesses.
The same original profile reach and proposed 0.8 limit are used at both edges;
this is a stronger diagnostic hypothesis, not an adopted physical law. J<=1e-9
produces missing curvature. Keep material-J findings visible. Existing primary
graphs remain center macaroni or material J; label optional edge witnesses and
their separate scope explicitly.

## Fusion view

```python
from devtools.ribbon_analysis.viewer import Viewer, ViewLimits

view = Viewer(
    owned_component, active_document,
    ViewLimits(max_candidates=2, seconds_per_candidate=10, total_seconds=30),
)
result = view.add(candidate)  # analyzes once, freezes, then draws
evidence = view.evidence(candidate.identifier)
data = evidence.inspect(kind="material J", trace_number=1)
view.show(candidate.identifier, sheet=True, graphs=True)
# Reveal the retained original route sketches independently of the sheet:
view.show(candidate.identifier, sheet=False, graphs=False, originals=True)
# Reveal a single constraint component without recomputing the result:
view.show(candidate.identifier, constraints=("center_bend",))
constraint_data = view.constraints(candidate.identifier)
```

Create/choose `owned_component` under the authorized scratch explicitly. The
viewer never searches by document name, looks up historical experiment globals,
hides unrelated roots, runs the solver, or builds native solids. An optional
Fusion transform passed to `add` places a candidate without moving its inputs.
For evidence already analyzed, `region_graphics.draw_evidence(component, evidence)`
renders without evaluating the original path again; bound this external call.
Every result automatically retains three separately named native fixed-spline
sketches under its component: Original A boundary, Original Center trajectory and
Original B boundary. They start hidden and can be unhidden in Fusion's Sketches
folder. These reproduce the frozen measured cubics, including failed endpoints;
closure-gap witnesses never become part of them. They are cubic approximations
of the solved model, not a claim about native swept conductor geometry.

`original_guides.retain_guides(component, evidence, checkpoint)` adds these to an
older result without rerunning analysis or redrawing its diagnostics. Provenance
stamps reuse completed sketches without changing user visibility; partial native
failures remain and require review. The returned `original_guides` maps permanent
trace IDs (-1 A, 0 center, -2 B) to sketches. `original_guide_seconds` and
`original_guide_maximum_error_mm` report authoring time and native point checks
against the frozen cubics. Viewer records retain these alongside graphics timings.
Optional checkpoints passed to `draw_evidence` bound each native guide operation.
`Viewer.show(..., originals=None)` preserves manual original-sketch visibility;
explicit True/False toggles all three for the selected results.

New gym drafts and diagnostic method components retain two native closed sketches:
`Sweep profile - Start cap` and `Sweep profile - End cap`. They use the unchanged
joined-profile builder at the fixed target positions, tangents and width frames.
Unhide a profile and the original center guide to use them as manual sweep inputs.
Each cap is one joined region, including multi-conductor layouts. Profiles are
initially hidden; reuse preserves manual visibility. Failed routes retain their
actual guides and their separate fixed target profiles, without closure repairs.
The profiles alone do not establish a sweep result or physical compliance.

Custom layout displays should call
`end_profiles.retain_end_profiles(owned_component, targets, checkpoint)` explicitly.
It returns `{"start": sketch, "end": sketch}`; repeated calls reuse a complete
matching pair. Different targets require a separate owned layout component;
incomplete, missing or duplicated native inputs stop for review. Gym drafts replace
their owned profile component when inputs change; diagnostic caps remain outside
the disposable proposal scene. No solid is created automatically.

Each result also contains five hidden child components named `Constraint - ...`
and an initially visible `Solver details` sketch directly inside the experiment's Sketches
folder. Unhide a helper with its component/sketch eye, or use `Viewer.show(constraints=...)`.
An empty tuple hides all; None preserves manual visibility. The keys are:

| Key | Geometry and measured scope |
| --- | --- |
| `containment` | Three sphere rings and the worst retained occupied-point witness, including a thickness allowance. |
| `center_bend` | Minimum radius from the center macaroni limit, actual sampled radius, and projected material-width direction. |
| `lane_bend` | Minimum 3D radius and actual radius at the worst sampled A/B boundary witness; not an all-conductor audit. |
| `material_progress` | Normalized forward-advance segments at the worst retained boundary J; unavailable scalar samples stay unmeasured. |
| `targets` | Fixed terminal width/tangent axes and an explicitly labeled center gap; no connector-body obstacle is invented. |
| `solver_limits` | Native gauge lines and text in the experiment's Solver details sketch, with caller-declared coordinate/work bounds distinct from physical geometry rules. |

Descriptions occupy separate titled slots beside each route so several helpers
can be unhidden together. `constraint_geometry.layout` repositions labels and
abstract solver bars without remeasuring or moving physical witnesses. Native
solver text boxes reserve enough width for one line per caption.

Red bend circles show minimum radius; blue shows actual radius. Green indicates
width/target axes. Circles lie in their real bend planes and may appear edge-on
until the view is rotated. Very large actual circles are omitted but retain their
numerical radius. All circles are 64-chord display glyphs. They draw through the
diagnostic sheet to remain visible; they are not cable geometry.

`constraint_geometry.Restriction(name, value, lower, upper, source)` captures an
explicit frozen solver bound. Pass a tuple through `Viewer.add(..., restrictions=)`
or `draw_evidence(..., restrictions=)`. Omitted metadata is labeled unavailable.
`constraint_views.retain_constraints` adds overlays to an older Evidence/component
pair without fitting. Returned `constraint_evidence`, `constraint_fingerprint` and
`constraint_seconds` retain the same immutable measurements/geometry, digest and
creation time the agent reads. `Viewer.constraints(id)` exposes these snapshots.
`solver_details.retain_solver_details` retains the solver panel directly as a
visible native sketch; its attributes keep the full frozen overlay/source snapshot.
It reuses complete matching sketches without changing manual visibility and stops
on incomplete authoring. Other helper components are unaffected.
Visibility changes do not rebuild them. No constraint is relaxed by showing it.
Adapters that supply individual coordinate-value or trial panels also show them
by default. Reuse preserves manual visibility, including a user's choice to hide
the solver sketch or value panel after creation.
Local margin or a coordinate at its bound does not establish causal responsibility
for a failed solve; that requires a controlled counterfactual experiment.

The material sheet has no thickness. It can overlap in an invalid map and is
not a valid conductor sweep. Colored cells include neighboring crossing brackets;
compressed folded regions can occupy little visible space. Use region ticks and
the metric graph together. `tubes.tube_mesh` separately provides circular tube
approximations from actual cubics; it rejects opposed mesh tangents rather than
inventing a valid tube. It is not a physical simulation or kernel predictor.

`Viewer.records` retains attempted/failed stages, timings, evidence, graphics
handles and RSS samples. Invalid model regions are completed diagnostics;
API/source/resource errors latch a stop. Review before renewing; never silently
restart the old viewer or erase its ledger. Read-only evidence inspection remains
available after a stop or source edit. Future rendering needs a coherent runtime.

The numerical evidence contains no native-construction/compliance acceptance.
No contact, equilibrium, strain, bonded insulation, ending, containment or
continuous-native audit is implied by the sheet view. Report missing coverage.

### Experimental fold construction policy

`experiment_ribbon_fold_route.solver.connect` and `construct_candidate` accept
`construction=ConstructionPolicy.RIGID_PERPENDICULAR` for an explicitly declared
ordinary-sweep trial. `MATERIAL_FOLD` remains the existing reference default.
This setting is independent of `FoldStrategy` and the material macaroni limit.
For spatial routing it encloses the unchanged joined profile's bounding rectangle
in a disk and requires cylinder radius `rho / utilization * (1 + 1e-9)`.
Since center curvature is at most `1/R`, any rigid transported orientation then
has local Jacobian at least `1-rho/R`. Straight and aligned planar solutions retain
their original tight radius. The disk bound is sufficient and conservative;
it does not find the smallest buildable radius or certify native interpolation.

Retain material compatibility/contact checks and separately measure native outcome,
terminal roll, banking and material lengths. A larger radius does not make an
ordinary rigid sweep equal to the isometric material fold. No new rule tolerance,
native builder/profile change, seed discovery or production promotion follows.
The first one-case native trial and its remaining roll failure are recorded in
[construction evidence](pinch.md#rigid-sweep-construction-policy-trial).

For measured local limits, `sweep_transport.inspect_sweep` uses actual circular
profile support and exact helix parallel transport instead of the enclosing disk.
`sweep_profile.joined_profile_arcs` supplies the unchanged contour analytically.
An explicit `minimum_radius_mm` on `connect`/`construct_candidate` supports a
dimensional boundary study without weakening the material rule. Report the local
J boundary, construction margin and native outcome separately; kernel build alone
can accept a modeled negative-J probe. See [actual limits and ratio tests](sweep-limits.md).

The user subsequently clarifies that native output must reproduce the material
plan directly; current fidelity checks are development/regression verification,
not routine per-sweep repair or post-processing.204..206find a centerline match
but large ordered edge errors and a179.318545degree arrival reversal, hidden by
the old modulo180axis measurement. Verify actual three-path correspondence and
retain identity before applying planned macaroni results to a native solid. Do
not tune material rules to compensate for a different construction representation.
See [trajectory fidelity and retained evidence](trajectory-fidelity.md).

Geometry fidelity is now the immediate investigation priority. For experimental
direct construction, `material_profile.material_profile(lines, diameter_mm)` returns
the unchanged joined circular contour in clockwise material order, with the side
caps split at their outer tips. `material_surfaces.material_patches(pieces, profile)`
translates a frozen material plan into surface controls with positional bounds.
The Fusion-only `material_native.define_material_body(pieces, patches, checkpoint)`
returns a closed BRep definition and face provenance; one explicit `createBody()`
constructs the whole ribbon. No production builder or diagnostic discovery method
is switched by importing these helpers.211..213verify one complete gym specimen's
sampled surfaces, three ordered guides, cap frames and seam chains. Different gym
layouts and complete physical compliance remain unmeasured.
