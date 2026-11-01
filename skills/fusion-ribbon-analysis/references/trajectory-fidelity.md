# Material plan to native geometry fidelity

The user's clarified contract is that output geometry reproduces planned material
geometry directly. Left/center/right trajectories, profile dimensions, ordered
side/conductor identity and prescribed frames remain authoritative. The tightest
left/right macaroni utilization governs; equality is a measured special case.
A centerline plus whole-profile regularity check does not replace those checks.

These inspections are development/functionality and regression verification.
They are not a requirement for expensive checks on every production sweep, nor
permission to repair, relabel or post-process a different output into acceptance.
When construction differs from the material plan, correct the plan-to-solid
translation before tuning material bend limits to accommodate the different shape.
Do not use199..203's rigid-sweep radius ratios as validated material-plan minima.
Geometry fidelity now takes priority over solver-rule tuning. An experimental
direct material constructor is implemented; production builders remain unchanged.

## Direct material construction: first development result

`experiments/experiment_ribbon_fold_route/material_profile.py`,
`material_surfaces.py` and `material_native.py` build one joined body from the
prescribed material map. They retain the original circular joined contour and
fixed caps. Planar leads use exact ruled surfaces; folds use tensor-product NURBS
with rational circular profile coordinates and cubic Hermite phase interpolation.
The current specimen's conservative positional representation bound is
4.231e-9mm. This is a geometric approximation bound, not a continuous curvature,
contact or physical-compliance certificate. No centre-only sweep, route fitting,
radius relaxation, side relabeling or corrective processing is used.

211rebuilds unchanged202case4 (N3,D1.5,R1.805685915mm,L101.834898632mm): one complete
gym configuration evaluated/attempted/built, one retained positive solid,
620.203830261mm3. Definition0.616s, kernel0.745s, total2.160s; these are replayed
construction timings, not a new endpoint solve. Full healing is disabled, although
Fusion still reports analytic surface simplification. All200surface faces and two
caps remain distinct. Cap sketches and three original native guides are retained.
214displays a copy of the actual native BRep with the original guides, not a
reference envelope; the individual native body remains hidden.215positions its
caption. The failed203sweep remains intact and hidden.

212checks7000corresponding native points over all200surface faces: no point
failures, maximum3.270e-9mm. Its exact-one-edge seam assertion failed48times on
native edge subdivisions; that failed audit is preserved.213replaces the edge
count assertion with a connected, nonbranching shared-edge chain and both planned
endpoints:390/390checks pass, including eight explicitly collapsed material-tip
lead seams. Ordered face families remain fixed; no nearest-side reassignment.
Maximum sampled left/center/right errors are1.568e-9/2.124e-9/1.783e-9mm; maximum
sampled tangent error6.720e-8degrees. Both caps match ordered width and outward
normal (arrival width error2.249e-14degrees); cap center gaps<=1.894e-9mm.
The body revision is unchanged through these read-only checks.

Earlier run failures remain:208API rational/open flag error before a full body
attempt;209built but an exclusive-output recorder error caused transaction
rollback;210could not audit the absent body.211uses identical geometry with a
corrected recorder. Across these runs: one complete configuration, two kernel
attempts/two transient builds, one retained body.213passes named fidelity checks;
complete physical compliance and diverse gym-layout reliability remain unmeasured.
No native collateral or untouched holdout cases have been evaluated for this new
constructor.46focused numerical tests cover contour/map translation at1/3/6
conductors andD.75/1.5/3mm with both fold senses; these are unit checks, not46native
ribbons. Native source/evidence is under `artifacts/verification/ribbon_material208`
through215. Executed source copies accompany later IDE-only archive annotations.
The sole later profile change corrects the two reflected left-cap segment labels;
coordinates/weights are unchanged.211retains the original source with its exact
plan hash as `material_profile.executed.py.txt`.

Focused verification:46material-surface unit checks pass; scoped Ruff lint/format
and IDE inspections pass on the new implementation, tests and recorded adapters.
Executed sources remain byte-exact beside archive-only annotations/import sorting;
208..213source pins were verified against those copies and retained pre-priority
rules. Recorded RSS samples peak at698400KiB against the4GiB ceiling; in-flight
peak and209's final RSS samples are unavailable after its recorder error. No
repository-wide QA, native dimension matrix or different-layout collateral/holdout
validation has run for the new constructor. These remain required evidence before
any generalized reliability or production claim.

## Different-layout fidelity after resumption — 2026-11-01

User authorized fidelity item1; macaroni-limit item2 remains for direct collaboration.
216..221retain four independent development configurations: unchanged211calibration
and three gym layouts frozen before routing, seeds20261101/2/3, N1D.75/N3D1.5/N6D3.
Different zone/face/roll selections are not a factorial dimension study or holdouts.
One unchanged CONTINUOUS algebraic material candidate per new layout, default
material radius, existing contact gate; no retired discovery or radius study.
Four native attempts/four retained positive solids; no geometry retries or builder,
profile, target, rule or production changes. Final uniform221checks pass4/4:
30,520surface samples,1,702ordered seam chains, three material guides and both caps.
Maximum sampled surface/guide errors6.824e-9/2.414e-9mm; tangent6.956e-8degrees.

