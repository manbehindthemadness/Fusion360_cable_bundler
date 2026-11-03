# Selected material solver and gym integration — 2026-11-01

## First-pass movable-bend contraction530–536 — 2026-11-03

Five-conductor ed8423build exposed113.250549mm first-pass excursion. Its nearer
37.901194mm branch is correctly rejected for actual penetration; fallback has
92.4%explicit straights. Earlier498contraction remained standalone and was absent
from selected v2. It is now called before smoothing when first-pass optimization
is enabled, only after strict initial separation. Checkbox off skips it; v1 is
unchanged. Same ordered bends/radii/profile/caps, four deterministic descent steps,
at most two strict1024pair certificates,0.35CPU s and at most2wall s within the
remaining original4sfirst-pass allowance. Optional exhaustion/rejection keeps the
safe baseline; hard worker cancellation/time/RSS/source errors propagate.
All trials are logged; counters include it and smoothing uses its shorter length.
New package/model/solve files are included in the185-file source lock.

530baseline/531prototype/533maintained compare four independent examined gym
configurations:113.251→28.943,20.057→15.911,47.585→32.261,84.532→78.528mm,
all shorter/strictly separated, exact prototype parity. Known invalid branch stays
penetrating1/1. Compact guide agreement worsens; no universal route-quality claim.
534live source-list setup stop launches0solves/builds; retained, corrected by
reloading live lock under a new identical-budget535plan. Normal535job
`selected-39baa7239d65410d826a21b601f00b55`completes, matching gym/body visible.
Smoothed length29.232429mm instead of113.772232mm.212faces/7350points/406seams/
guides/caps strict original-goal pass,0warnings, maxsurface1.230084e-9mm.
Contraction CPU.198446s; numericalCPU1.222301/wall1.299308 incl.firstpass.567424
and smoothing.687272s subsets. Native generation1.302123s/audit20.528263s.
One native configuration attempted/built/named-audited of four; other three native
unattempted,0fullphysical/holdouts. Old output/history retained hidden.78focused
tests/Ruff pass; new code IDE-clean, fullQAunrun. No production/standards changes.
Detailed rule/coverage/performance/retention evidence is maintained in
`../experiment_ribbon_bend_relocation/NOTES.md`, ignored530–536plans and outputs.

## Exact side-tip control authoring524–529 — 2026-11-03

Five-conductor job`selected-b00738ef7d1d4532b092a9e573464b2b` passes numerical
material/cap/contact and smoothing1%, then fails before a native kernel attempt:
`Fold coordinates must lie within the material strip.` The same seed2641972872
and goal selections as518now use5conductors/D0.75mm, scaling the gym targets.
This is distinct from the contact-depth failure; the prior three-conductor jobs
still build. Fusion application logs were inspected; the retained native traceback
identifies the local profile-to-patch translation, before any Fusion kernel call.

524freezes this trigger and contracted499/correspondence461/tight-baseline422
before four cached translation baselines. Trigger fails; all three controls
translate. Its four side-cap tangent controls have q=+/-1.9500000000000002mm,
one floating-point step(2.220446049250313e-16mm)outside strip half-width1.95mm.
The outer tip itself already uses the correct1.95mm. Computing the tangent
control through a cancelling trigonometric expression introduced the discrepancy.

`material_profile` now authors the tangent control at the same exact q as the
outer tip, nominal+extension. This is the analytic tangent-intersection identity
for that circle, independent of conductor count/size, not a tolerance/clamp or
modified material strip. Profile arc ordering/labels/weights, dimensions, lane
identity and all route/radius/contact/accuracy gates remain. No search or iterative
work is added.525replays one unchanged fix on all four cached configurations:
4/4translate,0failed/unresolved/skipped/unattempted. All three collateral profiles
are bit-for-bit equal to their baselines. Trigger produces224lateral patches.
No native construction or full physical audit is inferred from translation.

526launches one normal solve/build on unchanged five-conductor targets/settings.
It builds a226-face solid in1.356475s, but verification stops before measuring any
points: the live`experiment_ribbon_joint_route.fidelity`adapter still imports the
old profile function. Native builder/current base audit/coordinates had been
refreshed; this additional live consumer was missed. This is a failed verification
setup, not an accepted build or a measured native geometry finding. Original job
`selected-12fe5996957b418d93ba0c53e018c162`and its hidden body remain unchanged.

528records this stopped-run review and renews exactly one ordinary solve/build
under the same limits/source/rules/targets/settings, explicitly refreshing the
missed audit binding.529collects normal completion, visible body, no UI error:
job`selected-ed8423def6314462952076ff4d60ba9f`, revision
`f3ce0cea-3906-4f7b-b649-dfd15012b7df`. Saved route exactly equals original
failed b007route.226faces,7840surface samples/434seams/three guides/two caps pass
the original accuracy goal, max surface error1.433269e-9mm,0warnings/hard findings.

Final numerical wall1.984228s/CPU1.897612s; first pass0.392499s including
contact0.291758s, smoothing1.553906s is a subset. Smoothed contact separates
in166pairs. Generation1.467048s, audit26.724730s, native operation29.922398s.
Numerical time exceeds matched generation here; no speed-goal improvement claim.
524–525cached translations total0.820598CPU s; the two native operations total
31.587123s, with generation2.823523s a subset. Orchestration/native CPU/token and
currency costs unmeasured. Each native plan120sworker/120snative/240sphase,
4GiB RSS/3.8GiB launch headroom held; final retained native peak1326208KiB.

Coverage:4independent examined gym configurations translated;1/4native attempted,
2native operations/built bodies on that same trigger,1complete named fidelity
audit,3/4collateral native attempts unattempted by scope,0full physical audits or
holdouts. Original failed translation and stale-binding audit remain failed;
renewed build passes. No universal success or native breadth beyond that one
configuration is claimed.157focused material/cylinder/accuracy/correspondence/
selected-solver tests pass, including5-conductor independent circle/material-map
comparisons and exact strip bounds for1/3/5/8/12/128conductors across five diameters.
Scoped Ruff lint/format and complete diff review pass; existing duplicate-fragment
IDE weak warnings in material_profile.py/old tests remain, no new findings.
FullQA unrun. Source lock remains182files, profile hash renewed; no production or
standards edits. Evidence: ignored`ribbon_profile524/525/526/528`,524–529drivers,
original source and525source snapshot. Live refreshes of profile authoring must
also update joint_route.fidelity's imported function; new processes import it fresh.

## Conservative occupied-profile contact bounds518–522 — 2026-11-03

The14:14:03failure, job`selected-c5758c2df1104c01a4e4ae4fca18ccfc`,
stops before smoothing/native construction. Seed2641972872,3conductors,D0.75mm,
void/zone300%,A10/face0/roll0,B7/face8/roll1 produces one closed23.433206mm
branch. Strict contact stops after336pairs at depth36 between straight pieces0/4,
without a penetration witness. Total original numericalCPU0.110771s. This is a
contact-enclosure limitation, unrelated to the native0.01mm warning policy.

518freezes and replays this unchanged rejected route once, instrumenting only
the existing depth return. Both stalled material boxes contain no actual joined
profile: piece0 |height|>=0.280518mm versus profile maximum0.180483mm;
piece4 |height|>=0.374268mm versus maximum0.069227mm. The full rectangular
section envelope includes empty space outside the original lobes and side arcs.

`contact_profile.clip_profile` now encloses actual profile half-height across each
cell's complete qinterval, using interval endpoints and any enclosed circular-lobe
apex. Side arcs decrease toward the outer tips. An outward numerical guard enlarges
the bound; height is intersected with that enclosure, and empty cells are discarded.
This changes no profile/route/pose/radius, clearance threshold or physical rule.
Pair1024/depth36 limits remain; discarded cells still count against the pair budget.
True penetration and remaining unresolved contact still reject ordinary geometry.
The bound is constant work per cell, independent of conductor count.

519first establishes original baselines for the trigger, contracted499,
correspondence461 and tight-baseline422, plus a known penetrating branch control;
then applies one unchanged clipping prototype.520repeats the same fixed scope with
maintained code and the renewed182-file source lock. Four independent complete
examined gym configurations planned/evaluated,4/4separated,0failed/unresolved/
skipped/unattempted. Invalid branch control correctly rejected1/1, separately.
No holdouts, new route searches or native builds in these contact-only runs.

| Configuration | Original contact | Maintained contact | Maintained CPU s |
| --- | --- | --- | ---: |
| trigger2641972872 | unresolved,336pairs/depth | separated,289pairs | 0.047516 |
| contracted499 | separated,138pairs | separated,138pairs | 0.042011 |
| correspondence461 | separated,28pairs | separated,28pairs | 0.007413 |
| tight-baseline422 | separated,127pairs | separated,127pairs | 0.032233 |
| invalid branch control | penetration,57pairs | penetration,57pairs | 0.014964 |

521–522perform one ordinary solve/build on the unchanged trigger and original
settings: optimization on,smoothing1%,UVoff. Fresh worker passes strict contact;
first pass0.118994s includes contact0.051211s. Numerical wall0.963169s,
CPU0.904951s; smoothing0.836739s is a subset. Smoothed contact separates in28pairs;
cap error4.254e-15mm, material metric error6.517e-16. Native generation1.064487s,
named fidelity audit13.515103s, native operation total16.568573s.132faces,
4550surface samples/250seams/three guides/two caps pass the original goal;
maximum surface error1.899204e-9mm,0precision warnings or hard findings.

Native coverage:1/4independent configurations attempted/built/named-fidelity
audited,3/4native unattempted by the declared scope;0full physical audits.
The original failed job/report remain. New job
`selected-3a88112972014a9ca62f3c530e957ee3` completes normally with visible body,
revision`07eaa329-a688-45bc-97f2-269544f3e437`, in the existing owned gym/document.
No unrelated geometry/layout changes. Limits120sworker/120snative/240sphase,
4GiB RSS/3.8GiB launch headroom held; highest retained native sample718160KiB.
Contact diagnostics518–520 total0.537470CPU s, excluding imports/unit tests;
native CPU, orchestration wall time and token/currency costs unmeasured.

Focused contact/profile tests and affected solver/smoothing/selection consumers
pass; Ruff lint of contact/selected-solver/feature/aesthetic packages and changed
tests, changed-file format checks and complete diff review pass. New helper/tests
are IDE-clean; existing duplicate-fragment weak warnings remain in contact.py.
Two initial synthetic10mm parallel-prism unit probes still exhausted finite contact
work; the isolated profile test uses0.2mm prisms. No algorithm budget was increased.
Long near-contact configurations can still remain unresolved. No universal solver
success, native preservation on the other three controls, fullQA or full physical
certification is claimed. Evidence: ignored`ribbon_contact518`through`521`,
frozen518–522drivers and520source snapshot. No production/standards edits.

## User-directed0.01mm warning ceiling516–517 — 2026-11-02

User explicitly requests native dimensional deviations below0.01mm to warn while
still aiming at original accuracy. `accuracy.py` separates original1e-6mm goals
from the exclusive0.01mm warning ceiling. Errors <=original goal pass; goal misses
strictly below0.01mm warn;0.01mm or greater, invalid or nonfinite measurements stop.
Surface-representation bounds, native surface/trim distances, connected seams,
guide positions and cap positions share this policy. Actual values, original goals,
maxima and every warning remain recorded. Original `failed_points`/`seam_failures`
are retained as strict-goal findings; warnings do not claim original-goal compliance.

The native audit now completes remaining checks after a warning-level surface or
seam measurement. Valid membership, complete native-face coverage, conductor/profile
ownership, seam topology, closed positive volume and original angular gates remain
hard. No0.01degree conversion is implied. Contact/material/bend/resource/source and
internal mathematical/API convention assertions are unchanged. Exact-cylinder
construction remains enabled and aims at original accuracy; no route or native
geometry is adjusted to meet the warning band. Historical default audit replay
remains strict unless the display policy is explicitly supplied.

NativeOwner passes the display policy to both direct and merged-face audits. The
controller, counters and optional native-QA reporter propagate precision warnings
without aborting geometry or labelling them strict passes. Diagnostic rule archives
now accept additive `warning` observations; native fidelity rows show warning rather
than failed when only accepted dimensional goal misses exist. Raw detailed audit
findings and original goal remain available. The older seam-only/live-point-tolerance
helper is retained for historical replay/tests but no longer governs active builds.

516freezes four examined independent gym configurations: the old smoothing/sphere
failure plus three retained controls. Three controls replay complete cached strict
audit records; actual read-only native re-audits cover the sphere and merged-face
control.0new solves/builds/native attempts,2/4new native audit evaluations,0full
physical audits or holdouts. Sphere audit now completes all4900surface/270seam/
three-guide/two-cap measurements with7surface warnings, max7.907172e-6mm,18.440282s.
Merged-face control retains its original goal pass without warnings,20.937290s.
Other two controls remain cached-only, not new native coverage. No new failures,
resource stops, body/visibility changes or historical report edits. Original exact
failed/strict reports remain unchanged. Executed accuracy/fidelity sources are
archived alongside516before the final defensive nonfinite-data guards were added.

517refreshes scoped native/controller/correspondence/accuracy bindings and the
current archive rule parser, with181-file source lock verified. Existing scene,
selection, body revision/visibility and exact-cylinder policy remain unchanged.
No job, solve or native build is launched. Future gym builds use the new warning
policy. Mandatory safeguard files record this explicit user policy revision.

84focused accuracy/correspondence/controller/progress/performance/inspection tests
pass, including exact0.01mm rejection, sub-limit errors, nonfinite/missing data,
preserved profile ownership and warning archive support. Changed Python passes
Ruff lint/format and complete diff review; new helper/tests are IDE-clean. Existing
legacy duplicate/shadow/fail-soft findings remain in older adapters. Full QA and
native geometry creation under the new reporting policy were not rerun; topology,
angular and physical acceptance are not inferred from dimensional warnings.
Evidence: ignored `ribbon_accuracy516/517`,516driver/payloads and517application
result. Numerically identical geometry and prior515successful body remain visible.

