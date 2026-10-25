# Cap-transition candidate v2 — five-width development

## Radius-bounded allocation and visible trajectories — completed 2026-10-25

`bounded_travel.py` allocates nonnegative extra travel above the required segment
lengths. A chord-projection separating check precedes at most 63 algebraic supports
of size 1..3; no geometry is constructed during these finite basis checks. Choose
minimum total travel among feasible supports. Rank/tolerance exhaustion remains
unresolved; an explicit separating margin applies only to this fixed motion family.

`radius_allocation.py` retains the chord-guided schedule and derives minimum
travel from analytic center curvature and the unchanged 0.8 macaroni contract,
with a fixed conservative 1e-12 relative roundoff guard. It never clips negative
coefficients or moves targets. A connecting allocation supplies a candidate;
otherwise an explicitly unclosed trace at the required minimum lengths is kept
for inspection. This diagnostic is not a fallback completed cable.

`radius_native.run()` uses the same seven frozen development cases and cached
displacement-guided baseline. One allocation problem/case, up to 63 linear bases,
no geometric search/retries/solids;10s numerical/30s drawing/60s overall/2GiB
sampled RSS. Stop on control regression, source/fixture/resource/API failure.
Draw all seven center trajectories and both edges; mark the actual endpoint gap
for unclosed diagnostics. Reuse numerical audits and cubic spline drawing without
changing their limitations. Native spline banking and full ribbon compliance
remain unmeasured. Only F3D/PNG artifacts; read counters from memory into chat.
Ten new unit checks plus seven prior chord checks pass; Ruff/format/IDE clean.
The above plan was frozen before evaluation; no general feasibility claim.

Seven planned/evaluated/drawn, each with center and both outer-edge splines.
0/7 native ribbon-solid attempts/builds/full compliance audits; native failure
rate unmeasured. Overall 0/7 accepted,5/7 failed,2/7 unresolved controls. No invalid
controls or holdouts. All five spatial outputs are **unclosed diagnostics at
minimum center-radius travel**, not connecting ribbons or alternate accepted paths.

| Case | Allocation evidence | Diagnostic endpoint gap mm | Minimum sampled lane radius mm | Solve ms | Drawing ms |
| --- | --- | ---: | ---: | ---: | ---: |
| banked crossover | Separating chord margin 21.027 mm | 40.072 | 0.832 | 0.632 | 108.189 |
| lateral90 | Separating chord margin 57.442 mm | 99.631 | 6.852 | 0.547 | 54.802 |
| straight | Original connected control | 0 | Infinite | 0.137 | 24.197 |
| broad return | Original connected control | <1e-8 | 45 | 0.110 | 19.887 |
| quarter_plus | 63 bases exhausted; feasibility unresolved | 27.130 | 0.129 | 1.494 | 55.718 |
| quarter_minus | 63 bases exhausted; feasibility unresolved | 179.282 | 5.257 | 0.605 | 55.638 |
| half_oblique | Separating chord margin 23.640 mm | 34.213 | 1.656 | 0.528 | 56.832 |

Three separating witnesses have all positive extra-travel chord projections;
required minimum travel already overshoots along the chord. This diagnoses this
fixed motion family, not physical endpoint infeasibility. The other two cases
remain unresolved after finite-precision basis exhaustion. Total basis checks126;
controls bypass allocation and three cases exit through the separating check.

All five diagnostic centerlines have analytic macaroni ratio0.7999999999992 and
zero curvature at joins; modeled width-axis curvature is zero by construction
(sampled floating residual <=1.51e-17/mm). Nevertheless crossover,quarter_plus,
half_oblique violate the4.5mm sampled lane-radius minimum. Four diagnostics also
exceed the71.25mm occupied-sphere radius (all except quarter_plus). All five
have9.4456% sampled lane-length spread, a warning rather than a hard rejection.
Rapid changes of the width frame affect lane curvature beyond the centerline
radius bound; these observations do not certify native interpolation or strain.

All solves4.054ms; all numerical audits161.099ms (controls6.514/6.707ms, spatial
diagnostics29.497..29.771ms). Numerical phase0.306983s includes source/RSS guards
and excludes cached baseline work; drawing0.602952s, archive/image0.642311s,
overall2.926402s, processCPU3.817024s. Maximum sampledRSS1085760KiB, final-run
1085760KiB, postflight853488KiB; in-flight peak and token/cost unmeasured.
All7/63-bases/10s math/30s display/60s overall/2GiB limits held;scope exhausted.
No geometric retries, target moves, bound relaxation or further refinement.

Open component: `Radius-bounded trajectories - connected or unclosed` in the
single owned candidate project. Verified seven children,21 visible fixed splines,
five labelled endpoint-gap guides, and viewport image. All eight original solids
retain identities,names,volumes. Only F3D/PNG artifacts under
`artifacts/verification/ribbon_cap_transition/radius_allocation/3725d7e6d8b4437089f54c7674fe5088/`.
Full source/input/rule fingerprints,cached baseline,counters and outcomes remain
in `radius_native._state`; no report file. Production/historical sources unchanged.
The next construction needs a different bend/roll schedule and lane-curvature
control; length allocation within this fixed family did not produce a spatial
connection. No new construction or batch automatically launched.

## Displacement-guided coupled motion — completed 2026-10-25

`chord_coupled.py` selects a chord heading and transported endpoint-width bisector
as an intermediate frame. Two three-motion orientation legs and one chord-aligned
straight motion replace the single three-motion schedule. The primitive oblique
basis is unchanged. Seven lengths follow one unconstrained minimum-deviation
linear projection around equal nominal chord-length allocations. Nonpositive
travel or singular systems reject; no clipping, alternate branch or active-set
search. Compatible analytic planar controls retain the original construction.

`chord_native.run()` uses the same seven fixed development cases and the completed
in-memory three-motion baseline, verifying original source/input fingerprints.
Cached baseline solving is excluded from current timers. One new solve per case,
no search/retry/solids,10s numerical/30s drawing/60s overall/2GiB sampled RSS;
stop on control regression, source/fixture/resource/API failure. Reuse the original
numerical audits and center/edge drawing unchanged. Known numerical failures may
be displayed diagnostically; unconstructed routes get endpoint guides only.
No new report files; results remain in memory, with F3D/PNG artifacts only.
Seven new unit checks and twelve existing primitive/route checks pass; Ruff,
format and IDE checks clean. The above procedure was frozen before evaluation.

Seven planned/evaluated; 0/7 native ribbon-solid attempts/builds/full compliance
audits. Native failure rate unmeasured. Overall 0/7 accepted, 5/7 failed, 2/7
unresolved controls; no invalid controls or untouched validation cases. All five
spatial poses still reject because the unconstrained length projection returns
nonpositive travel. Lane/envelope audits were skipped on those five cases.

| Case | Negative travel lengths mm | Solve ms | Guide drawing ms |
| --- | --- | ---: | ---: |
| banked crossover | -2.650 | 0.395 | 8.974 |
| lateral90 | -5.979, -18.241 | 0.300 | 8.712 |
| straight | None; original geometry preserved | 0.119 | 18.336 |
| broad return | None; original geometry preserved | 0.089 | 18.005 |
| quarter_plus | -0.554 | 0.291 | 8.456 |
| quarter_minus | -16.194, -15.711 | 0.313 | 8.159 |
| half_oblique | -2.550, -0.655, -1.281 | 0.274 | 8.801 |

Straight remains 80 mm and the return radius remains 45 mm. Both retain zero
modeled width-axis curvature and sampled lane-length spread; the return has
macaroni ratio 0.320434 and sampled lane radius 45 mm. Their numerical audits
took 6.584/6.716 ms. Only these two controls have center and both edge splines;
all five spatial failures show endpoint guides only. No new spatial route exists.

New solves total 1.781 ms. Numerical phase 0.152249 seconds includes memory/source
guards but excludes cached baseline work; array drawing 0.249336 seconds,
archive/image 0.696245 seconds, overall 2.451453 seconds, process CPU 3.393508
seconds. Maximum sampled RSS 840160 KiB, final-run 833264 KiB, postflight 735936
KiB; in-flight peak and token/cost unmeasured. All limits held. Scope exhausted;
no negative-length clipping, additional allocations, searches or retries ran.

New component: `Chord-guided coupled motion - three guide diagnostic`. Seven
children/six visible fixed splines and the viewport image were verified. One
owned document remains open; all eight original solids retain identities, names
and volumes. Only F3D/PNG artifacts were written under
`artifacts/verification/ribbon_cap_transition/chord_coupled/99ff1845c2424bbab2a62cae18e25c22/`.
Full source/input/rule fingerprints, cached baseline and results are retained in
`chord_native._state`; no report file. Production and historical sources unchanged.

This does not establish whether the seven-motion basis has any positive allocation:
an unconstrained minimum-deviation result outside the positive region is not a
proof that the feasible region is empty. Smaller negative numbers are not geometry
progress. Before another geometry round, a useful next question is whether forward
travel and analytic curvature-based minimum segment lengths can be satisfied
together within the frozen motion family. That constrained allocation is not
implemented or authorized as an automatic retry here. Native banking, continuous
lane/clearance/strain/compliance and broader routing feasibility remain unmeasured.

## Coupled bend and orientation diagnostic — completed 2026-10-25

`coupled_motion.py` integrates positive forward travel while rotating the tangent
and ordered width together. The rotation axis stays in their plane, enforcing
the modeled no-edgewise-bend invariant. Quintic angle easing gives zero curvature
and frame rate at joins. This is a kinematic construction, not elastic equilibrium
or a measured physical corkscrew ratio.

`coupled_route.py` uses one fixed three-rotation orientation factorization and one
linear solve for three lengths. Singular or nonpositive solutions reject; there
is no alternate-branch search, target adjustment or refinement. Straight and
compatible planar circular controls retain their analytic geometry. Positive
travel alone does not establish radius, spacing, strain or containment compliance.

`coupled_native.run()` is prepared for seven existing development configurations:
banked crossover, lateral90, straight, broad return, quarter_plus, quarter_minus,
and half_oblique. It evaluates all old biarc baselines before the new procedure,
then draws the centerline and both outer edges for constructed candidates. Failed
position solves receive endpoint guides only. Cubic display curves approximate the
coupled motion; they do not inherit its analytic banking guarantee. Solid sweeps
and complete post-build compliance audits are outside this scope.

Approved limits: seven solves, no search/retry/solid attempts, 10 seconds numerical,
30 seconds drawing, 60 seconds overall, 2 GiB sampled Fusion RSS. Stop on control
regression, source/fixture change, resource limit or API/harness failure. Results
stay in memory for chat readout; only F3D/PNG artifacts are exported. This scope
completed with seven cases evaluated, zero native ribbon-solid attempts/builds
and zero full post-build compliance audits. Native failure rate is unmeasured.
Overall: 0/7 accepted, 5/7 failed, 2/7 unresolved controls; no invalid controls or
untouched holdouts. All seven old biarc baselines preceded the new solves.

| Case | New numerical outcome | Solve ms | Guide drawing ms |
| --- | --- | ---: | ---: |
| banked crossover | Rejected: middle travel -44.309 mm | 0.217 | 28.458 |
| lateral90 | Rejected: middle travel -88.694 mm | 0.198 | 7.799 |
| straight | Preserved; compliance unresolved | 0.091 | 27.181 |
| broad return | Preserved; compliance unresolved | 0.134 | 17.762 |
| quarter_plus | Rejected: middle travel -298.442 mm | 0.170 | 7.760 |
| quarter_minus | Rejected: first/middle travel -123.081/-111.197 mm | 0.196 | 8.494 |
| half_oblique | Rejected: middle travel -50.222 mm | 0.158 | 9.223 |

Five rejected cases have endpoint guides only; their lane/envelope audits were
not attempted. The two controls have center and both edge splines. Straight
length remains 80 mm; the return remains radius 45 mm, with analytic macaroni
ratio 0.320434 and sampled lane radius 45 mm. Both controls have zero modeled
width-axis curvature and zero sampled lane length spread. These are mathematical
checks, not native ribbon compliance. Cubic guide interpolation remains approximate.

All solves totaled 1.165 ms; control numerical audits were 6.340/6.590 ms.
Numerical phase including baselines, RSS and source guards: 0.277486 seconds;
array drawing 0.335906 seconds; archive/image 0.639861 seconds; overall 2.593273
seconds. Process CPU 3.476708 seconds includes Fusion host work. Maximum sampled
RSS 1051680 KiB; postflight 875920 KiB; in-flight peak and token/cost unmeasured.
All limits held, with no search, retries or automatic refinement. Scope exhausted.

One owned candidate document remains open, with eight original solids unchanged.
The new component is `Coupled bend and rotation - three guide diagnostic`.
F3D/PNG evidence: `artifacts/verification/ribbon_cap_transition/coupled_guides/8000ff21fd974830aea81e13ba205b5a/`.
Source/input/rule fingerprints and full outcomes remain in `coupled_native._state`;
no report file was generated. The viewport and seven children/six splines were
verified. Twelve new focused unit checks and six prior biarc checks remain passing;
unchanged code checks were not repeated. Production and historical policies remain
unchanged. Full native banking, clearance, strain and compliance remain unmeasured.

The fixed oblique axes enforce coupled motion, but selecting their orientation
sequence before accounting for endpoint displacement overrestricts routing.
Negative travel rejects this basis for these five poses; it does not establish
physical infeasibility. A next construction needs displacement to participate in
axis selection. No revised construction or further batch was launched.

## Corrected longitudinal roll policy — prepared, not built

**Subsequent rule check: HOLD, not a rule-compliant build candidate.** User
reasserted no bending along the long/wide section axis. For nonzero centerline
curvature this requires `curvature dot width =0`;banking must enforce it rather
than be replaced by an independent roll prescription. Read-only scaffold checks
on the prepared pair found maximum normalized width-axis curvature0.9954953175
(90) and0.9954963769(180),violations at30/32 stations each (exploratory relative
threshold1e-8,not a newly approved tolerance). The reflected policy rotates the
width into the bend plane. The fixed planar curves cannot accommodate that full
continuous roll excursion while retaining zero wide-axis bending. Native0/2
attempted;no new geometry/compliance claim. Roll/frame unit passes below do not
cover this invariant. Even native-budget approval does not clear this geometry
gate. Bank and bend geometry must be coordinated,or twist confined to suitable
zero-curvature regions under a newly frozen plan;no such adjustment implemented.

User clarified and confirmed0 ->180 ->0 roll around the ribbon's long axis while
following the existing90/180 centerline turns. The previous360-to-everywhere-zero
pair below is a control,not the requested moving-roll comparison. No lateral
centerline change or section deformation. `ReflectedTwistDiagnostic` retains the
same endpoint orientation but creates a smooth bounded excursion using two C2
quintic halves;requested-360 analogously goes0 ->-180 ->0. It deliberately rejects
other requests,not a generalized limiter. This is360 total angular travel,not
retained full winding. Native interpolation can differ from the analytic field.

`turn_pair_native.start_reflected(context)` registers the corrected experiment;
`run_next` schedules one case at a time. Typed experiment configuration shares
the existing native procedure without changing the zero-roll entry point. Both
fixed fixture/cap/target dictionaries must exactly match the archived zero-roll
plan,whose hash is checked between stages. Separate artifact/display names retain
the control and all historical evidence. Native provenance now reports the actual
policy field instead of labeling every prescription a single global quintic.

Prepared2 development boundary layouts; **0 native attempts/0 new solids/0 full
audits**, native failure rate unmeasured. No geometry success claim. Renewal
proposal2 attempts/120s per case/300s overall/2GiB,no search/retries,first incomplete
construction stop awaits user budget approval;no Fusion operation launched here.
Twenty-seven focused reflected/fixture/old bounded-policy tests pass;changed code
Ruff lint/format and IDE clean,complete code/diff reviewed. Focused verification
does not substitute for native evidence;fullQA/host runner/compliance unrun.
Production and standards untouched. Analytic field <=180,zero cap/reversal first/
second derivatives;32 sampled frames remain undeformed/perpendicular with identical
origins/tangents/caps. Inter-station native spacing,flow,strain and curvature unknown.

## Tight90/180 turns with requested360 reduced to0 — 2026-10-06

User approved two complete configurations, no search/retries,120s per case,
300s overall,2GiB sampledRSS and first incomplete-construction stop. `turn_pair.py`
uses the existing passing R18.16887617111206mm from
`curve_limit/8591cac8b216442d80c05e2a8513ff43`: quarter-turn uses the first arc,
reversal uses both. Same19x1.5mm material,4x/114mm sphere,original32 planar lobe
sections,exact shared caps and both reverse-loft ending sets. Requested360 twist
maps0 through the existing shortest-twist rule; there is no full winding or warp.
Both complete cap/connection layouts freeze before either native attempt.
`turn_pair_native.run_next(context)` schedules one case at a time, then `finish`
archives/focuses the rigid display array. Sources/rules/production are fingerprinted.