Preserve two instrument stops.216gym1has eight rejected UVmembership queries on
triangular tip faces.217directUV also rejects;218same prescribed face proxies give
distance<=1.8e-11mm, solid pointOn and exactly matching NURBS controls/knots/weights.
219adds at most64same-face corroborations per case at unchanged1e-6mm/.001degree
thresholds; no nearest-other-face fallback.219gym3then stops on three derived guide
samples just below zero(-2.47e-17/-4.36e-17).221records raw fractions and measures
those endpoint-roundoff probes at zero, rejecting excursions beyond1e-14. All four
existing bodies pass the same renewed audit with unchanged revisions; neither
instrument failure was resolved by rebuilding, relabeling or repairing geometry.

220displays actual native BRep copies and original guides for the three new layouts
using rigid display translations only. Bodies stay individually hidden, with both
native cap sketches and three original guides retained. Existing211/203remain.
Sampled RSS max528496KiB; in-flight peak unmeasured. Stage budgets/source pins held.
46focused material-surface tests, scoped Ruff and IDE inspections pass; fullQA unrun.
Final report/measurements/sourceZIP: `artifacts/verification/ribbon_fidelity221/`;
earlier216..220outcomes remain. Four named fidelity passes are not continuous
curvature/contact/strain certification:0fully accepted physical cables. No further
builds or automatic item2work are scheduled.

## Existing triple sweep inspection

204examines one existing gym-created203N3D1.5solid, source202case4. It performs
29transient plane intersections at eight fold middles and one critical station,
including nearby samples for finite-difference tangents. Two terminal caps are
measured directly. Original native guide sketches match their frozen material
source within1e-6mm. Native side-cap arc-length midpoints identify the actual
profile extremities, with native midpoint/width/arc consistency checked to1e-4mm.
That is an instrument consistency threshold, not an invented trajectory tolerance.
Each section requires one unique centered contour; no nearest-other-leg fallback.

At matching center material stations, maximum sampled position errors are:

|Trajectory|Native-to-planned position error|
|---|---:|
|Left|4.799915125mm|
|Center|3.162009205e-8mm|
|Right|4.799915125mm|

Sampled edge tangent differences reach37.2445degrees. Center finite-difference
error reaches0.08921degrees at the critical sample; halving its step changes that
estimate0.04460degrees, so do not call this a precise native tangent certificate.
The remaining fold-middle center estimates are<=0.000215degrees. Position evidence
and the independently verified terminal identity failure establish the mismatch
without relying on these finite-difference tangent extrema.

205verifies native face topology: the body has10faces; native longitudinal side
face34 joins the departure-left arc to the opposite signed arrival side, and
face35 does the converse. Ordered width error is179.318544571degrees. The earlier
0.681455degree number was an unsigned axis comparison modulo180 and concealed
ordered-side reversal on the symmetric contour. Preserve that historical number,
but do not describe it as the complete frame/identity error or accept swapped sides.
This is prescribed-frame fidelity, not reinstatement of a total-roll cap.

205then stops at its first interior membership call because MeasureManager rejects
the component-native BRepFace argument;29section membership checks are unattempted
there. After application-log review,206records a renewal using each native face's
own parameter evaluator plus trimmed-face membership. All29section labels are
corroborated by58point checks, maximum surface residual4.213e-9mm. No labels change.
The terminal reversal and204's ordered position errors therefore do not depend
solely on the modeled parallel-transport frame used initially to label landmarks.

The rigid sweep is driven by the center guide and does not reproduce the two
material-fold edge guides. The material fold has curved transverse sections;
its corresponding material stations need not be perpendicular planar sections.
A single native section check or a successful solid build does not bridge these
representations. Construction control/representation must be resolved before
claiming planned three-path macaroni or material compliance on the built solid.
Explicit three-path acceptance is pending this fidelity gate; no rule was relaxed.

One existing configuration examined,0new solves/sweeps/solids,0fully accepted
physical cables. Body revision remains identical throughout the inspection.
204takes10.878841s,205stops at0.412751s,206takes2.368430s. Limits90s/29cuts for204,
45s/512face-query bounds for205/206,4GiB RSS/3.8GiB launch headroom held; in-flight
peaks are unmeasured. Plans, all section/station results, native IDs, retained API
stop and renewal are under artifacts/verification/ribbon_trajectory204..206.
No new native build, solver/profile change or batch follows from this inspection.

207corrects only the current203triple caption to report trajectory mismatch,
4.800mm ordered edge gap and179.319degree ordered arrival error; original caption
and body revision are retained. Geometry/camera/profile sketches are unchanged.
Scoped inspection-harness Ruff lint/format and IDE diagnostics pass.205/206's
post-execution duplicate-code annotations leave byte-exact executed source copies
beside their reports. Application tests/fullQA were not run for read-only native
inspection, labeling and documentation; earlier solver checks remain separate.