## Exact circular flat supports511–515 — 2026-11-02

Smoothing1% jobs `selected-a4a715699144469a960d5e55d0a1893a` and
`selected-a03c378186cd498fb42146ef7b29c715` pass numerical/material/cap/strict
contact checks and each create a142-face solid. The surface audit rejects seven
samples on flat region face124, maximum7.907172e-6mm, before guides/caps are audited.
This is a distinct surface failure; the seam-only warning correctly does not apply.
Both original failed builds/reports remain retained, not retrospectively passed.

512reads the existing failed body without modification. Its corresponding flat
patch is stored as a native **Sphere**, whereas the supplied rational patch is a
circular extrusion. Independent actual-trim distances reproduce all seven errors;
this is not merely inaccurate point inversion. Direct authored UVs are inapplicable
to that spherical chart.511first assumes NURBS getData shape and stops with an
IndexError before measuring; its stopped payload is retained.512validates the
surface-data shape and records the sphere and distances.0new native attempts.

`material_cylinder.py` derives each circular profile's center/radius from exact
rational-arc points, with normalized reconstruction and independent quarter-point
checks. A flat before/after/straight region is an extrusion along its constant
material tangent, even when crease trims are oblique. Supply its exact analytic
Cylinder support to the existing body definition, retaining every authored edge,
vertex, trim, radius, profile identity and target. Curved regions retain their
original bounded NURBS; unsupported noncircular profiles retain original NURBS.
No perturbation, welding, scaling, route repair or audit-tolerance change.

The shared body author accepts an optional surface factory, defaulting to its
original NURBS for historical callers. `NativeOwner` defaults to typed
`FlatSurfaces.CYLINDERS`; the original NURBS policy remains explicit for comparison.
This avoids the observed spherical approximation at construction time. Optional
physical/material-coordinate metadata is unchanged; UV/textures stay off in this
native verification. Native UV/appearance coverage for the new supports is untested.

513freezes the smoothing trigger and three distinct previously examined gym
controls before any new build; all routes are replayed without solving/refitting.
Four planned/evaluated/native attempted/built/named-fidelity audited;4/4strict
passes,0failed/unresolved/skipped/unattempted,0full physical audits/holdouts.
Original full-profile/guide/cap/seam gates pass without even the seam warning.
122-face correspondence mode preserves the earlier merged-face repair.

| Gym configuration | Faces | Generation s | Audit s   | Max surface error mm |
| ----------------- | ----: | -----------: | --------: | -------------------: |
| smoothing trigger |   142 |     3.300876 | 24.620825 |           1.29745e-9 |
| contracted499     |   132 |     1.453072 | 15.058932 |          7.33566e-10 |
| correspondence461 |   122 |     1.078187 | 22.667229 |           3.80966e-8 |
| tight baseline422 |   152 |     1.224755 | 18.076026 |          7.59657e-10 |

Limits120s/case480s/phase,4GiB RSS/3.8GiB launch headroom, one attempt per case,
first failure stop. Sampled maximum717472KiB. Separate RPCs schedule one case
at a time. No source/resource/API/kernel/audit stops or warnings in513. Measured
case-operation total93.405028s excludes orchestration; generation7.056891s and
audit80.423013s are subsets. Native CPU/currency costs unmeasured. These are
development construction results, not new cold-solver or global generality evidence.

514adopts the verified policy in the live owned callback and launches one normal
matched Solve/build with smoothing still1%.515confirms job
`selected-fa4508b4c8594694bb3b31a8d41e5cff` completed and visible, event error clear,
strict named fidelity passes with zero warnings. Entire saved material route is
exactly equal to the original failed job's route; only native support authoring
changes.142faces/4900surface samples/270seams, zero failures, max1.297448e-9mm;
all three ordered guides and both caps pass. Native generation1.164765s, separate
audit16.065551s; workerCPU1.109528s/wall1.158266s, smoothing.947663s subset.
Measured solve/check wall meets matched generation goal narrowly on this run.
Native operation19.178421s; sampled maximum532880KiB. Body revision
`fa27dbf4-1e9a-42fb-ac6f-9d6e1abdb479`; capture with matching gym inspected.

Five new native operations across513/514remain **four independent configurations**;
the live smoke repeats the trigger. All prior bodies/history/layout/settings are
preserved; four standalone verification copies retained hidden.180-file source
lock verifies. Numerical solver/smoothing and standalone contraction status unchanged.
16new analytical support tests pass;52focused cylinder/precision/progress tests pass.
Changed Python passes Ruff lint/format and full diff review. New helper/tests are
IDE-clean; pre-existing legacy duplicate and fail-soft exception weak warnings
remain. No full QA, unseen matrix, new contact search or full physical audit.
Evidence: ignored `ribbon_smoothing511/512`, `ribbon_cylinders513/514`, frozen
payloads/513driver and all source-pinned native/numerical job records.

## Bounded native seam precision warning507–510 — 2026-11-02

User reports another creation stop. Job `selected-f7c1bb4572a14dfb99d92a8b334efcc7`
passes numerical material/caps/strict contact and creates a positive-volume152-face
solid in1.136320s. The strict post-build audit then hides it:20shared-one-edge seam
endpoint discrepancies1.599e-6..4.435e-6mm exceed its1e-6mm gate. All5250surface
points,150patches,three ordered guide positions/tangents and both caps pass.
This is a native audit/display stop, not a routing or kernel construction failure.
Original strict report/body remain retained unchanged.

Implement the user's previously allowed bounded precision-warning policy in
`precision.py`, called only after the original combined seam/tangent exception.
Require a complete fixed-revision audit; every original surface/guide/cap gate
must pass independently. Every seam finding must be a connected direct single
shared-edge chain with positive endpoint residual above1e-6mm and no greater than
Fusion's live point tolerance. The original audit proves chain connectivity before
emitting a positive direct-edge residual. Reject missing/branched/merged-face or
zero-residual topology failures, malformed/incomplete evidence and other errors.
Restrict native continuation to original one-to-one face/patch mapping so UV face
provenance remains established. No geometry repair, tolerance change in the base
audit, target/radius/profile/contact change or extra route search.

Reports retain `audit.seam_failures` and use `built_with_precision_warning`, never
the strict named-fidelity-pass status. The controller shows `completed_with_warning`
and retains a failed strict native-fidelity rule with the diagnostic warning
explained. Counter labels distinguish this result. A simultaneous contact-warning
session still reports contact unmeasured. UV remains separate/off in this live run.
Strict QA still treats warning status as distinct from an unconditional pass.

507replays four already examined complete-gym audit records: triggering f7c1 plus
499contracted hairpin,461correspondence repair and422tight baseline. Trigger
qualifies for warning; all three strict controls retain their original passes.
Classifier-only0.007490CPU s including report reads;0solves/native attempts or new
geometry coverage. Synthetic tests also reject missing topology, larger seams,
guide/cap failures, malformed/partial reports and exceeded native tolerance.

508stops before reload/solve/native launch because its input guard compares tuple
fields in a live payload with JSON lists.509normalizes that comparison to JSON;
exact targets/settings/rules and budgets remain unchanged. This is a preserved
setup failure, not a failed geometry attempt. Source-pinned one-case native scope:
4s first-pass,120s numerical/120s native,240s phase,4GiB RSS/3.8GiB launch headroom,
one native attempt; no retries after launch. Refresh only current owned native and
controller callbacks. Source lock becomes179files; numerical solver/math unchanged.

509normal Solve/build job `selected-9cd41ae70d98450892e9733219b994dc` completes;
510confirms visible body, clear event error and `completed_with_warning`. One
independent configuration attempted/built/complete named measurements, with the
strict seam audit still failed and bounded warning explicitly retained;0full
physical audits. Three collateral configurations native-unattempted in this phase.
152faces/5250surface points/290seams,20same precision flags/max4.435041e-6mm versus
live tolerance1e-5mm; surfaces/guides/caps pass. Generation1.394604s, separate audit
16.137033s, native operation19.032865s. No relaxed contact or native correction.
Body revision `545a7e39-f9c8-4a55-aaaa-4e80cad4ef00`; capture inspected. Existing
layout, settings and historical bodies/reports preserved. This does not install
the standalone497–500bend contraction in the numerical solver.

Latest focused verification:63precision/controller/progress/performance/contact
tests pass; prior selected-solver checks also passed before the final UI-only
consumer changes. Seven changed Python files pass Ruff lint/format; full diff
reviewed. New helper/tests are IDE-clean; pre-existing duplicate fragments in
native/controller/performance and the documented native fail-soft broad exception
remain. No full QA, new unseen geometry matrix or complete physical audit.
Evidence: ignored `ribbon_precision507`, `ribbon_precision509`, original/current
job files and `precision507.frozen` through `precision510-collect.frozen`.

New standalone experiment497–500 contracts existing individual bends rather than
inserting a rotation stage. Four examined gym routes shorten with strict numerical
contact; one builds/passes named fidelity and is visible separately. Selected gym
solver and rollback496 body remain unchanged. The compact layout worsens guide
agreement; no unseen validation or global optimum is claimed. Full fixed procedure,
costs and limitations: [existing-bend contraction](../experiment_ribbon_bend_relocation/NOTES.md).

## User-directed rollback496 — 2026-11-02

The user directs reverting the unsuccessful angular/event-insertion attempt.
Executable code/tests/lock are restored exactly to pre-attempt HEAD `e75a189`:
178sources, original v2two-contact/four-second first-pass policy. Remove the new
angular modules/tests; preserve the earlier closure, geometry-correspondence,
progress, visibility and orphan-gym fixes. Failed464–495payloads/results remain
under ignored verification artifacts and are not active solver capabilities.

496restores retained job `selected-88c7ae3777e5450290c5d005520a0e9d` and its
42.746057mmoriginal body/diagnostic selection/counters, unchanged native revision
and0%smoothing/UVoff/optimizationon. Removes exactly the unchanged enhanced470
occurrence after verifying both revisions, current inputs and idle ownership.
Original body visible, event error clear;0solves/0native builds. Histories retained.
No accepted event insertion or excursion correction is claimed. Evidence:
`artifacts/verification/ribbon_revert496/` and `revert496.frozen`.

Rollback verification:42focused solver/closure/progress tests pass; restored
Python files pass Ruff lint/format and IDE inspections. Executable diff is empty
against HEAD and the178-file lock verifies. No full QA or new native build needed.

## Native/material correspondence repair 453–462 — 2026-11-02

**Current disposition:** the unchanged current gym layout now completes normal
Solve and build, passes all named fidelity checks and displays its positive solid.
The previous count guard rejected122actual faces versus132authored material
regions before measuring geometry. Fusion merged the tiny terminal bend's material
regions into neighboring native faces. Independent measurements establish their
sampled physical correspondence; a raw count difference alone cannot decide it.
This supersedes the unresolved disposition in443–451, whose original failures and
alternative constructions remain recorded without rewriting their results.

`correspondence.py` records actual native-face identity separately from ordered
material regions. It requires full sampled source coverage, ownership of every
actual lateral face by one unique profile arc, and two independently matched
terminal caps. Selected points are evaluated on actual native supports. Raw trim
membership failures require independent minimum distance to the actual trimmed
face in assembly space. Material boundaries inside a merged face receive nine
authored-support samples checked on both source families. Where a shorter source
seam occupies part of a larger actual shared edge, its nine samples also require
distance to that real edge. Original whole-edge discrepancies remain in the
report. No synthetic native faces/edges, route edits, radius changes, physical
rule changes or tolerance expansion: surface/trim/seam1e-6mm and original guide
tangent/cap gates remain. Face-query/distance limits30000/512, native120s/4GiB.

The normal NativeOwner keeps the original audit fast path when native/authored
counts match and uses verified correspondence on count mismatch. Real native
counts remain explicitly reported. Optional UV metadata enumerates actual faces
and retains every contributing source region; the new `coordinates_for_face`
inverse recovers continuous global material U/V/thickness from those regions.
It creates no appearance or texture. Unit tests cover multi-source roundtrips;
this phase's normal native run has UVoff, so native UV attribute writes are
**unattempted**. This is development fidelity work, not product-time generation
expense or a complete physical native audit.

All experiments concern variants/measurements of **one independent configuration**:
seed1283296667,3xD.75,A22f5r2/B12f3r0,optimizationon,smoothing1%,UVoff.

- 453reads current user job `selected-3336adc182db41ecbc0b78a96d1e43d2` and
  retained face IDs. IDs are reindexed and do not supply authored correspondence.
- 454stops on an artifact-script fingerprint path error before construction:
  **0native attempts**. The corrected455is separately frozen, not a rewritten454.
- 455one scaled transient construction yields129/132faces and stops before
  conversion/restoration. 456one normalized-knot scaled construction also yields
  129/132and stops. Neither completes fidelity or persists geometry; both remain
  artifact-only, unpromoted experiments. Original builders stay unchanged.
- 457read-only sampling stops after89complete patches at its512distance-call
  cap;0failed sampled points, incomplete coverage. 458checks cheap memberships
  first, then independent trim distance: all4550points pass across130patches,
  maximum6.628815e-8mm,12trim distances,11.360588s. All lateral native faces have
  unique profile ownership; two caps remain for independent matching.
- 459full correspondence audit passes surfaces, three guides and both caps,
  but12whole-edge endpoint comparisons reject shorter logical seam subsegments.
  It stops with those findings intact in13.329846s.
- 460adds actual shared-edge subchain measurements:4550points,250seams with
  0failures, all three ordered guides and both caps pass in41.415299s. Complete
  correspondence covers122actual native faces and132material regions. Combined
  trim/edge distance corroborations192/512. This is a read-only audit of the
  existing solid, **0solves/builds/geometry edits**.