**2 planned/2 evaluated/2 natively attempted/2 complete ribbons built;2 partial
diagnostic audits,0 fully audited.** Both input certificate ratios0.799999996883251,
sampled roll0. Preflight reports no hard findings but remains unresolved; overall
0 accepted/0 known rule failures/2 unresolved, denominator2. No failed/skipped/
unattempted construction and no invalid controls. These are two boundary layouts
in one examined planar-bend family, not distinct broad families or untouched
validation. Native continuous curvature/strain/flow/clearance and complete conductor
lengths remain unmeasured. No universal construction or physical limit established.

| Path turn | Requested/actual twist | Solve ms | Native trunk+endings s | Diagnostic audits s | Case total s |
| --- | --- | --- | --- | --- | --- |
|90|360/0|37.736|6.720|11.413|32.702|
|180|360/0|75.415|6.840|14.714|36.758|

Wall81.944s includes separate array display/archive11.674s; original radius-search
cost is excluded, solver certificate checks included. Audits are not solver cost.
Maximum recorded RSS1207232KiB; final read-only inspection859520KiB,below2GiB;
in-flight peak/token cost unmeasured. All scheduling limits held,slots exhausted.

Active/open `Tube ribbon 4x - 90 and180 turns - requested360 bounded0` contains
two components with39 positive-volume solids each (one trunk+19A+19B). Screenshot
visually reviewed. New successful scratch documents archived/closed only after
their rigid display copy. Previous six-case array and five unrelated documents
remain open. Earlier failure/pilot documents are absent from final inventory;
this runner did not target or close either. No cloud saves or body deletions.
Evidence `turn_pair/df07c6c851004737b3ece9c552c61942/` holds frozen plan/report,
individual report paths and arrayPNG/F3D. Three focused input/certificate/frame
tests pass; new files Ruff lint/format and IDE clean, complete new code/diff
reviewed. Focused verification keeps code contracts separate from geometry evidence;
fullQA and full mechanical audits unrun. No production/standards changes or
automatic continuation; next step requires user review of the displayed pair.

## Original six-case planar/bounded-twist replay — 2026-10-06

`bounded_twist_native.run_next(context)` replays the original six absolute-faith
certificate-limit layouts, not the later straight warp pilot. Frozen scale values
are read from the original plan; all parent/selected geometry, exact caps and
connection targets must match before scheduling. No new certificate search,
rerouting, section flex or fallback. Original32 planar lobe sections,19x1.5mm
material,4x/114mm sphere and both reverse-loft ending sets remain unchanged.
`shortest_twist` reduces signed total roll modulo360 into [-180,+180], retaining
half-turn sign and ordered endpoint orientation but not extra physical winding.
Only the skew-return prescription changes (-360 to0); other five are controls.
The previous bank-rate diagnostic exception remains explicit, not newly proved.

User approved6 complete configurations/6 solves/6 native attempts,0 retries,
120s/case,840s overall,2GiB sampledRSS; first incomplete-construction/source/host/
resource failure stops scheduling. Native prediction was six complete builds.
**6 planned/6 numerically evaluated/6 natively attempted/6 complete ribbons built;
6 partial diagnostic audits,0 fully audited.** No failed/skipped/unattempted native
case and no invalid controls. Overall compliance:0 accepted/5 known rule failures/
1 unresolved, denominator6. PlanarS has unresolved preflight; other five reject
known rules (end-region allowance and/or sampled lane/end curvature). Construction
is not mechanical compliance. Continuous native flow/strain/clearance and complete
conductor lengths remain unmeasured. These are examined development regressions,
not untouched validation or proof of a universal180-degree limit.

| Original layout | New roll | Shape solve ms | Native trunk+endings s | Diagnostic audits s |
| --- | --- | --- | --- | --- |
|Shallow|0|47.700|6.801|9.830|
|Quarter|+90|34.724|6.845|16.564|
|Arch|-90|1.609|6.957|15.900|
|Planar S|+180|11.124|7.067|24.480|
|Spatial S|-180|14.692|6.895|21.366|
|Skew return|-360 reduced to0|72.292|6.993|14.204|

The formerly failing skew-return builds with the same frozen geometry/caps and
no full winding. This supports this endpoint-equivalent simplification on the
named fixture, not the claim that every ribbon with<=180 roll will construct.
Total scheduling wall280.981s, separate array display/archive29.952s; individual
case total31.043/38.146/37.496/46.363/43.099/35.848s, excluding array display.
Shape solve excludes historical scale search, and audit cost is not solver cost.
Maximum recorded caseRSS1252944KiB; post-batch RSS857376KiB; in-flight peak and
token cost unmeasured. All scheduling limits held; no additional run authorized.

Evidence `bounded_twist/5414e13d29834ad3b356e774ab1f255c/` contains frozen plan,
per-case reports and arrayPNG/F3D. Live `Tube ribbon 4x - planar bounded twist
replay` is active/open with6 components,each39 positive-volume solids (one ribbon,
not39 cases). Newly created successful scratch documents archived/closed after
rigid display copying; original failure,pilot and five unrelated docs untouched.
Screenshot inspected. Nineteen focused roll/budget tests pass; changed code Ruff
lint/format and IDE clean, full new code/diff reviewed. FullQA/native complete
compliance not run. Verification skills kept code checks separate from geometry
evidence; production/standards unchanged. Shared array helpers now accept an
explicit owned array name, with original entry points/default behavior retained.

## Alternate-section half-warp retry — 2026-10-06

User explicitly requested every-other-section construction. One unchanged half-
warp/+360twist development trunk replay used1,3,5,...31 plus exact terminal32,
17closed Paths total. Other15 sections are omitted from loft input, not deleted.
`alternate_warp_native.run(context)` checks parent fingerprints and3150 retained
interior fit points before one NewBody solid loft. Source/centerline/warp/twist/
caps unchanged; no rerouting/search/other parity/retry. Native prediction unknown.
One attempt maximum; preceding user-waived time cutoff and2GiB RSS retained.

**1 existing trunk variant planned/replay-evaluated/native-attempted;0 new solids,
0 complete ribbons,0 fully audited.** Construction0successful/1failed; numerical
sample replay valid, actual kernel again `ASM_LOFT_SURFACE_SELF_INTERSECTS` /
`LOFT_TOOLBODY_CREATE_FAIL`. No other selection was attempted. No invalid controls.
Preparation3.194s, native1.995s,total5.317s; separate display0.986s/finalRSS582672KiB;
max prelaunch sampledRSS509888KiB,
in-flight peak/token cost unmeasured. Replay fit error1.192e-14mm; no post-build
skin/spacing/strain or omitted-station-fidelity audits. This sampling did not
resolve the observed failure; it does not prove every sparser arrangement fails
or establish an intrinsic section-warp limit. One specimen, not family breadth.

Frozen plan/report at `alternate_warp/10a3b7e4e98941d1b0a5714ce5adde61/`, linked to
the half-warp parent report. Original native geometry/archive retained unchanged;
owned pilot left open with selected sections visible and omitted sections hidden
only. Original failure example and unrelated documents remain untouched/open.
Seven focused selection/replay tests pass; new module/test Ruff lint/format and
IDE clean, full new code/diff reviewed. Full QA/native compliance not run. Focused
verification separates reference selection from native validation; production and
standards unchanged. No further native attempt is scheduled after this failure.

## Section-warp sweep with twist retained — 2026-10-06

User-renewed continuation: "just build them we will deal with performance later"
explicitly removed the time scheduling cutoff for this fixed batch only. Three
loft-attempt maximum,2GiB sampled RSS and first-failure stop remain; geometry/rules
and lack of post-build compliance audits are unchanged. `resume(context)` verifies
the preceding report and all unchanged implementation/input hashes, retains the
29 existing zero-warp interior contours after checking6090 fit points against
frozen math, and finishes sections31/32. `warp_replay.py` resolves their Paths
without reconstructing native curves. A new report preserves the earlier timeout.

Continuation outcome: **one development trunk family planned/evaluated/attempted;
three variants planned/two deformation-prepared/two loft-attempted/one solid built /
zero complete ribbons or fully audited configurations.** Zero warp constructed;
half warp failed; full warp unattempted because of that first failure. Within
construction-only scope1successful/1failed/1unattempted, denominator3. Mechanical
acceptance unresolved for all3; no invalid controls or prediction-accuracy claim
(all native predictions unknown). No retry, geometric adjustment or fallback.

| Section-warp scale | Peak imposed edge tilt | Preparation s | Native loft s | Outcome |
| --- | --- | --- | --- | --- |
|0|0 degrees|11.387 continuation|12.213|one solid,2.140895269cm3|
|0.5|43.265 degrees|23.804|0.753|ASM_LOFT_SURFACE_SELF_INTERSECTS / LOFT_TOOLBODY_CREATE_FAIL|
|1|unbuilt|not attempted|not attempted|stopped after half-warp failure|

Both attempted cases retain the same+360quintic twist and spline representation.
Half warp's maximum sampled point displacement0.547984mm and plane departure
0.510106mm; sampled center pitch ratios0.999999800..1.000000358. These are section
authoring measurements, not interpolation/native spacing/strain compliance.
Adding this warp pattern can induce kernel rejection on the twisted straight
fixture; no exact maximum angle or monotonic threshold is established. Kernel
self-intersection may concern generated skin/correspondence, not proof that the
intended continuous section deformation physically intersects itself. The original
curved negative-twist cause remains unproven; the fixture is deliberately different.

Continuation total49.196s (case24.436/24.758s); separate display/archive2.841s,
archive0.635s subset. Prior stopped preparation60.684s/display1.475s remain separate
historical costs; final focus7.476s, instrumented combined121.673s excluding
orchestration/template extraction. Final focused RSS721072KiB.
No search/endings/compliance-audit cost. Final archive RSS1353536KiB, below2GiB;
in-flight peak/token cost unmeasured. No more native work scheduled; one unused
loft slot does not waive the first-failure review gate.

Evidence `section_warp/ba8be6ab459645d291fa8da45016575d/`: frozen renewal plan/report,
parent lineage, presentation/F3D and visually reviewed screenshots. Same live pilot
remains open with zero-warp solid beside half-warp contours (no half-warp body).
Prior three solids are unchanged/hidden only for review; original failure example
and five unrelated documents remain open/untouched. No cloud saves or deletions.
Fourteen focused replay/context/budget tests passed; changed code Ruff lint/format
and IDE clean, full new code/diff reviewed. Unchanged math/contour tests retain
previous passing results. Replay success path verified live, not separately unit
tested; full QA and complete compliance unrun. Focused verification distinguished
adapter preservation from native evidence. Production/standards untouched.

User corrected the previous longitudinal-twist diagnostic: test section warp on
the new straight scaffold while keeping+360-degree quintic twist unchanged.
`section_warp_trial.py` scales the measured outer-edge normal tilt angles about
their fixed local azimuths by0/0.5/1. `section_warp_native.py` uses the same
57mm/32station/19x1.5mm scaffold, three fixed anchor positions, original planar
terminal caps and shared Hermite flex implementation. Directions are read from
the original failure's physical guides into a frozen local-coordinate template,
then transferred to the straight scaffold. They are imposed diagnostic normals,
not the actual derivatives of that scaffold's edge curves or compliance proof.
Identical42segment five-fit-point spline interior Paths at every scale provide a
representation-matched zero-warp control; zero is rebuilt rather than assuming
the previous40arc/Profile solid proves this adapter. No longitudinal twist search.

Approved3attempts maximum/60s per variant/300s overall/2GiB sampled RSS; stop
first failure or limit, no retry/tuning. One development family/three variants,
not independent complete ribbons or collateral-regression challenges. Existing
pilot row and failure example retained; additional components go in a second row.
No endings, sphere test, full-rule preflight or post-build mechanical audits.

Result: **1 family planned /direction-input preflight evaluated /0 natively
attempted /0 new trunks or complete ribbons built /0 fully audited.** Three
variants planned; zero-warp preparation timed out, half/full unattempted because
of that stop.0 accepted/1 preparation-exhausted/2 unattempted; all3 native outcomes
unresolved, native failure rate unmeasured; no invalid controls. Zero-warp contour
setup reached30/32 section Paths before the scheduling check at section31 found
60.682s and899040KiB RSS. It never reached a loft.29 interior spline contours
are retained alongside32 source sketches; section31/32 conversion unattempted.
Zero-warp sampled displacement1.435e-14mm, plane departure7.105e-15mm, tilt0;
these are control-authoring diagnostics, not evidence about nonzero warp limits.

Batch60.684s; separate display/archive1.475s (archive0.425s subset), final
RSS976656KiB. Instrumented cumulative62.160s excludes orchestration/template read.
No native build/search/endings/audit cost incurred. The preparation
cost combines original contours, midpoint splits, spline authoring and API Path
checks; it is not solver-math timing. The time cap stopped further scheduling;
memory remained below2GiB, in-flight peak/token cost unmeasured. No adapter fix,
larger budget, discarded case or altered topology was introduced after the stop.
The warp-limit question remains unanswered. Need user renewal before completing
the retained control or any nonzero-warp trial; an extended budget is not implicit.

Frozen plan/report/template fingerprints, partial F3D, screenshot and presentation
at `section_warp/0d37bc048c4d44a3b2b66af7a6dfbe55/`. Existing straight pilot stays
open; its three prior solids and the original failure example remain unchanged.
New component explicitly labeled PREPARATION TIMEOUT, NO LOFT. Thirty-four focused
warp/flex/midpoint/context/budget tests passed; three new files Ruff lint/format and
IDE clean, complete new code/diff reviewed. Full QA, runner success-path tests and
native warp validation not run. Focused verification avoids promoting code checks
to geometric evidence; no production/standards changes or cloud saves/deletions.

## Straight planar twist-only pilot — 2026-10-06

Renewal result: repaired only the guard to `app.userInterface.activeCommand`,
then ran the unchanged three-variant pilot. **One development family planned /
authoring evaluated /natively attempted /trunks built;0 complete ribbons and0
full audits. Three of three variants attempted and built;0 failed/skipped.**
All outputs are one positive-volume solid each, not surfaces. Native predictions
were unknown for all three; no prediction-accuracy claim. Construction-only
outcome3/3 successful, mechanical/complete-rule acceptance unresolved3/3; no
invalid controls. Endings and independent collateral challenges remain unattempted.

| Twist | Analytic peak deg/mm | Preparation s | Native loft s | Case total s |
| --- | --- | --- | --- | --- |
|0|0|4.942|0.205|5.528|
|180|5.921|6.662|0.855|7.872|
|360|11.842|9.136|0.906|10.534|

Batch25.154s; separate display/archive1.075s (archive0.254s subset); instrumented
cumulative26.229s excludes orchestration. No search or compliance-audit work.
Final presentation RSS820048KiB, below2GiB; sampled run limits respected,
in-flight peak and token cost unmeasured. All three build slots consumed; no
further native work scheduled. Source/rule fingerprints stayed frozen during run.

This found no twist-only failure through11.842deg/mm on the straight fixture,
slightly above the original failed span's sampled11.723deg/mm. It weakens a
universal scalar-rate-only explanation at that rate; it neither establishes an
absolute twist limit nor proves the original cause. Sign, centerline curvature,
bend-plane change, bank orientation, section topology and profile correspondence
are not all matched to the original skew -360 specimen. Native interpolation,
spacing, strain and mechanical goals remain unaudited. These inspected cases are
development diagnostics, not untouched validation or a proposed fix's regression.

Evidence `straight_twist/7787dfd56da247ecabdef5c26337976b/`: frozen plan/report,
presentation inspection, array F3D and visually reviewed screenshot. New document
`Straight ribbon - planar twist rate pilot` stays open with0/180/360 left-to-right.
Original failure example and five unrelated documents remain open and unchanged;
no cloud saves/deletions. Guard change passes Ruff lint/format and IDE inspection;
the unchanged nine authoring/budget tests were not redundantly rerun. Full QA and
post-build compliance not run. Focused verification kept the repair limited to
the adapter. Production and standards untouched. Next bounded decision: distinguish
bend/twist interaction from correspondence, rather than assume a rate-only fix.

Approved scope: fixed57mm straight centerline,19 conductors at1.5mm pitch,
32 original40-arc planar sections, identical quintic roll with0/180/360 degrees.
Analytic peak rates0/5.921/11.842 degrees/mm. One development route family with
three variants, not three independent complete ribbons or collateral challenges.
No flex, rails, endings, sphere test, search, or post-build mechanical audits.
Three native attempts maximum,60s/case,300s/batch,2GiB sampled RSS; first failure
stops all subsequent work, no retries/tuning. Existing failure document retained.
`straight_twist.py` freezes authoring; `straight_twist_native.py` is the pilot.

Initial pre-renewal disposition: one family planned/authoring evaluated; **0 native attempts/0 trunks
built/0 complete ribbons built/0 fully audited**. All three variants unattempted.
Idle-command guard incorrectly accessed `Application.activeCommand` and raised
AttributeError before document creation, budget initialization or geometry work.
This is a harness failure; native failure rate, limit, memory and original cause
remain unmeasured/unresolved. Fusion application log confirms39ms execution.
No retry, repair or new scratch was performed. Evidence is under ignored
`straight_twist/preflight_20261006T164844/report.json`.

Nine focused authoring/budget tests passed, Ruff lint/format and IDE inspections
clean; complete new code and tracked diff reviewed. Focused verification does not
validate the live adapter, and no general construction claim is supported. That
stop required user renewal, subsequently granted for the result recorded above.

