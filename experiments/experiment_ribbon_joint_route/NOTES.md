# Joint first-pass position/orientation construction — 2026-11-01

Four previously examined gym configurations planned/evaluated. Three improved
first-pass plans were natively attempted/built and passed the named fidelity checks;
the unchanged calibration was not rebuilt. Zero complete physical native audits.
These are development results, not holdouts, production promotion or a shortest-path
guarantee. Previous successful bodies remain available and unchanged.

The user identified the serial first-pass bias: an early turn, long excursion and
late correcting folds. Read-only284traced its source to entry-frame-returning
translation modules, conservative spacing along the departure axis, signed-distance
backtracking and a separately appended arrival rotation. In the raw branch feeding
the last successful Gym3result, the backward straight was98.413622mm and dedicated
arrival orientation began after91.135%of material travel. A radius pass can turn
that excursion into a broad curve without removing the underlying arrangement.

## Fixed replacement procedure

This experiment constructs from the fixed endpoint frames/profile/radius policy
and frozen270reference cubic. It does not initialize from the old fold angles,
banks or straight lengths. Old plans provide comparison limits only.

Derive all exact algebraic direct endpoint-rotation roots, plus two stages through
one intermediate frame. That frame uses the reference tangent at parameter1/2and
the projected mean ordered endpoint width. A degenerate width uses the longest
projected endpoint width/entry normal with stable input order; no world-axis choice.
The guide's midpoint location is not imposed as a physical routing landmark.
At most six topologies/six folds (these four layouts use four folds in guided
families). Unlike the previous method, the intermediate orientation makes useful
progress toward arrival; it is not required to return to departure orientation.

For each topology, jointly allocate nonnegative straight slots and radius growth
above the existing declared construction bound. Positions are affine in those
diameter-normalized variables, while the derived rotation closes exactly.
Enumerate supports0..3for three positional equations, including degenerate supports:
at most378supports per topology for the general six-fold representation.

Retain every algebraic support outcome and full closed candidate. Discard candidates
longer than the latest accepted route or with more bends. Rank remaining candidates
by material length, then sampled ordered guide RMS, fold count and stable identity.
Contact-check at most twelve candidates, stopping on the first separated result.
These are finite nonnegative basic solutions, not random seeds. Guide scoring over
vertices is not a global nonlinear guide-distance optimization, and interior
contact-free allocations could be missed. Family exhaustion is not physical
infeasibility. No serial offset module, entry reset, envelope spacing, compensating
U-turn rule, bend simplification, radius post-pass or attraction pass is called.

Fixed contracts: ordered terminal positions/tangents/widths, conductor identity/
profile/order, equal local material increments,99.6%pinch, no lateral bending and
full joined thick-profile self-contact rejection. Gym solids are not obstacles.
Native profile and material-geometry construction are unchanged. No appearances,
healing or output repair are involved. Production code is untouched.

## Inputs, budgets and provenance

The four frozen270plans are last successful baselines: calibration N3/D1.5 from
202case4, Gym1N1/D.75, Gym2N3/D1.5, Gym3N6/D3. Historical `calibration` is a gym
layout, not the separate retained non-gym N1control. Latest native comparison
bodies are271calibration/Gym3 and268Gym1/Gym2. All are already examined development
cases. Repeated variants, bodies, patches and certificates are not extra cases.

285pins source/rule/input hashes before solving. Limits120s/case,600s/phase,4GiB
sampled RSS; six topologies,378supports/topology, twelve contact attempts/case,
20000contact pairs/depth36. Existing affine uncertainties are retained: rank1e-10,
equation1e-8, nonnegative1e-9, omitted straight<=1e-10D; independent complete ordered
cap1e-7. No physical tolerance is changed. Source/resource/API/harness or false
acceptance stops the affected batch, with no in-flight budget enlargement.

##285numerical outcomes

Three improved results, one unsuccessful improvement search with the prior valid
calibration retained. All four final numerical contact checks separated. No new
invalid-control ribbon configurations were included; analytical invalid controls
are unit checks only.

| Case | Latest length -> new mm | Shorter | Bends | Ordered guide RMS before -> after mm | First-pass solve/contact s | Full numerical case s |
| --- | --- | ---: | --- | --- | ---: | ---: |
| calibration | 60.833732 -> unchanged | 0 | 6 -> 6 | 11.953130 unchanged | .043393 | .167311 |
| gym-1 | 20.436687 -> 11.870847 | 41.914% | 8 -> 4 | 3.404201 -> 1.727899 | .584303 | 1.200231 |
| gym-2 | 44.641054 -> 35.807024 | 19.789% | 6 -> 4 | 4.345290 -> 3.011414 | .084394 | .307692 |
| gym-3 | 280.614178 -> 154.190348 | 45.053% | 7 -> 4 | 68.293900 -> 6.155345 | 4.012322 | 4.182492 |

