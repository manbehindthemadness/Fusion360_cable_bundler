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

## Optional appearance requirement and deferred workflow — 2026-11-01

The user accepts the prototype's endcap mismatch and visual side-face result.
Detailed appearance work is an optional, infrequent operation. It must not become
a mandatory geometry-generation cost. Record these timing categories separately:

- Geometry generation includes the required material-surface translation, BRep
  definition, native construction and insertion. Do not call kernel time alone
  the full generation time or silently exclude required geometry preparation.
- Optional appearance preparation includes source-map extraction, native display
  chart collection, material-coordinate evaluation, rasterization and image I/O.
- Optional appearance assignment includes document appearance creation/copying,
  connecting the generated maps and assigning them to their corresponding faces.
- Development checks, screenshots, archiving and orchestration have separate
  timings. Retain total elapsed time when those operations actually execute.

The earlier approximately29s is the prototype's optional chart/bake/assignment
workflow, not a new geometry-generation measurement. Excluding it changes the
reported scope; it does not constitute an optimization or measured speedup.
No production counter or generation pipeline was changed by recording this policy.

### What exists independently of a texture

The frozen material plan defines material progress s and ordered profile position
q, plus thickness/profile coordinates. These can be evaluated without images,
appearance objects or physical-material assignment. They are not the renderer's
UVs. The current successful method does not install arbitrary custom UVs into
Fusion's BRep. Fusion still owns its actual per-face display texture coordinates.

A useful native body therefore can exist first. A later explicit appearance
operation can read its display charts, evaluate the retained material map and
generate an image adapted to each face. There is one image per bounded BRep face,
including analytic faces; mesh triangles are interpolation cells within it.
This is a texture-specific compensation operation. Applying a different ordinary
Fusion appearance afterward does not automatically inherit corrected native UVs.

Retain the construction's fixed plan, conductor/order identity and face-family
provenance so that later sampling has an authoritative material correspondence.
Do not identify a conductor by whichever face is nearest. Experimental face
indices are guarded against the exact body revision and topology; they are not
persistent IDs that can be reused blindly after regeneration. Production would
need durable associations to the existing conductor and routing identities.

### Appearance classes and support boundary

| Appearance class | Proposed later operation | Evidence boundary |
| --- | --- | --- |
| Plain exterior color | Assign a color appearance directly; no image bake | Initial untextured copies and color read-back are tested |
| Image-backed opaque base color | Read source bitmap and supported placement settings; bake face images when requested | Experimental supported subset; see trial outcomes below |
| Roughness or scalar masks | Remap their source maps through the same material mapping | Separate channel validation required; color-only evidence is insufficient |
| Tangent-space normal/bump maps | Remap and, where necessary, transform the normal/tangent basis | Not validated by copying a normal-map filename or color rasterization |
| Native procedural wood/noise/checker shaders | Need an evaluator/exporter or a separately implemented generator | No generic shader-sampling/bake API found; not established as supported |
| Layered, transparent or other complex shaders | Need explicit per-shader/channel support | Not covered by an opaque base-color image proof |

Native library names alone do not indicate a simple image appearance.239finds
Fabric with albedo/specular-related channels and an unknown normal texture, Oak
with separate color and roughness images, and Carbon Fiber with layered maps.
The breadth trial extracts Fabric's base-color bitmap into a generic opaque
Fusion appearance with fixed roughness0.47. It does not reproduce the complete
library Fabric shader. That distinction must remain visible in reliability claims.

The implemented experimental source subset is opaque RGB/RGBA8 noninterlaced PNG,
positive finite physical tile dimensions, zero source offset/rotation and both
repeat modes on. Nonopaque alpha, unsupported PNG formats, unknown/procedural
texture types and unvalidated source transforms reject explicitly. This is a
bounded experiment contract, not a promise that all appearance classes work.

### Later selection, cache invalidation and persistence

An intended application flow is: create geometry and its provenance; leave
ordinary colors available; on an explicit textured-appearance request, inspect
the source, validate supported channels/settings, collect native charts and bake;
then apply document-owned appearance copies. Unsupported sources must leave a
clear unsupported outcome rather than silently flattening or substituting them.
No automatic production UI or drag-and-drop interception is implemented here.

Cache identity must include source image content, source mapping settings, the
retained material plan, body revision/topology, actual renderer charts, resolution
and the mapping/raster algorithm version. An appearance name or local image path
alone is inadequate. Replacing bytes at the same path or selecting another source
must invalidate the generated images. Geometry regeneration requires correspondence
validation and fresh charts; a matching face count is not sufficient.

