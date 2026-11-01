# Aesthetic curvature easing after the joint first pass — 2026-11-01

Four independent examined gym configurations planned/numerically evaluated/native
attempted/retained/named-fidelity-audited: **4/4/4/4/4**. No skipped or unattempted
configurations in the completed302phase; **zero complete physical native audits**.
One earlier calibration construction was rolled back after a display exception,
so five kernel calls occurred across these four configurations. Preserve that
failure and the unsuccessful reuse attempt below. These are development results,
not new holdouts, production routing or a universal smoothing guarantee.

## Question and fixed rule

After292/295restored contraction passes left all four compact285routes unchanged,
the user requested an aesthetic pass to ease the harsh bends shown in the Gym3
image. The optional length-preference question received no answer before the run;
the announced recommended5%ceiling was used. This is a ceiling, not required growth.
No contact, pinch, material or endpoint rule is weakened for aesthetics.

Keep fold count/order, signed angles, crease banks, flat lead dimensions and ordered
cap frames fixed. Make every straight slot before/between/after folds available,
including slots omitted at zero in285. Redistribute straight travel and fold radii.
An existing broad fold may tighten, but every radius retains the original declared
construction floor and no fold may exceed the baseline peak material-lane curvature.
Conductor profile, identities/order and the material constructor are unchanged.

Minimize the exact dimensionless geometric score
`D * integral(kappa_lane^2 ds) = sum(abs(angle)*cos(bank)^3*D/radius)`.
Each cylindrical material lane has curvature`cos(bank)^2/radius`through the curved
portion of length`radius*abs(angle)/cos(bank)`. Flat leads contribute zero; staggered
lane entry/exit changes do not alter this integral. This is a geometric fairness
measure, not physical elastic energy or equilibrium. The new derivative-integral
unit check independently evaluates material accelerations rather than restating
the objective formula.

With angles/banks fixed, endpoint orientation is invariant and position is affine
in straight lengths/radii. Project the negative analytic curvature gradient onto
the three position equations and active nonnegative/material-length bounds, then
take bounded steps. Accept only decreasing curvature score and unchanged complete
ordered caps, no greater peak lane curvature, the declared length ceiling, and
separated thick joined-profile contact. Equal local material increments and no
lateral bending remain intrinsic to the same primitives and independently sampled.
Gym solids are excluded from avoidance. No guide attraction, random routes, added
folds, profile changes, appearance work or post-build repair is involved.

This broadens existing arcs; their flat/arc joins remain tangent-continuous with
curvature jumps. It does **not** produce curvature-continuous/G2transitions or
remove every visible crease. No minimum-energy, shortest-route or optimality claim.

## Frozen numerical scope and results296

Use the same four285plans and immutable targets, not rerun first-pass discovery.
At most8iterations,6step halvings per iteration and8total contact proposals per
case; largest normalized coordinate change0.5Dper iteration. Limits120s/case,
600s/phase,4GiB sampled/local RSS,20000contact pairs/depth36. Sources, inputs,
safeguards and numeric bounds are pinned before solving. Affine rank1e-10and
consistency1e-8remain; complete cap guard1e-7; objective gain>1e-9; length arithmetic
uncertainty1e-8Dand peak-curvature uncertainty1e-10/Dare explicitly numerical bounds.
First resource/source/API/harness/false-acceptance stops the phase. No in-flight
policy/budget change or result-driven specimen tuning occurred.

| Case | Length mm before -> after | Added length | Curvature-score reduction | Peak-curvature reduction | Aesthetic pass s | Full numerical case s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| calibration |60.833732 ->63.875419|5.000%|14.046%|36.922%|2.719187|2.876202|
| gym-1 |11.870847 ->12.464389|5.000%|14.782%|0%|1.442670|2.232658|
| gym-2 |35.807024 ->35.880117|0.204%|5.743%|24.322%|.332035|.416218|
| gym-3 |154.190348 ->154.269946|0.052%|8.784%|24.733%|.015966|.021904|

All4improve the integrated score and retain separated final numerical contact.
Gym1's worst fold remains unchanged; do not describe all four peak curvatures as
improved. Gym3adds0.079598mm. Fold counts remain6/4/4/4.26contact proposals were
all accepted/separated;42other complete step proposals had insufficient score
gain. Contact-start events also retain every pending route before evaluation.
Calibration/Gym2reach the eight-iteration ceiling; Gym1/Gym3stop after six no-gain
halvings at a later step. None is proven optimal. No new invalid complete-ribbon
controls were included; rejection/resource/straight/slack controls are analytical
unit checks, not additional native configurations.

Max ordered-cap residual7.688e-14mm, sampled material metric residual4.441e-16.
Numerical phase5.549850s, pass timers sum4.509859s; full timers also include
baseline/final contact and recording. Local peak RSS19,513,344bytes. Original285
first-pass solve time is excluded from these incremental finishing costs.

