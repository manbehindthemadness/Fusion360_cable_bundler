# Guide-directed coupled joints — 407/408/409, 2026-11-02

Five existing gym configurations planned and numerically evaluated: four improve
the declared placement objective and shorten; one retains its coarse route. Two
native attempts produce solids: one passes named fidelity, one fails topology.
The other three configurations are natively unattempted. Zero complete physical
audits and zero untouched holdouts. The selected solver and live gym are unchanged.

## Question and frozen procedure

Use the pre-path to distribute existing bend activity while joining the whole
chain correctly, within the same work limits as reduced-joint403. Begin with the
same five saved381 coarse selections, stopping archive parsing at their first
separated candidate. Neither selected first-pass optimization nor aesthetics runs.
These are incremental experiments, not cold solver benchmarks.

The implementation is isolated in this package. It reuses403's internal-frame
kinematics without changing that package or the selected source lock:

1. Sample the guide's tangents at its existing257parameters. Accumulate absolute
   heading variation in order, including through reversals. Stationary sampled
   tangents or zero total guide/fold turning leave placement unresolved.
2. Weight each existing bend by its baseline center-lane heading change. Assign
   its midpoint in cumulative bend turning to the matching guide-turn quantile.
   Freeze these target points and weights for this run. No uniform-spacing rule,
   new feature, random frame bank or specimen-specific landmark is introduced.
3. Minimize weighted squared distance between actual curved-interval centers and
   those targets, normalized by guide length squared. Targets are preferences,
   not hard waypoints. The objective does not match signed bending, intermediate
   width orientation, full tangent history or complete guide deviation.
4. Differentiate through the three shared internal-frame coordinates and the
   current affine endpoint-closure support. Six fixed1e-5rad derivative probes
   include the response of every active straight/radius coordinate to all three
   endpoint position equations. This is not an independent fit per bend.
5. Use placement descent if it also descends length. Otherwise use the bisector
   of the two negative unit gradients; this locally descends both unless opposed.
   It does not require a tuned scalar objective weight. Limit the first step by
   the predicted nonnegative-allocation boundary and the existing pi/4trust cap.
6. Re-factor the same algebraic branch and fold-group sizes. Use the existing
   complete nonnegative basic affine allocation enumeration; choose the best
   placement among candidates no longer than the preceding accepted route.
   Strict placement gain, ordered caps, material metric and separated full-profile
   contact are mandatory. Composed material frames share exact joins.

The convex guide objective is evaluated only on existing basic allocations; this
does not find its minimum over the full feasible allocation polytope. Only one
internal orientation frame is free, not every bend independently. These retained
representation limits and the objective's narrow scope remain important.

407 pins all five inputs, selected and experimental dependencies, scripts and rule
files before execution. Limits:4s/case,20s/phase,4GiB local RSS,4updates,4step
halvings/update,4contact attempts/case,1024contact subdivisions/default depth36,
0native attempts. No cleanup, builder repair, tolerance expansion or budget change.
Resource/source/API/harness errors stop the phase and preserve unattempted cases.

## Numerical outcomes and costs

All five numerical configurations finish; none is skipped or unattempted. Four
improve, one retains. Thirteen updates accepted across20contact attempts. Strict
placement gain is1e-10 in the dimensionless score; the existing1e-8D comparison
uncertainty is used for the per-step length non-growth gate. Every saved final
route is shorter or unchanged relative to its coarse input.

| Case | Coarse → result mm | Shorter | Placement/closure s | Contact s | Work total s |
| --- | --- | ---: | ---: | ---: | ---: |
| new-excursion |72.876677 →51.343299|29.548%|.044204|.368959|.413163|
| trigger |41.756299 →36.685741|12.143%|.045170|.621976|.667146|
| gym-recent |19.123811 →18.640363|2.528%|.058555|.423754|.482309|
| gym-one |11.870847 → unchanged|0%|.035797|1.203415|1.239213|
| gym-six |154.186705 →154.113311|.048%|.054200|.007045|.061246|

