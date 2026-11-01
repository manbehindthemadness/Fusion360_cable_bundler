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

## Texture continuity gate — 2026-11-01

Geometry fidelity does not establish appearance UV continuity. User requested
investigation before extending this method.222..226test native Automatic mapping
on appearance-only copies of all four221material bodies plus the ordinary203
sweep of the calibration plan. Same asymmetric diagnostic texture/settings; no
new routes, geometry builds, profile/rule changes or production integration.

All four direct bodies fail the named default-UV continuity gate. Across830/830
longitudinal face joins,4,880matched display-mesh nodes expose nonmatching UVs;
native captures corroborate texture phase/direction resets.226independently
confirms that every measured pair shares native edges and all five originals'
revisions are unchanged. Raw UV jumps use1e-6UVunits as a diagnostic reporting
floor, not a physical tolerance. The ordinary sweep has eight continuous side
faces along its path, so it has no equivalent internal longitudinal face joins;
zero comparator seams is inapplicable, not a complete texture acceptance claim.

Live2706.1.17 exposes projected Automatic/Planar/Box/Cylindrical/Spherical and3D
mapping controls. Rendered `TriangleMesh.textureCoordinates` is read-only. No
supported arbitrary per-BRep-face UV assignment was found in the examined API;
this does not prove all material-aware parameterization/baking strategies
impossible. Mathematical material coordinates are not automatically renderer UVs.
Neither alternative is implemented or validated for generic color/normal/roughness
maps, save/reopen, regeneration or export. Hold adoption as a sweep replacement
where seamless material-following texture mapping is required; flat per-conductor
color assignment is a separate capability.

223stopped at Automatic setter InternalValidationError after one native copy;
224confirmed the default mapping but stopped at nested occurrence placement.
Both precede UV measurements.225reuses that copy, adds four others, avoids the
mapping setter and moves only the root diagnostic occurrence. Failures remain.
Five copies stay under `223 - Native texture continuity - fixed body copies`,
translated100cm for display; direct calibration visible, other four hidden.
Original geometry/visibility remains intact.225takes27.227s, all measured Fusion
stages30.223s; RSSmax964576KiB, in-flight peak unmeasured. Scoped Ruff/IDE checks
pass; no app tests/fullQA because no application or constructor changes occurred.
Report/source archive: `artifacts/verification/ribbon_texture226/`; native captures
and raw seam records: `artifacts/verification/ribbon_texture225/`. Prior geometry
fidelity remains separate and valid; no new physical or item2limit acceptance.

## Build-time parameter investigation — 2026-11-01

227..229use one unchanged calibration configuration, three native attempts,
three returned positive solids, two completed geometry audits and zero accepted
seamless texture solutions. No new solve or limit tuning; production is unchanged.

227assigns positive affine U/V domain stamps to all200side surfaces before
`createBody`, preserving controls, weights and physical edges.48faces remain
NURBS and retain the supplied domains; their actual rendered UV offsets change.
The other152faces become40tori and112cylinders, losing the caller domains.
The named7000point/ordered-seam/three-guide/cap audit passes. This proves partial
build-time influence, not supported arbitrary renderer-UV assignment. Automatic
mapping normalizes physical scale; domain scaling alone is not a seamless atlas.

228multiplies the rational numerator and denominator by the same positive linear
factor, preserving exact shape and parameterization with a higher profile degree.
Fusion still produces the same48/152NURBS/analytic split. Geometry audit passes;
the representation change does not prevent simplification or resolve texture joins.

229concatenates existing spans into ten longitudinal NURBS skins, retaining the
original boundary edge chains.4000transient correspondence samples agree within
1.547e-14mm. Native construction takes56.656s and returns92faces rather than the
expected12; outcomeInfo includes `illegal surface detected, healing failed` and
analytic simplification. Its positive volume is620.197359537mm3, differing from
the original620.203830261mm3. The topology guard stops before any native surface,
guide, cap or texture audit. This is a failed construction candidate despite
returning a solid, not proof of preserved geometry or continuous charts. It remains
hidden under `229 - Continuous native material skins`; no retry or breadth batch.
Total229Fusion work78.640s.227/228take50.539s/71.080s respectively; these include
preflight and audits, not end-to-end solve timings. In-flight memory peak unmeasured.

