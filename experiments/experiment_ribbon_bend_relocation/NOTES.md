# Existing-bend contraction — 497–500, 2026-11-02

The user clarified that the visible bend should move, rather than adding another
two-bend rotation stage. One unchanged deterministic procedure shortened all four
examined gym configurations numerically. One new solid builds and passes the named
native fidelity checks. This is an experimental prototype, not an installed solver,
unseen validation, shortest-route proof or delivered feature-insertion capability.

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