## Flexed solid-prefix closure diagnostic — 2026-10-06

User requested the solid up to the failure point. `flex_prefix_native.py` reuses
the existing32 closed contour Paths, probing1-2,1-3,... until first failure, with
at most31 prefix operations/120s/2GiB sampled RSS and zero search/retries. Inputs,
curve ordering, flex implementation and source hashes stay frozen. Each success
would replace only the preceding prefix created by this call; historical geometry
is never deleted. A partial loft ends on a nonplanar interior section, introducing
an end-closure requirement absent at that station in the full loft.

Result: **1 planned /0 newly numerically evaluated /1 configuration natively
attempted /0 successful solid prefixes or complete ribbons /0 fully audited**.
One native operation1-2 produced a surface, not a solid (`isSolid=false`,volume0).
The solid-validity check stopped the run;1-3..1-32 (30 operations) were unattempted.
Last successful solid prefix: NONE. Overall0 accepted/1 failed solid-prefix
construction/0 unresolved within this scope; no invalid controls. Original full-
loft failure location remains unresolved; this is not evidence it begins at section2.
Read-only inspection found43 faces/42 free boundary edges; every free-edge endpoint
matches section02 contour endpoints within5.439e-15mm. This supports an uncapped
section02 boundary; it is not a complete edge-curve or mechanical compliance audit.
No explicit patch/stitch, flattened cap, fallback or geometric repair was attempted.

Native prefix0.116s; existing Path setup3.144s; run3.365s; separate display/archive
1.443s (archive0.174s subset). Instrumented cumulative4.808s excludes orchestration
and read-only diagnosis. RSS656192KiB after native,796352KiB after presentation;
limits respected, in-flight peak/token cost unmeasured. Zero shape solves/audits.
This is one known development configuration, not new family coverage. Endings and
three collateral challenges were unattempted; no generalized or performance claim.

Evidence `flex_prefix_native/3c2b07d7eb1f4dcbbd109b26a8e1558f/`: frozen plan/report,
contour coordinates, closure diagnosis, F3D and screenshot. Document remains open,
with the surface labeled `Flex prefix 1-2 - SURFACE ONLY, not solid`, sections01/02
and both physical guides visible. Other contours are retained/hidden. The old
baseline was already absent at preflight; initial guard stopped before any native
operation, and that removed body was not restored. All five unrelated designs are
untouched; no cloud save or deletions occurred. The requested partial solid remains
undelivered. Next user decision: authorize an explicit nonplanar cap/stitch diagnostic
before continuing solid prefixes; do not assume it fixes the full-loft flow failure.
Twelve focused budget/context tests pass; new runner Ruff lint/format and IDE clean,
complete diff reviewed. Successful-prefix cleanup/retention branch was not exercised
live; full QA and dedicated runner success-path unit coverage were not run. The
verification skill kept checks focused and reports that residual coverage explicitly.

## Three-anchor nonplanar section prototype — 2026-10-06

`section_flex.py` keeps the center and two outer mid-thickness anchors fixed.
It projects each width direction perpendicular to its own path tangent, then
uses piecewise cubic Hermite midlines and smoothstep unit thickness interpolation.
The mathematical local section plane at each anchor is perpendicular to that
anchor's tangent; this does not certify geometry between anchors or stations.
Exact terminal caps use their original contours and authoritative center tangents,
not fitted edge-guide endpoint derivatives. No centerline, roll or target search.

The user-approved `flex_native.run(context)` reads the two existing physical
edge splines in the current owned failure document. `flex_contours.py` approximates
each interior mapped contour with five-point fitted splines per original arc,
shared contour endpoints and a closed nonplanar `Path`, not a planar `Profile`.
One full 32-section trunk loft is scheduled, with 120s/2GiB sampled RSS limits,
no retries/endings and no full mechanical audits. Baseline, source sections and
physical guides are preserved; evidence remains under ignored `flex_native/`.
Future anchors/edge curves belong in solver math: creating these extra physical
vertices and guides in Fusion is **not** the intended implementation requirement.
This physical prototype exists to clarify the deformation visually. Fitted native
contours are approximations; fit-point coincidence is not an interpolation audit.
Sampled center pitch is reported separately, never inferred from construction.
This single known development case does not replace the required three distinct
collateral-mechanics configurations; their native baselines remain unattempted.

Initial prototype disposition: **1 planned /0 fully evaluated /0 native loft attempts /
0 trunks or complete ribbons built /0 fully audited**, denominator1. One unresolved
development case; no invalid controls. The adapter stopped at first-section setup
with `InternalValidationError: Utils::getObjectPath(...)`, before creating any
flexed sketches or reaching `loftFeatures.add`. This is a harness failure, not
evidence that nonplanar flex cannot construct. Both first-station edge derivatives
were subsequently read successfully; source curves have no assembly context.
An assembly-context issue in contour-path setup is a suspected cause, not proven.
No adapter repair, alternative construction or retry was scheduled after the stop.

Run elapsed0.881s; no search, trunk-build or compliance-audit time incurred. Final
RSS460240KiB, below the approved2GiB ceiling; in-flight peak/token cost unmeasured.
Evidence: `flex_native/92df7c841a70466c9a35dbc4b055f34d/`, including frozen plan,
report and read-only diagnosis. Live document/guides remain open and the sole
visible baseline volume is unchanged at1.107125050cm3; all five unrelated designs
remain open. No new archive was needed for an unchanged geometry state.
Seven new mathematical tests plus eight retained midpoint tests passed; four new
code files passed Ruff lint/format and IDE inspections. Full QA was not run. The
verification skill kept checks scoped and separates code-contract evidence from
native coverage. Next bounded decision: authorize investigation/repair of the
Fusion contour-path adapter and renew the same one-attempt pilot, without changing
the mathematical deformation or fixed inputs. That initial call delivered no live flex.

User renewed reference-only adapter repair and the same one-trunk pilot. Adding
explicit occurrence proxies fixed the first cap Path error. The next harness exit
at section02 retained42 fitted curves/210 points but returned an open23-curve Path.
Read-only endpoint traversal found one closed42-curve contour; passing those same
references in connection order returned a closed42-curve Path. No point movement,
flattening or tolerance change was needed. `curve_context.py` now resolves proxies
and orders a single closed chain, rejecting gaps/branches/disconnected loops.
That intermediate report remains at `flex_native/da408fbec3c942c9950ad3d1f8634f42/`.

Corrected adapter result: **1 planned /1 section-deformation evaluated /1 native
trunk attempted /0 trunks or complete ribbons built /0 fully audited**, denominator1.
Overall0 accepted/1 failed native construction/0 unresolved within prototype scope;
no invalid controls. This is the same known skew-return -360 development case, not
a new independent configuration. Full master-rule numerical screening was not rerun.
All32 closed42-curve Paths reached loft input, with both original terminal contours
unchanged. Retained section02 was reused only after all210 fit points matched the
fixed math;29 other interior contours were authored,30 total retained. No extra
solid attempt, route/twist change or fallback. The one solid loft failed with
`ASM_BAD_UV_SKIN_DIR` / `LOFT_TOOLBODY_CREATE_FAIL`. The adapter limitation is fixed;
this is now an actual kernel failure, not proof that nonplanar sections are forbidden
or that every three-anchor interpolation is infeasible. No geometric repair followed.

Named section diagnostics: maximum mapped-point displacement1.022304mm; departure
from original plane0.748100mm; native fit-point error1.589e-14mm. Sampled conductor
center pitch ratios0.999999527..1.000000847. These are section/sample measurements,
not native skin spacing, whole-lane curvature, interpolation accuracy or compliance.
Endings and all three collateral-mechanics configurations remain unattempted.

Corrected-run preparation (guide reads/math/native contours combined)29.895s,
native trunk6.206s, total36.799s. Search and post-build compliance audits0/absent;
math-only solve cost is not separated. Physical diagnostic contour authoring is not
a future solver timing or demonstrated performance gain. Intermediate harness
exit1.361s; separate display/archive1.759s (archive0.451s subset); current renewal
instrumented cumulative39.919s, excluding orchestration/read-only diagnostic time.
Final native RSS785728KiB; presentation746192KiB, below2GiB. In-flight peak/token
cost unmeasured. No more construction is scheduled; remaining pilot native attempts0.

Final report/plan/F3D/screenshot/presentation at
`flex_native/e8cbb5e632244200af529f56efa33637/`. Owned document stays open; unchanged
baseline volume1.107125050cm3 remains visible with both guides and flex sections
17/18/19. Other27 flex contours are retained but hidden for readability; all five
unrelated documents unchanged. No cloud save, deletion, production or standards edits.
Eight adapter tests plus seven unchanged math tests passed; four changed code files
passed Ruff lint/format and IDE inspections, complete diff reviewed. Full QA and
complete geometry compliance not run. The focused verification skill kept checks
proportionate. Next bounded decision requires user review of the visible flex and
authorization before further kernel diagnostics or changing the interpolation.

## Explicit outer section midpoint vertices — 2026-10-06

User-directed enhanced-section rule: put an actual contour vertex at both outer
width extrema, halfway through thickness. `section_midpoints.py` splits the two
existing circular side caps at their angular midpoints, retaining the outline,
ordered conductors, spacing and exact terminal geometry. No section warping,
rails, changed twist field or production changes are implied. The historical
40-arc 19-lane section becomes 42 arcs; it remains one closed profile.

`midpoint_native.run(context)` is a registered one-case Fusion diagnostic on the
open `Tube failure - skew return -360 - exact replay` document. It preserves the
1-17 partial-solid baseline, modifies all 32 input profiles and attempts the full
trunk once. Budget 120 seconds/2GiB monitored RSS, zero solves/search/retries.
Kernel errors are recorded without throwing out of the host script transaction;
archive/presentation errors remain separate. Frozen material, centerline, roll,
cap positions and target geometry stay unchanged. No endings or post-build
mechanical audits are scheduled, and no collateral-regression claim is supported.
Generated plans/reports and native archives go under ignored
`artifacts/verification/ribbon_cap_transition/midpoint_native/`.

Diagnostic baseline: growing prefixes 1-2 through 1-17 constructed, first failure
1-18 reported `ASM_BAD_UV_SKIN_DIR`; 1-19..1-32 unattempted. 17 prefix operations
are not 17 independent ribbons. Cumulative native time 3.881s. A subsequent
selection error rolled back live prefix bodies; an explicitly approved 1-17
replay restored the visible baseline in 0.503s. Both historical reports remain
under `prefix_native/6755a0c107344d0fbd0a5a8fdd9a59d5/` and
`prefix_native/0e5d813f757e4cb99f2dfb6d55e3291d/`.

Midpoint result: one existing configuration, 32/32 sections enhanced, 64/64
midpoints each joining two contour arcs; all profiles remain single/42 arcs.
Maximum error from frozen frame width extrema 1.628e-14mm. Zero new numerical
solves/evaluations; one native trunk attempt, zero trunks/complete ribbons built,
zero post-build compliance audits. The full loft still reports
`ASM_LOFT_SURFACE_SELF_INTERSECTS` / `LOFT_TOOLBODY_CREATE_FAIL`; no retry or fix.
Topology 2.719s, loft attempt 0.407s, total 4.560s; final RSS845408KiB. Endings
and three collateral configurations were not attempted; no generalized claim.
The unchanged 1-17 baseline remains visible with volume1.107125050cm3, alongside
enhanced section sketches, in the user-saved/renamed
`Tube failure - skew return -360 - exact replay - Rate of twist failure v1`.
Archive/screenshot/report/64-vertex verification are retained at
`midpoint_native/be2ea1afd5074c82bd4979bf04e9bca0/`. No user document was closed
or cloud-saved by this diagnostic. The initial exact-name guard stopped before
edits/native attempts; explicit renamed-document targeting then ran once.
Eight focused helper tests, Ruff lint/format on three code files and IDE
inspections passed; complete change reviewed. Full QA and collateral native
regression not run. The verification skill kept checks scoped; unit tests are
not additional complete-ribbon configurations.

## Six-case absolute-faith construction prediction — 2026-10-06

**6 planned /6 evaluated /6 solved /6 native-attempted /5 completely built /
0 fully master-rule audited**, denominator6. All six inputs pass the unchanged
0.8/depth16 curve certificate at their selected finite boundary. Registered
certificate-pass -> native-build hypothesis:5 matched builds,1 false acceptance.
Overall0 accepted/5 failed known geometry rules/1 unresolved. No invalid controls,
skipped cases or retries. The failure happened last; the generic stop text says
remaining cases not attempted, but there are NONE remaining in this batch.

User approved six distinct endpoint/curve families,0,+90,-90,+180,-180,-360deg
twists;19x1.5mm material and114mm(4x) sphere. Uniform centerline-only compression,
24 probes/family(144 total),120s/case,2GiB monitored RSS,60s display/cleanup and
840s total cap. Warnings/findings non-blocking; native/host failures stop with no
repair. Six scaffold-only calls author transported guide rolls before searches;
all selected caps/connection targets freeze before any complete-ribbon solve.
144 probes75passed/69rejected,4.997s total authoring,0 ribbon solves in search.
Passing scales:0.450845122337,0.454223155975,0.763704419136,0.662864685059,
0.502778053284,0.454222202301. All ratios just below0.8; brackets2^-23.
Centerlines fixed during solve, no rerouting or outcome-dependent target changes.
These are development variants; arch/spatial families have existing lineage, not
untouched holdouts or proof of generality. Material and sphere never shrink.

| Configuration | Search s | Solve ms | Native build s | Audits s | Total case s | Native result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| shallow /0deg | 1.528 | 46.226 | 6.654 | 9.585 | 30.132 | built39 |
| quarter /+90deg | 0.857 | 34.648 | 6.495 | 16.299 | 35.872 | built39 |
| asymmetric arch /-90deg | 0.034 | 1.657 | 6.774 | 15.639 | 35.669 | built39 |
| planar S /+180deg | 0.332 | 11.175 | 6.880 | 24.610 | 45.164 | built39 |
| spatial S /-180deg | 0.583 | 14.388 | 6.648 | 21.128 | 41.406 | built39 |
| skewed return /-360deg | 1.664 | 72.833 | 2.640 failed attempt | 0 absent | 4.951 | kernel failure,0 solids |

Shape solve includes its input certificate/table/roll, excludes authoring search
and numerical preflight. Native build includes trunk+endings, excludes audits.
Per-case trunk/endings/preflight/display/archive timings are retained in JSON.
Total case includes host setup/display/archive, excludes prior authoring search,
array copy/close and between-call overhead. Cumulative shape181ms,native36.090s
(including failed attempt),audits87.261s,total case193.194s. Array copy/close/
finish23.343s; overall batch322.511s includes search and orchestration gaps.
Limits respected; maximum final case RSS1162160KiB,between-op sample1102304KiB,
final verified Fusion RSS469664KiB. In-flight peak/token cost unmeasured.

Failure: `faith_skew_return_minus360_certificate_limit`, curve ratio
0.7999999881034527,3939 certified intervals; guide radius30.863mm fits57mm sphere,
signed winding-360 retained and shared exact-cap handoff reached. Fusion rejected
the TRUNK loft: `ASM_LOFT_SURFACE_SELF_INTERSECTS`, then
`LOFT_TOOLBODY_CREATE_FAIL`.0 solids,all38 endings not reached,post-build audits
absent. This is actual native rejection, not a preflight guard or missing ending
misreported as success. Logs inspected; no recovery, multiple-loft workaround,
solver/certificate weakening or second attempt. Certificate alone is NOT a
universal native construction guarantee; exact geometric cause beyond the reported
self-intersection remains undiagnosed. Failed evidence preserved for investigation.

Numerical findings kept separate: shallow exceeds combined6% end allowance on
both ends; quarter has fitted/whole-lane radius and end allowance findings; arch
has one end allowance finding; spatial S and skew return have fitted/whole-lane
radius findings. Planar S has no hard preflight findings, but full compliance is
unresolved. Five constructed cases retain requested rolls,39 solids/trunk+19A19B
and clean named ending audits. Length goals warn; continuous final skin curvature,
strain,cap flow and global native clearance remain unmeasured. No acceptance claim.
Authored caps and planned targets match frozen matrix exactly; native guide-derived
target numeric roundoff max1.421e-14,route keys unchanged,not post-result repair.

`faith_native.py` records every stage/decision; `faith_fixtures.py` freezes layouts;
`PrescribedTwistDiagnostic` uses the existing global quintic prescription with
declared signed roll,original bank-rate exception,and modular endpoint validation.
Ordinary banking and historical FullTurnDiagnostic remain unchanged. Shared body
copy helper preserves prior three-array display behavior. No production changes.
43 existing affected tests passed,16 new tests rechecked after isolating mocked
memory/float-normalization assertions;59 unique focused tests passing overall.
Nine changed code files Ruff lint/format and IDE inspections clean;complete diff
reviewed. Verification/code-search skills focused checks on shared consumers;
full QA not run. Unit checks are not extra geometric validation cases.