- 461freezes one normal v2job, one native attempt,120s numerical/120s native,
  240s phase,4GiB RSS/3.8GiB launch headroom; no retries. Reloads only the three
  reviewed native-audit modules and rebinds the existing owner's actual build
  callback. The palette's ordinary polling completes job
  `selected-a4aee91715cb416abfcec6e099502687`:122-face positive solid, generation
  .985002s, named audit22.344116s, total native24.989209s. Numerical acceptance
  is separate:.383071s wall/.359844s CPU, strict separation retained.4550surface points,
  max6.628815e-8mm,250seams/0failures; guide position<=1.078e-9mm and tangent
  <=4.985e-8degrees. Both complete cap checks pass; actual revision unchanged by
  audit.10345face queries/192distance checks, sampled RSS peak723920KiB. Native
  generation excludes audit/graphics; in-flight memory peak is not measured.
- 462read-only live confirmation: completed job, clear event error, current
  NativeOwner/class callback, visible positive solid, same native revision,
  one valid tracked gym context group, strict contact mode and preserved1%/UVoff
  settings. Capture inspected.0additional solves/builds/geometry edits.

This continuation has3positive-solid creation events (455/456/461), one complete
normal native-build fidelity pass and the separate460existing-body audit pass;
neither measurements nor child faces count as independent configurations. Three
collateral numerical layouts from445remain natively unattempted in this scope.
0full physical audits/new holdouts. No universal topology, route-optimality or
production-readiness claim. Failed and incomplete runs remain explicit above.

178-file executable lock reviewed/refrozen and verified. **70focused tests pass**
across correspondence, selected solver, v2, native clear, progress, closure,
graphics and Jacobian consumers. All13changed Python files pass Ruff check and
format check; complete diff/new-file review and `git diff --check` pass. IDE
inspections show no introduced findings. Existing copied-source duplicate-fragment
reports, original fidelity-local shadowing and the documented native fail-soft
broad exception remain. No full repository QA, standalone type/document checker
or full physical audit was run. Native UV writes and three collateral native
configurations remain unattempted. Original geometry construction is untouched;
speculative scaling/conversion remains unpromoted. Evidence:
`ribbon_topology453/`,454response,`ribbon_scale455/` and456,
`ribbon_measure457/` and458,`ribbon_audit459/` and460,`ribbon_native461/`, plus the
original frozen job directories. Host application log inspected before changes.

## New closure failure and duplicate gym graphics 443–451 — 2026-11-02

**Historical disposition before453–462:** the reported layout closes numerically, including its
requested1%smoothing, and the duplicate gym context is removed. Native construction
still fails the unchanged topology/fidelity guard. Do not describe this case as a
successful complete build or solved native translation problem. No native builder,
physical-rule or fidelity-tolerance change is promoted from this investigation.

Trigger: gym seed1283296667,3conductors/D.75, A(zone22,face5,roll2),
B(zone12,face3,roll0), optimization on/UVoff/smoothing1%. Original user job
`selected-c2798bd10fa344e18252faa1850097ed` stops in65.76ms with0closed branches,
0contacts,0smoothing and0native attempts. Its best existing root[0,0] reduces
position residual to.0654031diameters (.0490523mm), then hits the two-correction
cap. This failure precedes contact checking and is distinct from437–442.

`reclosure.py` preserves the original two corrections on every derived branch.
Only when **none** closes does the closest still-progressing unfinished branch
receive up to four further residual-derived corrections, with the same pi/4step
cap, two halvings, fixed roots/radii/sites and strict cap/material/contact gates.
Stalling stops; no new guessed orientations, candidates or target snapping.
Successful original constructions never enter this continuation. The trigger uses
only two extra corrections: residual .0654031D ->.000187843D ->6.290218e-10D;
the resulting strict first-pass contact check uses33comparisons.

444baseline freezes that trigger and three collateral gym layouts before changes:
compact4033669276, shallow8conductor gym424-05 and spatial12conductor gym424-09.
Three pass; trigger unresolved. First444candidate closes its route/contact but
stops in1%smoothing when a finite-difference coordinate rounds outside its bound.
The raw early-error report lists all four as unattempted because results append
only after solve returns; actual disposition is **trigger attempted/stopped,
three collateral unattempted**. Trials and traceback preserve that failure.

The shared closure Jacobian now clamps probe coordinates to the unchanged closed
bounds and divides by their actual representable separation. For example,
3e-6-(3e-6-1e-6) can become9.999999999999997e-7, below the1e-6signed angle floor.
This corrects derivative evaluation, not geometry or constraints. Four analytic
regressions cover both signs and exact-bound probes. 445then completes all four
strict numerical cases in.775308s/CPU.772204s. Trigger15.695280mm, solve/checks
.278646s (firstpass.079430s, smoothing.191014s), cap residual1.292e-10mm.
All three collateral snapshots are byte-equivalent as parsed to their baseline
geometry; no extra closure work occurs for their already successful constructions.
Four examined layouts, not new holdouts or native coverage.

443read-only inspection also confirms two visible reserved gym graphics groups
inside the current diagnostics component: one tracked, one orphaned. The shared
gym renderer now completes a replacement, then retires all earlier groups with
its reserved name in that explicitly owned component. It preserves differently
named graphics and prior groups on drawing failure. Tests cover lost handles,
repeat replacement, interrupted drawing and failed deletion. 446live refresh
measures **2 ->1**groups;448still observes1. Older hidden workspaces, native bodies,
draft inputs and layer preferences remain untouched.

Native findings, all variants of **one independent trigger layout**:

- 446normal1%job `selected-79b916f4c675453db508ccbecea38b32` builds a positive
  solid in1.016686s, but has122faces versus132authored faces;0fidelity audits
  completed. Last fold is driven to1e-6radians by smoothing. The audit fails
  before point/seam/cap sampling; positive volume is not fidelity acceptance.
- A derived full bend-station-chord filter was tested in447, preserving the axial
  bank contribution. Numerical4/4pass; trigger15.559836mm/.302182s and unchanged
  collateral routes. 448normal job `selected-b3353a4f55ab4610a0c60f17cc4a75a0`
  builds in1.031331s but has137faces versus142authored; fidelity still fails.
  **That filter is insufficient and is removed from active code.** Exact source
  bytes and its tests are parked under `ribbon_closure447/parked_source/`.
- 449read-only support inspection locates missing exact NURBS bend patches only
  in the tiny final turn: all10in446, profiles0/1/2/3/9in448. Many ordinary flat
  lead supports become analytic cylinders; absence of an identical NURBS support
  there is not itself proof of missing material. Both existing bodies retain their
  revisions. Inspection21.088649s,0construction attempts.
- 450scales a disposable transient copy by2then.5 successfully, keeping137faces
  and original-body revision; .544390s,0construction attempts. This establishes
  only API capability, not a fidelity repair.
- 451constructs the exact448plan once at a derived power-of-two scale256, then
  restores physical size and inserts it before the unchanged audit. Scaled body
  has all142authored faces, but the restored/inserted body has145and fails the
  same guard. Intermediate face count between restoration and insertion was not
  retained, so do not attribute splitting to one stage alone. Generation1.787121s;
  0fidelity audits completed. MCP reports failure and may roll back its newly
  created component; persistent retention of that third body is unverified.
  Scale normalization remains an unpromoted artifact-only experiment. Final452
  read-only inspection confirms its component is absent after MCP rollback;
  both446/448failed bodies remain retained. The current gym has one valid tracked
  context group, strict policy and the latest native job explicitly stopped.

Native total:1independent configuration across3attempts/3positive-solid creation
events, **0named fidelity passes/0full physical audits**. Three collateral layouts
remain natively unattempted throughout this scope. No further builds scheduled;
the next question is native face correspondence and small-face handling, without
waiving topology or altering planned material geometry.

Final executable source matches the fully checked445candidate source exactly:
177-file lock, closure continuation + bounded Jacobian probes + orphan graphics
replacement. Speculative resolution gates, signature plumbing and scaling are
absent from maintained runtime. Original profile/native builders, contact fix,
strict policy, targets/identity and optional UV behavior remain unchanged.
Focused verification passes (including53tests after final restoration, earlier
graphics/handoff/selection/controller checks); scoped Ruff/format and IDE checks
show no introduced findings. Existing duplicate-fragment weak warnings remain.
No full repository QA, standalone type checker or complete physical audit.
Evidence: `inspect443.json`, `ribbon_closure444/`, `ribbon_closure445/`,
`ribbon_closure447/`, `ribbon_scale451/`, and the three named job/script records.

## Contact measurement repair 437–442 — 2026-11-02

The user requested pair-budget exhaustion to stop/log measurement rather than
abort geometry, explicitly **temporarily**, followed immediately by a real fix.
An explicit v2 session policy retains only `unresolved/limit=pairs` with its raw
count, pieces and reason. Worker rules, progress, counters and native completion
keep contact unmeasured; successful native fidelity cannot erase the warning.
Penetration, depth/regularity ambiguity and all other hard gates still reject.
Normal APIs and v1 remain strict. The temporary policy is now **inactive in the
live gym**; 442 restored `require_separation` for both advertised versions.

437 examined four retained complete gym layouts, not untouched holdouts. Two
separated and two exhausted1024pairs; geometry continued with explicit warnings
on those two only. 438 made one native attempt on the unchanged user-trigger
20.057443mm route: built and passed named fidelity,162faces, generation1.356529s,
separate audit18.380582s. The other three were natively unattempted in this scope;
zero full physical audits. Its original job stays `completed_with_warning` and
contact-unmeasured. Do not silently upgrade historical reports.

439 traced the unchanged checker once per retained route. On the user trigger,
654 comparisons involved pieces1/2,249 involved1/3 and41 involved2/3:92.2%of the
1024budget around the first folds/following straight. No penetration witness was
found. Inspection located unnecessary interval inflation: rotated material xi/eta
were bounded independently, losing their correlation inside a banked fold.

The integrated repair retains that correlation. A thick rectangular material
cell projects as f(xi)+beta*eta, affine in height. Extrema therefore occur on its
four parallelogram edges at either height endpoint. `contact_extrema.py` evaluates
edge endpoints, plane/cylinder joins and every analytic stationary phase, without
angle grids or guessed candidates. `contact_bounds.projection` adds a numerical
guard scaled by cancelling transform terms; nonfinite/underflowed extrema fall
back to the old conservative interval implementation. The full rectangular
thickness envelope, witnesses, cap/bridge exclusions, subdivision and1024pair/
depth36limits remain. Construction steering deliberately retains its original
interval envelopes, so tighter contact bounds do not change module spacing.
These remain guarded floating calculations, not exact-arithmetic certificates.

440 compared the prototype on four unchanged routes plus the already penetrating
gym424-09branch (five dependent variants, four independent configurations).
Both formerly unresolved routes separated; the known penetrating branch retained
the exact same witness. No solves or native work in that comparison. The exact
prototype bytes are archived as `ribbon_contact_bounds440/prototype-source.frozen`.

441 then reran the integrated **strict** v2 constructor on all four original inputs,
smoothing0/UVoff, at most two contacts and4s/solve,20s/phase,4GiB. Every resulting
snapshot exactly matches its437route. All four passed the numerical material/cap/
contact checks, with no warning or budget increase:

| Retained layout | Length mm | Selected contact pairs | Solve + numerical checks s |
| --- | ---: | ---: | ---: |
| User trigger |20.057443|198|0.133437|
| gym424-02 |22.969329|28|0.072893|
| gym424-05 |47.585465|453|0.225485|
| gym424-09 |84.531991|175|0.194536|

User-trigger contact time0.060569s; its snapshot also exactly equals the route
used for native438. This supplies a separate strict numerical measurement of that
geometry without another native build. The penetrating control is still rejected
in198comparisons with the same witness. Entire441phase0.751860s/CPU0.732154s;
zero unresolved/stopped/unattempted numerical cases. Other algebraic branches
remain contact-unattempted according to each solver's ordinary bounded policy.
No native reruns, full physical audits or generalized reliability claim follow.

442 reloads only the measured contact modules/consumers and restores the live
controller's strict policy, preserving its draft, selected historical job, body
revision and geometry. No solve/build/deletion,0.200904s, sampled RSS301392KiB.
The old warning remains visible because it describes438, while future runs use
strict checking. The reviewed bundle now pins176files. Four examined layouts
are limited developmental evidence; broader unseen geometry remains unverified.

Verification:144distinct focused tests passed across the analytic bounds, strict
regression, temporary policy, constructor/selection, original fold/contact/cap,
v1/v2 dispatch, controller/progress and performance consumers. Changed Python
lint/format checks pass; IDE inspections show no introduced findings. Existing
duplicate-fragment weak warnings remain in unchanged adapter/interval/steering
sections. Full repository QA and standalone type checking were not run. Evidence:
`artifacts/verification/ribbon_contact_warning437/`, `ribbon_contact_profile439/`,
`ribbon_contact_bounds440/`, `ribbon_contact_strict441/` and native438job
`solver_v2_promotion/gym433/jobs/selected-a8b4ddc4e2704e8b92f3416c4d754d61`.

## Material solver v2 gym promotion — 2026-11-02

**Subsequent matched user-run regression:** gym seed4033669276,3conductors/D.75,
identical endpoint/profile records across v1 and v2. V1 final19.218321mm,
first-pass18.303163mm, initial selected candidate18.991639mm; v2 final50.389604mm.
V1smoothing5%versusv2zero cannot explain the excursion: v1was already much shorter
before aesthetics. V2's recorded20.057443mm closed branch has RMS2.441302mm but
exhausts1024contact pairs on pieces1/2, with no penetration witness. It is unresolved,
not known colliding. V2then certifies its next50.389604mm branch, RMS12.576853mm.
The monotonic rule has no spare certificate after the original first branch fails.
V1first pass allows a.934946mm fold radius versus.376506mm floor; v2locks all radii
at the floor. This difference in construction freedoms also needs accounting;
the records do not prove that contact-budget expansion or radius growth is the
correct repair. Both user-produced bodies pass named native fidelity;0full physical
audits. V1route/checks4.959145s/native1.108713s; v2.598799s/native2.165924s.
One complete layout across method/repeated-run variants, not new independent cases.
Evidence: gym433/jobs/selected-d5515776b56349f2adc54371a523d823(v1) and
selected-1cbfb78962134189ba568dd26da840d9(v2); repeated v2selected-46d68a...matches.
This read-only comparison launches0solves/builds and changes0solver policies.
Retain the reported turn-removal benefit while recording v2's clear routing-quality
regression. Next diagnostic target is the unresolved compact branch's1/2junction;
do not mask it with smoothing, invented candidates or a silent contact-budget rise.

