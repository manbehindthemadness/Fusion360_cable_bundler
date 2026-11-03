# Existing-bend contraction

## Selected v2 integration530–536 — 2026-11-03

The five-conductor excursion is the built ed8423layout. First-pass branches are
37.901194mm and113.250549mm. The nearer-guide branch is tried first but has a
strict interior penetration witness between pieces0/4 after544pairs. The fallback
clears in516pairs;104.639508mm(92.4%)is explicit straight travel. Smoothing raises
its length to113.772232mm. This is first-pass feasibility without effective
contraction, not a smoothing defect or permission to ignore the collision.

Earlier497–500contraction had not been installed in v2.530freezes this pre-smoothing
route and the compact/shallow/spatial gym controls from464, confirms all four strict
baseline separations, and retains the penetrating trigger branch as invalid control.
531applies the same498rule: four projected total-material descent steps,0.2radian
coordinate limit, two scalar halvings, six-Newton/four-halving cap retraction with
exact zero-straight active sets, at most two final strict1024pair checks. No guessed
initialization, inserted event, radius growth or smoothing.533maintained snapshots
exactly match531on all four independent examined development configurations:

| Configuration | Original mm | Contracted mm | 533 CPU s | Guide RMS original → new mm |
| --- | ---: | ---: | ---: | ---: |
| five-conductor trigger2641972872 | 113.250549 | 28.942999 | 0.144575 | 26.266540 → 3.789160 |
| compact4033669276 | 20.057443 | 15.911437 | 0.091437 | 2.441302 → 2.826886 |
| shallow8-gym424-05 | 47.585465 | 32.261073 | 0.151864 | 4.833012 → 2.632929 |
| spatial12-gym424-09 | 84.531991 | 78.527534 | 0.089591 | 3.481914 → 1.581348 |

4/4shorter/separated,0failed/unresolved/skipped/unattempted. Compact guide position/
direction worsen despite shortening. Guide frames initialize this phase but do not
lock descent. All retain four ordered bends, original radii/profile/targets,
cap error<=1.57e-9mm, sampled metric error<=8.03e-16 and no native straight slivers.
Invalid control correctly rejected1/1. No holdouts, global optimum or universal
shape-quality guarantee is claimed.

532integrates model/solve in this package. Selected v2 calls contraction before
smoothing when first-pass optimization is enabled and initial contact is separated.
Checkbox off retains previous midpoint branch behavior and skips contraction;
temporary contact-unmeasured routes also skip it. V1/native builder are unchanged.
All trials/raw contact results log as`first_pass_contraction`; first-pass counter
includes it, and smoothing's length allowance starts from the contracted route.
Optional work caps:0.35CPU s, at most2wall s shortened to the remainder of the
existing4sfirst-pass deadline. Local exhaustion/rejection retains the safe original;
hard worker cancellation/time/RSS/source errors propagate.185-file lock includes
the three new package/model/solve files. No production/standards edits.

534source guard stops before any solve/native attempt because the live lock module
still hashes its old package list. Response/setup disposition retained.535records
renewal with identical sources/inputs/limits, reloads live lock, updates method
explanations and runs one ordinary unchanged gym solve/build: optimization on,
smoothing1%,UVoff.536collects completion/body visible and no UI error. New job
39baa723first pass28.942999mm becomes29.232429mm after smoothing, versus old
113.772232mm. Old body/revision/history retained hidden; matching gym remains and
native screenshot inspected. No unrelated document/layout edits.

Native coverage:1/4independent configurations attempted/built/named-fidelity audited;
other three native-unattempted by scope,0full physical audits.212faces,7350surface
samples/406seams/three guides/two caps pass original goal,0warnings/findings,
max surface error1.230084e-9mm, revision`b9a7afa7-a461-4d30-8077-348ba67b0352`.
535numerical CPU1.222301s/wall1.299308s; first pass0.567424s includes contraction
CPU0.198446s/wall0.228190s. Smoothing0.687272s is a subset. Generation1.302123s,
audit20.528263s, native operation23.776170s. Numerical wall is near matched
generation on this run; no stable speed guarantee.530/531/533SDK phases total
1.577136CPU s excluding imports/QA/orchestration/native CPU. Native sampled peak
501104KiB;120sworker/120snative/240sphase/4GiB RSS/3.8GiB launch limits held.
One native attempt, no geometry retry; token/currency costs unmeasured.

78focused relocation/contact/solver/selection/controller/aesthetic/relaxation tests
pass; scoped Ruff lint/format and new changed-file IDE inspections clean. Coverage
includes checkbox integration, physical/cap invariants, contact rejection, optional
CPU/wall fallback and hard caller errors. Contact-specific tests disable optimization
to retain their isolated baseline. FullQA/three collateral native builds/full physical
audits unrun. Evidence: ignored`ribbon_excursion530`,`ribbon_relocation531/532/533/535`,
530–536drivers,534setup stop and533source snapshot. This is active experimental gym
v2 behavior, not production promotion or universal solver success.

## Standalone prototype497–500 — 2026-11-02

The user clarified that the visible bend should move, rather than adding another
two-bend rotation stage. One unchanged deterministic procedure shortened all four
examined gym configurations numerically. One new solid builds and passes the named
native fidelity checks. These are the standalone-stage results; selected-v2
integration is recorded above. They do not establish unseen validation, a shortest
route proof or delivered feature-insertion capability.

## Rule and degrees of freedom

Minimize **complete material length**, including cylindrical bend length and
bank-dependent flat leads. Move every existing bend angle/bank and every straight
slot together, including slots initially absent at zero length. Preserve original
fold count/order, radii, profile/ordered conductor identity and both external poses.
Internal guide-derived frames are initialization, not hard constraints. The
prepath is measured diagnostically; it neither fixes bend sites nor rejects a
shortening move. No radius growth, added bend, aesthetic pass or angle/position bank.