Final active `Tube ribbon 4x - absolute-faith certificate array`,five fixed-slot
components195 solids total,39/19A19B each; screenshot visually inspected and F3D
archived. All six new scratches archived/closed(including empty failed scratch),
only result experiment array left open alongside all five original user designs.
Prior experiment documents closed on user's request,archives preserved.
Evidence `artifacts/verification/ribbon_cap_transition/faith_native/435bedfe25f245cc86db435fc01dddf0/`
contains plan/report,array.png,array.f3d; native failure
`artifacts/verification/ribbon_cap_transition/native/85a8e1315e0f47eda63d272232140ef4/`.
Scope exhausted/stopped; next bounded decision is investigation of this retained
self-intersection, not automatic tuning or promotion.

## Three-family input-certificate-limit array — 2026-10-06

User approved three uniformly tightened family variants, warnings non-blocking,
24 certificate probes per family, three native builds, zero retries,120 seconds
per case,2GiB monitored RSS, retain new array/scratch documents. The unchanged
certificate uses curvature*enclosing reach <=0.8 and depth16. Only centerlines
scale about their sphere centers;19x1.5mm material,114mm spheres and width
directions do not shrink. Newly positioned caps/connection targets freeze for
ALL three before any ribbon solve; no solver rerouting or native-driven tuning.
`array_limits.py` authors inputs; `array_limit_native.py` registers parents,
hashes, unknown native predictions, all probes and exact caps/targets upfront.
Authoring cap10s/family and390s total scheduling including authoring/display.

**3 planned /3 evaluated /3 solved /3 native-attempted /3 completely built /
0 fully master-rule audited**, denominator3. Overall0 accepted/2 known-rule
failed/1 unresolved; no invalid controls, skipped or unattempted cases. Three
development variants from examined families, not holdouts or generalized durability.
Native predictions unknown for all3; construction success is not compliance.

| Family | Passing scale | Input certificate ratio | Final sampled lane minimum radius | Native / audits / total |
| --- | ---: | ---: | ---: | --- |
| U-turn | 0.999999880791 | 0.799999997767 | 6.271mm | 6.877 /27.790 /49.224s |
| spatial S | 0.628472566605 | 0.799999981129 | 1.958mm | 7.155 /26.084 /47.272s |
| orthogonal bends | 0.605630874634 | 0.799999995601 | 1.396mm | 7.489 /28.445 /50.132s |

Each rejected/passing scale bracket width is2^-23; finite observed boundary, not
an exact physical/native minimum or final twisted-lane certificate.72 probes:
28 passing/44 rejected (U2/22,S14/10,orthogonal12/12),3.631s authoring,0 ribbon
solves during search. Same algorithm/budget across families. Input certificate
is necessarily recomputed inside the three solves, separately from authoring.
S and orthogonal retain `sampled_fitted_end_radius_below_trial_minimum` and
`sampled_whole_lane_bend_radius` findings: minimum required4.5mm. These rule failures
are NOT weakened, repaired or kernel failures. Passing the input envelope does
not certify these final fitted/twisted lanes. U-turn has no hard preflight finding.
All three retain360deg winding, trunk+19A+19B=39 solid bodies and clean named ending
audits. Full final-lane curvature/strain/native global clearance remain unmeasured.
Length goals still warn; no equality/mechanical accuracy claim.

Total case work146.628s; last build checkpoint176.102s includes search and
between-call overhead. Numerical prediction/preflight167.749/47.127/156.431ms,
separate from authoring, native and diagnostic audits. Final case RSS
1087152/1029472/1033664KiB. Display12.652s,RSS1089280KiB; all agreed caps respected,
in-flight peak/token cost unmeasured. Rigid display copies are presentation only.
Active `Tube ribbon 4x - certificate-limit 360 array` verified3 components with
39 solids each; new three scratch documents and previous array remain open.
Final inventory10 documents (user-controlled inventory), no document closed by
the runner. Screenshot visually reviewed and F3D archived.

22 focused tests passed, then8 affected tests rerun after test-only IDE adjustment;
four changed code files Ruff lint/format and IDE diagnostics clean, full diff
reviewed. Verification skills kept this focused; full QA not run. New authoring/
runner/tests and optional array display name only; no production/solver changes.
Evidence `artifacts/verification/ribbon_cap_transition/array_native/3380368dd3974c879d177d16fc4b7818/`:
plan/report plus display.json,array.png,array.f3d. Scope exhausted; no auto repair.

## Three-family array delivered under diagnostic waiver — 2026-10-06

User explicitly authorized: "ignore the violations and build the solids."
`array_diagnostic.py` renews ONLY the two unbuilt configurations, one solve/build
each, 120 seconds each /240 seconds renewal, 2 GiB monitored RSS, zero tuning or
retries. All frozen cases/caps/targets compare exactly with the stopped batch.
Completed U-turn reused, original rejection reports and empty scratch preserved.
Numerical/audit findings remain recorded but are not construction gates; resource,
source-drift, host-error and incomplete-construction stops remain. No solver or
production change. The historical stop below describes the original batch only.

Renewal: **2 planned/evaluated/solved/native-attempted/completely built, 0 fully
master-rule audited**. Across the array: three distinct configurations built,
not 117 configurations. S retains occupied-sphere rejection (known-rule failed);
orthogonal specimen has no hard preflight findings (full compliance unresolved).
Both have trunk+19A+19B=39 solids; named ending audits have no findings. Native
paired-side length diagnostics are 4.615% and20.000%, warning goals, not equal-length
claims. Overall array:0 accepted/1 known-rule failed/2 unresolved of3. No skipped
or unattempted configurations remain; no generalized durability claim.

| Renewed configuration | Native construction | Diagnostic audits | Total case |
| --- | ---: | ---: | ---: |
| spatial S 360 | 6.923 s | 27.991 s | 49.395 s |
| orthogonal bends 360 | 7.537 s | 31.089 s | 53.731 s |

Numerical preflight23.462/29.907 ms; final RSS979008/977904 KiB. Cumulative renewed
case work103.126 s; last build checkpoint114.543 s includes between-call overhead.
Rigid display copies took12.456 s, final RSS1014128 KiB, below agreed ceilings.
In-flight peak memory unmeasured. Presentation adds no solves or validation cases.
Live read-only inventory confirms active `Tube ribbon 4x - three-family 360 array`,
three components with39 solid bodies each, all11 documents retained. Screenshot
visually reviewed, array F3D archived; source geometry was not moved or modified.
U-turn/S/orthogonal sphere centers rigidly placed at X=-140/0/+140 mm.

14 focused scheduler/policy tests passed; changed runner/tests Ruff lint/format and
IDE inspections clean, complete diff reviewed. Verification skills kept checks
focused; full QA and continuous final-skin mechanical certification not run.
Evidence: `artifacts/verification/ribbon_cap_transition/array_native/9e1ea00daecf4b73b31a03b9a4f0dd76/`
contains renewal plan/report, display.json, array.png and array.f3d. No further
builds, retries or refinement authorized by this completed scope.

## Three-family four-width full-turn array — stopped, 2026-10-06

User approved three fixed configurations, one solve/native attempt each, zero
tuning/retries, 120 seconds per case /360 seconds batch, 2 GiB monitored Fusion
RSS, retain all documents. Expected diagnostic turnaround 2–3 minutes. Same
19x1.5 mm material, 114 mm sphere, short reverse-loft plans and explicit360
quintic winding/bank-rate exception ONLY. Solver and curvature policies unchanged.
`array_fixtures.py` freezes the repeated certificate-boundary U-turn, an existing
four-width spatial S with new full-turn B roll, and existing R30 perpendicular
bends with full-turn B roll and four-width sphere. Two scaffold-only calls author
transported B widths before caps/connection targets; not extra ribbon solves.
Every case/cap/target/hash and unknown native prediction registered upfront.

`array_native.py` schedules one case per call and latches failures. A new typed
`NativeGeometryPolicy.STOP_ON_KNOWN_FINDINGS` prevents native construction after
hard preflight rejection; historical explicit-rejection diagnostics retain their
default observe policy. Length goals still warn. Native provenance accepts the
frozen array parent/boundary notes without changing shapes or algorithms.

**3 planned /2 evaluated /2 solved /1 native-attempted /1 completely built /
0 fully master-rule audited.** Positive-case disposition: 0 accepted /1 known-rule
failed /1 evaluated unresolved /1 unattempted, denominator3. No invalid controls.
One repeated reference plus two new development roll variants, not three unseen
validation cases or proof of generalized durability. No false native acceptance:
predictions unknown. Native construction failure rate outside the attempted
reference is unmeasured; rejection below is NOT a kernel failure.

| Configuration | Numerical / native disposition |
| --- | --- |
| sphere4_reversal180_twist360_curve_limit | No hard findings; trunk+19A+19B=39 solids, ONE ribbon; named native audits pass, full compliance unresolved |
| array4_spatial_s_twist360 | Known occupied-sphere containment rejection; 0 native attempts/solids, all endings unattempted |
| array4_orthogonal_bends_twist360 | Not evaluated or natively attempted after mandatory stop |

S fixture: full guides56.291 mm and sampled trunk occupied radius56.439 mm fit
the sphere radius57 mm, but conservative branch-control-hull occupied bound
58.072 mm exceeds it by1.072 mm. This is a containment-certificate finding, not
proof of actual native skin protrusion or a Fusion construction failure. Input
curve certificate0.626706<0.8, sampled minimum lane radius10.714>4.5 mm, winding
360 degrees retained. No spacing/curvature/cap/end-allocation finding. Length
warnings: trunk30.048%, complete sampled29.390%, native complete lengths unknown.
The intentional preflight guard is labeled legacy `unexpected_failure` at shape
stage, but report overall explicitly `failed_known_geometry_rules` and native
attempt count0. No retry, target movement, larger sphere or check bypass.

Repeated U-turn: generation pipeline73.747 ms (includes adaptive certificate),
numerical diagnostics92.415 ms, native construction6.752 s, diagnostic audits
27.053 s, total47.307 s. Same48.170% trunk /46.833% complete sampled warnings;
continuous final-lane strain/curvature, native flow/global clearance unmeasured.
S: generation1.346 ms, numerical diagnostics19.959 ms, native/audits0, total
2.007 s. Cumulative case work49.314 s; batch timer69.440 s includes between-call
overhead. Stopped despite unused budget, not exhausted or automatically continued.
U-turn final RSS1,263,856 KiB (~1.205 GiB), largest between-operation sample
1,121,168 KiB; S final807,360 KiB. In-flight peak/token cost unmeasured.

All six documents present at launch preserved; user had closed older scratch
documents before this batch. New complete U-turn active as
`Tube ribbon array - 1 tight U-turn 360`; empty guarded S scratch retained as
`Tube ribbon array - 2 spatial S 360`. Inventory confirms39 solid bodies/19A/19B
versus0 S solids. Third scratch and side-by-side array NOT created. Array display
code is unexecuted: intended rigid body copies using the documented
[Autodesk temporary BRep sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager_Sample.htm),
not extra geometry coverage. No presentation copy capability claimed validated.

25 focused tests passed; five changed code files Ruff lint/format and IDE
inspections clean; complete diff reviewed. Verification skills kept checks focused
on authoring/scheduler/budget/policy consumers. Tests include mock hard/native/audit/
host stops and deterministic scaffold winding, not additional native coverage.
Full suite and continuous certification not run. Only new experimental fixture/
runner/display, native guard/provenance and tests; no production or solver changes.
Evidence batch `artifacts/verification/ribbon_cap_transition/array_native/160505c123a84fe1a4df7fd69eaf68a8/`;
reference native `c18799ba7be941119d12214ee5fc8845`, guarded S native
`0c1b65ed6264479eb7be6916128c9aa7` under the same ribbon-cap native artifact root.
Array delivery remains incomplete. Renewal needs explicit direction on the S
containment policy/fixture and remaining scope; no automatic local fix or rebuild.

## Four-width full-turn at the input-certificate boundary — 2026-10-06

User approved up to 24 unchanged curve-certificate checks during fixture authoring,
then ONE selected solve/native attempt, no retries, 120 seconds, 2 GiB monitored
Fusion RSS and retain-all documents. A conservative 10-second authoring scheduling
cap was also enforced. Same 114 mm sphere, 19x1.5 mm material, cap directions,
global quintic 360-degree roll and shared exact cap handoff; only the diagnostic
bank-rate exception persists. Parent `sphere4_reversal180_twist360_gap40`, selected
development case `sphere4_reversal180_twist360_curve_limit`. No solver changes,
rerouting, rule relaxation, production edits or untouched holdouts.

`curve_limit.select_radius()` first checks R20 then bisects its uniform scaling
family 23 times against the original `certify_curvature()` defaults: ratio 0.8,
maximum depth 16. Authoring probes: 12 passing /12 rejected, 24 total, 0 ribbon
solves or native attempts during search, 0.847 s. Every probe remains in the report.
Selected passing R18.16887617111206, cap gap **36.33775234222412 mm**. Lower rejected
radius 18.16887378692627, gap 36.33774757385254 mm; bracket width 0.000004768 mm
in gap. Keep the passing side, not the unobserved mathematical infimum. This is
the finite-depth certificate boundary for these quarter-cubic semicircles, NOT
the closest endpoint distance for arbitrary routes or a native material limit.
Adaptive subdivision explains why scaling the R20 reported ratio alone would
have stopped too early. Selected caps/targets froze after authoring and before the
sole solve; source/rule/production hashes verified again in Fusion. Unknown native
prediction recorded before construction. Search evidence:
`artifacts/verification/ribbon_cap_transition/curve_limit/8591cac8b216442d80c05e2a8513ff43/report.json`.

**1/1 complete configuration planned, evaluated, solved, natively attempted and
built; 0/1 fully audited to all master rules.** Positive cases 0 accepted /0 hard
geometry failures /1 unresolved of one. No invalid controls or skipped native
cases. Certificate rechecked normally in Fusion: maximum ratio 0.7999999968832509,
4,016 certified intervals (child computational work, not geometry coverage).
No detected hard numerical violations; whole-lane sampled minimum radius 6.271 mm
vs 4.5 mm. Full-guide/branch-hull diagnostics contained; sampled occupied radius
32.415 mm vs sphere radius 57 mm. Node winding 360.0 degrees, maximum average span
rate 0.206313 rad/mm (~2.81x original bound), explicitly excepted, not rate compliant.

Trunk +19/19 A +19/19 B reverse-lofts =39 native solids, ONE ribbon. Named section,
landmark, connection and interference audits passed. Length goals warn: sampled
trunk spread 48.170%, complete sampled 46.833% (gap40 parent 44.717% /43.514%).
Native paired seam spread approximately zero does NOT prove complete conductor
equality. Native complete lengths, continuous final-lane strain/curvature, global
clearance and native join/connection flow remain unmeasured; no full-rule acceptance.

Native-run shape pipeline 74.437 ms includes input certification; numerical
validation 93.341 ms. Native trunk 2.579 s + endings 4.038 s =6.617 s construction;
diagnostic audits 26.999 s, other overhead 12.987 s, native-run total 46.771 s.
Display/archive 1.676 s is nested in other overhead. Search + native run cumulative
47.618 s; no budget remains. Near-boundary adaptive certificate work rose from
20 intervals at R20 to 4,016; these are API/numerical pipeline times, not pure
kernel CPU or controlled speedup measurements. Maximum sampled between-operation
RSS 953,248 KiB, final 970,640 KiB (~0.926 GiB); in-flight peak unmeasured.
Token/cost data unavailable. Both scheduling/resource caps respected as measured.

Retained active document: `Tube ribbon 4x - U-turn 180 + twist 360 - curve limit`.
Read-only inventory confirms all nine preceding documents retained and 39 solids,
19 A and 19 B. Native report/image/archive:
`artifacts/verification/ribbon_cap_transition/native/6bd33481ff074bf78aa0d086d7c3416c/`.
Experimental authoring module/fixture, native provenance entry and tests only.
36 focused tests passed; after test-only IDE adjustment, all nine changed tests
passed again. Four changed code files Ruff lint/format and IDE inspections clean;
complete code/prose diffs reviewed. Focused verification skills constrained checks
to affected contracts; unit tests are not native geometry coverage. Full suite and
continuous/native certification not run. Scope exhausted; no further tightening,
certificate-depth increase, repair, retries or default bank-limit changes authorized.

## Four-width full-turn, closer caps — 2026-10-06

User approved one fixed-centerline variant: cap-center gap 60 to 40 mm by changing
the semicircle from R30 to R20. Same 114 mm sphere, 19x1.5 mm material, endpoint
directions, explicit global quintic 360-degree roll and exact cap handoff. New cap
positions and reverse-loft targets were frozen before solving. Parent:
`sphere4_reversal180_twist360`; case: `sphere4_reversal180_twist360_gap40`.
Bank-rate exception ONLY remains explicit; ordinary bank defaults, spacing and
macaroni checks unchanged. Unknown native prediction registered with source/input
hashes. Approved limits: one solve/native attempt, no refinements/retries,
120 seconds, 2 GiB monitored Fusion RSS, retain every document.

