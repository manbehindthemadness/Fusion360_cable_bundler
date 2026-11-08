# Yield an oversized reflected correction to existing constrained joints

The fifth monitored exception is case 78 of run 1148,
`range-d2118eb335ac4cee9dd4082b0018d55b`. The run stopped at 77 passes from
78 attempts, with zero warnings. Live inspection 1162 confirmed the tester was
inactive, the worker absent and keep-awake released. The fixed input is N3,
seed 1080035090, diameter 0.75 mm, void/zones 300%, with zero-based endpoints
A6/face1/roll35 degrees and B8/face8/roll20 degrees. Evidence 1163 freezes the
failure, the actual preceding passes 75–77, and the complete old source bytes.
Evidence numbers below refer to ignored `artifacts/verification/ribbon_terminal*`.

The original numerical result was rejected because connector clearance was not
established. Fusion subsequently built an explicitly rejected inspection body.
That is a native inspection attempt, with no accepted native result, named
fidelity pass or gym-boundary certificate. It is retained separately from the
later accepted native qualification; the original failure is not relabeled.

## Cause and maintained rule

The construction was self-clear at 27.209417483725247 mm. Contraction shortened
it to 19.77171971429499 mm, but both entered the start connector keepout. The
existing late recovery selected the incident fold from the actual straight
witness and reflected it. Its fixed selected angle/bank then led to poorly
conditioned cap corrections. One exact linear correction requested almost
976 radians, while actual angular steps were limited to 0.2 radians. Four
updates/24 Newton steps reduced the largest normalized cap residual only to
1.547894. No self-contact certificate was attempted for that unclosed proposal.
The original recovery spent only 0.061331 CPU seconds; more CPU allowance would
not address how those corrections used their finite step allocation.

The maintained rule compares the actual projected Newton correction's largest
angular component with the total remaining original angular trust travel:

`maximum angular correction > angular step limit × remaining Newton steps`.

If it exceeds that travel, late fixed reflection yields before applying the
correction. This is a local work prediction, not proof of global infeasibility.
The already-existing constrained signed-joint fallback receives only genuinely
unused updates, CPU, wall time and construction pairs. It starts from the original
closed source and actual intrusion, retains the original construction ceiling,
and solves its existing cap and complete-feature clearance equations. The
unclosed reflected proposal and its geometry do not become a new initialization
or inherit a contact certificate.

The angular step limit is shared with `step_limit`, retaining its original value.
`close_update` accepts an optional remaining-step allocation, validates it against
the original 24-step maximum and stops if it is spent. Default early-contraction
and incident-recovery callers retain their existing behavior. Only late recovery
passes this allocation and recognizes the new yield reason. All radii, material
ordering, original sign policies, fixed target poses, dimensional goals, strict
contact and both finite connector checks remain authoritative. No new model,
root/event bank, damping, output welding or tolerance increase was promoted.

## Retained experiments

These repeated variants do not increase independent geometry coverage. All
numerical phases below have zero native attempts.

| Evidence | Planned / evaluated | Outcome |
| --- | --- | --- |
| 1164 | 1 / 1 | Unchanged replay reproduces the failure and logs all 24 corrections; 0.817940 CPU seconds. |
| 1165 | 1 / 1 | A bounded least-squares correction with a stricter Euclidean 0.2 trust region reduces the cap residual to 3.519e-11 after 24 steps; still rejected, with no clearance proof. Total 0.847600 CPU seconds; recovery 0.087299. |
| 1166 | 4 / 0 | Driver omitted imports; stopped before any solve. All four inputs unattempted, no geometry effect. Original driver/plan retained. |
| 1167 | 4 / 4 | Corrected driver uses the existing per-angle trust limit. Three controls remain exactly unchanged. Trigger closes in 18 Newton steps but produces a rejected 48.568050 mm branch and a 1.649e-9 mm straight. Neither numerical experiment is promoted. |
| 1168 | 4 / 4 | Releasing the selected reflected angle/bank on an excessive correction passes all four cases, controls exact. Trigger closes/rejects the long reflection after 17 steps, then the existing signed-joint fallback accepts after four more. Recovery 0.132089 CPU seconds. This model increase is not promoted. |
| 1169 | 4 / 4 | The simpler budget yield accepts the identical final trigger geometry and leaves all three controls exact. Reflection yields after six steps; existing fallback needs four more. Combined three updates/10 Newton, 130 contact pairs, recovery 0.095697 CPU seconds. |
| 1171 | 4 / 4 | Maintained implementation exactly matches 1169 for the trigger and preserves all three control first/final routes. Trigger cold CPU 0.910611 seconds; whole batch 3.029066 wall seconds. |