The live getter can return a library-relative image path such as
`1/Mats/fabric_wire_grey.png`;240records this behavior. Resolve it only against an
explicit known library asset root, check containment/readability and fingerprint
the actual file. Do not guess a file in the working directory. Paths may also
change after an archive import. Imported image bytes and face associations need
checking independently of whether the source filename still looks familiar.

Archive testing must distinguish embedded-image survival from an in-memory render
cache. Export an owned component, make its external baked paths unavailable,
reimport into an owned target and read the imported image data/face associations.
Restore temporarily renamed experiment files on every exit. A same-session archive
test is not a cold Fusion restart, generic export test or regeneration proof.

### Reliability experiments and retained failures

The maintained experimental entry points are
`experiments/experiment_optional_appearance/{runner,bake,persistence_split}.py`;
they are separate from production construction and ordinary test collection.
The retained inputs are unchanged221calibration plus gym-1/2/3, with conductor
count/diameter N3/D1.5, N1/D0.75, N3/D1.5 and N6/D3 respectively. These are four
examined development configurations, not unseen holdouts or new route solutions.
All geometry, caps, solver rules and conductor ordering remain fixed.

240prepares all four plain-colored copies before selecting the image source and
exports their actual charts.241bakes calibration but stops on gym-1 before its
completion; gym-2/3are unattempted in that run.242diagnoses a periodic-phase branch
mistake: a slightly negative entry angle was wrapped to the opposite fold end.
243uses nearest-interval phase unwrapping, passes calibration/gym-1/gym-2and stops
at gym-3's strict material-coordinate audit.244retains the16failed adjacency rows;
maximum material disagreement is4.407e-4mm at float display samples.

245adds an interpretation for actual mesh-boundary nodes that agree with an
authored crease plane, circular profile arc and ordered arc extent within the
float32 positional uncertainty. It supplies the known entry/exit phase rather than
inverting an almost collapsed inner radius. No body point, UV, target, geometry
limit or correspondence tolerance is changed. All four numerical preflights pass
the same1e-4mm material-coordinate gate, maxima8.735e-7/2.386e-7/7.309e-7/2.679e-6mm.
245uses constant placeholder pixels to isolate coordinate checks; it is explicitly
not a texture bake or visual acceptance result. Preserve241/243rather than replacing
their failure classifications with the later result.

246then bakes the actual Grey Fabric source image on all four layouts.247checks
every installed image by content hash, all native bitmap transform settings,
roughness0.47and unchanged display points/UVs/triangles and geometry.248repeats the
same algorithm with the native Light Brown Fabric base-color image;249applies and
checks that replacement. Both variants pass the named mapping/data-assignment
checks on4/4configurations. All872generated images and all four content-bound
cache identities change for the replacement. This verifies explicit source-image
selection/replacement, not automatic propagation from arbitrary material edits.

| Configuration | Side faces | Actual side adjacencies / sampled | Matched nodes | Maximum material disagreement, mm | Grey source: mean / max RGB disagreement, 0–255 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Calibration N3/D1.5 | 200 | 382 / 382 | 2,122 | 8.735e-7 | 6.57 / 43.50 |
| Gym-1 N1/D0.75 | 126 | 238 / 238 | 1,300 | 2.386e-7 | 2.30 / 25.00 |
| Gym-2 N3/D1.5 | 210 | 402 / 402 | 2,212 | 7.309e-7 | 4.97 / 36.07 |
| Gym-3 N6/D3 | 336 | 648 / 648 | 3,439 | 2.679e-6 | 11.67 / 97.50 |

The RGB values come from bilinear samples of the actual saved PNGs at shared
display nodes, not a renderer shader evaluation. Fine source-image detail exposes
substantial128x128sampling/interpolation/gutter differences despite correct material
correspondence. Brown-image mean/max values are8.86/63.50,2.54/26.00,6.87/62.00and
14.21/90.69respectively. This is a known quality limitation, not seamless or
pixel-perfect general image reproduction. A validated resolution/antialiasing/
filtering policy remains necessary for demanding textures. Do not infer full
Fabric-shader, color-management or normal-map fidelity from these results.

### Archive outcome and transaction boundary

250exports/imports the calibration component while its external generated PNG
directory is temporarily unavailable, but stops after21verified faces because
some imported image paths are not yet readable.251later reads them successfully.
252adds a bounded10s event-pumped wait: calibration verifies200/200images, then
gym-1stops waiting for two resources; gym-2/3remain unattempted.253again finds those
resources readable on a later call. Retain both failed persistence procedures.