The original four221geometry-fidelity results remain separate. Keep the texture
adoption hold. Per-face material-coordinate texture baking is an unvalidated
alternative, not a native UV fix or an implemented resolution. Reports, pinned
sources and failed evidence are retained in `artifacts/verification/ribbon_texture227/`
through `ribbon_texture229/`. Scoped Ruff and IDE inspections pass on229's four
artifact scripts; no production/app change or full QA run occurred.

## Per-face texture bake: first development result — 2026-11-01

User authorized trying face-specific images after the build-time-domain trials.
230..238test one unchanged calibration configuration: one appearance-only copy,
zero solves or geometry construction attempts, one completed named appearance
audit. No additional independent configurations or full physical acceptance.

The final200side-face PNGs encode global material progress s, ordered width q,
and an asymmetric3mm directional pattern. Each BRep face receives one128x128image
with a four-texel filtering gutter. Triangles interpolate within each face's image;
they do not receive separate images. The actual Automatic-mapping display charts
remain unchanged, including native analytic faces. Coordinate compensation happens
in the images and appearance scale/offset controls, not writable BRep/mesh UVs.

233exports23,636side-face display nodes in6.164s.235analytically inverts the frozen
piece map and independently reconstructs every point against the original material
evaluator/profile: maximum reconstruction1.111e-6mm, circular-profile radial
residual1.384e-6mm. These measure float32 display coordinates, not a new relaxation
of native geometry fidelity.230nodes have q roundoff outside exact width; validation
sample clipping is bounded by1e-5mm after measuring the maximum1.011e-6mm overrun.
Original q remains in the baked material coordinates. Across190longitudinal joins/
1,038matched nodes, material-s disagreement<=8.962e-7mm and q<=5.583e-7mm.

235bakes200PNGs in9.941s.236assigns200document-owned appearances in12.920s and
captures native overview/five closeups; complete236work19.021s.237independently
reads every assigned image by hash, exact scale/offset settings and all actual
mesh coordinates/UVs/triangles against233. All200checks pass; original revision,
copied revision and volume are unchanged.237takes9.732s including captures.
The native captures visibly carry the gradient/pattern through face boundaries.

238decodes the actual PNG files and samples them bilinearly at2,122matched nodes
across382/382actual native side-face adjacencies.382excludes the eight explicitly
collapsed seams counted by the earlier390topological checks. Maximum progress/
width gradient disagreement is1/255color step. The finer blue directional pattern
has up to26/255difference: coarse resolution/interpolation/filtering remains an
observed seam defect. No claim of pixel-perfect arbitrary-texture continuity.
27synthetic inverse checks and an independent raster midpoint check pass; these
are algorithm checks, not27ribbon configurations or a physical-compliance audit.

Preserve setup failures:230FloatProperty.units getter InternalValidationError;
231transient surface-inverse correspondence residual;232read-only diagnosis finds
original/copy face IDs/points/local mesh coordinates agree;234strict material-width
evaluator rejects float32 endpoint roundoff before rasterization.235records the
measured roundoff handling before its renewed bake. No geometry repair or rebuild.

Only color-pattern baking on this development calibration is demonstrated.
End caps, arbitrary source imagery, normal/roughness maps, save/reopen, regeneration,
export, resolution/filtering policy and the three existing gym collateral layouts
remain untested. Keep production unchanged and retain the texture adoption hold
pending those checks. This is a viable compensation prototype, not shared native
UV preservation. The copy stays visible under `230 - Per-face baked material texture`,
translated100cm;237leaves a shaded overview. Original geometry is unchanged.
Plans, failures, PNGs and sources remain under `artifacts/verification/ribbon_texture230/`
through238. Final235..238Ruff/IDE checks pass; no app tests/fullQA were needed for
this artifact-only prototype. Native capture:237/baked-overview-shaded.png.

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