**1/1 planned, evaluated, solved, native-attempted and completely built; 0/1
fully audited to all master rules.** One development variant, not new family or
holdout coverage. Positive cases: 0 accepted / 0 hard geometry failures /
1 unresolved of one; no invalid controls, skipped cases or unsuccessful native
attempts. Trunk +19/19 A +19/19 B reverse-lofts =39 solids, ONE configuration.
Named native section, landmark, connection and interference audits passed.
Continuous final-lane strain/curvature, native join/connection flow, global
clearance and complete native conductor lengths remain unmeasured.

Node winding 360.0 degrees; maximum average span roll rate 0.187424 rad/mm,
~2.55x the unchanged 0.073488 experimental bound under the approved exception.
Enclosing-radius input certificate maximum ratio 0.787605 vs 0.8: little remaining
margin, not a native cloth certificate. Sampled minimum lane radius 7.072 mm vs
4.5 mm, sampled occupied radius 34.246 mm vs sphere radius 57 mm, full guides and
branch hull checks contained; no detected numerical hard violations. Length
warnings worsened: trunk 44.717%, complete sampled 43.514% (parent 30.267% and
29.579%). Native paired seams approximately zero spread, NOT complete-length proof.

Shape generation 2.039 ms, numerical validation 20.301 ms, native trunk 2.650 s,
endings 4.402 s (construction 7.052 s), diagnostic audits 27.515 s, other overhead
14.762 s, total/cumulative case work 49.350 s. Display/archive 1.854 s is a subset
of other overhead. API pipeline timings, not pure kernel CPU. Maximum sampled
between-operation RSS 991,168 KiB; final 1,140,320 KiB (~1.088 GiB), below ceiling;
in-flight peak and token/cost data unmeasured. Scope exhausted; no further builds.

Active retained document: `Tube ribbon 4x - U-turn 180 + twist 360 - gap 40`;
all eight prior documents preserved, verified read-only: 39 solids and both sets
complete. Evidence/image/archive:
`artifacts/verification/ribbon_cap_transition/native/254d7fbda0614f2aa256ee1e4ee75048/`.
Changed experimental fixture, dedicated native entry/provenance and unit test;
no solver or production modifications. 24 focused tests passed; three changed
code files Ruff lint/format and IDE inspections clean. A new test initially used
unsupported vector operators; corrected to established vector helpers before any
native execution. Full suite and continuous-native certification not run. The
verification skills kept scope focused; unit tests are not extra ribbon coverage.
Next bounded decision requires user approval; do not automatically tighten again
or tune this specimen. Construction success does not establish mechanical accuracy
or generalized solver durability.

## Four-width full-turn diagnostic — 2026-10-06

User approved one fixed U-turn/360-degree twist diagnostic, one solve/native
attempt, zero tuning/retries, 120 seconds, 2 GiB Fusion RSS, all documents retained.
Explicit exception: experimental width-scaled bank-rate bound ONLY. The 114 mm
sphere, 30 mm-radius U-turn cubics, 19x1.5 mm material, nominal spacing, curvature
checks, exact cap handoff and frozen reverse-loft plans are retained. Parent case:
`sphere4_reversal180_twist180`; this is a roll variant, not a new geometric family.
B width returns to +Y for a full turn, so its ordered cap/connection inputs were
authored accordingly BEFORE generation; no post-result relocation. This is not
an identical-boundary-condition comparison with the half-twist.

`FullTurnDiagnostic` prescribes one global quintic roll over chord-distance nodes,
not a tuned bank search. `master_scaffold()` and `solve_tube_ribbon()` accept the
explicit typed prescription; ordinary callers retain the unchanged bounded-bank
pass. Enclosing-radius input certification, final-lane diagnostics and all other
policies remain intact. No auto full-turn fallback. Principal endpoint orientation
alone would allow zero roll; finite-node accumulated roll is checked before native
construction, preventing that false outcome. Production code/rules untouched.

**1 planned / 1 evaluated / 1 solve / 1 native attempt / 1 complete build / 0
fully audited to all master rules.** Geometry positive case: 0 accepted / 0 hard
geometry failures / 1 unresolved out of one; one explicitly excepted rate finding.
No invalid controls. Native prediction registered as unknown. Diagnostic development
case, not holdout/generalized readiness evidence. Approved attempt exhausted.

`sphere4_reversal180_twist360` built the trunk and 19/19 A + 19/19 B reverse-lofts,
39 solids = ONE complete ribbon. Native section, landmark, connection and
interference checks reported no findings. Authored node net roll measured 360.0
degrees. Maximum average span roll rate 0.124949 rad/mm exceeds the original
0.073488 rad/mm by ~1.70x. This is an acknowledged bank-policy exception, not a
pass under the original limit or a continuous/native safe-twist certificate.

Sampled minimum whole-lane radius 12.199 mm vs required 4.5 mm; nominal 1.5 mm
station pitch/order retained. Sampled occupied radius 44.247 mm vs sphere radius
57 mm; full guides and branch hull diagnostics contained. Native vertex-only
radius 33.661 mm is NOT skin containment. No sampled hard geometry findings.
Length goals still WARN: trunk sampled spread 30.267%, complete sampled 29.579%.
Native paired seam spread approximately zero meets that separate goal, but does
not establish equal conductor lengths; native complete lengths unmeasured.
Continuous final-lane curvature/strain, native join/connection skin tangency and
global clearance remain unmeasured. No full-rule or mechanical acceptance claim.

Generation 1.610 ms, numerical validation 20.115 ms, native trunk pipeline 2.679 s,
all endings 3.854 s (construction 6.533 s), diagnostic audits 29.345 s, other
overhead 13.116 s, total 49.015 s. Compared with 180 degrees, both roll-field
strategy and B boundary roll differ: no controlled native speedup claim. Timers
include API authoring overhead, not pure kernel CPU. Maximum between-operation
sample RSS 1,013,744 KiB, final 1,104,080 KiB (~1.053 GiB), below ceiling;
in-flight peak unmeasured. Token/cost data unavailable. No further scheduling.

Retained active document: `Tube ribbon 4x - U-turn 180 + twist 360 - diagnostic`.
Every pre-run document, including the successful 180-degree result, retained.
45 focused tests passed; six changed-code Ruff lint/format and IDE inspections
passed. Tests cover winding, incompatible targets, bank defaults, unit scaffold,
existing authoring/cap/sphere/budget consumers; not additional geometry validation.
Full suite and continuous native certification not run. New experimental policy,
optional solver/scaffold wiring, fixture/native entry and tests only. Evidence:
`artifacts/verification/ribbon_cap_transition/native/6d792f0eb9d44b84900b53890a9839d9/`.
Next bounded review: native construction tolerates this prescribed roll beyond the
experimental bank limit on ONE fixed specimen; do not loosen the default limit or
promote the diagnostic without diverse-case evidence and separate approval.

## Four-width reversal/half-twist native result — 2026-10-06

User renewed ONE solve/native attempt after the setup stop below, keeping the
same fixed fixture/targets, unchanged tube solver, 120-second scheduling cap,
2 GiB Fusion RSS ceiling and retain-all-documents policy. Only the private harness
binding changed: `native_policy.py` passes the explicit 4x multiplier to the
existing sphere auditor. Full-guide containment and the auditor's shared 5x
default remain intact; wrong size/displaced-guide regressions are tested.
The source/fixture/rule hashes, fixed cap/connection inputs and unknown native
prediction were registered before construction. No tuning or post-result repair.

**1 planned / 1 numerically evaluated / 1 solve / 1 native attempt / 1 complete
build / 0 fully audited to all master rules.** Positive-case acceptance: 0 accepted /
0 hard failures / 1 unresolved out of one. No invalid controls. The prior setup
stop and this renewed attempt are the SAME configuration, not two geometry cases.
Known-violation-free sampled preflight remains unresolved, not predicted acceptance.

`sphere4_reversal180_twist180` constructed the trunk and BOTH reverse-loft sets:
19/19 A endings and 19/19 B endings, 39 solids representing ONE complete ribbon.
Native section, landmark, all connection and interference checks reported no
findings. Native cap handoff was exercised with the same solved frames used by
the exact frozen-plan guard; no relaxed input equality or target displacement.
Post-run replay of the 32 authored section observations measured 180.0 degrees
net roll relative to shortest tangent transport and endpoint tangent dot -1.0,
confirming the requested half-twist/U-turn at the sampled scaffold. Zero extra
solves/builds for this replay; it does not certify between-section skin/strain.

Mechanical goals WARN, not geometry rejection: sampled trunk spread 32.610%,
sampled complete spread 31.813%, native paired-seam spread 32.721%. Complete
native conductor lengths remain unmeasured. Sampled whole-lane minimum radius
7.813 mm exceeds the 4.5 mm trial minimum; nominal 1.5 mm station pitch/order
retained. Sampled occupied radius 44.255 mm vs the 57 mm sphere radius. Native
vertex-only maximum 33.619 mm is a weaker diagnostic, not a skin-containment
proof. Continuous conductor curvature/strain, native cap/connection flow and
global clearance remain unmeasured; no generalized or production acceptance.

Timings: shape generation 1.609 ms; numerical validation 20.271 ms; native trunk
pipeline 2.924 s; all reverse-lofts 4.385 s (native construction 7.308 s). Diagnostic
audits 23.604 s, other overhead 13.369 s, total 44.303 s. These are instrumented
API pipelines, not pure kernel CPU or a native-baseline speed comparison. The
earlier setup-stop overhead adds 2.209 s, giving 46.512 s cumulative for this
configuration across the two explicitly authorized sessions. Peak sampled RSS
1,030,208 KiB (~1006 MiB), final 971,616 KiB (~949 MiB), below 2 GiB. Token/cost
data unavailable. Approved solve/native attempt exhausted, no automatic continuation.

Active retained document: `Tube ribbon 4x - U-turn 180 + twist 180 - run 2`.
Previous documents and empty setup-stop scratch were not closed or discarded.
Only experimental policy binding, its tests and reporting changed this renewal;
production, solver algorithm, material/spacing rules and fixed geometry untouched.
11 focused policy/handoff tests passed; three changed-code Ruff lint/format and
IDE inspections passed. This is code-contract evidence, not additional geometry.
Full suite and continuous-native certification not run. Evidence/archive/image:
`artifacts/verification/ribbon_cap_transition/native/f8c8300316c7418ea85902fe3fec4ee3/`.
Next review: transfer the shared geometry method to distinct bend/twist challenges
under a newly approved bounded scope, keeping length compensation separate.

## Four-width reversal/half-twist setup stop — 2026-10-06

User explicitly approved ONE 4x-sphere configuration with a 180-degree U-turn
and 180-degree twist: one solve/native attempt, zero tuning/retries, 120 seconds,
2 GiB Fusion RSS, all existing/new documents retained. `reversal_case()` freezes
two tangent-continuous 30 mm-radius quarter-cubic approximants, 19x1.5 mm lanes,
opposite Y endpoint widths and a 114 mm sphere centered at the origin. No obstacle
or route search. Fixed short reverse-loft targets and the tube solver remain
unchanged. `CapFrameHandoff` shares equivalent solved cap objects with native
ending requests after a 1e-12 component-vector/mm equivalence check; frozen-plan
equality stays exact. Historical native procedure remains selectable unchanged.

**1 planned / 0 numerically evaluated / 0 solves / 0 native attempts / 0 built /
0 fully audited.** The only case is unresolved/unattempted geometrically due to
a harness setup error, not a kernel or solver rejection. No invalid controls.
`sphere4_reversal180_twist180` stopped at `end_boundary`: the shared legacy
`audit_end_boundary()` requires FIVE widths. The runner's missing 4x policy adapter
was a setup mistake, not an intentional partial geometry outcome. Frozen 4x
inputs were not changed to satisfy that guard. No retries or automatic fixes.
Native prediction remains unknown; all 38 reverse-lofts unattempted.

Elapsed 2.209 s, all setup/display/archive overhead; solve, build and audit timings
zero. Final RSS 728,256 KiB (~711 MiB), later inventory 663,360 KiB (~648 MiB),
well below the ceiling. Token/cost data unavailable. Active retained document
`Tube ribbon 4x - U-turn 180 + twist 180` is EMPTY. All six documents present at
pre-run inventory, including the previous spatial result, remain open. No complete
native outcome, twist behavior, cap-handoff transfer or compliance claim supported.

32 focused tests passed; four changed-code Ruff lint/format and IDE inspections
passed. Tests cover fixture boundaries, synthetic cap identity/atomic rejection
across the original plus three collateral inputs, existing budget/scheduler/master
and end preflight contracts. They do not validate native geometry or the missed
legacy sphere gate. Production and the tube algorithm were not edited. New code:
`cap_handoff.py`, reversal fixture/native entry point, focused handoff tests.
Evidence: `artifacts/verification/ribbon_cap_transition/native/2678215211d2433ca458860d2f4c1529/`.
Renewal decision required: adapt only the private harness sphere-policy check to
the approved 4x size, preserving full-guide containment, then launch at most one
solve/native attempt under the same caps in a distinctly named retained document.

## Native master-tube diagnostic — 2026-10-06

User approved three preselected complete configurations, three solves/native
pipeline attempts, zero tuning/retries, 120 seconds per case, 360 seconds total,
2 GiB Fusion main-process RSS. Explicit retention override: leave all new scratch
documents open, including partial failures; never close existing documents.
`tube_native.py` freezes all three cases/caps/targets and fingerprints before
construction. `native.py` selects a typed procedure, retaining historical defaults.
Native build predictions were unknown, not predicted passes. No production edits.

**3 planned / 1 numerically evaluated / 1 native-pipeline attempted / 0 complete
builds / 0 fully audited.** Positive cases: 0 accepted / 1 unsuccessful / 2
unattempted; continuous compliance unresolved. No invalid controls in this batch.
All examined development configurations, no untouched holdouts or generality claim.

| Configuration | Numerical result | Native result / disposition |
| --- | --- | --- |
| spatial_s_twist45_19x1.5 | No detected hard finding; length goals warn | Trunk + all 19 A branches built; B1 stopped by frozen-plan input guard before its native loft |
| regression_asymmetric_arch | Not evaluated in this batch | Not attempted after stop |
| regression_twisted_quarter | Not evaluated here; earlier radius/end rejection remains | Explicitly diagnostic selection, not attempted after stop |

The retained document `Tube ribbon 5x - spatial S +45` has 20 verified solid
bodies: workload of ONE incomplete configuration, not 20 geometry successes.
All seven preceding documents remain open. Native trunk section and landmark
audits reported no findings; all A connection/section checks completed. Paired
seam length spread is 0.8273%, within the 1% goal; complete native conductor
lengths remain unmeasured. Native vertices lie within the loose sampled sphere
limit (65.4994 mm vs radius 71.25 mm), not a continuous skin proof. Continuous
lane curvature/strain, join flow/tangency and global clearance remain unmeasured.

Failure is **not a B-branch kernel rejection**: `EndPlan.__call__` compared the
construction inputs by exact equality and rejected them. Read-only code/data
inspection shows the harness constructs endings with its earlier banked frames,
while preflight freezes against the new shape frames. Replaying the already
archived cold scaffold (zero new solves/builds) gives identical endpoint tangents
but B thickness components differing by approximately 1.11e-16 and 1.39e-17.
A inputs agree. This supports a floating-point frame-source mismatch, not a
demonstrated macaronic failure. No guard weakening, solver adjustment or retry.
Next bounded decision: use one authoritative cap frame for planning and native
ending requests, test identity/ordering/target preservation, then renew native
coverage with the other structurally distinct challenges retained.

Observed shape solve 1.332 ms; numerical diagnostics 19.580 ms; trunk native
pipeline 2.968 s; A endings 1.653 s. Diagnostic audit timers total 18.457 s;
other overhead 8.211 s; total case 31.310 s. Construction timers include profile
authoring and API overhead, not just kernel CPU; branch audits are timed separately.
No native baseline comparison or native speedup claim. Peak sampled RSS
775,536 KiB (~757 MiB), final 780,496 KiB; later inventory 697,200 KiB. Token/cost
data unavailable. Batch stopped despite unused budget, with no renewal/refinement.

Focused verification: 16 tests for scheduler retention/stop/error boundaries,
resource limits and master frames; changed-code Ruff lint/format and IDE inspections
passed. Unit counts are not geometry coverage. Archived scratch and screenshot:
`artifacts/verification/ribbon_cap_transition/native/4492dd2251244e6683f7c86de8a9fe61/`.
Frozen batch plan/all dispositions:
`artifacts/verification/ribbon_cap_transition/tube_native/63f1473c1746480e87ca56c85399c2c1/`.

## Cold master-tube cost comparison — 2026-10-06

User approved eleven fixed configurations, at most 22 solves, zero tuning/native
builds, 60-second scheduling cap and 512 MiB host ceiling. A five-second estimate
stop remains stricter than the cap. Question is COMPUTATIONAL COST, not looser
geometry acceptance. All baseline inputs, cap fits, identities/order and complete
connection plans were frozen before generation; source/rule/fixture and production
fingerprints stayed unchanged. No Fusion calls, document changes or production edits.