User explicitly authorized adding the measured431method as solver v2 for gym
testing. `versions.py` advertises `guide-material-v2` as default and preserves
`joint-material-v1` as a selectable comparison. V1's numerical construction and
cleanup policy remain; its aesthetic sequence is shared through `smoothing.py`.
The source bundle now pins174files and both method identities. The former160-file
lock and exact source bytes are retained under ignored
`artifacts/verification/solver_v2_promotion/source_v1/` with `.frozen` suffixes.
Old jobs retain their original pins; do not silently rebuild them against v2.

V2 runs the421/430two-stage guide-frame tight constructor, at most two contact
certificates and four seconds for first construction. No extra-feature insertion,
historical route/v1 fallback or first-phase radius growth/sliver repair. Defaults:
smoothing0%, first-pass optimization on, optional material UV off. The optimization
toggle switches bounded monotonic branch selection versus original midpoint
selection; its UI description changes with version. It does not invoke v1's
contraction pass. Fusion's measured point tolerance is frozen in each job and
forwarded to v2's tiny-straight rejection gate. Unknown/malformed versions and
controls fail before launching work.

Optional smoothing retains the original radius/merge/layout/merge sequence and
one0..10%shared material allowance; v1 defaults5%. V2's unchanged certified first
pass avoids a redundant contact audit. Changed aesthetic geometry receives a fresh
conservative certificate. Optional UV metadata and native attribute storage remain
separately timed and create no texture/appearance. Joined profile, conductor/face
ordering and native fidelity gates are unchanged. Gym Solve and build, numerical
cancellation, transparent scaffold controls, counters, progress log, clear geometry
and recorded-result selection remain available. This is development gym promotion;
ordinary product harness routing is unchanged.

Installed owned workspace `gym433`, preserving the current draft and prior owner.
432installation stopped before any solve/build: stale loaded gym renderer lacked
the current prepath keyword. Host log confirmed it;433coherently reloads graphics,
viewer and workspace dependencies, same30s/4GiBscope, completes3.985820s. No
application-code workaround or source/tolerance relaxation. All setup failures
remain recorded.434's optional nonexistent refresh helper raised after its one
successful dispatch launch; dispatch had already sent state, so normal palette
polling completed that same worker/build, without another launch. Its script
transaction also invalidated a cached context graphic;435display selection reports
the deleted handle.436resets that invalid cache and redraws the same immutable
result,0solves/builds. Original draft and older native geometry remain retained.

434smoke: **1planned/1numerically evaluated/1native attempted/1built/1named-fidelity
audited/0full physical audits**, same examined gym08, not a new holdout. V2 reproduces
33.150386mm. Route/checks.714317s, numerical CPU.606925s, native generation1.222210s,
generation counter1.936527s; separate fidelity audit20.987426s, native operation
23.723710s, sampled peak579760KiB.226faces,7840surface points,434seam chains,
0seam flags, max surface error6.965238e-9mm. No v1 native comparison or positive
smoothing/native UV smoke in this phase. Complete rule compliance remains unmeasured.

82focused tests pass, including12new v2 dispatch/toggle/coordinate/tolerance cases;
Ruff check/format pass on affected packages/tests and viewer HTML is IDE-clean.
IDE checks cover all changed Python files; pre-existing duplicate-fragment weak
warnings remain in unchanged adapter sections, plus the documented broad native
fail-soft exception. No new IDE errors/findings in v2 implementation/tests. Full
repository QA and standalone type checker were not run. A native screenshot shows
v2 heading, selector, matching completed counters and optimization control; backend
version selection is unit-tested. Optional live keyboard switching hit a computer-
use transport timeout, so no extra comparison solve was launched. Evidence and
all setup/display dispositions: `artifacts/verification/solver_v2_promotion/`.

Four fresh complete gym configurations planned and numerically evaluated in314;
two natively attempted and built, **one passed the named fidelity checks and one
failed**. The other two remain natively unattempted after the stop. Zero complete
physical audits. This is a locked development baseline, not production promotion
or a claim that arbitrary endpoint configurations are solved reliably.

## Selected policy and controls

The user selected the joint first pass and the approved composite aesthetic pass.
`joint-material-v1` constructs from immutable endpoint poses, conductor dimensions
and the existing pinch radius floor. No successful historical route is required.
It derives finite direct/guide-middle orientation families, jointly allocates
nonnegative travel and radius growth, and checks contact in length order. Six
families and at most twelve contact attempts retain the existing finite bounds.
An unsuccessful construction is unresolved, not proof of infeasibility, and has
no retired-search fallback. A guide ranks candidates; global optimality is unproven.

The second pass preserves the selected composition: radius easing, compatible
turn merging, layout-scaled angle/bank/radius/runway easing, then compatible merging.
Fixed ordered caps, equal local material increments,99.6%pinch, no lateral bending,
thick self-contact separation and the existing joined profile remain unchanged.
Gym objects are visual context, not avoidance boundaries.

`Settings.smoothing_percent` accepts finite numbers from0to10, default5. It is a
maximum percentage of extra material length relative to the first pass. All stages
share that one ceiling; growth is not compounded. Zero skips the entire second
pass. More allowance permits smoothing but does not guarantee monotonically better
visible results under finite contact/iteration bounds. Straightaways are runway.

`Settings.material_uv` is optional, default false. True retains continuous material
coordinates `U=s/total_length`, `V=(q+half_width)/(2*half_width)` and thickness b,
plus the exact route, ordered profile and per-native-face source records. This
creates **no textures or appearances**. On the passing native case, all86face
attribute records and the component map read back exactly, with no new appearance
or geometry revision. Numerical metadata creation took0.208..0.294ms across314;
Fusion attribute storage/read-back took0.450s on its one fully verified UV case.
These optional costs are recorded separately from geometry generation.

These are application material coordinates. Fusion's renderer charts remain
read-only and face-specific. Later optional appearance baking uses the existing
verified physical inverse in `experiment_optional_appearance/material.py`; see
that experiment's notes for appearance-family limits and texture creation costs.
Endcap mapping differences remain accepted. This does not promise writable native
UV charts or reproduction of arbitrary procedural shaders. Per-conductor exterior
appearance assignment remains supported through the unchanged profile face order.

`solver-lock.json` hashes the selected numerical/native/coordinate implementations
and shared diagnostic/gym sources. Workers and native launches reject source drift.
Review changes, complete checks and explicitly write a new lock **before** freezing
a new run plan; never update a lock to continue an in-flight run. Historical
comparison `joint_route.solve` keeps its previous fallback contract; the new
endpoint-only `construct` entry point does not invent a provisional route.

The maintained `fidelity_base.py` copies the221audit, removing the selected
runtime's dependency on ignored artifact source. The existing strict actual-trim
adapter is shared through `audit_with`; measurement gates and tolerances are
unchanged. No native body repair or profile change is included.

## Frozen gym evidence and retained failures

All four inputs were generated and pinned before outcomes, with default5%smoothing
and UV enabled. Seeds2026110101..104; standard void/zone300%except case4void900%,
zone150%. Each phase allows four cases,120s/case,600s total and4GiB RSS, with3.8GiB
native launch headroom. Source/resource/API/harness/native-fidelity failures stop
the affected phase; no retry or search enlargement is automatic.

The initial313batch stopped on case1before native work: `Boundary.half_width_mm`
used `(N+.2)*D/2`, whereas `FoldRoute` used `N*D/2+D*.1`. At D=.75 these differed by
one floating-point step, rejecting a boundary sample. The correction uses exactly
the established route expression; no physical dimension or tolerance changes.
Fractional-diameter analytical regressions cover.75/1/1.5/3mm.313retains its failed
first case and three unattempted cases.314is a new source-pinned plan using the
same four fixed inputs; these repeats are four configurations, not eight.

| Case | N / D mm | Numerical | Native | Named fidelity | Solve CPU s | Solve wall s | Generation s |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| gym-cold-1 |1 / .75|pass|built|pass|.561|.561|.813|
| gym-cold-2 |3 /1.5|pass|built|failed|1.256|1.259|.902|
| gym-cold-3 |6 /3|pass|unattempted after stop|unmeasured|1.846|1.863|unmeasured|
| gym-cold-4 |3 /1.5, larger layout|pass|unattempted after stop|unmeasured|1.449|1.450|unmeasured|

CPU uses the host worker's `process_time`; native generation uses wall time for
translation+definition+kernel. This does not measure Fusion CPU utilization.
Full numerical phase5.713s, native phase17.485s. Case1audit7.633s is development
verification overhead and excluded from generation. Solve-versus-build timing goal
passes case1and misses case2; cases3/4comparison remains unmeasured. Numerical
solver timing includes optional metadata and final numerical checks; worker totals
also include diagnostic snapshot construction. No full physical audit was run.

Case2failed surface membership on face79, region `before`, fractions.33/.50/.71
at v=.03. Pointwise positional errors there are2.48e-15..4.61e-15mm; overall sampled
maximum6.365e-9mm. The native trim checks still rejected these points. Do not
misreport this as a proven trajectory deviation or relax the membership gate.
The body is hidden and partial measurements retained. The host log was inspected;
the operation completed normally. Root cause remains unresolved. Cases3/4were
not built. Earlier308calibration surface-distance failure remains separately
unresolved; it is not replaced by this different trim-membership failure.

Evidence: `artifacts/verification/solver_gym313` and `solver_gym314` retain plans,
sources, exact inputs/routes, every proposal, timings, partial native audits and
dispositions. There were no expected-invalid controls and no feasibility oracle.
After examining these results they are development regression cases, not untouched
holdouts. One passing case does not establish general reliability.

## Gym use and boundaries

`gym.install(owned_directory, configured_python, document_id, scene)` installs a
retained workspace in the explicitly owned idle Fusion design. Open the gym layout
in diagnostics, then use **Selected material solver v1 → Solve and build**. Changing
the gym alone never launches a solver. Smoothing and UV controls are frozen with
the endpoint/gym payload before the worker starts. Native construction follows
numerical acceptance once; native failure remains visible as a failed disposition.
Cancellation is cooperative during numerical work, not an in-flight kernel abort.

The ordinary diagnostic controller still rejects retired procedures. The selected
controller advertises a separate `active_solver` contract; historical archives
remain replayable. No production harness command, schema or material profile was
replaced. Complete physical compliance, containment, optimality, generalized native
reliability and arbitrary UV rendering remain outside the measured evidence.

The initial315palette round-trip reached the selected worker but its configured
SDK inherited Fusion's embedded `PYTHONHOME`/`PYTHONPATH` and failed interpreter
initialization before numerical work. Evidence and log are retained. The launcher
now removes those two variables; the controller regression verifies that boundary.
A separately pinned316integration run repeats only314case1with UV disabled:
numerical CPU.559s, native generation.863s, named fidelity pass. No UV file or face
attributes are created in this mode. This repeat adds no independent coverage.

Selecting its result then exposed an existing diagnostic-only normalization bug:
very short cubic intervals have tiny raw acceleration despite finite curvature.
The generic `unit` cutoff rejected their bend witnesses. The witness now normalizes
the already positive finite curvature normal by its measured magnitude, preserving
the original curvature threshold. Analytical tests retain the same parabola's
radius/plane at parameter intervals1and1e-7in two spatial orientations. Display
recovery317freezes new source pins before refreshing the **same** completed316body;
its revision is unchanged. No solve, native build, tolerance or historical manifest
is altered by this recovery.

The live316workspace remains retained in the owned design; its accepted body and
selected diagnostics are visible. Gym/diagnostic navigation and explicit run/poll/
select were exercised through Fusion's HTML bridge; native UI pointer actuation
and cancellation during a long solve remain unmeasured. Sources match the final
lock. Maximum sampled Fusion RSS across314/316was713392KiB, below4GiB. Source/UI
launch/display corrections are recorded separately from the unchanged numerical
policy.62focused solver/controller/handoff tests and27affected witness/pinch/
constraint tests pass across scoped invocations; Ruff lint/format, changed-file
IDE inspections, JavaScript syntax and diff checks pass. No repository-wide suite
was run. The native trim-membership failure remains the next bounded investigation.

## Excursion report: conversion parity audit318

The user identifies the large departure/U-turn excursion in the displayed316case.
A frozen numerical-only replay covers that case plus the three distinct earlier
Gym1/2/3configurations, with their original targets and declared radius bounds.
Four planned/evaluated, zero native attempts/builds/full physical audits. No solver
source, budget, tolerance, target or live body changed. Every stage/proposal is
retained under `artifacts/verification/ribbon_port318`; these are examined cases,
not fresh coverage. No invalid controls or general reliability claim.

The cold selected entry point reproduces both first-pass and final archived
geometry with **zero measured difference** on all four cases, sampling129material
stations on center and both ordered edges. Earlier first-pass references are285;
final references are307. The observed case compares to316. This supports numerical
port parity on those configurations, not a continuous equivalence proof. The
approved radius/merge/layout/merge stages were not omitted in the gym conversion.

On the reported case, first-pass length21.888787mm grows to22.983226mm at5%smoothing,
with endpoint chord6.855122mm. Initial explicit departure straight4.899480mm grows
to5.187876mm; total explicit straight15.481740->16.129061mm.65station corresponding
guide RMS4.016938->4.333689mm and maximum6.996649->7.518347mm. These ordered arc
correspondence metrics are not nearest-distance or continuous deviation bounds.
The large excursion exists before smoothing and increases during smoothing.

