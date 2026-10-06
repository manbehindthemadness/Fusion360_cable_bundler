# Cap-transition candidate v2 — five-width development

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
