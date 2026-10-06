# Cap-transition candidate v2 — five-width development

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