The first pass uses guide-middle orientation and guide RMS only after material
length in candidate ranking. It has no continuous guide-attraction/deviation
trimming pass. The second pass minimizes curvature and permits up to5%growth,
without a non-worsening guide-deviation gate. Thus unchanged approved mechanics
can retain a long departure on new poses and increase deviation while easing
curvature. Increasing smoothing allowance is not an evidenced solution. Future
compactness work should separate first-pass fold/runway placement from smoothing
deviation preservation, using normalized rules and all four frozen cases. No such
algorithm change or additional native build was performed for this diagnosis.

## Visible pre-path319

User requests the pre-path beside the other gym diagnostics. Gym drafts and frozen
diagnostic contexts now draw it in magenta, even without a route result. The native
display uses the exact cubic; both palette canvases use129samples. The original
chord/3endpoint controls were moved unchanged into shared `prepath.controls`, used
by both `Guide.create` and the renderers. Arrival travel direction is preserved.
The diagnostic Gym layout checkbox controls this reference with its other context.
Display state carries it separately; frozen gym payload bytes/identities, profiles,
solver settings, material geometry and native bodies are unchanged.

319refreshes one already examined316result using fresh, explicitly named viewer
classes and its existing native manifest/controller. Old stateful viewer objects
and archives remain retained. Zero solves, native ribbon attempts or physical
audits. The body revision is unchanged and displayed controls exactly match the
solver's guide. The viewport capture shows the magenta reference crossing the
central gym area alongside the long-excursion route. Display10.519s; this includes
new diagnostic helpers/profiles/palettes and capture, not route-generation time.
Evidence: `artifacts/verification/ribbon_prepath319`. New source lock records the
shared helper/display changes without overwriting historical run fingerprints.

47focused pre-path/guide/solver/handoff/witness/thickness tests pass. Changed Python
and HTML files pass IDE inspections, scoped Ruff lint/format and JavaScript syntax
checks. No repository-wide suite or new geometry generalization test was run.

## Conductor count and performance counters320/321

Both gym palettes now show conductor count plus generation total, route/check wall
time, numerical CPU, first-pass and smoothing subsets, geometry build, optional UV
preparation/storage and fidelity audit timings. Generation is measured solve/check
wall time minus optional UV preparation, plus native geometry construction. Audit
and optional UV storage are excluded. CPU is the numerical worker only. Missing,
negative, boolean, malformed or nonfinite measurements display as unmeasured;
measured zero remains zero. A partial native failure does not fabricate an audit
or total time. The latest job remains explicitly addressable after layout
navigation, while exact endpoint and complete gym-context matching prevents stale
timings from being attributed to a changed draft.

Read-only counter fields are cached by file timestamp/size. Gym counter polling
updates only the counter panel; it does not reset in-progress editor values,
redraw geometry, collect a worker or start a solve. UI counter refresh and source
locks were adopted through fresh palette/controller-view objects, retaining the
same live session, controller state, geometry handles and native body revision.
Zero solves, native ribbon attempts or physical audits. Current316recorded values:
1conductor; generation1.426s=route/check.563s+geometry.863s; CPU.559s; first.158s;
smoothing.340s; separate fidelity audit8.223s; UV off. These remain original run
measurements, not a new benchmark. Initial palette refresh.908s; no geometry work.
Evidence: `artifacts/verification/ribbon_counters320` and `ribbon_counters321`.

20focused counter/controller/handoff tests pass, covering cost exclusion, layout
attribution, partial results/cache refresh and navigation identity. Scoped Ruff
lint/format, changed-file IDE inspection, JavaScript syntax and a bridge-function
check that polling leaves editors intact pass. The live diagnostic panel was
visually reviewed; palette requests acknowledge without errors. No full suite or
new solver/geometry validation was run. Source lock includes the counter display.

## Stale diagnostic cleanup322/323

The user reports old gym objects/pre-path remaining after a layout change. Live
inspection322finds two visible gym-context groups in the active diagnostic root,
only one tracked by the viewer, plus a visible retired workspace. Root cause:
`enable_gym` reset the already-created `_gym_group`/`_gym_id` when attaching the
workspace, orphaning that initial group. It now preserves both handles and manual
layer visibility. Normal context replacement can therefore remove its prior group.
Selected installation also retires previous owned workspaces in the same document,
with an active-job guard. Retirement hides view/palette handles and the old owned
native output; it does not delete histories or ribbon bodies.

323creates one current replacement before removing the two identified stale
transient context groups, and hides the two retired workspace views. The current
body revision is unchanged. An acknowledged HTML-bridge switch to another existing
gym context and back leaves exactly one gym group after each change, with no event
error or retired view visible. The original user layout/body visibility are restored.
No solves, native ribbon attempts or physical audits; this is display verification,
not added geometry coverage. Cleanup.266s; source pins and partial evidence are in
`artifacts/verification/ribbon_cleanup323`; initial inspection is `inspection322.json`.

16focused palette/handoff tests pass, including repeated binding/layout replacement,
manual layer visibility, retained case histories and refusal to retire an active
job. A test fixture initially lacked its fake root; that setup was corrected before
the passing run. Scoped Ruff lint/format and changed-file IDE inspections pass;
the live cleaned viewport was reviewed. No full suite or new complete workspace
installation/native build was run for this fix. The selected solver/source lock
is retained with these display-lifecycle changes.

## Smoothing contact certificate324–330

The user's N3/D.75 gym layout (seed719117695) spent35.446s at5% and41.404s
at10% smoothing while returning the original route unchanged. Each pass rejected
its proposals as contact-unresolved: easing inserted short straights between folds,
so the original shared-cap certificate no longer applied to those fold pairs.
The interval checker exhausted its unchanged20,000-pair/depth36 bounds.

`contact_caps.straight_bridge_pairs` extends the same half-space argument across
continuous, straight-only bridges. The first cell must remain behind its end cap
and the second ahead of its start cap, using the existing cell-specific tests.
Their rigid frames must join, cap normals must agree, and positive signed plane
separation must exceed a conservative floating/frame-error envelope. Tiny gaps,
malformed joins, intervening folds and returning interiors retain subdivision.
No adjacency-wide exemption, clearance tolerance, geometry repair or budget increase
is introduced. This remains a floating analytical certificate, not exact arithmetic
or a complete physical audit. The shared checker can also resolve previously
unresolved first-pass candidates; first-pass geometry need not remain identical.

Four independent, examined gym development layouts were frozen before the fix:
the triggering layout plus priorGym1/2/3. They are not untouched holdouts.325uses
the same frozen first passes/settings: trigger andGym1improve; Gym2/3reproduce their
previous routes. Trigger smoothing.585s; curvature score220.575→38.319 (82.63%lower),
peak2.484→.460; maximum sampled trajectory movement2.872mm. Eight radius and eight
layout steps are accepted. Length21.206→22.266mm respects the original shared5%
ceiling. Gym1further improves score131.952→120.050; smoothing1.839s. Gym2/3timings
.417/.216s. All4final numerical cap/metric/contact gates pass.

326cold entry-point verification reproduces first/final geometry for trigger,
Gym1andGym2. Trigger cold solve/check.786s CPU.785s, including first.209s and
smoothing.573s. Gym1solve2.378s/smoothing1.786s; Gym2solve.534s/smoothing.408s.
Gym3hits the deliberately strict archive-parity assertion: the new checker accepts
rank0at154.186705mm instead of the previously accepted rank1at154.190348mm.
The stopped report is preserved.327reviews its retained trace without another
solve: first sampled difference.08322mm; final.00754mm; final cap3.15e-11mm,
metric3.33e-16, contact separated and5%ceiling retained. Its curvature score changes
slightly (69.893→69.900, each normalized to its first-pass length); this is not an
additional smoothing gain. Gym3was numerically attempted, despite326erroneously
leaving it in its unattempted list after the assertion. Its missing cold timer is
unmeasured. No cold or smoothing retry was run.

After stopped-run review,327/328attempt only the two changed cold-parity results.
Native construction2/4attempted,2/2built and passed unchanged named surface,
ordered-guide, seam and cap fidelity checks;0full physical audits. Gym2is unchanged
and has no fresh native claim; Gym3's changed cold variant remains diagnostic and
natively unattempted. Trigger geometry.862s, separate audit12.012s; Gym1geometry
.814s, audit7.890s. The solve<=construction timing goal passes trigger and misses
Gym1(2.378>.814s). Optional UV is off; no appearance/texture expense is counted.
The old308/314fidelity failures remain unresolved and are not reclassified.

329/330imports the trigger as an explicitly labelled5%variant through the existing
HTML bridge, preserves editor settings/history, and replaces only the owned native
display with its verified body. The body revision is unchanged by display movement;
matching counters and selected result acknowledge without event errors. Both native
captures and the live viewport were reviewed.52focused contact/aesthetic/selected
solver tests pass across scoped runs; scoped Ruff lint/format and changed-file IDE
inspections pass. No full QA suite or production promotion. Frozen sources, plans,
all dispositions and the parity-stop review are under
`artifacts/verification/ribbon_smoothing324`; source lock includes the certificate.

## Diagram orientation331–338

The diagnostic canvas used Y-up; Fusion uses Z-up. Both canvas presets now use
the native isometric camera at (+X,-Y,+Z), with a right-handed camera basis and
matching back-to-front depth sorting. Reset restores that preset. Canvas orbit
remains independent of the Fusion camera; world targets and routes are unchanged.
The initial Z-up-only correction still faced the opposite XY direction; live
review caught that intermediate mismatch before the final camera correction.
Both scripts parse,20translated/orbited projection comparisons pass, the preset
matches the native camera basis, and both HTML files have clean IDE inspections.
The refreshed diagnostic diagram was reviewed beside the same native ribbon;
body revision, selected result, histories and counters are retained. The current
local review page adds only initial scrolling to center the canvas. No solves,
native attempts or added geometry coverage. Updated source lock and evidence:
`artifacts/verification/ribbon_diagram331` and `ribbon_diagram334`.

## Unresolved sub-resolution topology339–347

The new N3/D.75 gym layout in jobs `selected-b61f749b2d6c486683bca3f933ebbfc4`
and `selected-6e6fd8a3140b47f488467f101d1ecfa3` passes numerical checks and builds
a solid, but the strict native audit rejects142faces where152were authored.
These two user builds repeat one independent configuration. Its terminal straight
is8.613755e-8mm long. Read-only340inspection retains the same body revision and
confirms matching retained NURBS controls, followed by two planar caps; a complete
ten-face terminal band is absent.339first used the generic surface getData layout
on a Plane and failed without changing geometry;340uses explicit surface families.

341freezes that trigger plus three distinct gym collateral maps before changes.
342exact flat-run/lead coalescing preserves sampled full-thickness positions within
2.20e-14mm across4/4maps and all numerical cap/metric/contact gates. One cold trigger
solve1.172s includes smoothing.958s; others are frozen-map replays, not new solves.
343builds the trigger with the expected122faces and passes4200surface samples
(maximum4.12e-9mm), ordered guide positions/tangents and both caps, but fails one
strict shared-edge seam check between faces118/119. The subnanometre tip lead
has no shared native edge. The three collateral native attempts remain unattempted.

After separate frozen reviews,345uniform1024construction-unit conditioning still
fails the seam gate.347exact bend/positive-exit NURBS consolidation instead returns
122native faces where its authored compact layout expects102: the kernel partitions
the composite surface again. Its surface/guide/cap audit is therefore unattempted.
Neither experiment relaxes an audit tolerance, moves a target or drops material.
Each stops on its first native failure; no alternative scale or automatic retry.

Independent scope:4planned/numerically evaluated,1/4natively attempted (three new
attempts of that same trigger),1/4built but unaccepted,0/4named-fidelity passes and
0full physical audits. Three collateral configurations remain natively unattempted
in every stopped phase. No untouched holdouts or generalized construction claim.
New construction times1.904/3.950/2.913s; native phases15.950/26.896/3.660s including
audits. Retained RSS samples remain below4GiB; in-flight peak is unmeasured.

Candidate unit checks validate resegmentation, exact surface span concatenation
and optional material inverse coordinates; they do not validate native topology.
117focused candidate tests pass across scoped runs. Ruff passes. IDE checks find
pre-existing archive-duplication/shadowing/Fusion-method-name/broad-boundary warnings;
newly introduced shadowing was corrected. Full QA was not run.

All candidate executable/test changes were reverted after the native failures;
the selected source lock is restored to its prior accepted implementation. No
failed policy was installed in the live workspace. Failed bodies/reports and source
copies remain under `artifacts/verification/ribbon_flat341`, with read-only evidence
in `ribbon_topology340`. The original user's failed job remains rejected/hidden.
This case is unresolved: preserving a sub-resolution native seam requires a new
construction investigation, not relaxing the gate or claiming the solid passed.

## Low-cost solver alternative349–351 — proposal only

The user asks whether the unresolved topology can be addressed cheaply. A change
to the planned route requires an explicit exception to the recorded fixed-material-
plan construction investigation. No accepted solver or native geometry changes
were made while measuring this alternative; native feasibility remains untested.

349/350try existing bounded Newton retraction after zeroing the8.61e-8mm straight.
Reclosure takes6.53ms CPU but increases peak curvature3.588e-9/mm and is rejected
by the unchanged peak gate.349fails to retain individual gate values before its
assertion;350preserves the same algorithm/settings and records them before stopping.
Both stopped outcomes remain; the three collateral cases are unattempted there.

