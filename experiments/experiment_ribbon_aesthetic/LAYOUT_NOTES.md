# Layout-relative easing and turn-merging investigation — 2026-11-01

Four independent examined gym layouts planned/evaluated. Latest307produced three
changed numerical candidates and retained Gym2. Across308/311, three configurations
were natively attempted/built: **two passed named fidelity, one failed**. Gym2was
not rebuilt. **Zero complete physical native audits**. Calibration retains its
previous passing302body; the failed new candidate remains hidden and recorded.
Gym1/Gym3new accepted variants are visible with312reference overlays and Gym3framed.
The four layouts are development cases, not new holdouts or a general success claim.

## User direction and generalized rule

The user approved the earlier smaller layouts but found Gym3still too harsh,
identified static scaling, allowed bends to use straightaways as runway and asked
to investigate merging turns. Inspection found a0.5conductor-diameter step cap and
fixed banks/angles in296. Read-only comparison also found that its fixed six-step
halving policy could stop near a projected optimum; neither observation alone proves
that changing one scalar radius would solve the large layout.

The new model normalizes all linear coordinates by the immutable initial material
length of each layout, with angular coordinates in radians. Step limits are5%of
that layout length for linear coordinates and0.2radian for angles. Conductor size
still controls physical bend limits. All straight slots are nonnegative available
runway, including initially omitted slots; there is no reserved straight length.

Relax signed fold angles, crease banks, radii and straight lengths together. Keep
fold sign/order, conductor/profile identity and both complete ordered target frames.
Update the bank-dependent minimum flat leads geometrically, retaining any original
extra margin. All lanes still use the same isometric material map. Do not fit an
independent edge or repair a built body.

Minimize `L0 * sum(abs(angle)/(radius*cos(bank)))`: the layout-normalized integral
of full cylindrical material-surface curvature squared, per unit strip width.
This avoids the earlier lane-only score's`cos(bank)^3`underweighting of diagonal
creases. It is a geometric fairness measure, not elastic energy, equilibrium or
actual conductor strain. The material/native profile constructor is unchanged.

Project descent onto six endpoint equations and an active material-length bound,
then retract the nonlinear mathematical trial before acceptance. The maximum
length remains the **original285length times1.05**, never another compounded5%.
Radii cannot fall below either the declared construction floor or the current
tightest radius. Complete caps, no greater peak lane curvature, full-profile
contact separation and decreasing full-surface score remain acceptance gates.
Equal local material increments,99.6%pinch,no lateral bending and identities stay
fixed. Gym solids are not obstacles. There is no spline attraction or native repair.

## Turns that can merge

Before and after relaxation, test consecutive same-bank/same-direction fold groups
whose total angle fits one half-turn primitive. Equal original radii are no longer
required: use the angle-weighted mean radius to preserve curved material length.
Retain outer flat leads, make internal straight travel available and reclose the
complete route with the existing affine closure implementation.

A merge must reduce fold count, preserve complete cap frames, stay within the same
length budget, not worsen full-surface/peak-lane curvature and pass thick contact.
Different crease axes are not treated as a scalar angle sum; reversed turns and
groups exceeding a half-turn are not covered by this rule. Each merge call allows
two passes, twelve algebraic proposals and four contact proposals. There are two
calls per case. These four layouts had **zero eligible groups**, both before and
after relaxation; no production shape or native face reduction is attributed to
turn merging. Analytical tests demonstrate a real different-radius two-to-one
merge with cap/contact acceptance. Broader simultaneous reorganization of unlike
axes remains untested; absence of these exact merges does not prove minimal turns.

## Bounded experiments and zero-runway correction

Both304and307use the same four frozen296plans, with285as the original length/target
reference. Limits120s/case,600s/phase,4GiB sampled/local RSS;8relaxation iterations,
6proposal halvings,6Newton corrections/4correction halvings and8relaxation contact
proposals. Contact retains20000pairs/depth36. Merge limits are additional finite
bounds as above. No budget/physical tolerance changed during either phase.
Sources/rules/inputs are snapshotted before execution; all unsuccessful, pending
and unattempted proposals remain in the per-case ledgers.

