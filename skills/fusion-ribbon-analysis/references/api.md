# Candidate and evidence API

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