351uses fixed fold angles/banks and nonnegative radius growth instead. Existing
positive straight slots may redistribute, tiny slots at/below the existing1e-7mm
cap-closure scale are fixed at zero, and absent slots remain zero. A bounded affine
projection solves XYZ closure, with the original total-length ceiling added when
needed; no new routing/smoothing pass or alternate thresholds. Four examined gym
layouts are screened: the trigger changes, three others remain exactly unchanged.
Trigger cleanup takes1.186ms CPU/1.187ms wall with two linear projections. Maximum
sampled full-thickness movement1.721e-7mm; cap error1.602e-14mm; material metric
4.44e-16; contact separated; peak curvature unchanged; total length changes only
by floating roundoff(-7.1e-15mm). Unchanged cases cost11–16microseconds each.
Trigger checking/diagnostic sampling.0617s is separate from the cleanup timer.

These are4numerical development checks,0native attempts,0native fidelity passes,
0full physical audits; no native success is implied. This deliberately changes
the planned material path slightly, unlike339–347. Approval was requested for
that specific solver-policy exception and one bounded native check. Evidence:
`artifacts/verification/ribbon_cleanup349`, `ribbon_cleanup350`, `ribbon_cleanup351`.

## Approved numerical cleanup352–358

The user's “yeah, lets try it” approves the351microscopic reclosure exception and
one bounded native check. The selected solver now applies this deterministic rule
after aesthetic smoothing and before final validation/optional UV metadata. The
1e-7mm sliver floor follows the existing cap-closure scale; it is not a universal
Fusion minimum-feature certificate. Fold angles/banks/order/profile remain fixed,
radii may only grow, existing positive straights may redistribute and absent slots
stay zero. At most2*(variable count+1)linear projections run, with no new search or
smoothing pass. Unresolved closure fails explicitly instead of sending the original
sliver to construction. Smoothing0still disables aesthetic smoothing; numerical
cleanup remains active. The original native builder and all audit gates are unchanged.

353replays the four frozen341development configurations:4/4numerical checks pass;
only the trigger changes, with exact sampled parity to351. Cleanup costs1.312ms CPU
(1.313ms wall); the three unchanged maps retain object identity and cost7–9microseconds
CPU. These are development cases, not untouched holdouts. Its additional cold solve
stops at2seconds because the harness hashes every source at every checkpoint.
354rejects the missing completed prerequisite before any native attempt.355reviews
that monitoring overhead and uses the existing worker's0.5second source-check
interval, retaining the same2second cold bound/search budgets. Cold solve passes
with exact sampled replay parity:1.16949s wall/1.16855s CPU, including first pass
.18756s, smoothing.95507s and cleanup.001246s wall. Cap error1.602e-14mm, material
metric4.44e-16 and contact separated. Maximum sampled movement versus the original
route remains1.721e-7mm; peak curvature is unchanged and total length changes only
by roundoff. Optional UV metadata is off for this check; when enabled it is computed
from the cleaned route, without creating textures or appearances.

356executes exactly one native attempt of that trigger under the120second/4GiB
limits: built and all named fidelity checks pass. Expected/actual142faces;
4900surface samples maximum4.121e-9mm,270seams without failures, ordered guides and
both caps pass. Geometry generation2.58502s (translation.24843s, definition.99652s,
kernel1.34008s); audit19.12234s; native-operation wall23.84451s. These are separate
timers, not all generation expense. Sampled RSS remains below4GiB; in-flight peak
is unmeasured. Scope:4independent numerical configurations,1native attempted/built/
named-fidelity pass,3native unattempted by agreement,0full physical audits. Earlier
user failures and339–347stopped constructions remain rejected historical outcomes;
this success follows the explicitly approved microscopic change to the planned path.
The separate308/314native failures are not resolved by this check.

357imports the accepted result into its matching idle gym, preserves1%smoothing/
UV-off preferences and existing histories, and updates counters to this exact job.
358confirms the selected ID, clear event error, source pins and unchanged native
revision after display translation; the accepted body is visible and captured.
The source lock includes cleanup.23focused selected-solver/cleanup tests pass;
Ruff lint/format pass. IDE inspections introduce no findings; solver/settings retain
pre-existing archive-duplication weak warnings. Full QA, other native configurations
and full physical audits remain unrun. No production promotion or further batch.
Frozen plans, monitoring-stop evidence, native audit and live review are retained
under `artifacts/verification/ribbon_cleanup352`.

## Outward terminal bends359–363 — routing quality unresolved

The user rejects the visible backwards exterior curvature in the356/357result.
Construction/fidelity success does not establish acceptable route shape; the earlier
handoff understated that distinction. Keep the result as built/fidelity-passing
development evidence while treating this layout's routing quality as unresolved.

359read-only live inspection confirms the selected355trigger, matching targets,
idle owned document and no event error.360compares the same four frozen development
maps before/after cleanup, with no solves or builds. Trigger first-pass snapshots
before/after the cleanup implementation are exactly identical. All four routes
retain identical fold angles/banks; trigger maximum sampled full-thickness movement
is1.7213429e-7mm and the other three maps have zero movement. The first and last
curved center-lane directions versus directed cubic cap curvature have cosines
-.89549/-.71413 in the original first pass, the original smoothed route and the
cleaned route. The visible outward turn predates cleanup; removing that cleanup
would retain the turn and restore the native sliver failure. This does not establish
that all possible future cleanup inputs preserve route quality.

361archive harness stops on a smoothing row with no `stage`; no solve/build occurs.
362reviews that error and reads optional stage tags under the same2second bound.
All11closed first-pass candidates have the outward start. Eight `guide-0-1`
candidates have both outward terminal signs; three `guide-0-0`candidates reverse
only the exit sign and are longer. The direct and two remaining guided families
have no nonnegative basic position closures. This is a limitation of the offered
frames/rotation families, not proof that better endpoint routing is impossible.
Changing candidate ranking alone cannot select an absent inward-start candidate.

363screens one explicit representation alternative across those same four fixed
gym inputs: both signs of the free intermediate width, preserving ordered endpoint
frames and all existing algebraic rotation/nonnegative-position equations. The
screen broadens to at most10families instead of the selected6and records that cost
rather than silently changing the solver budget. Trigger9families/23closed supports
still offer no pair of positive terminal guide-curvature signs; neither does Gym1.
Recent/Gym6already have such candidates. No contact attempts, smoothing or native
builds run; this representation experiment is unsuccessful and is not installed.
Guide-curvature signs remain diagnostic preferences, not new physical rejection
rules: one previously liked Gym1also has negative signs, so a blanket sign gate
would not be justified by this evidence.

Scope:4/4archived maps compared and4/4inputs numerically screened,0new native
attempts/builds/fidelity audits/full physical audits. All screened candidates have
contact unmeasured. No invalid-control cases or holdouts. Trace.193s, archive.039s,
representation screen.584s wall; no native or end-to-end generation benchmark.
Selected solver, source lock, live geometry and native history remain unchanged.
The remaining correction belongs in first-pass fold-direction construction; no
successful correction or renewed solver-quality acceptance is claimed. Evidence:
`artifacts/verification/ribbon_curvature359`. Prose diff reviewed; application QA
and IDE code inspections are not repeated for this documentation-only change.

## Second excursion365–366 — 2026-11-02

The user identifies another visibly excessive hairpin in the live gym. Read-only
365captures its distinct fixed input: seed557726847, Aface8/roll0/zone20 and
Bface8/roll2/zone17, N3/D.75, endpoint separation5.266593mm. Job
`selected-7265ad6611b54fbbbe2c9dd2242dc699` is completed with named native fidelity
passing, while the diagnostic selector is `input`. The photographed native body
and latest counters belong to that job; no display or geometry is changed.

Archived first-pass length72.876677mm, final73.605444mm. First-pass explicit straights
are9.816056/16.422036/31.171350mm. Maximum sampled ordered guide deviation increases
33.259502->33.464300mm during smoothing. The excursion exists before smoothing;
cleanup reports `not_needed`, zero projections/removed slots. Existing cold timing:
first pass.102549s, smoothing.560580s, total numerical.670823s/.670289s CPU. These
are archived measurements, not a new solve or comparative performance claim.

366freezes route/trial/native hashes and the unchanged selected source pins before
one bounded diagnostic screen (2seconds, at most8exact half-turn factor branches,
one contact attempt maximum,0native attempts). Both endpoint tangents and ordered
widths are antiparallel. Each direct fold is exactly pi; its signed alternatives
and mirrored banks represent the same terminal frame but different spatial
displacements. All8symmetries of that direct two-fold representation are screened
through the unchanged nonnegative affine allocation and full-cap guard. Zero closed
candidates: the missing-sign hypothesis supplies no correction in this representation.
Actual.02117s wall/.02115s CPU. Contact is unattempted because no candidate closes;
there is no contact or physical infeasibility claim. No family/solver change is
installed and no smoothing, native build or fidelity audit is repeated.

Scope:1new independent gym input archived/numerically screened,0new native attempts,
0new builds/audits/full physical audits. This increases the retained diagnostic
inventory, not successful geometry coverage or holdout evidence. The old successful
native fidelity status is preserved separately from unacceptable route compactness.
Keep this fixed case alongside359's outward-turn case for the general first-pass
correction; do not infer a physical excursion/length cap from endpoint distance.
Evidence:`artifacts/verification/ribbon_excursion365`. This turn changes maintained
notes only; prose/diff checks apply, application tests/IDE code checks are not rerun.

## Guide influence traced367 — 2026-11-02

The user asks why the pre-pass guideline is being ignored. Read-only selected-call-
path inspection identifies a concrete gap between continuous loose directional
guidance and the implemented policy. `prepath.controls` supplies the same cubic
to solving and drawing; the guide is not missing or independently rotated.
`joint_route.frames.middle_frame` samples only parameter.5for tangent and computes
an intermediate ordered width. Its origin is explicitly informational; orientation
factorization uses the frame vectors. The resulting topology retains folds and
`middle_after`, not a positional guide anchor. In the selected path `middle_after`
is written to trial metadata but never used to constrain allocation.

`allocation.Model.equations` solves final endpoint XYZ only. It has no guide or
interior positional/directional objective. Nonnegative basic supports can therefore
carry the correct middle orientation far from the cubic. `construct` ranks length
first and guide RMS second, so distance matters only for ties in length rounded
to10decimal places. Measured mean direction loss is archived but never used in
selected candidate ordering/acceptance. The selected aesthetic stages receive no
guide; their curvature objectives and physical/cap/length gates do not preserve
guide agreement. This is the implementation's limited influence, not a failed
guide load or Fusion translation problem. Family limitations also remain: changing
the ordering cannot choose a close route absent from the generated candidates.

367freezes sources and the365case archives before a2second read-only measurement.
At its derived middle boundary after two folds, first-pass tangent matches the
cubic middle tangent exactly (vector error0), ordered width error2.388e-16, but
that boundary is18.912718mm from the guide midpoint. It occurs at32.511%of route
material length. This directly demonstrates orientation matching without spatial
following; it does not prescribe a rigid midpoint landmark or certify a replacement.
Actual measurement.00754s,1archived case inspected,0new solves/native attempts/
builds/audits/full physical audits. No solver, source-lock or live-display change.
The correction should give ordered guide position/direction influence during first-
pass construction and preserve that preference during smoothing under unchanged
physical gates. No new weights, deviation threshold, algorithm or successful fix
is asserted by this diagnosis. Evidence:`ribbon_excursion365/{plan367,result367}.json`.
Documentation diff reviewed; application tests/IDE code checks unrun for prose only.

## Guide tuning368–372 — rejected and restored

The user requests stronger pre-pass guidance. Five fixed gym development inputs
are frozen before this work: the365hairpin,359outward-turn/sliver trigger, and
the three collateral maps retained in352. Repeated variants are these same five
independent configurations, with no holdouts or invalid controls. Native/profile/
material rules remain fixed and no new native operation or appearance is scheduled.

368adds exact single-fold tangent steering at ordered guide arc fractions1/4and3/4,
with balanced algebraic middle rotation roots, followed by unchanged nonnegative
XYZ closure. It retains existing families and ranks by squared chord-normalized
guide RMS plus directed tangent mismatch. Limits3s/case,15s/phase,9families/six
folds,12contact attempts/case,4GiB RSS. All5first-pass screens complete. None of the
new endpoint-steering families supplies a closed candidate for either trigger; guide-priority ordering
does improve the large retained case through a different existing family. Both
problem cases retain their original first-pass branches. No promotion follows.

369reviews the large bank-dependent leads of the middle two-fold rotation and
adds the existing exact orthogonal three-fold decomposition, retaining the same
case/time/family bounds. All5screens complete; neither trigger improves. This
representation alternative is rejected and remains artifact-only.

370then tests an implementation retaining the original6families/12contact budget:
up to16affine projected steps fit ordered fold-cap points toward guide positions,
followed by distance+direction-first ranking. All original basic allocations remain
available; contact/cap/material checks stay unchanged. A first-pass-relative guide
cost allowance across aesthetic stages prevents drift, with candidate stage outputs
explicitly provisional. Matched baseline uses the exact prior constructor hash,
same current cleanup/metric instrumentation and1%smoothing/UV-off/radius settings,
with the new aesthetic guard disabled. Its instrumentation is not an uninstrumented
historical speed benchmark. Limits5s/solve,40s/phase,10cold solves over5inputs,4GiB.

All5matched baseline/candidate pairs complete numerically, but tighter guide costs
reject entire aesthetic stages. Candidate full-cylinder curvature exceeds matched
baseline in all5cases; peak lane curvature also increases. This reintroduces sharp
features and is unacceptable despite improved guide metrics. Candidate cold solve
times.514–3.388s;35focused prototype tests pass, but do not certify route quality.
No native build is attempted or inferred from these passes.

371uses saved routes only to check monotone guide correspondence:33route samples
match65guide samples through a prefix-minimum dynamic program, endpoints fixed,
interior guide indices nondecreasing. It addresses rigid same-percentage matching
without requiring positional landmarks.5archived pairs examined,.07092s,0solves.