497 first isolates straight placement: enumerate the nonnegative linear program's
supports of up to three positive straight slots for its three XYZ equations.
This includes all five slots around the four existing bends. Trigger and shallow
are already minimal **with those angles fixed**; compact and spatial shorten.
This does not establish a nonlinear route optimum. Compact guide agreement worsens.

498 removes the angle restriction using the existing `FlexibleModel` material map,
with all radius coordinates eliminated. Project the analytic negative length
gradient into the six external-cap equations' tangent space and active bounds.
Take at most four steps, limiting each angle/bank change to 0.2 rad before nonlinear
retraction, with two scalar halvings. Restore caps with at most six Newton/four
halving steps, retaining each step's exact predicted zero-straight active set.
The final original cap gate is checked independently of the local rotation residual.

Only real shortening proceeds. Check at most two last numerical iterates, newest
first, with the unchanged strict thick-profile contact checker, 1024 pairs each.
Accept only `separated`; otherwise preserve the original accepted route. All four
first final certificates separated, so no second check was needed. Hard resource
errors propagate; no temporary pair-limit waiver. The per-case CPU cap is 0.35 s,
wall cap 2 s, phase wall cap 8 s, RSS cap 4 GiB. No new endpoint solves or live
geometry changes occur in either numerical phase. Cached-route timings are
incremental contraction/check costs, not full cold solver performance.

## Independent configurations and outcomes

The same four existing gym layouts are examined development evidence throughout,
not eight cases across two methods. Inputs and executable sources/rules are pinned
before each phase. No configurations fail, skip or remain unattempted numerically;
no invalid-control or untouched-holdout coverage is claimed.

| Gym input           | Original mm | 498 contracted mm | Guide RMS original → contracted mm | 498 CPU s |
| ------------------- | ----------: | ----------------: | ---------------------------------: | --------: |
| hairpin2710428323   |   42.746057 |         16.553806 |                7.435363 → 1.176936 |  0.100679 |
| compact4033669276   |   20.057443 |         15.911437 |                2.441302 → 2.826886 |  0.101336 |
| shallow8-gym424-05  |   47.585465 |         32.261073 |                4.833012 → 2.632929 |  0.159678 |
| spatial12-gym424-09 |   84.531991 |         78.527534 |                3.481914 → 1.581348 |  0.098198 |

All four retain four folds, fixed radii/profile/targets, cap residual <=1e-7 and
sampled material metric error <=1e-10. The trigger improves 61.275%. Its lower
pair's explicit inter-bend straight remains zero: the contraction is demonstrated,
but a particular separated-corner arrangement is not established. Compact becomes
shorter while guide RMS, maximum distance and direction agreement worsen. Do not
describe this as monotonic guide improvement or acceptable appearance on all four.
Spatial crosses one fold angle through zero between finite iterates; the accepted
output still has four folds. No collision-free continuous editing motion is claimed.

497 total CPU/wall 0.384702/0.384900 s; 498 0.462248/0.462533 s. 500 adds 0.043291 CPU s
of read-only invariant/gradient checks, not another route fit. Combined measured
host CPU is 0.890241 s, excluding imports/process startup, orchestration and native
work. Token/currency cost and native CPU are unmeasured. Local peak RSS <19 MB;
native sampled peak 469440 KiB. No resource/source/native errors occurred.

## Native 499 and retained state

Four planned/evaluated, **1/4 native attempted, built and named-fidelity audited**;
other three native-unattempted by the frozen sample design. Zero full physical
audits. Native outcome was unknown before this one attempt; no retry or tolerance
waiver. The trigger produces one positive-volume, 132-face solid: 4550 surface
points, 250 seam chains, zero seam flags, three ordered guides and both caps pass.
Maximum surface error 9.151e-9 mm. Generation 4.695317 s; separate development
audit 26.336234 s; complete phase including display 34.912306 s. Its incremental
contraction/contact cost meets the measured generation timing goal; a cold combined
solver timing comparison has not been performed.

Visible standalone component at x=1460 cm:
`Existing bends relocated - 16.554 mm - experiment499`, revision
`0bebab31-8a9b-4448-a5ca-1bb587f5c5a8`. Magenta exact prepath visible; three original
material guides and two joined cap profiles retained hidden. Capture inspected.
UV/textures remain off. Original job88 body/revision, selected solver, gym settings,
diagrams and 178-file source lock are unchanged. The rollback496 remains effective.

Display follow-up501 adds the exact frozen gym primitives to the comparison.
505–506 later hide that retained comparison and return the camera from x=1460 cm
to the live gym at x=610 cm. The user's new layout had generated correctly off
screen; current seed2428091357/revision8 is preserved. Full gym framing verified
visually; palette errors are clear. No solve, body rebuild, deletion or source change.

500 independently verifies all four saved outputs' fold count/radius/target/profile
invariants and positive explicit straights >1e-5 mm. It checks the analytic total
length gradient against finite differences at initial/final coordinates; maximum
absolute discrepancy 1.40e-10. No additional solve, contact check or native attempt.
IDE diagnostics return no findings for the four frozen payloads; no application
code changed, no application unit/full QA suite or full physical audit ran.

Evidence and exact executable prototypes are ignored artifacts:
`artifacts/verification/ribbon_relocation497/` through `ribbon_relocation500/`,
`relocation497.frozen`, `relocation498.frozen`, `relocation499-native.frozen` and
`relocation500-audit.frozen`. Existing helpers are reused unchanged. No further
refinement, wider batch or solver promotion is scheduled by this result.