Candidate `master_frames.py` evaluates exact positions/tangents/curvature on 32
nodes using a fixed 128-interval-per-cubic chord-length lookup. It minimally rotates
width between exact tangents and makes one greedy bank pass toward easy-axis bends,
reserving enough angular distance to reach the fixed end guide. Roll increments
reserve the 1.875 maximum slope of quintic easing under `2*pi/(3*width)` radians/mm.
This width-scaled experimental rate is NOT a Fusion-derived safe twist law, and
easing/transport between nodes remains uncertified. No roll lattice, full-turn
fallback, lane blend, fold/equalization/wrinkle search or rerouting occurs.
`tube_solver.py` retains the current continuous enclosing-radius macaroni input
certificate, authors ordered nominal-pitch lanes, preserves exact cap centers and
lobe orientations, then measures sampled lengths. First/last spans count as end
treatment unless exact rigid translated geometry needs no authored correction.
Frozen reverse-loft endings are inspected by the unchanged diagnostic procedure,
not built. Final conductor curvature, native skin flow and continuous clearance
are not certified by the input tube. Mechanical length goals still only warn.

**11 planned / 11 baseline-evaluated / 6 candidate-evaluated / 0 native-attempted /
0 built / 0 fully audited**. Seventeen solve calls, zero retries/refinements, no
harness errors. Baseline ten positives: 0 accepted / 4 failed / 6 unresolved.
Candidate six evaluated positives: 0 accepted / 2 failed / 4 unresolved; four
positive candidates unattempted. Invalid control correctly rejected in baseline,
unattempted in candidate. Native failure rate unmeasured. All development cases,
not untouched holdouts; no native/generalized readiness claim.

| Complete configuration | Baseline generation ms | Candidate generation ms | Candidate numerical disposition |
| --- | ---: | ---: | --- |
| sphere5_both_outward | 13.204 | 2.242 | Unresolved; no detected violation |
| sphere5_both_inward | 16.601 | 7.268 | Unresolved; envelope-growth comparison stop |
| sphere5_A_out_B_in | 15.265 | Unattempted | Skipped after stop |
| sphere5_A_in_B_out | 15.291 | Unattempted | Skipped after stop |
| sphere5_gentle | 11.576 | Unattempted | Skipped after stop |
| spatial_s_twist45_19x1.5 | 49.938 | 2.538 | Unresolved; no detected violation |
| spatial_s_twist-90_19x1.5 | 33.912 | Unattempted | Skipped after stop |
| sphere5_invalid_tight | 0.343 early rejection | Unattempted | Skipped after stop |
| regression_twisted_quarter | 18.899 | 2.416 | Failed: sampled radius and 23 combined end findings |
| regression_orthogonal_bends | 40.334 | 2.988 | Failed: sampled whole-lane radius |
| regression_asymmetric_arch | 14.358 | 2.505 | Unresolved; no detected violation |

Across the SIX MATCHED cases, generation wall time totals **153.333 ->19.956 ms**
(7.68 times less elapsed time, ~87% reduction), process CPU **153.316 ->19.949 ms**.
Identical numerical diagnostics total **226.794 ->224.208 ms**, effectively unchanged.
Matched generation+diagnostics **380.127 ->244.164 ms**, approximately 1.56x faster
(36% less time), excluding fixture preparation, imports and report serialization.
The original spatial case alone is **49.938 ->2.538 ms** generation (~19.7x), while
generation+diagnostics is **87.609 ->39.191 ms** (~2.24x). These are observed single
timings, not statistically established speedups. No stored geometry/seed/result is
replayed, but imports are already loaded and baselines precede candidates, leaving
process warm-up/order effects uncontrolled. Baseline retains its original fold
search; candidate deliberately does less mechanical optimization. Faster numerical
generation is not equivalent output quality, native speed or complete build speed.

All six candidates preserve measured 1.5 mm station spacing/order, planar section
centers and zero cap-center gaps. Spatial +45 minimum sampled radius improves
4.59750 ->5.81684 mm; its sampled findings clear, but it remains unresolved without
native/continuous evidence. Trunk length spread rises 6.723% ->7.239%, warning only.
Twisted/compound collateral cases remain below required 4.5 mm sampled radius
(4.46914/2.99540 mm), although baseline radii improve and findings reduce. Compound
length spread worsens 11.291% ->22.965%, separately reported as a mechanical goal.

Stop fired on candidate `sphere5_both_inward`: occupied sampled radius increased
45.519108 ->45.575802 mm (+0.056694), still inside its 71.25 mm sphere and with no
detected hard geometry violation. The frozen comparator treats ANY envelope growth
above 1e-7 as a review regression, so it stopped scheduling the five remaining
candidates. This is a comparison-policy stop, not a demonstrated containment failure.
Exact-node versus polyline sampling may affect envelope maxima; no retuning, gate
loosening or rerun was used to continue. The triggering case and all three collateral
challenges were reached before that stop. No promotion/native build is authorized.

Batch turnaround **2.317 s**: all generation calls including early rejection 0.250 s,
all numerical diagnostics 0.603 s, other setup/fingerprinting/serialization overhead
1.464 s. Native build/audit time absent. Peak host RSS 143,114,240 bytes (~136.5 MiB),
below 512 MiB; Fusion memory/token cost unmeasured. Scope stopped despite unused
solve/time budget; no automatic continuation. Evidence supports a numerical cost
advantage on six cases, with diagnostics now dominating that measured work. Next
review is practical construction and the envelope-growth stop policy, not another
length-equalization search or a claim of complete geometry compliance.

Verification: 32 focused master-frame/authoring/sampling tests passed in 0.14 s;
five changed-code Ruff lint/format and IDE checks passed. Exact derivative nodes,
multi-curve traversal, cap/spacing authoring, distance/rate constraints and both
authoring/tube stop schedules covered. Mocked scheduler/authoring checks do not add
independent geometry coverage. No full suite, native checks or continuous-lane proof.
Evidence: `artifacts/verification/ribbon_cap_transition/tube_cost/817b8c40dc764c839b1cd929879afe50/`.

## Directional tube/ribbon diagnostic replay — 2026-10-06

User requested evidence of an advantage from an enclosing tube plus oriented x/y
macaroni calculation, with length measurement/correction deferred. This first
experiment is deliberately a cheap cached diagnostic, NOT an implementation or
benchmark of that new solver. Scope: eleven frozen configurations, zero new solves,
zero bank searches/refinement/native builds; 60-second scheduling cap and 512 MiB
host peak RSS ceiling. Original cap/connection targets and reverse-loft direction
inheritance are untouched because no geometry changes. Production and rules stay
unchanged. No Fusion calls or document changes; native prediction remains unknown.

`directional_replay.py` uses the eleven saved baseline records from the authored-
section comparison, source report SHA256 recorded in its plan. Ten have existing
32-node banked scaffolds; the correctly rejected tight control has no samples and
is retained as unmeasured. It estimates curvature with projected finite tangent
differences divided by chord distance. On IDENTICAL existing orientations it
compares circular `hypot(a,b)*|k|` and rectangular `a*|k_width|+b*|k_thickness|`
support, using `a=(lines+0.2)*diameter/2`, `b=diameter/2` to retain the current
enclosing lobe dimensions. The rectangle is enclosed by that circle; directional
support cannot exceed the circular value for an orthonormal frame. Smaller values
are mathematical screening information, not demonstrated new feasible geometry.
Current banking already penalizes width-axis bending; this replay does not improve
the bank solution. A pointwise ideal-bank lower bound is recorded but ignores caps,
continuity and twist and must not be treated as an attainable bank policy.

**11 planned / 10 cached proxy-evaluated / 0 newly solved / 0 native-attempted /
0 built / 0 fully audited**. One invalid control unmeasured (no archived frames),
no harness errors or budget skips. Historical positive-case dispositions remain
0 accepted / 4 failed / 6 unresolved out of ten; invalid correctly rejected 1/1
historically, not newly tested. Native failure rate unmeasured; no case is promoted.
All cases are examined development data, not untouched validation.

| Complete configuration | Circular proxy | Directional proxy | Maximum estimated bank degrees/mm |
| --- | ---: | ---: | ---: |
| sphere5_both_outward | 0 | 0 | 0 |
| sphere5_both_inward | 0.687154 | 0.035741 | 0 |
| sphere5_A_out_B_in | 0.677628 | 0.035245 | 0 |
| sphere5_A_in_B_out | 0.677628 | 0.035245 | 0 |
| sphere5_gentle | 0.880854 | 0.045816 | 0 |
| spatial_s_twist45_19x1.5 | 0.409619 | 0.189054 | 6.016 |
| spatial_s_twist-90_19x1.5 | 0.409619 | 0.381056 | 5.172 |
| sphere5_invalid_tight | Unmeasured | Unmeasured | Unmeasured |
| regression_twisted_quarter | 0.880854 | 0.426655 | 7.885 |
| regression_orthogonal_bends | 0.533927 | 0.092865 | 7.570 |
| regression_asymmetric_arch | 0.641778 | 0.033381 | 0 |

Worst directional proxies are approximately 95% lower on pure easy-bend cases,
54% lower on spatial +45, 7% lower on spatial -90, 52% lower on twisted quarter
and 83% lower on compound bends. This supports orientation-sensitive screening,
not solver performance or construction improvement. The original spatial failure's
circular AND directional centerline proxies are already below 0.8: the new number
alone does not repair its cap/spacing/conductor-curvature problems. Recorded bank
rates are measurements, not certified safe limits; rapid twisting of a straight
centerline is invisible to BOTH bending formulas, as the focused test demonstrates.

Measurement anomaly retained: gentle and twisted-quarter circular proxies exceed
0.8 despite their original input curves passing continuous certification. Both
peaks occur at nodes 8 and 23 on the same quarter-curve geometry. Inspection shows
`ribbon_frames()` first linearly resamples a route polyline and then estimates
interior tangents from chords, whereas the certificate uses exact cubic geometry.
This supports a sampling-artifact explanation, not a proven native defect or false
certificate. No retuning or recalculation was used to rescue the result. Finite
frame-derived proxies MUST NOT replace the continuous rule. A follow-up should
derive tangent/curvature and bank transport from the exact master curve before
evaluating a new shape-generation procedure, with separately agreed budget.

Turnaround **0.059 s**, including 0.00441 s arithmetic/parsing and approximately
0.0545 s loading/fingerprinting/report preparation; report final write excluded.
No search/build/audit time (unattempted). Cached timing is NOT end-to-end solve time
or measured speedup. Host peak RSS 35,241,984 bytes (~33.6 MiB); Fusion memory and
token cost unmeasured. Source/code/production fingerprints unchanged. Nine focused
tests, two changed-file Ruff lint/format checks and IDE inspections passed; no full
suite or native checks. Rules and production untouched; original report preserved.
Evidence: `artifacts/verification/ribbon_cap_transition/directional_replay/2f6913130d8743749c407b2b9e435f24/`.

## Shared section authoring v1 — stopped on curvature, 2026-10-06

Question: can nominal-pitch planar sections eliminate the spatial construction
representation mismatch without breaking another mechanic? User approved at most
eleven fixed configurations, 22 solves, 60 seconds, zero tuning/native attempts.
The run added a conservative five-second estimate stop and 512 MiB host peak-RSS
scheduling ceiling. All inputs, conductor identities, cap fits and short-connection
targets were frozen before solving. Source/rule/fixture and production fingerprints
were unchanged throughout. No Fusion calls or document changes occurred.

Procedure: baseline retains cap-transition-v2 and its original fold search.
Candidate directly authors ordered lanes from the same 32 banked section nodes
at nominal pitch, with no individual lane blend, projection or length search.
`candidate_frames()` shares input validation and unchanged banking; baseline
blending/search behavior remains unchanged. `SectionField` defines a piecewise
quintic origin and normalized eased-width interpolant with matching C2 node jets
and exact cap tangents. Width derivatives vanish at every node, not only caps:
this deliberate initial simplification is not an optimized orientation field.
Only node/chord geometry was screened; the field's continuous curvature, speed,
clearance and containment were not certified. Intermediate sections may be slanted
relative to the interpolated centerline. Input route nodes remain fixed, but this
interpolant is neither the original continuous route nor Fusion's loft. Its first/
last span is the cap-specific derivative treatment; the larger span conservatively
sets both end supports. Different strategy/search budgets prohibit interpreting
runtime differences as equal-budget optimizer performance.

**11 planned / 11 baseline-evaluated / 1 candidate-evaluated / 0 native-attempted /
0 built / 0 fully audited**. Twelve solve calls; no refinements or retries. Baseline
ten positive cases: 0 accepted / 4 failed / 6 unresolved. Candidate positive cases:
0 accepted / 1 failed / 0 evaluated-unresolved, with 9 of 10 unattempted after stop.
The invalid control was correctly rejected in baseline; candidate invalid screening
was unattempted. Native failure rate unmeasured. All examined cases are development,
not untouched validation; no collateral or control preservation claim is supported.

| Complete configuration | Baseline numerical outcome | Candidate outcome |
| --- | --- | --- |
| sphere5_both_outward | Unresolved; no detected violation | Not attempted: curvature stop |
| sphere5_both_inward | Unresolved; no detected violation | Not attempted: curvature stop |
| sphere5_A_out_B_in | Unresolved; no detected violation | Not attempted: curvature stop |
| sphere5_A_in_B_out | Unresolved; no detected violation | Not attempted: curvature stop |
| sphere5_gentle | Unresolved; no detected violation | Not attempted: curvature stop |
| spatial_s_twist45_19x1.5 | End allowance and section compression findings | Failed: new fitted/whole-lane radius findings, two end-allowance findings retained |
| spatial_s_twist-90_19x1.5 | End allowance and compression findings | Not attempted: curvature stop |
| sphere5_invalid_tight | Correct input-curvature rejection | Not attempted: curvature stop |
| regression_twisted_quarter | End allowance, whole-lane radius and compression findings | Not attempted: curvature stop |
| regression_orthogonal_bends | End allowance, fitted/whole-lane radius and compression findings | Not attempted: curvature stop |
| regression_asymmetric_arch | Unresolved; no detected violation | Not attempted: curvature stop |

Original spatial +45 case: pitch range becomes 1 within approximately 4.4e-15;
minimum signed lane order is 1.5 mm. Maximum station-center plane offset reduces
from 0.834902 mm to 5.4e-15 mm, exact cap center gaps remain zero, and sampled
occupied radius is unchanged. BUT sampled minimum whole-lane radius falls from
4.59750 to 4.21148 mm, below the required 4.5 mm; fitted-end radius also worsens
from 5.03834 to 4.21148 mm. Combined end findings reduce from 38 to two (end B,
lanes 1/19), but this does not offset new curvature failures. Trunk length spread
increases from 6.723% to 9.713%, a warning goal. Finite cap chords worsen and are
recorded separately from the explicit field's endpoint derivatives; neither
establishes native skin flow. The first candidate triggered the regression stop
correctly: ten later candidates were skipped, not silently counted as passing.

Total **1.608 s**: solves 0.251 s, numerical inspection 0.446 s, other preparation/
serialization overhead 0.910 s. Build/audit time absent. Host peak RSS 82,952,192
bytes (~79.1 MiB), below 512 MiB; Fusion memory unmeasured/unaffected by this run,
token cost unavailable. Scope stopped at review despite unused numerical budget.
Do not promote or build this candidate; next decision is whether to authorize a
spacing-preserving orientation/curvature strategy, not a spacing relaxation.

Verification: 48 focused tests across authoring, sampling, cap transition and
stage recording passed; after final test-only edits the 12 authoring/scheduling
tests passed again. Changed-file Ruff lint/format and all four IDE inspections
passed. No full suite, continuous certificate, native build or post-build audit.
The scheduler unit test uses inert shapes and does not add geometry coverage.
Evidence: `artifacts/verification/ribbon_cap_transition/authored_sections/e43b41466f8242db9a715a8718bfd666/`.

## Section plane intersection comparison 2026-10-06

One host-only candidate intersects each lane polyline with the two source segments
adjoining each interior frame plane. It requires a unique local crossing and
increasing source traversal; no projection, remote crossing fallback, target
movement or new solver search occurs. Exact cap samples/fits and banked frames
remain fixed. Reconnecting the intersections changes sampled polylines, so their
length/radius measurements do not establish continuous path or tangent preservation.
The candidate is not installed in the Fusion builder.

Approved scope: eleven fixed configurations, baseline versus one unchanged
adjustment, maximum 22 solves, 60-second scheduling cap, zero tuning/native builds.
The run also used a five-second estimate stop. Inputs and every connection target
were frozen before evaluation; all eleven baselines preceded candidates. Candidate
order was the original spatial +45-degree failure, three collateral cases, then
retained controls. Source/fixture/rule and production fingerprints stayed unchanged
during the run. These are development cases, not untouched holdouts.

**Stop protocol limitation:** the initial comparator caught new hard findings and
worsening radius/envelope but missed worsening minimum spacing when compression
was already a finding. All eleven candidates ran before the report review exposed
that regression. The first candidate should have stopped further scheduling; the
ten later attempts are retained diagnostics, not a clean stop-compliant comparison.
The original report's empty `new_regressions` lists are incomplete. A separate
`post_run_review.json` qualifies them without overwriting the report. The spacing
stop check was corrected and unit-tested afterward; no geometry was rerun and no
candidate tuning or promotion followed.