Work includes target preparation, joint updates and numerical contact, excludes
original coarse solving/contact, interpreter startup and orchestration. Contact
is a subset of work, placement/closure is its remainder. Phase wall2.916348s,
CPU2.913692s, local peak20,185,088bytes. Numerical joins have measured position/frame
error0; maximum cap error3.098e-13mm and material metric6.019e-16. Changed routes
have fresh separated certificates under this bounded contact policy. Unchanged
gym-one retains its historical coarse certificate; none of its four new proposals
was accepted. Iteration budget stops the other three four-update cases; trigger
uses all four contact attempts after one accepted update.

The objective improves but distribution is not uniformly corrected:

- Gym-recent longest flat2.943→1.643mm; guide RMS1.484→1.407mm and direction
  loss.10972→.10032. Its previous length-only403variant had a9.352mm longest flat.
  That is useful examined-case evidence for placement, not an overall dominance
  claim:403shortened it7.55%, versus2.53%here.
- New-excursion longest flat31.357→21.268mm but still41.42%of the route; guide
  RMS improves19.338→13.509mm while direction loss worsens.67677→.69489.
- Trigger longest flat13.912→13.440mm; guide RMS7.600→6.153mm and direction loss
  improves.49399→.44848. It shortens slightly more than403's11.69%result.
- Gym-six longest flat88.434→88.524mm and guide RMS6.176→6.241mm worsen despite
  a small improvement in the bend-center target score. Gym-one is unchanged.

Thus absolute turn-quantile target matching alone is insufficient to certify
better full-route feature placement. No extra objective, branch or deeper run is
added in response to these results.

## Native408 and display409

After numerical review,408 freezes exactly trigger then new-excursion, matching
the stated two-problem-layout scope. Limits2attempts,120s/case,250s/phase,4GiB
sampled Fusion RSS and3.8GiB launch headroom; stop first source/resource/API/build/
fidelity failure. The tiny1.295257e-6mm explicit straight in new-excursion and its
403variant's topology failure are recorded risks before construction. No repair,
cleanup or changed tolerance is applied.

Trigger: one positive-volume142-face solid, named fidelity pass.4900surface
samples,270seam chains and both ordered caps checked; maximum surface error
5.762302e-9mm. Generation2.222540s (translation.193960, definition.833209,
kernel1.195371), audit20.267048s, native operation24.758414s. Sampled peak440160KiB.

New-excursion: a positive solid is built but has142faces versus152authored;
the unchanged `Frozen triple/topology guard` rejects it. Surface/guide/seam/cap
audits are unattempted, not passing:0samples/chains/caps. Generation2.595172s,
native operation3.058874s. Sampled peak308368KiB. A tiny connector and a missing
ten-face band are consistent with collapse, but exact face-to-patch attribution
is not established. The failed solid/report remain hidden and retained.

408stops after the second attempt; both planned cases were attempted and built,
one audited/pass and one topology failure. Three other numerical cases are
natively unattempted by scope. Total native phase28.133436s. Host application logs
were inspected after the failure. No native retries or builder edits follow.
Incremental work is below matched generation for the two attempted layouts, but
the original coarse work is excluded and one fails fidelity: no cold performance
or general native reliability claim follows. UV, textures and appearances are off.

409 is display-only, frozen30s/4GiB,0solves/builds. The accepted trigger at x880cm
retains three hidden original A/center/B guides, two existing hidden cap profiles
and the magenta endpoint-tangent reference. Capture visually inspected; a large
arch remains rather than close guide following. Native revision is unchanged.
Display1.438766s. Prior bodies/controls/history and failed hidden results remain.

## Verification and evidence

Seven new focused tests pass; the five403tests passed with the initial shared-
dependency check. New tests cover scale covariance, ordered targets, independently
reclosed finite-difference placement/length slopes, shared frames, conservative
contact, finite work, explicit zero-turn rejection and resource-stop propagation.
Contact outcomes are mocked only in unit acceptance tests, not in407.