372reviews/replaces the overly restrictive cost allowance with one shared sampled
spatial corridor (first-pass maximum plus profile half-width and the configured
extra material length), and uses monotone distance/direction preference in fitting
and ranking. Same5s/40s/4GiB/five-input matched plan. The new hairpin is exactly
unchanged; the359trigger has better guide metrics but much higher curvature because
its layout-easing stage is still rejected. Recent gym guide cost worsens slightly
.06203666->.06256330 despite lower curvature, triggering the registered stop. Both
remaining matched comparisons(Gym1/Gym6)stay unattempted in372. Four focused tests
of the revised preference/corridor pass; this does not override the geometry stop.

Independent accounting:5/5inputs screened in368/369/370,3/5matched pairs completed
in372and2/5unattempted there;0/5native attempted/built/fidelity-audited/full physical
audited. Across phases there are10first-pass screens and16complete cold solves,
not26independent configurations. Selected outputs pass numerical gates, but no
candidate meets the combined routing/aesthetic improvement goal. Measured phase
wall total22.0941s includes the read-only371check, excludes implementation/QA and
orchestration; no token/usage cost or in-flight memory peak is measured.

All tuning code/tests are removed from the selected implementation after the
regressions. Rejected sources remain in`ribbon_guide372/rejected-source` with plans,
trials and unsuccessful/stopped reports retained in368/369/370/371/372directories.
The pre-existing accepted cleanup/source lock is restored exactly and lock.verify
passes; earlier sliver/build fix and live Fusion geometry are untouched. Candidate
IDE warnings are not installed; only prior archive-duplication findings remain in
the restored code. No full QA or new Fusion checks run. Documentation diff/check
passes; unchanged restored checks are not repeated. The next investigation must
give construction joint orientation/placement freedom against the ordered guide;
merely stronger ranking or post-stage rejection is insufficient on these inputs.
No successful guide correction, solver-quality acceptance or further run is claimed.

## Explicit contraction373–374 — missing objective isolated

The user emphasizes the dominant straightaways and rejects inference that the route
cannot contract. Selected-call-path inspection confirms a missing objective:
layout easing differentiates full-cylinder fairness; its direct straight-coordinate
gradient is zero. Straight travel changes only through projected closure while
rounding folds. Length appears as a ceiling derived from the already long first
pass, not a descent target. Merging considers compatible common-crease turns only.
The separate historical angle/straight contraction is not invoked by the selected
pipeline. These are numerical/representation choices, not material impossibility.

373freezes the same five fixed maps and source lock, then probes one negative total-
length gradient projected onto exact-cap closure, suppressing first-order aggregate
curvature growth. Same signed folds, bank/radius/model bounds and physical floor;
four halvings with existing bounded nonlinear retraction. Limits2s/case,10s/phase,
one direction and at most one contact attempt/case,4GiB,0native attempts. A shorter
candidate must retain cap/material, nonincreasing peak lane curvature and initially
also nonincreasing full-cylinder fairness. All5probes complete in.25108seconds.
Each offers
a negative length derivative, but no candidate passes all those acceptance gates.
The report label`no_length_descent`means no ACCEPTED contraction in this probe;
it does not mean no decreasing direction or no shorter trials were found.

For the new hairpin, first trial73.605444->72.065943mm preserves caps(error9.305e-10mm)
and material metric5.573e-16; peak lane curvature improves.763226->.734410/mm.
Its full-cylinder fairness7.128075->7.139008increases only.15337%, which vetoes
contact in373. Thus an aesthetic monotonicity condition blocks a physically
promising shortening move. This is not proof of complete compliance or the ability
to remove the whole excursion. Center-lane flat material includes explicit
straight42.254432mm plus fold flat leads10.768969mm,72.04%of the final route;
the original first pass is78.78%explicit straight travel alone.

374reviews that distinction and repeats the SAME one-direction/four-halving probe,
reporting aggregate fairness as a goal rather than a physical veto. All physical
gates and nonincreasing peak lane curvature remain. Three of five candidates now
shorten and pass thick-contact checks: new hairpin73.605444->72.065943mm,
recent19.265524->18.889226mm and Gym1 12.464389->12.255655mm. CPU per successful
probe.02663/.03146/.03867s, including numerical checks/contact; phase wall.18951s.
Aggregate fairness
increases are retained, not hidden. The359trigger and Gym6 remain unaccepted due
to peak-lane-curvature growth; their contact checks are unattempted. No resampling,
extra iterations, physical-gate relaxation or further refinement occurs.

Independent scope5/5numerically probed in each phase,3/5accepted numerical
contractions in374,2/5unaccepted there,0native attempts/builds/fidelity audits/full
physical audits. No invalid controls or holdouts. No selected code, source lock,
live display or earlier native result changes. This supports a bounded contraction
test as a distinct stage before final smoothing, with total length as the primary
objective; it does not establish convergence, visual quality or full contraction.
It also refines372's conclusion: a larger orientation-family redesign is not yet
shown necessary for incremental length gains. Sources/plans/all dispositions and
candidate maps:`artifacts/verification/ribbon_contraction373`and`374`. Prose-only
maintained changes; diff checked, no application QA or new Fusion checks required.

## Historical contraction trace375 — requested comparison with the original change

The user explicitly requests returning to the modification that successfully
contracted the original geometry, rather than proposing another small move. This
review distinguishes the historical stages and their current call paths.

`2a94f63`introduced fixed-fold straight-only nullspace contraction(258/259), then
bend-first rewriting(263/264). `f5d978d`introduced radius/straight LP allocation
(267/268), guide-branch selection(270), and the major joint first-pass replacement
(285/289). Radius allocation minimizes explicit straight travel FIRST, then total
material, while only growing radii and never increasing the input material budget.
It reduced straight travel in all four original267inputs; accepted contact fractions
and the native evidence remain as recorded in its own NOTES. This is different
from later curvature-only radius easing, despite both changing radii/straights.

`d6b1538`and`068acbb`added curvature/aesthetic easing and layout-relative banks/
angles/radii/runway freedom(296/307). The307scale/zero-runway corrections remain
in the active source. On the new hairpin the layout pass runs to its eight-iteration
budget; the combined radius/layout second pass reduces explicit straight travel
57.409442->42.254432mm. It is not being skipped. Its objective, however, is curvature
rather than total-length contraction.

The `c669883`gym handoff calls `joint_route.construct` directly, then radius easing,
merge/layout easing/merge. It calls neither the original straight contraction nor
the straight-first radius allocator. The radius allocator's model/program/solve
files still match`f5d978d`byte for byte; there is no implementation regression in
those files. Inclusion in the source lock does not mean they execute.

The joint first-pass math is also retained across that handoff: rotation families,
guide midpoint orientation, affine allocation and length-first ranking were not
replaced. The substantive entry-point difference is comparison-based improvement
versus cold construction. Historical `solve(source,guide)` rejects longer/more-fold
candidates and retains the prior accepted route if nothing improves. The gym
`construct(boundary,guide)`has no prior route/comparison and selects among whatever
closed finite families it generates. Continuous positional guide following was
not present in the earlier successful joint implementation either. Earlier good
comparison results therefore do not establish that the cold routine has an effective
excursion-repair pass for every new input.

375freezes the unchanged sources, original four267inputs and both current problem
inputs(first/final variants). It replays only the original pure radius LP and
straight-only nullspace diagnostic, with1s/map/8sphase and no contact/native calls.
All original four controls again offer their original full LP straight reductions:
32.933069->24.814734,11.186927->7.243102,16.631904->3.043508and257.332563->0mm.
These are unconstrained-contact optima; the original Gym2/Gym3accepted half-steps
remain the historical contact-verified outputs, not replaced by this replay.

For the new hairpin first pass, the exact old allocator retains57.409442mm straight
travel and72.876677mm total: no straight reduction under its fixed-angle/bank/
nonincreasing-length contract. Straight-only nullspace descent is also zero.
On the smoothed new hairpin, it offers only42.254432->41.597576mm straight travel,
with total material unchanged73.605444mm; contact is unattempted. The outward-turn
trigger offers no old-LP reduction either before or after smoothing. Thus merely
reconnecting that allocator would not remove the new long detour. The current
first pass has already selected a basic minimum-material allocation inside its
fixed rotation family; the old downstream move cannot freely relocate those bends.
This is a limitation of that representation/move set, not geometric infeasibility.

Independent scope:6saved gym configurations,8maps evaluated(original4plus2variants
of each current input),0contact attempts/native attempts/builds/fidelity audits/
full physical audits. Actual.11245s; no failed/unattempted trace maps. Original
native successes remain historical, not new coverage. No source/lock/live geometry
change; current lock verified before/after. This corrects the earlier oversimplified
claim that a missing contraction call alone explains the full excursion. The
next investigation should target the fixed orientation/placement contract and
length-vs-curvature objective in this existing chain, with the original controls,
rather than invent guide weights or infer physical impossibility from no-op output.
Evidence:`artifacts/verification/ribbon_history375`. Prose diff checked; no new
application QA or Fusion operation required for this read-only historical trace.

## First-pass optimization repaired376–384 — 2026-11-02

The user explicitly requires this repair inside first-pass routing; second-pass
smoothing remains aesthetic. `joint_route.construct` keeps the existing bounded
coarse rotation/allocation/contact construction, then jointly adjusts signed bend
angles, banks, radii and straight runway before returning its first-pass result.
Angles are no longer frozen to the coarse family or its original sign. Radius
can move down to the unchanged declared physical floor; the original peak/fairness
is not a routing restriction. There is no diameter/endpoint-distance shortcut or
case-specific coordinate rule. Production harness code and native construction
are unchanged. Historical rejected guide tuning368–372 remains removed.

Total material length is the descent objective. Projection preserves six cap
equations; bounded Newton retraction and independent complete ordered-cap checks
retain closure. Every accepted trial strictly shortens material, passes sampled
local metric and separated thick-profile contact, and does not exceed the original
coarse route's sampled guide cost. Guide correspondence uses33material stations
matched to65ordered reference samples with nondecreasing indices and fixed ends;
cost combines chord-normalized squared distance and directed tangent mismatch.
This is a sampled preference, not a continuous proximity or feasibility proof.
It does not veto the later aesthetic stages, unlike rejected370/372.

Limits:16iterations,6proposal halvings,12optimization contact proposals and1024
contact subdivisions. Construction steps allow25%of initial layout length and
pi/4angular changes; six Newton corrections/four correction halvings retain the
existing smaller correction steps. Coarse and final contact retain20000pairs and
depth36. A separated coarse certificate already exceeding1024pairs retains that
route without further optimization contacts. This resource gate is conservative,
not proof that improvement is impossible. Exhaustion retains the latest accepted
route; external time/source/memory stops propagate. No automatic budget increase.

Shared flexible geometry/retraction moves out of the aesthetic module, while its
original sign/radius restrictions, curvature objective, peak gate, trust defaults,
length allowance and stage order remain intact. Immutable initial layout data is
cached. Zero-angle folds become flat leads and adjacent flats coalesce. Existing
numerical sliver cleanup still precedes final checks/optional UV metadata. Thus
smoothing0runs the repaired routing and cleanup, while disabling aesthetic easing.
UV remains optional/off in this experiment; no appearance or texture is created.

### Frozen phases and retained unsuccessful outcomes

376stops during input preparation because an old Gym3first-pass archive is absent:
zero case evaluations/native attempts.377reviews that prerequisite and uses the
original285Gym3map, with its distinct hash recorded. Its prototype shortens the
first three cases but times out during the small Gym1contact check under4s/case,
20s/phase; the last Gym6case is unattempted. Completed/partial accepted trials and
the stop remain recorded. This motivates bounded optimization-only contact work,
not loosening physical separation or continuing the stopped phase.

378uses the implementation with construction-size steps and1024pair optimization
budget:5/5numerical replays complete,4shorter/1retained,0native. It also proves exact
parity against the prior committed aesthetic model on these five initial maps,
including geometry/labels, gradients, residuals and Jacobians.379completes5cold
endpoint solves at0%smoothing plus two1%native-input solves,0native attempts.
381adds the coarse-contact work gate, verifies the current source lock and repeats
the same seven solves under the frozen6s/solve,40s/phase,4GiB plan. Every final
geometry matches379exactly. The copied original plan narrative is retained; the
new source hashes and this explicit work-gate disposition distinguish381.

All repetitions are the same **five independent examined gym configurations**,
not new holdouts or additional coverage. Cold solves start from endpoints and the
pre-path, not archived successful geometry. Here are381zero-smoothing results;
the comparison length is that run's separated coarse candidate, not a historical
body or the slightly different original285Gym3route:

| Case | Coarse -> optimized first pass mm | Optimization s | Cold numerical wall s | Disposition |
| --- | --- | ---: | ---: | --- |
| new-excursion |72.876677 ->37.130034|1.272601|1.475161|49.05%shorter,12accepted/contact budget|
| trigger |41.756299 ->35.646795|1.706230|2.042943|14.63%shorter,7accepted/contact budget|
| gym-recent |19.123811 ->17.310350|1.278890|1.523652|9.48%shorter,12accepted/contact budget|
| gym-one |11.870847 ->unchanged|.003045|1.110327|Coarse contact work gate,0optimization contacts|
| gym-six |154.186705 ->153.666098|.102908|.226670|.338%shorter,1accepted/proposal budget|

All five final numerical cap/material/contact gates pass; maximum cap residual
8.927e-9mm, maximum sampled metric6.019e-16. Trigger at0%smoothing still needs the
existing4.809e-8mm sliver cleanup, which succeeds. The two1%native-input results
need no cleanup. The coarse work gate reduces Gym1's otherwise wasted~1.95s of
optimization to~3ms while retaining the identical validated route. It does not
establish an across-the-board speed gain or physical inability to contract Gym1.

### Native382 and matching live gym383/384

382freezes exactly two native attempts,120s/case,250s/phase,4GiB RSS/3.8GiB launch
headroom; stop on the first failure, no retries. Both1%smoothing/UV-off problem
configurations build once and pass the unchanged named native fidelity policy.
Three other numerical configurations are natively unattempted by this scope.
No failed/skipped/unattempted case within the two-case native plan; phase37.924s.