All three selected branches use the guide-derived intermediate orientation:
Gym1`guide-0-0`, Gym2/Gym3`guide-1-1`. Gym3sampled maximum ordered guide deviation
is9.496278mm versus102.546312mm previously, and RMS drops about91%. This is actual
first-pass geometry, with no later attraction hiding the result. Matching normalized
arc stations is not a nearest-point or continuous deviation bound.

Explicit straight travel remains7.609687/12.921352/80.154558mm in Gym1/2/3, plus
bank-dependent flat leads. They now lie in the jointly solved connection; this
experiment does not minimize the percentage of straight material or prove that
every remaining fold/straight is necessary.

24derived topologies,2288linear supports,2208infeasible supports and80closed
candidates.25closed candidates failed the length/fold comparison guard, including
all13calibration candidates (its shortest new candidate64.993412mm). Their contact
is unattempted, not known invalid.55nonregressing candidates were ranked; four
contact attempts yielded three separated and one unresolved, with51remaining
candidates unattempted after selection. No physical infeasibility or optimum claim.
Gym3's shortest candidate exhausted20000contact subdivisions; the next separated
in12pair checks. This explains a concrete cost source; per-candidate timing was
not separately recorded, so its precise timing share remains unmeasured.

Numerical phase5.861453s, maximum local RSS22,724,608bytes. Full case timers include
baseline/final checks; solve timers include all new frame derivation, allocations,
archive writes, guide ranking and contact. Source-archive setup precedes that timer.
The guide was frozen270; its prior creation cost is excluded and was about1.5ms.
No previous routing search is reused as an initialization or omitted cold search.

##286stop and288independent trim diagnosis

286planned three changed native attempts. Gym1built once (86faces), then the old221
audit rejected one trimmed-face membership query. Surface position itself passed:
maximum7.089497e-9mm against1e-6mmgate. Face8, `before/right-bottom`, u~.5/v~.03
had raw membership false and body containment outside despite point round-trip
error5.721958e-16mm. Original controls matched exactly and trimmed-face distance
was2.926558e-12mm. The286report remains failed and unchanged; Gym2/Gym3were initially
unattempted. No body was rebuilt to address this measurement issue.

Host logs were inspected before host-side changes.288is read-only,0solves/builds,
20s bound, .364104s actual. It inspects the actual three coedge parameter curves:
complete u=0/u=1/v=1rectangle sides, with v=0physically collapsed to one tip. Fusion
rejects(.5,.03), but accepts(.1,.03),(.9,.03),(.5,.001),(.5,.5)and both end boundaries.
The native body revision is unchanged. This evidence motivated an independent
topological certificate, not a distance-tolerance expansion.

##289named fidelity policy and native continuation

The new validation-only adapter runs the original221audit, preserving its point
inversion, distances, seams, guide tangents, ordered caps and revision guards.
It adds an explicitly recorded alternative for a rejected membership query only
when all of the following hold:

- Exact corresponding native NURBS support matches authored degrees, knots, weights
  and controls under the existing1e-12mmcontrol comparison.
- One outer trim loop contains only three/four complete, distinct, straight sides
  in actual native UV coordinates. Curves must be degree-one nonrational curves.
- Any omitted rectangle side is independently constant in3D under the builder's
  existing1e-10mmcollapsed-vertex bound. Arbitrary missing edges are rejected.
- The queried UV point is strictly interior, more than1e-8of each parameter extent
  from its sides; coedge endpoint uncertainty is1e-9of extent. Curved, holed,
  partial, duplicate and unsupported boundaries fail closed.
- Independent distance to the same trimmed native face passes the unchanged
  1e-6mmgate. The original audit still checks actual-vs-planned surface position.