## Native attempts, display failure and retained results

297first planned the four native replays. Calibration's kernel call and named
fidelity audit passed, but its subsequent review panel accessed the missing
`baseline_folds`field in296's report. This raised an exception outside the builder;
Fusion MCP rolled back the whole script transaction, including the new component.
The saved filesystem-native report therefore records a successful temporary body,
not retained geometry. Gym1..3were unattempted in297. Phase29.447647s.

299froze a new metadata-only continuation and attempted to reuse calibration.
The body was absent; review stopped before any native call. Phase.576986s.
300read-onlyinspection confirmed the same owned document/SelectCommand and no297,
299or aesthetic components. Host logs were inspected after both errors. Preserve
all three records;299's copied evidence cannot establish that its reused body existed.
Its continuation script is archived with299sources and removed from active sources.

The shared experimental replay now validates panel metadata **before** connecting
to Fusion. An explicit typed baseline-route mapping derives the missing bend count
from285into a new source-pinned `numerical-review.json`;296is never rewritten.
Geometry still comes directly from the unchanged296route files. Native construction
and audit now commit in one MCP call, with guide/panel review in a separate call.
A review exception can no longer roll back a successfully committed native body.
The default audit remains the original221policy for other callers; this replay
explicitly selects the existing289trim-certificate fidelity adapter.

302is the reviewed renewal: second calibration kernel attempt and first Gym1..3
attempts, same plans/rules,4attempt ceiling,120s/case600s/phase4GiB/3.8GiBheadroom,
45s/case separate review limit. No geometry refinement or tolerance adjustment.
All four solids retained and pass the named surface/ordered-guide/seam/cap checks.

| Case | First-pass faces -> eased faces | Generation s | Named audit s |
| --- | --- | ---: | ---: |
| calibration |152 ->162|4.240129|22.096324|
| gym-1 |86 ->86|.825348|7.661120|
| gym-2 |142 ->142|1.527541|12.214184|
| gym-3 |210 ->210|1.003019|17.994980|

Generation is surface translation+definition+kernel, excluding audit, guides,
display and appearances. Gym1's incremental numerical cost exceeds generation;
the other three fit that incremental timing goal. Combined cold first-pass plus
finishing time was not rerun and must not be inferred from this cached replay.
The shared panels' `original_face_count`column refers to older221bodies, not the
first-pass comparison in this table. Calibration gains surfaces from newly nonzero
straight slots; there is no new fold or per-conductor child-solid coverage.

20,720native surface samples,1,142seam chains,8caps. Maximum native surface error
1.502e-8mm and ordered-guide error1.189e-8mm under unchanged1e-6mmposition gates.
Only Gym1needs four of the already established strict actual-trim certificates;
other cases need zero. Numerical contact and named native fidelity remain separate
from continuous native contact, strain, manufacturability and full physical audits.

302phase85.430630s, with per-case guide/panel review2.407/2.456/2.491/2.393s.
303display-only overlays the same270magenta cubics on these four results;5.749151s,
0solves/builds, all four body revisions unchanged. All captures visually inspected;
Gym3framed, compact arrangement retained, tight turns broader but G1joins remain.
Previous successful289and earlier bodies/visibility remain available. New components
are`302 - Aesthetic fold easing - <case>`at display x450cm in the same owned unsaved
development design. No unrelated document, appearance, file save or production edit.

Selected296+297+299+302+303phase times total126.754264s, excluding300read-onlyquery,
preparation/code/checks and unmeasured token/cost accounting. Maximum sampled Fusion
RSS1,027,808KiB; exact in-flight peak is unmeasured. All time/RSSceilings held.

## Verification and reproducibility

18focused checks passed:8new aesthetic,8joint-construction and2native-preflight
tests. Coverage includes exact derivative integration, actual contact-gated easing,
fixed caps/material identities, missing straight slots, zero-slack vs5%slack,
unresolved/penetrating contact rejection, straight preservation, resource propagation,
and metadata rejection before any MCPconnection. Scoped Ruff lint/format and IDE
inspections passed for all new/changed code. Complete source/diff reviewed.
Full repository QA, new holdouts and full physical native audits remain unattempted.

Use the configured project SDK through`uv run --python <SDK>`and unused output paths:

```text
-m experiments.experiment_ribbon_aesthetic.runner --length-growth 0.05 --output artifacts/verification/<unused-numerical>
-m experiments.experiment_ribbon_aesthetic.native_runner --output artifacts/verification/<unused-native>
-m experiments.experiment_ribbon_aesthetic.display_runner --output artifacts/verification/<unused-display>
```

Native/display wrappers deliberately pin296/302respectively; they are development replay tools,
not automatic production integration. Historical source snapshots remain authoritative
for the exact executed versions. No further refinement or batch is scheduled.