| Case | Final mm | Numerical wall / CPU s | Native generation s | Named fidelity audit s |
| --- | ---: | --- | ---: | ---: |
| new-excursion |37.501335|2.003402 /2.001286|1.771372|17.382903|
| trigger |36.003263|3.378555 /3.318026|1.199254|14.069132|

Generation includes translation, surface definition and kernel construction;
audit/graphics are separate. New-excursion numerical first pass1.363381s (of which
optimization1.256523s), aesthetic smoothing.627070s. Trigger first pass2.110159s
(optimization1.896643s), aesthetic1.235346s. Full numeric time exceeds matched
native generation in both cases: the speed goal is still missed. This is bounded
extra routing work, not an assertion that the old route was geometrically necessary.
New-excursion gym generation counter totals3.775s (numeric2.003+native1.771).

Both bodies have142faces; combined9800surface samples,540ordered seam chains and
four complete caps pass. Maximum surface error2.838e-9mm; ordered guide position
error2.467e-9mm; zero failed points/seams. Trigger uses four existing actual-UV trim
certificates; new-excursion uses none. No tolerance/policy extension. **Zero full
physical native audits**; continuous native volume/strain/manufacturability remain
unmeasured. Numerical/constructive/fidelity success is not a global route-quality
certificate. Both captures were visually inspected; significant flat travel and
terminal excursions remain. Neither problem case reached a proven optimum.

383imports the exact verified new-excursion result into the matching idle gym,
after checking owned document, targets/gym, source pins, native revision and idle
worker. QA occurrence receives only the gym display translation. Existing bodies,
histories and1%/UV-off preferences are preserved; no rebuild.384confirms selected
result `run-firstpass381-new-excursion:joint-material-v1`, clear event error,
matching job/counters, visible body and unchanged revision; live capture inspected.
The other verified body remains hidden as development evidence. Source lock updated
to the reviewed implementation without changing the version/UI defaults.

56focused tests pass across scoped runs:7first-pass,8joint-route,14locked-solver,
18aesthetic and9sliver-cleanup tests. Scoped Ruff lint/format pass. IDE inspections
find no new semantic findings; shared extracted geometry/retraction retains weak
duplicate-fragment reports against immutable historical source archives. Those
archives are preserved, not rewritten. Complete code/new-file/diff review performed.
The verify-change skill's referenced `.agents/VERIFICATION.md` is unavailable;
the explicit AGENTS focused profile supplies the checks. No standalone type or
documentation checker, full repository QA or complete physical audit was run.
No new generalized-success, shortest-route, minimal-feature or production claim.
Evidence: `ribbon_firstpass376` through `379`, final
`artifacts/verification/ribbon_firstpass381` plus `adopt383.py`/`review384.py`.

## Diagnostic first-pass switch385–387 — 2026-11-02

The selected solver panel now has **Enable first-pass optimization**, checked by
default. It controls the bounded joint length optimizer inside first-pass
construction independently of smoothing. Unchecked returns the selected separated
coarse route; configured aesthetic stages, numerical sliver cleanup, final checks
and optional UV preparation still follow normally. It applies on the next run,
does not reroute the displayed result when clicked, and disables while a job runs.

`Settings.first_pass_optimization` is an explicit boolean, defaults true and is
recorded in new controller plans and worker result settings. Existing two-control
records remain parseable with the enabled default. Other unknown/malformed keys
still reject. Run counters show recorded On/Off, or an em dash for an older plan
without an explicit flag; they do not infer the setting from current checkbox state
or silently rewrite historical plans. The selected381body therefore retains its
old plan and displays an unrecorded flag, despite known optimization provenance.

61focused tests pass across first-pass, joint-route, selected-solver/controller,
sliver-cleanup and performance consumers. Coverage includes disabled dispatch,
independent0/1%smoothing, boolean validation, legacy parsing, serialized on/off
plans and counter attribution. Ruff check and format check pass on nine affected
Python files. Palette JavaScript syntax and a simulated DOM check pass for enabled
default, draft retention, true/false run payloads and busy-state disabling. The
initial DOM harness lacked a selected method and failed before exercising controls;
its corrected fixture includes the normal input method. No application fix was
needed for that harness setup error.

IDE inspection is clean on the HTML and new toggle tests. Existing performance
type warnings (`float(value)`/optional disposition), the unchanged controller-test
optional-job warning, and historical-source duplicate-fragment weak warnings
remain out of scope. The verification skill's relative document resolves through
its managed symlink to `standards/VERIFICATION.md`, read for this change; the prior
376–384logical-path lookup incorrectly reported it unavailable. No full QA or
standalone type checker was run.

386refreshes the idle owned Fusion palette and only its settings/performance
bindings; selected method, job, visible body revision and geometry are unchanged.
The new checkbox is visibly enabled in the live panel,1%smoothing was restored and
UV remains off. Live parsing accepts explicit false. The executable source lock
was reviewed/refrozen. This is settings/UI verification, **0new geometry solves,
0native attempts and0new physical-audit coverage**. Previous381/382geometry evidence
remains historical. Evidence: `artifacts/verification/checkbox385.cjs`,
`refresh386.py`/`.json` and `review387.py`/`.json`.

## Accessible scaffold visibility388/389 — 2026-11-02

The existing thickness-envelope layer control moves from beneath the diagram to
directly below the run counters, labeled **Show transparent ribbon scaffold (both
views)**. It retains the same single `envelope` identity and existing seven-layer
visibility protocol. It switches the complete translucent native Custom Graphics
group and the diagram mesh without rebuilding the route or native conductor body.
Other layer controls remain independent. No numerical or Python implementation
changes; the executable source lock is refrozen for the maintained HTML change.

388JavaScript syntax/DOM checks pass for unique control identity, accessible
location, off/on boolean visibility dispatch and immediate diagram redraw. HTML
IDE inspection passes (an initial timeout was repeated successfully).389checks
the live native group off/on/off, verifies matching palette state and retention
across a ready request, and preserves selected method/job/body revision/visibility
and all other layers. The live checkbox is visibly unchecked and the transparent
ribbon mesh absent; conductor geometry remains visible. No FPS benchmark or native
renderer profiling is claimed.0new solves/native attempts/physical audits.

Refreshing the palette reinitializes the smoothing draft to5%. An attempt to
restore1%was interrupted by Fusion reporting user-driven app changes; automatic
approval review then rejected a final UI state query for stale-state risk. Further
UI interaction stopped. Final draft smoothing value is unconfirmed; no solve was
started and the existing1%built result is unchanged. This UI recheck is the only
blocked check; the prior native visibility/HTML checks are retained. No full QA
or repeated Python tests were needed for this HTML-only control relocation.
Evidence: `artifacts/verification/scaffold388.cjs`, `scaffold389.py`/`.json`.

## Clear generated geometry390–392 — 2026-11-02

**Clear geometry** appears beside Solve and build. It removes only the latest
generated output occurrence retained by this gym's NativeOwner, including its
auxiliary end-profile sketches. Other outputs/components, frozen layouts, numeric
records and diagnostic graphics remain. It works for a hidden latest output too;
it does not scan names or delete all historical bodies. NativeOwner releases its
handle only after successful deletion; missing/invalid output is harmless.

The generic diagnostic viewer accepts an explicit empty `clear_geometry` action
through ownership/availability callbacks installed by SelectedWorkspace. Both
palette and native dispatcher block it during running/cancelling jobs. The native
owner also requires its own active idle document. The button disables when no
native body remains, and shows a completion message after success. Normal Solve
and build remains available afterward; clearing never deletes job records or
changes historical fidelity/performance measurements.

22focused tests pass:8new deletion/dispatch checks,8gym-handoff and6selected-
controller consumers. Native API deletion is mocked: latest-only handle usage,
repeat/no-output, wrong document/active command, failed deletion retaining ownership,
empty-action validation, busy rejection and session retention. JavaScript syntax
and simulated DOM checks pass for clear-button availability, empty action and busy
state. Ruff check/format pass on four changed Python files. IDE has no introduced
findings; existing historical-source duplication and the native builder's documented
fail-soft broad exception remain. Full QA and actual native deletion are unrun.

391installs the new callbacks/classes into the owned idle live gym and refreshes
the maintained palette.392rebinds the retained navigation callback to the refreshed
workspace class, then checks source lock, clear availability, callback ownership,
navigation binding and clear event error. Current selected result/job/body revision
and hidden-scaffold preference are unchanged. **0deletions,0solves,0native builds**;
the current body is deliberately left for the user's button click. This palette
refresh reinitializes draft controls to their usual defaults; it does not change
the existing1%built result. No new CUA interaction or FPS/physical-audit evidence.
Evidence: `artifacts/verification/clear390.cjs`, `clear391.py`/`.json` and
`clear392.py`/`.json`. Executable source lock reviewed/refrozen; production unchanged.

## Solve/build control failure and progress393–400 — 2026-11-02

393read-only inspection finds an actual control failure, before any worker launch:
the last request is `run`, but its event error is `Supply smoothing_percent and
material_uv only`. The live runner is an archived
`counter_controller321.Controller`, with the old two-field Settings binding, not
the maintained controller tested locally. Its latest job is still381historical
evidence and no worker exists. Clear geometry had successfully removed the old
output. Thus the user's missing new body is not evidence of an exhausted solver.
The earlier controller-binding check exercised the maintained module alias, not
this actual live runner; that verification gap is acknowledged and corrected.
Fusion application logs were inspected before host-side changes.

The selected panel now exposes an open **Build progress log**. It shows control
submission/rejection, worker validation, numerical stages/route acceptance, native
patch/definition/kernel stages, fidelity checking, optional UV and completion or
failure. Request errors are visible here even if no job can be created. Accepted
jobs retain UTC events in `build-progress.jsonl`; at most100events/64KiB are read
for the UI, tolerating partial writes. Numerical stage updates are throttled;
full trials/tracebacks remain separate. Native events also push to the palette
while the synchronous native call runs. Optional palette delivery cannot abort
construction, and durable logging remains available if it closes.

Controller collection now exposes worker crash output and distinguishes an
unresolved no-route result from successful completion. Native exceptions outside
the existing fail-soft adapter stop the control stage explicitly. Last successfully
launched controls are retained in controller state, so palette reconnects no longer
replace the last1%setting with the default5%. Malformed requests or failed launches
do not replace those controls. Solver geometry, physical gates and native fidelity
tolerances are unchanged; this is diagnostic/control work, not a solver tuning fix.

395class-only repair stops before a solve because the old runner also has a
per-instance `state` override, whose old class closure makes `super()` invalid
after class reassignment. Its error response is retained.396instead creates a fresh
maintained Controller and copies only explicit historical/job/layout state, never
bound method overrides. This preserves methods, targets, jobs and native ownership.
The actual controller contract now advertises and accepts all three settings.
No solve/native attempt occurs in395/396.

397freezes one current gym case,120s numerical/120s native/250s phase,4GiB RSS with
3.8GiB launch headroom, at most one native attempt/no retries. It launches through
the actual `DiagnosticViewer.dispatch('run',...)` path; the palette's ordinary
polling collects the worker and performs native construction. At default5%smoothing,
numerical routing succeeds and a152-face solid builds, but named fidelity rejects
six shared-seam endpoint discrepancies, each4.420389e-6mm. Surface samples themselves
pass (maximum1.615e-9mm). The solid remains hidden and its failure preserved. This
is a native seam-fidelity failure after construction, not a missing route/control
failure, and remains unresolved. Generation2.241300s; native-operation17.099224s;
partial audit timer is not separately retained. Numerical2.436148s/CPU2.186866s.
No gate is relaxed and no geometry retry is appended to that stopped phase.

A separately reviewed3981%verification refuses scheduling because the latest job
changed while the user was operating the panel: its prerequisite deliberately
does not replace that job.0new solves/native attempts there.399then inspects the
user-driven1%run `selected-eecd3dee1f3e472ca75af09d589731b8`: completed numerical,
native construction and named fidelity pass. Targets and gym match397exactly;
these are two settings variants of **one independent examined configuration**,
not two independent successful cases. At1%:142faces, numerical1.984736s/CPU1.980530s,
generation.988163s, named audit13.701331s, full controller elapsed18.860809s. Both
variants miss the numerical<=generation timing goal. Sampled native RSS peaks
612352/727536KiB, below4GiB; in-flight peak unmeasured.0full physical audits.

400retains that successful user job and installs last-used-controls persistence
without another build, deletion, layout change or forced diagnostic selection.
The body is visible with its unchanged native revision, scaffold remains hidden,
event error is clear, and29progress events end with named-fidelity completion.
Current source lock verifies. The successful job's full source hash differs only
in `controller.py`, whose subsequent edit retains launched preferences; its
numerical/native implementations and logged geometry remain the executed versions.
Do not relabel the old plan as a new exact full-source verification.

Coverage for this diagnostic: one independent current gym layout, two numerical
variants/native attempts/builds (one agent397launch and one user-driven run), one
named-fidelity pass and one named-fidelity failure;0full physical audits/holdouts.
395/398stopped setup/guard work and all historical failures remain recorded. No
generalized construction or5%reliability claim. No further geometry run scheduled.

23focused tests pass across7progress/worker/collection,7controller and9clear/UI
boundary checks. Covers bounded/partial log reads, worker crash traces, no-route
classification, native completion/error, launch failures, retained controls and
optional progress-display failure. JavaScript checks verify visible control
rejection, polled worker logs and pushed native events. Scoped Ruff check/format
and IDE inspections pass with only existing archived-source duplication, the
documented native broad exception and unchanged optional-job test warning. Complete
diff/new-file review done. No full repository QA or standalone type checker.
Evidence: `inspect393.json`, `log394.cjs`, repair395/396 responses,
`ribbon_dispatch397`, stopped398response, `inspect399.json`, `retain400.json`, plus
the original selected-job directories. Production harness/profile code unchanged.