304improved only Gym3: surface score29.086%lower, length155.646498mm and peak lane
curvature about32%lower versus296. Calibration/Gym1proposals were contact-unresolved;
Gym2proposals worsened peak lane curvature. Gym3used its eight-contact budget.
305built/audited that intermediate Gym3once,226faces, generation3.386613s, named
audit35.055275s.306drew its reference and retained all prior bodies. This successful
intermediate result is preserved, not overwritten by the subsequent result.

Read-only ledger inspection found microscopic straight slots introduced during
Newton reclosure between folds. Examples: calibration1.02e-6..2.01e-8mm;
Gym1 4.85e-8..2.17e-10mm;Gym3 8.02e-8..4.76e-9mm. Several near-contact failures
involve the two folds surrounding those slots. This did not establish that every
unresolved contact was an artifact; one Gym3proposal had a real .288mmrunway and
exhausted20000subdivisions.

307freezes a narrow retraction correction: runway slots predicted at zero
(normalized uncertainty1e-12) stay **exactly on that active face** during Newton
correction. Add their zero-coordinate equations and keep those variables at zero
while solving the other coordinates. Positive proposed runway remains free.
This prevents the closure algorithm from introducing microscopic features; it does
not delete arbitrary output geometry, change targets, waive contact or enlarge
its interval budget. Complete cap/contact checks still run on the final recomposed
geometry. The added regression perturbs a four-fold route and verifies successful
reclosure with all predicted zero slots exactly zero.

## Latest307numerical outcomes

All changes use the same procedure. Scores/peak reductions below compare against
the previously displayed296/302geometry, not the original serial router.

| Case | Length mm before -> after | Growth from original285 | Full-surface score reduction | Peak-lane curvature reduction | Pass s | Full numerical case s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| calibration |63.875419 ->63.865871|4.984%|20.800%|17.974%|1.278942|1.413637|
| gym-1 |12.464389 ->12.460801|4.970%|36.717%|41.141%|.736049|1.031286|
| gym-2 |35.880117 ->unchanged|.204%|0|0|.076673|.162051|
| gym-3 |154.269946 ->161.899865|5.000%|78.776%|83.510%|.198176|.204388|

Final numerical contact is separated on4/4; fold counts stay6/4/4/4. Maximum cap
residual3.086e-11mm and sampled material metric residual4.441e-16. Gym3radii change
from1.506/1.603/3.344/14.209mm to10.237/16.475/19.068/13.034mm. Explicit straight
travel falls79.395128 ->49.383989mm. This excludes the bank-dependent flat leads;
do not describe it as the complete amount of flat material. Gym1explicit straight
travel falls7.419615 ->4.925338mm.

307has17accepted contact proposals and7unresolved ones;11other proposals worsened
peak lane curvature,2had insufficient score gain, and2complete proposals were not
contact-tested after budget exhaustion. Calibration/Gym1stop at contact budget;
Gym2stops after6peak-rejected proposals;Gym3reaches8accepted iterations. None is
proven optimal. The earlier304has2accepted/18unresolved contact proposals,7peak
rejections and1budget-unattempted proposal. Do not combine these repeated four
layouts into eight independent configurations.

304elapsed10.409777s, local peak22,757,376bytes.307elapsed2.814148s, local peak
18,808,832bytes. Pass timings include projection/retraction/contact and recording;
full case timers add baseline/final contact and metric checks. Original first-pass
solving was not rerun; these are incremental finishing costs, not cold end-to-end
routing timings.

## Native rejection, continuation and current scene

308planned three changed307native attempts, using the existing289named fidelity
adapter with its unchanged1e-6mmposition gates. Calibration built once,192faces,
then failed nine surface-point checks in two `after`patches: maximum measured
surface error5.718377e-6mm. All nine reported membership true, so this is not the
prior trimmed-face membership exception. The precise source of the measured
error remains unresolved; do not attribute it to a proven Fusion limitation or
claim full native fidelity. The failed body remains hidden, report unchanged.
Gym1/Gym3were unattempted when this phase stopped. Phase30.768255s.

Host logs and the failed point records were inspected before continuation.
310is a separately frozen, metadata-only disposition: retain all four307case IDs
and mathematical outcomes; copy route bytes unchanged; exclude calibration from
further scheduling and retain its passing302body. Record both the native rejection
and original numerical status. No solve, build, tolerance change or calibration
retry occurs. Transformation .001851s; source/route hashes are preserved.

311is a new bounded plan for the two remaining **first native attempts** only.
Both build and pass the named surface/ordered-guide/seam/cap fidelity checks:

| Case | Faces before -> after | Generation s | Named audit s |
| --- | --- | ---: | ---: |
| gym-1 |86 ->80|1.381024|9.357832|
| gym-3 |210 ->210|1.187579|16.910318|

Generation is surface translation+definition+kernel. Both accepted candidates'
incremental numerical/checking times fit matched generation. Failed calibration
cannot establish an overall timing-success claim. Audit/graphics/appearance work
is excluded from generation. No optional appearances were created or applied.
The older221face counts in shared panels are not this table's baseline. Gym1's
six-face reduction comes from changed flat subdivisions, not an accepted turn merge.

10,010native surface samples,550seam chains,4caps in311. Maximum native surface
error1.759416e-8mm and ordered-guide error1.612593e-8mm. Gym1uses4and Gym3uses2of
the existing actual-UV trim certificates; the policy and distance gates are
unchanged. Zero full physical audits: continuous native volume contact, complete
offset-conductor strain, manufacture and global optimality remain unverified.

311elapsed38.404219s.312display-only adds the identical270magenta references to
the two accepted bodies;3.113295s,0solves/builds, body revisions unchanged. Both
captures visually inspected; Gym3has broader transitions and is framed. Components
are`311 - Layout-relative fold easing - gym-1/gym-3`at display x570cm. Earlier
302/305variants and Gym2/calibration passing bodies remain available. No unrelated
documents, production code, profile/native constructor or saved design changed.

Selected304/305/306/307/308/311/312phase timers sum131.145992s, excluding setup,
310transformation, read-only queries and local checks. Token/cost accounting and
exact in-flight RSS peak are unmeasured. All phase time/RSS ceilings held.

## Verification and replay

36focused checks passed across18aesthetic and18bend-reduction tests. The new tests
cover diagonal material/frame reconstruction, a10xlayout with conductor diameter
fixed, predicted-zero retraction, real different-radius turn merging, incompatible
axes/reversals, and conservative penetration/unresolved-contact rejection for both
new operations. Existing focused bend checks remained passing; no unrelated full
suite ran. All eight changed/new Python files passed Ruff lint/format and IDE
inspection; one initial IDE timeout was retried successfully. Complete source/diff
reviewed. No dedicated type checker exists. Full QA and new native physical audits
are unattempted. No further refinement or batch is scheduled.

Actual entry points use the configured SDK through`uv run --python <SDK>`:

```text
-m experiments.experiment_ribbon_aesthetic.layout_runner --output artifacts/verification/ribbon_layout307
-m experiments.experiment_ribbon_aesthetic.prepare_remaining --output artifacts/verification/ribbon_layout310
-m experiments.experiment_ribbon_aesthetic.layout_native_runner --numerical artifacts/verification/ribbon_layout310/result.json --component-prefix "311 - Layout-relative fold easing - " --display-x-cm 570 --output artifacts/verification/ribbon_layout311
-m experiments.experiment_ribbon_aesthetic.display_runner --native artifacts/verification/ribbon_layout311/result.json --numerical artifacts/verification/ribbon_layout307/result.json --output artifacts/verification/ribbon_layout312
```

These are historical executed paths; directories refuse reuse. A future replay
needs unused output paths, a distinct component prefix and its own frozen bounded
plan.310preparation explicitly depends on the retained308failure; it is not a
general automatic rejection-hiding layer or a new production routing API.

## Shared material geometry, separate routing objective — 2026-11-02

First-pass repair376–384 extracts this model's flexible geometry and bounded
retraction into `experiment_ribbon_fold_relaxation/flexible.py` and
`flexible_steps.py`. The aesthetic subclass retains its original angle-sign bounds,
radius floor, curvature objective/gradient, labels,5%/.2radian step defaults,
peak/contact gates and configurable length allowance. Immutable layout properties
are cached. The first pass supplies its own free-angle/radius policy and material-
length objective; smoothing0does not disable routing optimization.

378compares all five frozen inputs against the prior committed aesthetic model:
initial coordinates, reconstructed route/labels, score and length gradients,
residuals and Jacobians match exactly. Existing18aesthetic tests remain passing.
The new first-pass behavior and native coverage belong to joint-route and locked-
solver NOTES; they are not aesthetic gains or five new independent smoothing cases.