Before freezing407, an analytical acceptance test exposed zero contact attempts:
projecting placement descent onto the zero length derivative plane allowed finite
length growth. The common-descent rule above replaced that construction, and all
tests passed. Duplicate-code IDE findings were removed without altering403.
All new Python files pass focused Ruff check/format and IDE diagnostics; complete
code/diff reviewed. No full repository QA or standalone type checker was run.

Selected160-file source lock verifies unchanged. Standards revision matches the
evaluated revision; its unrelated untracked `.DS_Store` was not applied as a
standards update. No production, selected solver, native builder or policy changes.
Evidence: ignored `artifacts/verification/ribbon_guide407`, executed runners
`guide407.py`, `native408.py`, `display409.py`. Plans, inputs, all unsuccessful
steps, numerical routes, native reports and inspected capture remain preserved.
No further trial or promotion is scheduled.

The user subsequently authorizes zero-snap/reclosure410–414. See
`../experiment_ribbon_zero_snap/NOTES.md`: one of these five material plans changes,
four remain identical. Snapping resolves the142-vs152native topology discrepancy,
but the one corrected native solid fails the unchanged1nmseam endpoint guard
(maximum6.071nm, live Fusion point-comparison tolerance10nm). No named-fidelity
acceptance, tolerance relaxation or promotion follows. The initial no-length-growth
rejection411 and the explicitly revised bounded-parameter413policy are both retained.

## Long-run origin419 — static diagnosis, 2026-11-02

User requests understanding why the constructor retains long straight travel to
match bend events. Freeze and inspect all five saved407routes and their final
allocation ledgers; do not propose routes or run closure/contact/native trials.
Limits2s/case,10s/phase,4GiB. All5complete,0skipped/unattempted inspections,
0new route solves/contact/native attempts/full audits. Static phase.037389s wall,
.037331s CPU. Inputs and selected source lock remain unchanged. Evidence/script:
`artifacts/verification/ribbon_closure419`, `closure419.py`.

The shown hairpin's endpoints are5.266593mm apart; its unconstrained reference
guide is6.300599mm, not a certified feasible ribbon length. Actual material is
51.343299mm. Explicit straights contribute35.925338mm; flat portions intrinsic
to banked folds add10.944835mm. Only4.473127mm is center-lane curved travel:
91.2878%of this route is flat. Fold pieces therefore cannot be counted wholly as
bending activity when diagnosing distribution.

Its two large straight lengths are14.850976/21.074360mm, with tangent directions
164.777277degrees apart. Their chord-direction cosines are+.999855/-.966281.
The four fixed folds already contribute10.781525mm along the start/end chord;
the straight system must return5.514932mm along that direction to reach the
5.266593mm target displacement. This is compensating out-and-back travel.

Holding all other pieces fixed, resolve the endpoint residual along the first
large-run direction and the second run's perpendicular component. The remaining
sideways displacement is5.533534mm, and the second direction's leverage is
sin(164.777277deg)=.262571883. Thus its length is forced to
5.533534/.262571883=21.074360mm. The other equation gives14.850976mm. Both match
the recorded route within1.812e-13mm. This proves the conditional two-run closure
identity, not physical necessity of this bend family or a global routing optimum.

The saved final frame trial contains6basic position closures, and the selected
51.343299mm route is the shortest of them. Trigger and recent are also at their
shortest recorded basic allocations in their final frames (10/16closed supports).
Gym-six has7supports and only a.000222mm difference to its shorter unselected
support, whose contact is unmeasured. Gym-one retains its original coarse state.
Thus sparse-allocation selection is not the principal explanation for the large
hairpin's length: ranking more interior placements at fixed angles cannot beat
that fixed-family linear minimum. The previous discussion of interior guide-fit
allocations remains relevant to nonlinear placement quality, but is insufficient
as a remedy for this long-run example.