Actual coverage: **11 planned / 11 baseline-evaluated / 11 candidate-evaluated /
0 native-attempted / 0 built / 0 fully audited**, 22 solve calls, no skips/harness
errors. Each procedure has ten positive cases: 0 accepted / 4 failed / 6 unresolved.
One invalid control was correctly rejected in each procedure. Native failure rate
is unmeasured. The new diagnostic checks assess sampled section order and nominal
minimum spacing equally in baseline and candidate; historical reports are unchanged.

| Complete configuration | Baseline and candidate numerical outcome | Minimum pitch ratio baseline to candidate |
| --- | --- | --- |
| sphere5_both_outward | Unresolved; no detected violation | 1 to 1 |
| sphere5_both_inward | Unresolved; no detected violation | 1 to 1 |
| sphere5_A_out_B_in | Unresolved; no detected violation | 1 to 1 |
| sphere5_A_in_B_out | Unresolved; no detected violation | 1 to 1 |
| sphere5_gentle | Unresolved; no detected violation | 1 to 1 |
| spatial_s_twist45_19x1.5 | End allowance and section compression findings | 0.983677 to 0.977983; worse |
| spatial_s_twist-90_19x1.5 | End allowance and section compression findings | 0.986439 to 0.983564; worse |
| sphere5_invalid_tight | Correct input-curvature rejection before section sampling | Not measured |
| regression_twisted_quarter | End allowance, whole-lane radius and compression findings | 0.995294 to 0.993565; worse |
| regression_orthogonal_bends | End allowance, fitted/whole-lane radius and compression findings | 0.999738 to 0.999735; worse |
| regression_asymmetric_arch | Unresolved; no detected violation | 1 to 1 |

The original spatial case's maximum lane-center plane offset over all stations
fell from 0.834902 mm to approximately 7e-15 mm. Minimum paired-center spacing
fell from 1.47552 mm to 1.46697 mm for 1.5 mm conductors: planarity improved while
spacing worsened. Its sampled minimum radius improved from 4.59750 to 4.87700 mm;
trunk length spread improved slightly from 6.723% to 6.657%, still a warning goal.
All ten generated cases retained exact cap points with zero measured center gap.
Six planar cases were numerically unchanged. No lobe closure, native skin flow,
continuous clearance or complete native material-length claim follows.

Total diagnostic turnaround **3.537 s**: timed solves 0.473 s, intersection sampling
0.033 s, numerical inspections 0.813 s, other preparation/serialization overhead
2.218 s. No native construction or post-build audit time; host memory/token cost
unmeasured. No Fusion calls/document changes or production edits. Ten focused unit
tests, changed-file Ruff lint/format and IDE inspections passed; no full suite.
Evidence: `artifacts/verification/ribbon_cap_transition/sections/3b0d8f36c9bc450c916608fb4c13feee/`.

Scope exhausted. Do not launch native construction with this candidate. Next review
is whether section sampling can preserve spacing as well as caps/planarity, or
whether those properties must be coupled during shape generation. No additional
adjustment, search budget or native attempt is authorized by this result.

## Three collateral-mechanics baselines, 2026-10-05

The user's three-variant requirement means three structurally different COMPLETE
ribbon configurations intended to reveal a proposed fix breaking other mechanics.
It does not mean three solver alternatives, three retries, rigid copies or three
reproductions of the triggering failure. The protocol is now recorded in section
10 of `experiment_testing_rules.txt`. The original spatial +45° failure and all
eight existing fixtures remain registered; `comparison_cases()` adds these three
for an eleven-case future comparison. No fix or native batch is authorized by
registration. Each proposed fix must use one unchanged procedure across the
triggering input, collateral cases and existing controls, with an agreed budget.

New cases were frozen with identities, material, five-width sphere bounds, exact
cap orientations and all short connection targets before the first baseline solve.
One unchanged solve each; zero refinement/native attempts; 60-second scheduling
cap with an additional five-second estimate stop. No post-result fixture edits.

**3 planned / 3 numerically evaluated / 0 native-attempted / 0 built / 0 fully
audited**. Three positive developmental challenges: 0 accepted / 2 failed /
1 unresolved. No invalid controls, skips or harness errors. Native failure rate
and native preservation are unmeasured. These examined cases are not holdouts.

| Complete configuration | Mechanics to protect | Current numerical baseline | Sampled trunk spread | Maximum center off frame plane |
| --- | --- | --- | ---: | ---: |
| 60° twisted quarter bend | Twist/spacing and cap flow through curvature | End allowance and whole-lane radius findings | 22.783% warning | 0.520 mm |
| Two orthogonal bends | Width/thickness transport across bend planes | End allowance and fitted/whole-lane radius findings | 11.291% warning | 0.025 mm |
| Asymmetric variable-curvature arch | Exact cap alignment, ordering and translated-lane preservation | No detected violation; unresolved | 0% | 0 mm |

The first two are already failing diagnostic challenges, not certified passing
regression controls. Preserve their complete finding/metric vectors: a future new
failure of a previously satisfied check or worsening metric is collateral evidence,
but continued overall rejection alone proves neither regression nor preservation.
The arch supplies a no-detected-violation numerical baseline; its native build
baseline is still absent. Planarity measurements concern sampled lane centers,
not a native profile/skin certificate. All cases retain mechanical goal warnings
separately from hard geometry findings. No inputs were tuned to rescue a baseline.

Numerical baseline turnaround **0.266 s**, including fixed-target preparation and
evidence overhead. No Fusion calls, document changes or production modifications;
host memory/token cost unmeasured. Four focused fixture-registry unit tests,
changed-file Ruff lint/format and three IDE inspections passed. No full suite or
unchanged checks repeated. Unit tests are not native geometry coverage.
Evidence: `artifacts/verification/ribbon_cap_transition/collateral/840190f4cd654e95811ca26ad078f9d4/`.

This three-case numerical baseline scope is exhausted. Next review: select one
general section-construction adjustment and agree a comparison budget covering
the original failure, these collateral challenges and retained controls. Do not
claim it preserves native mechanics until corresponding native evidence exists.

## Spatial +45° native diagnostic: profile failure, 2026-10-05

User approved one existing spatial +45° configuration, one solve/native attempt,
zero retries/refinement, 120-second scheduling cap and 2 GiB RSS ceiling. Timing
was explicitly uncalibrated for this family. Fixed centerline, connection targets,
solver choices and construction procedure were unchanged; the current 1% warning
policy was used. Known combined end-allocation violations were retained as
compliance failures, with authorization to attempt diagnostic construction.

**1 planned / 1 numerically evaluated / 1 native construction-pipeline attempt /
0 completely built / 0 fully audited**. One positive case: 0 accepted / 1 failed /
0 unresolved; no invalid controls. The trunk attempt failed while drawing section
2: `Fusion did not produce one joined ribbon profile.` This is profile-authoring
failure before the actual solid loft kernel operation, not a proven loft-kernel
rejection. All 38 endings were not reached; post-build audits were absent.
Native prediction was unknown; observed construction failed. The 1% goal did not
block construction. Sampled trunk spread 6.723% and complete spread 6.569% are
nonblocking mechanical warnings. All 38 combined end-region checks remain known
geometry-rule failures; native paired-side/complete lengths remain unmeasured.

Timed numerical solve/inspection 0.046 s; failed native profile-authoring attempt
0.120 s; diagnostic audits 0 s (absent, not passed); other overhead 3.919 s;
overall **4.085 s diagnostic turnaround**. Final Fusion RSS 993040 KiB (~0.95 GiB),
not physical footprint. No retries, fallback, source changes during execution or
budget extension. The preceding reflected scratch was archived/closed; the active
failed scratch `Ribbon 5x spatial S +45 — native diagnostic` is also archived.
The copied builder cleaned up failed section sketches: only guides and centerline
remain, with zero solids. The error chain/report and two section observation
records, not the failed section sketch, are retained failure evidence. All six
user documents remain open; production and pinned source copies were unchanged.

Evidence: `artifacts/verification/ribbon_cap_transition/native/f841ce0361c94eeeb565aef0a20b4b76/`.
Runner entry-point and reporting diff, Ruff lint/format and IDE inspection passed;
live execution exercised the new selection and length-warning reporting. Unchanged
unit checks were not repeated; full QA was not run. Cumulative native history:
5 complete-configuration attempts / 4 complete builds / 0 fully master-rule
audited, 123.802 s diagnostic turnaround. Four prior planar controls built; this
first spatial transfer did not. The −90° spatial, gentle and invalid tight native
cases remain unattempted. No generalized construction-success claim is supported.

Approved scope exhausted. Next bounded decision: diagnose section-2 profile
closure/planarity from its frozen inputs before another build; do not tune the
specimen, relax geometry constraints or automatically retry.

## Current policy: warn but proceed on length goals, 2026-10-05

User explicitly revised the 1% length requirement to a mechanical accuracy goal.
Current experimental preflight reports trunk and complete sampled length spreads
under `mechanical_accuracy`, moves their goal misses to `warnings`, and excludes
only those two findings from geometry rejection. Native paired-side spreads are
also nonblocking goals, reported separately from native construction. Unmeasured
complete native conductor lengths remain unmeasured, never assumed accurate.

Geometry construction/compliance and mechanical accuracy are separate outcomes.
A goal-only miss is warn-but-proceed, not a geometry rejection or mechanical pass.
Curvature/macaroni, spacing/pitch, identity/order/targets, sphere containment, cap
approach and combined 6% end allowance remain unchanged. Thus the known spatial
cases still have independent end-allocation findings; the policy change is not a
claim that they now comply. Optional bounded fold equalization still aims for 1%;
its optimization target is unchanged, but missing it no longer rejects geometry.
No new aesthetic-only solver strategy is implemented by this reporting change.

Legacy preflight and production are unchanged. Historical reports below retain
their original strict rule interpretations. Future decomposition compares saved
spreads and remaining geometry failures, explicitly excluding historical length
failures from the rejection comparison; this is a declared policy revision, not
an unchanged-rule improvement. Native legacy paired-side `passed`/`failed` status
is retained as raw diagnostic evidence and not used as a construction gate.

Verification: 37 focused tests, Ruff lint/format and all five changed-code IDE
inspections passed. No numerical matrix rerun, native build or full suite this
turn; native reporting changes remain unexercised live. Fusion documents untouched.
The durable requirements revision is appended to `rollback_end_loft_notes.txt`.

## Numerical stage decomposition, 2026-10-05

User approved eight existing configurations, at most one solve call each, zero
refinement/native attempts and a 60-second scheduling cap. All connection fixtures
and targets were frozen before the first call. Optional immutable observation
hooks record unbanked lanes, banked lanes, each cap correction and equalized lanes;
the underlying banking, correction and search policies are unchanged. The same
saved v2 final spreads (within 1e-12) and failure lists were reproduced. The invalid
tight control was rejected before stage generation. No discrepancy or retry.

**8 planned / 8 numerically evaluated / 0 native-attempted / 0 built / 0 fully
audited** in this scope. Seven positive development cases: 0 accepted / 2 failed /
5 unresolved. One invalid control: 1 correctly rejected / 0 missed / 0 unresolved.
No skipped cases. These are not holdouts; mixed directions remain reflection-related.
Native failure rate is unmeasured here; the earlier four native builds remain
separate evidence and are not new builds from this diagnostic.

| Complete configuration | Unbanked spread | Banked | After both caps | After folds | Numerical outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Both outward | 0% | 0% | 0% | 0% | Unresolved; no detected violation |
| Both inward | 0% | 0% | 0% | 0% | Unresolved; no detected violation |
| A outward, B inward | 0% | 0% | 0% | 0% | Unresolved; no detected violation |
| A inward, B outward | 0% | 0% | 0% | 0% | Unresolved; no detected violation |
| Gentle bend | 0% | 0% | 0% | 0% | Unresolved; no detected violation |
| Spatial S +45° | 14.257% | 9.713% | 8.721% | 6.723% | Failed length and end allowance |
| Spatial S −90° | 15.686% | 18.409% | 18.061% | 16.223% | Failed length and end allowance |
| Invalid tight bend | Not generated | Not generated | Not generated | Not generated | Correct input-curvature rejection |

Banking improves one spatial case but worsens the other. Its current objective
penalizes width-axis bending and roll changes, rather than directly constraining
complete lane-length spread. Cap correction reduces spread in both spatial cases;
fold equalization improves it further but does not reach the unchanged 1% limit.
Thus cap shortening alone is not evidenced as a sufficient length repair. This
decomposition is observational, not proof of infeasibility or an isolated causal
comparison of alternative algorithms.

Both spatial cases still exceed the combined 6% end allowance on all 38 end/lane
checks, with maximum overruns 2.754 mm (+45°) and 5.247 mm (−90°). Authored supports
are 7.358/7.354 mm before branch allowance. The policy chooses up to 6% of the
shortest uncorrected lane without reserving branch length; its final complete-end
budget must be addressed separately from banking/equalization.

Finite final cap chords reach 42.678° (+45°) and 43.643° (−90°) from the signed
inward cap normal. These are resolution-dependent chords, NOT analytic tangents
or measured native flow failures. Exact cap-center coincidence and exact branch
arrival tangents do not supply missing analytic corrected-lane derivatives or
native skin interpolation/junction-curvature prediction. No kernel acceptance
prediction is claimed. Continuous strain, clearance and shortest routing remain
unresolved.

Overall numerical diagnostic turnaround: **0.690 s**, including observation,
fixture preparation, inspection and evidence serialization; not native audit or
production latency. No Fusion calls or document changes. Host memory and token
cost are unmeasured. Production/pinned sources unchanged. Focused verification:
26 distinct unit checks passed (21 retained cap contracts and five stage/stop
contracts); Ruff lint/format and all four changed-file IDE inspections passed.
No full suite or additional live Fusion check was run because this scope is
host-independent. Test/stage samples are not additional geometry configurations.
Evidence: `artifacts/verification/ribbon_cap_transition/stages/c50b442653f947b69ca6fcf73984cbe8/`.

The approved scope is exhausted. Next bounded decision: consider a length-aware,
cap-smooth banking policy across this development matrix and reserve branch
allowance before cap support; do not increase fold budgets or tune one specimen.
Native junction prediction remains a separate unresolved contract.

## Current stage: reflected mixed direction, 2026-10-05

User approved one A-inward/B-outward run under the renewed one-case limits:
one solve/native attempt, zero retries/refinements, 120-second scheduling cap,
2 GiB main-process RSS ceiling. Solver, fixtures, geometry rules, lofts and audits
were unchanged; only `native.py` changed for the entry point and reporting labels.
This reflected counterpart checks invariance, not a new geometric family.

Result: **1 planned / 1 evaluated / 1 native-attempted / 1 completely built /
0 fully master-rule audited**. Numerical checks found no violation; native build
prediction remained unknown. One trunk and all 38 endings constructed. Existing
finite diagnostics passed: 156 trunk sections, 1,140 lobe landmarks, all ending
sections and connection rims, interference and paired native sides. No build or
measured-diagnostic failures, skips or invalid controls occurred. Full-compliance
disposition is 0 accepted / 0 failed / 1 unresolved, retaining the unmeasured
junction/skin/complete-length/strain/clearance properties below. Macaroni ratio
0.75169 remains below 0.8; paired-side spread is approximately 2.10e-16.

Reports now explicitly classify these as **diagnostic construction runs**:

| Timing scope | Reflected case |
| --- | ---: |
| Timed numerical shape solve and candidate inspection | 0.029 s |
| Native trunk and ending construction | 5.710 s |
| Diagnostic audits | 21.742 s |
| Other overhead | 6.693 s |
| Total diagnostic turnaround | 34.175 s |

Timed numerical work excludes separate fixture/guide preparation. Other overhead
includes uninstrumented setup, display and archiving. Audit time and total
turnaround are not routine solver or demonstrated production latency. Timing
groups reconcile to the total; earlier immutable reports remain unchanged.

Final Fusion RSS was 1036000 KiB (~0.99 GiB), not total physical footprint. Only
the preceding owned mixed scratch was archived/closed; the reflected result is
active in `Ribbon 5x A-in B-out — native calibration` and archived. All six user
documents remain open; production and byte-pinned source copies are unchanged.
Ruff lint/format, IDE inspection and live entry-point/reporting checks passed.
Unchanged unit tests were not repeated; no full suite was run.
Evidence: `artifacts/verification/ribbon_cap_transition/native/f07ce2d6c2cb45018de662fab0c31a69/`.

Current complete-configuration coverage (not child-solid coverage):

| Direction configuration | Numerical checks | Native build | Finite diagnostics | Full compliance |
| --- | --- | --- | --- | --- |
| Both inward | No detected violation | Built | Passed | Unresolved |
| Both outward | No detected violation | Built | Passed | Unresolved |
| A outward, B inward | No detected violation | Built | Passed | Unresolved |
| A inward, B outward | No detected violation | Built | Passed | Unresolved |