The accepted trigger is 27.209417383725246 mm, within the unchanged original
construction ceiling. It is not a claim of minimum route length. Its final strict
self-contact certificate uses 130 pairs, and independent finite hardware clears.
All work remains within the original four updates/24 Newton, 0.35 CPU/2 wall
seconds and shared construction-pair pool; no unsuccessful phase renews a budget.

## Verification and native qualification

Affected verification 1170: 162 tests pass, including ten new budget, default-call,
straight-travel, exhausted-allocation, non-inherited-clearance and real-case checks.
Scoped Ruff lint/format checks pass for all five changed Python files. All five
IDE inspections complete without new findings. Initial inspections of steps and
reversal timed out; subsequent sequential inspections completed. Symbol lookup
succeeded. The call-graph endpoint rejected its analysis-kind arguments, so all
three maintained call sites were inspected directly. No repository-wide QA run.
Complete working code diff, new test and source-lock diff were reviewed.

The new implementation still has 245 pinned source files, with lock SHA-256
`a475821275630a9448b73936d47503ba25221a3962efcb0d8f034c1ae60db5a4`.

Corpus 1172: 73 planned/73 evaluated, 63 accepted/10 unresolved, no unattempted
inputs and no native attempts; 71.481498 wall seconds. Every previously accepted
first-pass and final geometry is exactly unchanged. Every acceptance retains
strict self-contact and independent finite-hardware clearance. The ten unresolved
inputs remain unresolved. The four-case set overlaps this corpus; do not sum them
as independent coverage. These are development checks, not untouched validation.

Qualification 1173: one fresh ordinary solve and one guarded native attempt of
the exact reviewed case-78 route. Construction and named fidelity pass with zero
warnings: 5,950 native points, 330 seams, maximum surface error 7.520722e-10 mm.
Solve CPU 0.976266 seconds versus generation 1.528856 seconds meets the timing
goal. Native audit 0.943088 seconds, native elapsed 12.772762 seconds, maximum
sampled native RSS 2,444,080 KiB. The prior rejected inspection body remains valid.
Other control/corpus inputs received no new native builds in this qualification.

View 1175: precise native bounds pass the original extra-cubicle-layer-plus-10 mm
region, half extent 26.875 mm, zero excess. Body revision and exact gym identity
are unchanged; the viewport capture was inspected. View RSS 1,995,792 KiB.
Full physical audit remains unmeasured. Optional UV remains unchanged and disabled;
no appearance or texture was created. There is no production promotion or claim
of universal reliability or global optimality.

## Campaign restart

The counter is now five of 20 exceptions, all five qualified. At exception 20,
stop and consolidate retained repairs into shared solver rules as recorded in
the campaign ledger; this repair does not reset that counter.

Run 1176 starts `range-412385efcb064aad96d3e8a259a4f5c7`, confirmed active at
zero attempts with keep-awake enabled. Its guard compares every specification
and solver-selection value against the previous frozen run: same ranges,
seed 2633163134, ten-second preview, screenshot directory `~/Pictures/test4`,
options and original resource limits. A source change starts a new streak.
Earlier 345 ordinary attempts/340 passes/five exceptions over 78 unique inputs,
with longest streak 77, remain retained. Qualification adds no ordinary passes.
The goal remains 1,000 consecutive problem-free iterations, and is not achieved.