The adapter uses [actual coedge geometry in the parent surface's parameter space](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BRepCoEdge_geometry.htm).
It does not modify SDK objects, the native body, target poses or output geometry.
Every raw rejection and certificate is retained. It cannot waive the retired277
attraction case's over-tolerance surface error. The membership policy is extended,
so do not relabel289as an unmodified221pass or rewrite286's historical failure.

289pins this named policy before proceeding: first re-audit the existing Gym1body
without construction, then make the first Gym2/Gym3builds. Two new native attempts
maximum,120s/case,600s/phase,4GiB sampled RSS/3.8GiB launch headroom,64trim certificates.
First new error stops remaining work. The shared experimental host accepts an
optional `fidelity_audit` entry; omission preserves the original221audit path.

All three changed configurations pass the complete named fidelity checks. Only
Gym1needs four trim certificates; Gym2/Gym3need zero.15,120surface samples and832
ordered seam chains checked, six complete cap records. Maximum surface error
1.493735e-8mm; maximum ordered-guide error1.230871e-8mm. No seam failure or tolerance
change. Numerical cap max5.549516e-14; sampled material metric max6.018106e-16.
Zero full physical native audits: these are material-fidelity/contact development
checks, not universal manufacturability or continuous native compliance certificates.

| Case | Latest successful faces -> new | Native generation s | Named fidelity audit s |
| --- | --- | ---: | ---: |
| calibration | 152 -> unchanged | not attempted | not attempted |
| gym-1 | 110 -> 86 | 1.460207, historical286construction | 9.930031,289reaudit |
| gym-2 | 182 -> 142 | 1.550402 | 12.576082 |
| gym-3 | 242 -> 210 | 1.412623 | 17.659097 |

Across286+289there are exactly three independent new native builds, not four;
Gym1's second measurement did not rebuild it. Calibration remains prior geometry.
289's `original_face_count` fields refer to older221bodies, not the latest baseline
column above. Both changed native geometry and all previous successful bodies are
retained. New native component names: `286 - Joint first-pass route - gym-1` and
`289 - Joint first-pass route - gym-2/gym-3`.

Full numerical time fits matched new generation for Gym1/Gym2and misses for Gym3
(4.182492vs1.412623s). Calibration fits its prior271generation timing. Hence two
of three changed cases meet the performance goal; it is not a universal speed gain.
286phase7.679180s,289phase55.771551s.289includes the new read-only Gym1audit, two
new builds and guide/profile review. Initial failed audit time is not separately
reported; its partial measurements remain in286. Optional appearance overhead is0.

##290/291display and current scene

290stopped before reference drawing because the owned design was temporarily not
idle. A read-only query then confirmed the same document and `SelectCommand`.
No user command was cancelled.291repeats only the source-pinned display phase:
three new bodies receive the identical frozen magenta guides and hidden exact
native reference cubics. Calibration's existing view is retained.0solves/builds,
120s/4GiB bound;4.228894s actual, maximum sampled RSS891,024KiB. All three captures
were visually inspected; Gym3is framed and the large former excursion is absent
in this example. Existing geometry/visibility and all body revisions are preserved.

Selected timed phases285+286+288+289+291sum73.905181s, excluding setup/code work,
the .135sfailed290host call and the brief read-only idle query. Exact in-flight RSS
peak and token/usage cost are unmeasured. All resource ceilings held. The same owned
unsaved Fusion design remains open; no unrelated documents were created or changed.

## Verification and supported claims

44focused tests passed across the8joint-route,10trim-domain,18bend-reduction and
8guide checks. Cases include exact joint corner allocation, material/cap identities,
simultaneous rotation progress, rigid-transform frame covariance, conservative
contact rejection, direct-straight controls, invalid UV/boundary rejection and
resource propagation. Scoped Ruff lint/format and IDE inspections passed on every
new/changed code file. Full source/diff reviewed, including the optional audit-path
hook; no full repository suite or type checker was run. Native live checks above
exercise both that hook and the read-only certificate. No new production behavior.

Supported: the forced entry-reset/late-orientation decomposition is absent from
the replacement; three of four examined layouts improve directly in the first
pass, with fewer folds and successful named native fidelity. Unsupported: shortest
routes, minimal bend count, unseen-case reliability, sufficient calibration
improvement, complete native physical certification or an across-the-board timing
win. No extra search, attraction/refinement or geometry retry is scheduled.

Commands use the configured project SDK through `uv run --python <SDK>`:

```text
-m experiments.experiment_ribbon_joint_route.runner --output artifacts/verification/ribbon_joint285
-m experiments.experiment_ribbon_joint_route.native_runner --output artifacts/verification/ribbon_joint286
-m experiments.experiment_ribbon_joint_route.resume_runner --output artifacts/verification/ribbon_joint289
-m experiments.experiment_ribbon_joint_route.display_runner --output artifacts/verification/ribbon_joint291
```

Frozen run directories refuse reuse.286remains stopped, and289depends on its
unchanged existing Gym1body. Archived source snapshots preserve every prior policy.

## Restoring the second pass — 2026-11-01

The user requested restoring the second pass to relax/normalize the remaining
kinks after viewing285/289. Two bounded comparisons used exactly the same four
frozen285routes, without rerunning the first pass or changing target poses.
These are four repeated development configurations, not eight independent cases.

292runs the existing radius/straight allocation once per case. It preserves
angles, banks and leads, grows radii only, and requires nonincreasing material
length. All four return `no_straight_reduction`: 418 linear supports,122feasible
projections, zero contact proposals and zero changed outputs. The finite allocation
does not demonstrate global inability to soften the routes.

295then restores the existing bounded angle-relaxation pass followed by one radius
allocation. Angle relaxation permits straight redistribution and signed angle
changes, with fixed banks/radii/leads; accepted steps must decrease both explicit
straight travel and total material length. Limits: eight iterations, six proposals
per iteration, six Newton corrections/four halvings per proposal,0.2radian step.
The subsequent radius pass has at most2517supports/eight contact fractions and
retains its angle-relaxed input as the radius floor. Both stages share120s/case,
600s/phase,4GiB local RSS and unchanged20000contact-pair/depth36 limits. Each phase
pins sources, input plans and safeguards before execution and preserves all results.

| Case | Angle-pass disposition | Radius-pass disposition | Final length mm | Folds | Combined pass s |
| --- | --- | --- | ---: | ---: | ---: |
| calibration | Six proposals without joint length gain | No straight reduction |60.833732|6|.044061|
| gym-1 | No projected straight descent | No straight reduction |11.870847|4|.004007|
| gym-2 | No projected straight descent | No straight reduction |35.807024|4|.003840|
| gym-3 | No projected straight descent | No straight reduction |154.190348|4|.003074|

Each phase:4/4planned/evaluated,0/4improved,4/4prior plans retained, no skipped or
unattempted numerical cases. All four final numerical contact checks are separated;
maximum ordered-cap residual5.550e-14and sampled material residual6.019e-16.
Zero native attempts, zero new builds, zero new native audits and zero complete
physical audits in this follow-up. Existing289native evidence remains historical,
not newly repeated. No Fusion calls, visibility changes, documents or appearances.

292elapsed1.240786s, allocation pass total .008468s;295elapsed1.340160s, combined
pass total .054983s. Full elapsed includes baseline/final contact and reporting;
pass timers are subsets. Maximum local peak RSS18,268,160/18,595,840bytes. No
matched new native generation benchmark exists. No token/cost estimate is available.

The restored contraction objectives found no acceptable move on these compact
routes. They are not direct curvature-smoothing objectives, and both retain
crease directions. This result does not mean the visible kinks are unavoidable or
that a broader joint angle/bank/radius relaxation has been tested. No new smoothing
algorithm, loosened length criterion, extra folds or production integration was
introduced. The user's visual smoothing goal remains unmet; the previous good
geometry is preserved. Native replay was skipped because no geometry changed.

The radius and angle experiment runners now accept the recorded joint input
directory; the angle runner optionally chains one radius normalization pass.
Legacy defaults remain263inputs with their original algorithms. The final straight
measurement is taken from actual output pieces after both stages. A later lint
correction binds the per-case radius ledger explicitly; archived292/295sources
remain the exact executed versions. No source change was applied during a phase.
Unused native/display wiring was removed because there are no changed bodies.

Focused verification:26radius/joint/trim tests plus6angle-relaxation tests passed,
32total. Ruff lint/format and IDE inspections passed for the two changed runners;
complete code diff reviewed. Full QA, new native fidelity and broader smoothing
coverage are unattempted. No additional experiment is scheduled.

```text
-m experiments.experiment_ribbon_radius_allocation.runner --input-directory artifacts/verification/ribbon_joint285 --input-suffix joint --output artifacts/verification/ribbon_finish292
-m experiments.experiment_ribbon_fold_relaxation.runner --input-directory artifacts/verification/ribbon_joint285 --normalize-radii --output artifacts/verification/ribbon_finish295
```

Use new output directories for reproduction; historical runs refuse reuse.

Subsequent aesthetic296/302/303changes the objective to integrated material-lane
curvature with a declared5%length allowance. All four examined layouts improve that
score and have retained native solids with named fidelity. Gym3peak curvature is
24.733%lower for .079598mmextra length;G1curvature jumps remain. This supersedes the
no-change outcome for visual broadening, not its historical contraction evidence.
See`experiments/experiment_ribbon_aesthetic/NOTES.md`for the method, exact budgets,
297transaction rollback,299missing-body stop, final coverage and limitations.