254changes the verification schedule: export, import and verify use separate MCP
calls, so import commits before verification. For each case, both its original
baked-image directory and the archive's export-sidecar directory remain renamed
and unavailable throughout import, commit and verification. They are restored by
the controller's `finally` block on every exit. Every side-face image is then
readable and byte-identical:200/126/210/336verified,4/4archives pass. Persistent
face attributes preserve correspondence; stored source points evaluate on their
corresponding imported faces within1e-6mm, with matching face counts and volume.
This supports a post-import transaction/resource-readiness dependency; it is not
proof that every missing texture anywhere in Fusion has that cause.

254takes52.992s for four component archives, imports and checks. It opens/closes
no documents, saves nothing to the cloud and leaves the imported diagnostic copies
hidden in the same owned design. Original source PNGs and sidecars are restored.
This is warm-session component archive evidence, not a cold application restart,
arbitrary export-format guarantee or geometry regeneration test.255confirms all
four original body revisions remain unchanged and the owned design is idle.

### Timing, verification and next boundary

The Grey source local bake/mapping/audit takes18.228/11.469/20.218/32.527s per
configuration; Brown takes18.071/11.419/19.197/30.924s.247native assignment alone
takes12.783/2.342/5.086/12.251s;249takes17.414/4.532/8.775/18.024s. These are
instrumented development measurements with distinct renderer/cache state, not a
controlled optimization comparison or production generation benchmark. All are
optional appearance expense. Total phase times include additional checks/captures.

Across the recorded240/241/243/246/247/248/249/250/252/254phases, measured target
work sums466.006s, including failures. This excludes local diagnostics, controller
latency and code preparation; total orchestration/token cost is unmeasured. Maximum
sampled process RSS is1,993,184KiB (249), below4GiB; in-flight peak is unmeasured.
Resource checks occur between bounded groups of16operations and between cases.
Current work comprises4appearance-only copies plus7archive-import copies of the
same four configurations,0newroute solves or sweep/createBody attempts and0newfull
physical audits. Copies, faces and image variants do not increase independent
geometry coverage. No production integration or promotion occurred.

33focused tests cover image reading/checksums, explicit library-relative path
resolution, replacement source bytes, invalid dimensions, unsupported native
texture types/transforms/transparency, material inversion/phase branches, known
crease recognition, unrelated chart-domain equivalence and restoration of offline
directories. Final review adds a filesystem-only restoration helper that preserves
files if an importer recreates a hidden directory; four focused tests exercise
normal restoration, conflicting directories and missing retained sources. Native254
used the earlier direct restoration path; the final helper does not alter import,
image or geometry checks. Scoped Ruff and IDE
inspections pass. No repository-wide suites/fullQA run was requested. Plans,
partial outputs, screenshots, source snapshots and failures remain under
`artifacts/verification/ribbon_optional239/` through256;256/summary.json aggregates
the final evidence. Historical source digests resolve to retained source snapshots
where the final implementation has changed.

Use fresh output directories; completed plans/results never overwrite. The
developer-only sequence is:

```text
uv run python -m experiments.experiment_optional_appearance.runner --phase export --output artifacts/verification/<new-export>
uv run python -m experiments.experiment_optional_appearance.bake --export artifacts/verification/<new-export> --output artifacts/verification/<new-bake> --asset-root "<known-library-resource-root>"
uv run python -m experiments.experiment_optional_appearance.runner --phase apply --export artifacts/verification/<new-export> --bake artifacts/verification/<new-bake> --output artifacts/verification/<new-apply>
uv run python -m experiments.experiment_optional_appearance.persistence_split --bake artifacts/verification/<new-bake> --output artifacts/verification/<new-archive-test>
```

The host guard is intentionally bound to the current owned idle design and frozen
case inputs. A different document/session requires an explicit newly pinned owned
context; do not disable guards or point the experiment at an unrelated design.
`bake --alternate` selects the recorded second library bitmap. The older
`persistence` entry point retains the single-callback failure procedure; use
`persistence_split` for the validated post-commit archive sequence.

Current conclusion: deferred opaque base-color application and source replacement
have positive evidence across these four development layouts; archived image data
and face associations survive the tested post-commit import without source files.
Fine-pattern visual fidelity, full procedural/PBR appearances, cold restart and
regeneration remain explicit limits. The optional appearance requirement can be
kept outside normal geometry generation, with the supported subset and remaining
quality work recorded rather than concealed by a blanket reliability claim.

Relevant API contracts: [read-only rendered texture coordinates](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TriangleMesh_textureCoordinates.htm),
[appearance image access and document image storage](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Appearance_colorTexture.htm),
and [texture type/property access](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_AppearanceTexture.htm).

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