Upstream construction limitations are explicit in maintained source:

- `orientation.orient` chooses two-fold factorizations with equal/opposite banks.
  This is a selected algebraic representation, not a macaroni/material law.
- The first pair here has banks+/-65.552785degrees. Each fold includes2.639601mm
  of flat lead at each end to accommodate that oblique crease across the profile;
  the pair alone carries10.558405mm of flat lead. Those leads are required for
  the selected bank, not universal required straight lengths for these targets.
- `frames.middle_frame` uses guide midpoint direction but explicitly leaves its
  spatial location unconstrained.407moves this one intermediate orientation in
  three angular coordinates, retaining the balanced factor branches/group sizes;
  it does not independently free all four bend events.
-407's objective scores bend-center positions without the ordered heading
  history, so a better score can retain the same compensating travel structure.

The start/end tangents are180degrees apart and the257sampled guide accumulates
180degrees of heading change. A reversal is required by these inputs;419does not
show that the reversal itself should disappear. It shows why the chosen fold
family places it far away and how the closure must then buy long travel.

Avoid a universal penalty on straight percentage: gym-six spans121.074mm and its
80.609mm straight advances toward the target with cosine.992018; long forward
travel there is not equivalent to the hairpin's nearly cancelling legs. Recent
has no explicit straight pieces and34.40%intrinsic flat travel. The useful next
investigation is coupled spatial/orientation choice and the balanced-bank
restriction, preserving physical rules and bounded cost. No alternate factorization
or improvement is established by this read-only analysis. No new implementation,
test suite, native attempt or display change is performed; documentation diff
reviewed under the prose-only profile.

## User-directed feature-insertion priority — 2026-11-02

The user separates two remedies for the pictured long-run problem: relax the
existing torus joint, or introduce another bend feature. Investigate feature
insertion first to establish compact tight-fold routing. Defer relaxed behavior
because it can conceal missing routing freedom. This priority supersedes treating
radius relaxation as the immediate remedy; it changes no physical bend minimum.

A bend feature represents an additional admissible directional transition with
incoming/outgoing material frames. It is not a split in a straight with unchanged
direction, nor a count of native faces. It may require multiple legal fold
primitives; report feature and primitive counts separately. Inserting it requires
re-solving neighboring rotations and complete position closure together, preserving
both fixed cap frames, profile/side/conductor identity and material compatibility.
Do not assume that a point on the guide supplies a physically admissible width
frame or that a sketch establishes a feasible corrected route.

First experiments must explicitly fix their tight-radius policy and disable
radius relaxation/aesthetic smoothing. Do not silently tighten existing nonminimum
baseline radii when comparing other layouts: freeze the comparison policy before
execution. Derive insertion intent from the measured closure deficit/guide turning
history, not an arbitrary angle bank, uniform feature spacing or specimen-specific
landmark. Limit the first insertion experiment to one additional feature per
configuration, with a frozen primitive/branch/contact/time budget and retained
fallback/failures. Additional features are allowed when needed for steering;
minimum feature count must not forbid a compact feasible route.

Verify compact placement, complete closure, physical rules/contact and CPU before
claiming insertion works. Native build/fidelity remains separate. No insertion
algorithm, new solve or native attempt is implemented by recording this direction.

User authorizes trying this in420–423; see
`../experiment_ribbon_feature_insertion/NOTES.md`. Five layouts, fixed tight radii,
one derived extra station, no guessed station/angle bank. Fixed guide headings420
overconstrain closure; bounded endpoint-derived angular reclosure421retains all
failures and yields three better tight baselines. Added-feature variants have no
compact contact-safe success under the fixed budget. A separately scoped hairpin
baseline improves37.13→23.78mm/flat14.26→6.55mm and passes one unchanged native
fidelity check; it is explicitly not an insertion success. Working solver unchanged.