Cumulative: **4 planned/evaluated/native-attempted/built, 0 fully master-rule
audited**, 119.717 s diagnostic turnaround, 21.873 s native construction. These
are fixed planar development controls, not holdouts or generalized solver proof.
The gentle numerical case remains natively unattempted; the two spatial/twist
cases remain numerical failures and natively unattempted. The invalid tight bend
remains correctly rejected numerically and natively unattempted. No new cases or
refinement are scheduled: this one-attempt scope is exhausted. The next decision
should address predictive interpolation/junction checks and the known spatial
failures under a separately agreed scope, not further tuning of these controls.

Historical stage reports follow; their counts and document states describe the
time of each run, not the current four-case state above.

## Native transfer check: A outward, B inward, 2026-10-05

User approved the next mixed-direction configuration under the same one-case
limits (one solve/attempt, zero retries/refinements, 120-second scheduling cap,
2 GiB main-process RSS ceiling; estimated total 36.4 seconds). Only a new runner
entry point and scratch name were added. Recorded source comparisons confirm
the solver, fixtures, geometry rules, lofts and audit policies were unchanged.

Independent configurations: **1 planned / 1 evaluated / 1 native-attempted /
1 built / 0 fully master-rule audited**. Positive full-compliance disposition:
0 accepted / 0 failed / 1 unresolved; no invalid controls or skips. Numerical
checks found no violation. The native prediction was unknown; observed complete
construction succeeded. All 38 split endings constructed, and 156 trunk sections,
1,140 lobe landmarks, branch sections, connection rims, interference and paired
native sides passed existing finite checks. Paired-side spread was approximately
2.10e-16; macaroni ratio 0.75169 was below the unchanged 0.8 ceiling. No construction
or measured-audit failures occurred. Native skin/junction/complete-length audits
remain incomplete as described below; no full compliance or generality claim.

Search/shape 0.009 s; numerical validation 0.020 s; trunk loft 2.078 s; all endings
3.436 s; section audits 6.503 s; landmarks 12.753 s; connections 0.014 s;
interference 1.901 s; paired sides 0.005 s; previous scratch archive/close 0.792 s;
display/archive 1.645 s; overall **33.012 s**. Final RSS 1003744 KiB (~0.96 GiB),
not total physical footprint. The flat owned scratch was archived/closed; curved
`Ribbon 5x A-out B-in — native calibration` remains open and archived. Production
and unrelated documents were unchanged. The added runner binding passed diff
review, Ruff lint/format and IDE inspection and was exercised in the live build;
unchanged unit checks were not repeated and the full suite was not run.

Evidence: `artifacts/verification/ribbon_cap_transition/native/14f8067120ed4289860c0b74bee07d5d/`.
Current cumulative stage: **3 native attempts / 3 complete builds / 0 fully
master-rule audited**, 85.542 seconds overall and 16.163 seconds native lofting.
The reflected mixed counterpart remains natively unattempted; the two spatial/
twist numerical failures are unchanged. All outcomes are development evidence,
not holdouts. Current single-attempt budget is exhausted; the next bounded decision
is the reflected case, not specimen-specific tuning or promotion to production.

## Native transfer check: both outward, 2026-10-05

The user's "on to the next" advanced one configuration under the same one-case,
one-solve, one-native-attempt limits: no retry/refinement, 120-second scheduling
cap, 2 GiB main-process RSS ceiling. Estimated total was 36.4 seconds. Only the
runner's case selection and owned scratch handoff changed; the recorded source
comparison confirms every other candidate/rule fingerprint was unchanged.

Both-outward result: **1 planned / 1 evaluated / 1 native-attempted / 1 built /
0 fully master-rule audited**. Numerical checks found no violation. All 38 split
endings constructed; 39 trunk sections, 1,140 lobe landmarks, branch sections,
connection rims, interference and paired native sides passed their existing finite
checks. Paired-side spread was zero. No construction/measured-audit failures,
invalid controls or skips occurred. Native prediction remained unknown; observed
construction succeeded. Full compliance is 0 accepted / 0 failed / 1 unresolved;
unmeasured junction/skin/complete-length/strain properties remain as listed below.

Search/shape 0.006 s; numerical validation 0.019 s; trunk loft 1.692 s; all endings
3.262 s; section audits 2.726 s; landmarks 0.907 s; connections 0.014 s;
interference 1.082 s; paired sides 0.004 s; prior scratch archive/close 0.813 s;
display/archive 1.619 s; overall **16.121 s**. Final RSS 1100176 KiB (~1.05 GiB),
not total physical footprint. The both-inward scratch was archived and closed;
`Ribbon 5x both-outward — native calibration` remains open and archived. No
unrelated document or production changes. Runner diff, Ruff lint/format and IDE
inspection passed; no unchanged unit suite was repeated for the selection-only
change. The live check verifies the new native handoff; full-suite QA was not run.

Evidence: `artifacts/verification/ribbon_cap_transition/native/4958ce09f7284c6191631cd8bbd68446/`.

| Direction configuration | Native construction | Measured finite checks | Total time |
| --- | --- | --- | --- |
| Both inward | Built | Passed; full audit incomplete | 36.408 s |
| Both outward | Built | Passed; full audit incomplete | 16.121 s |
| A outward, B inward | Not attempted | Absent | Unmeasured |
| A inward, B outward | Not attempted | Absent | Unmeasured |

Cumulative native stage: 2 planned/evaluated/attempted/built, 0 fully master-rule
audited; 52.530 seconds overall and 10.649 seconds native lofting. All are
development controls, not unseen validation. Broader spatial/twist numerical
failures remain visible below; two native successes are not a general solver pass.
Current one-attempt budget is exhausted. Next bounded decision is the first mixed
direction configuration under the unchanged procedure, not tuning either specimen.

## Native calibration, 2026-10-05

User approved one both-inward calibration, with loose diagnostic tolerances.
Fixed targets and the solver were unchanged during the run. Loose 0.05 mm native
vertex containment is a diagnostic measurement, not a substitute acceptance rule.
The existing stricter native checks also ran, retaining findings rather than
blocking construction. No retries, refinement, fallback or batch extension occurred.

Independent configurations: **1 planned / 1 evaluated / 1 native-attempted /
1 completely built / 0 fully master-rule audited**. Construction success is 1/1
in this named scope; positive-case full compliance remains 0 accepted, 0 failed,
1 unresolved. Invalid controls: none in this calibration. Pre-build numerical
checks found no violation. The registered native prediction was unknown; observed
construction succeeded. No build-prediction accuracy is inferred from that pair.

Fusion document `Ribbon 5x both-inward — native calibration` contains one trunk
and all 38 numbered reverse-loft endings: 39 solids are **one complete case**.
The measured checks passed: 195 trunk sections, 1,140 lobe landmarks, sections and
connection rims on all 38 endings, interference checks and native paired-side seam
lengths (maximum relative spread approximately 1.64e-16). The enclosing-profile
macaroni certificate ratio was 0.75169, below the unchanged 0.8 ceiling. Native
vertices were inside the 71.25 mm sphere radius; this does not bound the entire skin.

There were no construction or measured-audit failures in this calibration. Legacy
harness status `built_and_audited` refers only to its finite checks, not the full
master rules. Native trunk/branch join flow and curvature, connection skin tangency,
complete native conductor lengths, continuous final-lane strain/curvature, global
clearance and shortest routing are unmeasured. The two broader numerical spatial/
twist failures below remain failures. No generality or holdout claim is supported.

Per complete case: search/shape 0.009 s; numerical validation 0.020 s; native trunk
2.054 s; all endings 3.641 s; section audits 7.375 s; landmark audit 13.848 s;
connection audit 0.016 s; interference audit 1.629 s; paired-side audit 0.005 s;
display/archive 1.728 s; prior-preview archive/close 0.973 s; overall 36.408 s.
Trunk/end timers include their own profile authoring. Setup and uninstrumented
fixture work are included only in overall time. No API/token cost data is available.

Main Fusion RSS after the run was 986016 KiB (~0.94 GiB), below the agreed 2 GiB
ceiling; this is not total physical/compressed footprint. The owned old preview
was archived and closed; the new native scratch remains open and was also archived.
Other documents were not edited. Evidence and archives:
`artifacts/verification/ribbon_cap_transition/native/803a1011fdce472eb2b46fa693ceeb04/`.
Source/rule/fixture fingerprints were written before the first native loft.
Production and its byte-pinned copies were unchanged. Focused verification of the
runner/budget and candidate: 25 tests, Ruff lint/format and IDE inspections passed;
no full repository suite was run.

The approved one-attempt budget is exhausted. Next bounded decision: test the
other three direction configurations using the same procedure, archiving/closing
each owned scratch and measuring memory before each launch. Estimate about 110 s
from this calibration for three similarly expensive cases, not a guarantee; obtain
a fresh batch agreement before launching. Do not automatically tune this specimen.

The user explicitly requested a five-width sphere stage on 2026-10-05. This
changes the development boundary, not the other master rules and not production.
The current eight-case screen includes four end-direction configurations, a
gentle control, two spatial/twist challenges and one invalid tight bend. The
mixed-direction pair is reflection-related, not two geometric-family proofs.

For constant-width lanes perpendicular to every cubic derivative, the candidate
recognizes rigid translations and uses their exact endpoint derivatives. If the
ordered cap positions and tangents already match, it makes no correction and
allocates zero trunk end support. Unknown/twisting lanes retain sampled derivative
correction and conservative support accounting; they do not receive this exemption.
Historical default frame/end behavior and search budgets are unchanged.

Current fixture targets are authored before solving, with exact cap tangents and
fixed fifteen-degree turns of radius four conductor diameters. This is a declared
new fixture, not a post-result relocation of the old targets. Complete-conductor
6% checks are active; old trunk-only allowance findings remain separately reported.
Finite full-lane bend and occupied-sphere checks are included. Trunk containment
is sampled; branch containment uses conservative control hulls plus profile reach.
Neither certifies native skin or continuous final-lane compliance.

## Bounded local comparison v2, 2026-10-05

Question: does exact cap treatment preserve compliant numerical controls across
the four direction configurations while retaining the broader failures honestly?
Fixed centerlines; two procedures once per case, no refinement, maximum eight
configurations, sixteen shape calls, zero native attempts, 120-second scheduling
cap. Source/rule/matrix fingerprints were frozen before execution.

Independent configurations: **8 planned / 8 evaluated / 0 native-attempted /
0 built / 0 post-build audited**. Positive cases: 0 accepted, 2 numerically failed,
5 unresolved out of 7. The one invalid control was correctly rejected. No skips,
timeouts or regression stop occurred. Native failure rate remains unmeasured.

| Configuration | Candidate numerical outcome | Native / post-build |
| --- | --- | --- |
| Both outward | No detected violation; unresolved | Not attempted / absent |
| Both inward | No detected violation; unresolved | Not attempted / absent |
| A outward, B inward | No detected violation; unresolved | Not attempted / absent |
| A inward, B outward | No detected violation; unresolved | Not attempted / absent |
| Gentle bend | No detected violation; unresolved | Not attempted / absent |
| Spatial S, twist +45 | Length spread 6.72%; combined end allowance rejected | Not attempted / absent |
| Spatial S, twist −90 | Length spread 16.22%; combined end allowance rejected | Not attempted / absent |
| Invalid tight bend | Conservative macaroni certificate rejected as expected | Not attempted / absent |

The first five have zero sampled trunk-lane spread, zero required trunk end
support and cap-normal alignment within numerical precision. Macaroni, 1% length,
1.03 pitch and bend rules were not relaxed. The baseline retains historical
declared-support accounting, including a conservative rejection of undeformed
straight input; its rejection count is not proof that those geometries are invalid
or a meaningful production success-rate comparison.

All cases are development evidence; no untouched validation family has passed.
These translated-lane controls do not establish arbitrary twist, width-axis
bending or general rerouting. The two spatial failures remain visible. Continuous
strain, global clearance, shortest routing, native paired sides, cap-to-ending
flow and connection termination remain unresolved until appropriate audits.

Overall local screen: 1.013 seconds. Candidate solve/planning/preflight combined:
0.057–0.097 seconds per positive complete configuration. Search and numerical
validation are not separately timed; build/audit/archive time is unmeasured.
Evidence: `artifacts/verification/ribbon_cap_transition/d348e035ba3e4d9e967c224694c66668/`.
Focused verification: 56 tests passed; changed-code Ruff lint/format, diff review
and IDE inspections passed. No full-suite or native check was run. Production
and byte-pinned snapshots remain unchanged.

Fusion documents were untouched. Read-only host inspection found main Fusion PID
44078 at 204336 KiB RSS (~200 MiB); RSS is not total physical/compressed footprint.
Proposed next bounded decision: one both-inward native calibration, one attempt,
no refinement/retry, review at 120 seconds, 2 GiB RSS scheduling ceiling. Archive/
close only the owned old preview, retain the calibration scratch; no unrelated
document changes. No native launch until the user agrees. A running kernel is not
assumed cancellable by a client timeout. Batch estimates must follow calibration.

## Historical v1 implementation and first stopped comparison

The following describes the superseded first attempt and retains its evidence.

Experimental fixed-centerline comparison, not a general routing solver or a
production correction. Read `experiment_testing_rules.txt` and
`rollback_end_loft_notes.txt` before running or reporting it.

The candidate supplies exact endpoint tangents before frame transport and uses
each lane's own sampled derivative in a quintic correction field. The field adds
no second derivative at its cap or interior support boundary; that property does
not certify the complete lane or Fusion's interpolation. End support is capped at
six percent of the shortest input lane, without a positive-size clamp. This is
an authoring policy, not a complete-end compliance claim. Contraction can itself
make a transition infeasible; rejected output must remain rejected.

Connection targets are authored with the historical sampled frames before the
candidate solve. Only the cap-side branch handle changes. Connection positions,
connection tangents, cap centers, conductor identities and order stay fixed.
`prepare_candidate` retains an `EndPlan` that refuses different build inputs and
returns the same checked branch routes. It does not execute a native builder.

The macaroni curvature/profile-reach contract, bank procedure, 1% length and 1.03
pitch limits, and fold search budget are retained. Historical experiments continue
to use their original frame/end treatment unless explicitly given the new inputs
or policy. Byte-pinned production snapshots and production files remain unchanged.

The local screen is `uv run python -m
experiments.experiment_ribbon_cap_transition.screen`. It freezes source, rule and
fixture fingerprints into a unique ignored artifact directory before execution.
It compares two 19-conductor gentle controls and the unchanged six spatial cases,
once per procedure: at most eight complete configurations, sixteen shape calls,
zero refinement rounds, zero native attempts and a two-minute scheduling cap.
Four spatial cases are known curvature-rejection controls. The screen stops on a
new candidate violation, source drift, harness error or scheduling cap, retaining
unattempted cases and their reasons. It does not retry or extend its budget.

The sphere diameter is four nominal widths for this historical comparison, not
the current three-width requirement. These are development fixtures, not holdouts.
The added combined-end check measures sampled trunk portions plus bounded branch
lengths against 6% of complete sampled conductor paths including both endings.
No native skin/paired-side audit, continuous final-lane curvature, material strain,
global clearance, occupied-structure containment or shortest-route proof is supplied.
Any absence of detected violations remains unresolved, never an accepted native
prediction. Do not launch a native batch without a separate bounded run agreement.

Focused unit coverage is in `tests/test_experiment_cap_transition.py`. Unit-test
counts are not geometry coverage. Native failure rate remains unmeasured until
actual builds occur.

## First local comparison, 2026-10-05

Eight complete configurations were planned; two positive controls were numerically
evaluated and rejected by both procedures. Six spatial cases were not attempted,
including four known-invalid controls and two positive S cases. Zero native
attempts, zero builds, zero post-build audits; native failure rate unmeasured.
No holdouts were used. Overall local comparison time was 0.415 seconds; recorded
per-procedure solve/planning/preflight times were 0.097–0.109 seconds, not native
or end-to-end build timings. Search, planning and preflight timers are not split.

The gentle control's maximum planned cap-normal error fell from 2.890733 degrees
to numerical zero at both ends, with connection targets unchanged. Its outgoing
branch upper length bound grew from 2.827759 to 2.831320 mm. This exceeds the old
trunk-only cap of 2.827759 mm, triggering the fixed regression stop. Both tested
controls retain zero sampled trunk-lane spread; candidate branch macaroni ratios
remain below 0.8. These measured improvements do not make either case accepted.

The added conservative combined-support accounting also rejected both controls.
It charges the entire declared trunk support plus the branch, even on the straight
control where no positional correction is needed. That accounting and the retained
trunk-only branch cap need reconciliation with actual required end-region length
and the complete-conductor denominator. Neither result proves target infeasibility.
No check, target, budget or candidate was changed during that stopped run. The
user subsequently authorized end-budget reconciliation and the new five-width
development scope above; historical outputs were retained, not overwritten.

Evidence: `artifacts/verification/ribbon_cap_transition/9186c53a0aa2425e820d993a4d6d1eef/`
contains the frozen plan, fingerprints, every case disposition and detailed checks.
Focused verification: 51 unit tests passed, changed-code Ruff lint/format and IDE
inspections passed. Production source and byte-pinned copies were unchanged. No
Fusion operation occurred; document state was not changed and host memory was
unmeasured. Continuous strain, clearance, interpolation and optimality remain open.
