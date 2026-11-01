# Endpoint spline guidance experiment — 2026-11-01

The user proposed a compact unconstrained endpoint-tangent spline, drawn for
reference, to guide the initial physical routing direction. This first bounded
trial uses it to select exact fold branches before radius allocation. It does
**not** implement general attraction/deformation of an entire ribbon onto a spline.
It changes experimental code only; the production planner, profiles, identities,
native material constructor and physical rules are unchanged.

## Fixed question and procedure

Create one cubic Bezier/Hermite reference with controls
`P0, P0 + chord*T0/3, P1 - chord*T1/3, P1`. The final derivative follows travel
**into** the arrival cap. Handle length is a common, scale-invariant convention,
not a shortest-path calculation. There is no physical feasibility claim for the
reference. Use a257point polyline arc lookup and65ordered equal-arc comparison
stations. Normalized route/guide arc fractions establish correspondence; no
nearest-point jump between nearby guide branches is allowed. Guide RMS is a
sampled shape preference, not a continuous distance bound.

Reconstruct from the original fixed target poses using the existing minimum
material-fold radius. Enumerate the two algebraic endpoint-rotation roots and
the two choices each of lateral-layer mirror and planar negative-departure-pair
mirror: at most eight complete closed branches. Mirror both half-turns of a
departure pair together, never an isolated fold. These are exact discrete branches,
not randomized seeds. Existing module spacing/order remains a limitation.

Each branch receives at most24provisional common-crease rewrites over three rounds,
preferring largest bend reduction then guide RMS. Intermediate geometry is
algebraic only, not accepted contact-free geometry. Archive every completed closed
branch and every rewrite, including infeasible closure. Rank final branches by
guide RMS, direction loss, material length and stable branch ID. Contact-check
at most four in rank order, stopping at the first separated route. Apply one
existing radius/travel allocation, including its at-most-eight dyadic contact
fractions. Retain the candidate only if guide RMS improves, length does not grow
and bend count does not increase against the latest267result. Otherwise preserve
the latest accepted baseline. Candidates later rejected by this guard remain
archived; other branches are explicitly unattempted after selection.

All ordered cap positions/tangents/widths, conductor order/profile, equal local
material increments,99.6%pinch, no lateral bending and full thick self-contact
checks remain fixed. Gym solids are not avoidance inputs. Bounds:120s per complete
configuration,600s numerical phase,4GiB sampled RSS; contact20000pairs/depth36;
one radius LP, at most2517supports. First source/resource/API/harness or false
acceptance stops scheduling. Native replay separately pins at most four attempts,
120s/case,600s phase and45s guide review/case, with zero retries or repair.

## Independent configurations and provenance

All four are previously examined **gym-created development** layouts, not holdouts:

| Label | Original input | Conductors | Diameter mm |
| --- | --- | ---: | ---: |
| calibration | `ribbon_sweep202/case-4.json` | 3 | 1.5 |
| gym-1 | `ribbon_fidelity216/case-1.json` | 1 | 0.75 |
| gym-2 | `ribbon_fidelity216/case-2.json` | 3 | 1.5 |
| gym-3 | `ribbon_fidelity216/case-3.json` | 6 | 3.0 |

Paths above are relative to `artifacts/verification/`. Latest comparison baselines
are267allocated plans and268native bodies. Historical label `calibration` is
misleading: its frozen name is `Rubik gym preview`, N3/D1.5. The270plan coverage
sentence incorrectly called it the retained non-gym N1 control. This is a metadata
error only: the input hash, dimensions and geometry were always202case4. Preserve
that frozen plan and its archived source; the future runner description is corrected
after270..272, with no rerun or changed outcome.

## Numerical outcomes —270

Four planned/evaluated, two improved, two improvement failures with accepted
baselines retained, zero unresolved final routes. No invalid-control trials in
this batch. Four final contact checks report separated; no native outcome follows
from that numerical result.

| Configuration | Latest length mm | Output length mm | Gain | Bends | Ordered guide RMS mm | Solve/allocation/contact s | Full numerical case s |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| calibration | 75.209343 | 60.833732 | 19.114% | 6 -> 6 | 16.812245 -> 11.953130 | 0.220356 | 0.347461 |
| gym-1 | 20.436687 | unchanged | 0 | 8 -> 8 | 3.404201 unchanged | 0.195035 | 0.393516 |
| gym-2 | 44.641054 | unchanged | 0 | 6 -> 6 | 4.345290 unchanged | 2.402726 | 2.784594 |
| gym-3 | 321.265942 | 280.614178 | 12.654% | 7 -> 7 | 79.180906 -> 68.293900 | 0.406148 | 1.251746 |

Reference creation took1.460/1.561/1.477/1.468ms respectively. Numerical phase
4.792367s, maximum local RSS20,496,384bytes. Full case timers include baseline and
final contact verification; pass timers include branch creation/ranking, archived
proposals, contact attempts and radius allocation. They are not guide-only costs.
Source pin/archive setup precedes the numerical-phase timer. No optional material
appearance work contributes to these measurements.

All32branches were constructed,314provisional rewrites evaluated:284infeasible
closures and30closed proposals. Five complete-branch contact attempts: four
separated and one penetrating;27other branches unattempted after selection.
Four LPs evaluated3665supports. Seven radius/contact fractions: four separated,
two penetrating and one unresolved. Unaccepted contact never passes.

Failure dispositions:

- Gym1 selected `root0-lateral0-departure0`, full radius allocation, but its
  candidate21.143398mm/RMS3.646955mm worsened both latest length and guide score.
  The baseline is retained; no alternate-branch refinement follows the guard.
- Gym2's first branch `root1-lateral1-departure1` penetrated. The next mirrored
  branch separated. Radius fractions1and1/2penetrated,1/4was unresolved,1/8separated.
  Its candidate55.333595mm/RMS8.676119mm still worsened both latest values; baseline
  retained. No native attempt for this rejected candidate or the penetrating branch.
- All remaining branches' contact outcomes are unmeasured, not predicted failures.
  Their complete provisional geometry and skip reason remain in the case details.

Gym3 selected `root0-lateral1-departure1`: the first planar fold changes from
`+pi` to `-pi`, reversing its curl. The final banked fold angle changes from
2.923358to0.623754radians; these are fold parameters, not identical to centerline
heading change. Full radius allocation clears contact. Explicit straight travel
falls128.666281->0mm. Flat leads remain63.636769mm,22.678%of total length, compared
with171.410332mm/53.355%previously. Largest radius is92.763892mm. Calibration retains
9.943401mm explicit straight and23.881456mm all flat travel,39.257%of its length.
Do not describe zero explicit straights as an everywhere-curved material ribbon.

The guide lengths are approximately26.008522/5.507609/25.744129/149.296573mm. Their
shortness is not evidence that a physical ribbon can follow them. Gym3 still
departs substantially from its guide, maximum sampled ordered deviation102.546312mm.
This trial changes branches and rewrite choices together with allocation, so no
isolated causal/performance benefit from guide scoring alone has been established.

## Native outcomes —271

Of four independent configurations, two changed routes were natively attempted,
two built and two passed the named material-fidelity checks. The two unchanged
baselines were not rebuilt; no native failures or unattempted changed cases.
Zero complete physical native audits, not four fully certified ribbons.

| Configuration | Latest268faces | New271faces | Native generation s | Fidelity audit s |
| --- | ---: | ---: | ---: | ---: |
| calibration | 152 | 152 | 3.728618 | 15.423902 |
| gym-1 | 110 | not rebuilt | unmeasured | unmeasured |
| gym-2 | 182 | not rebuilt | unmeasured | unmeasured |
| gym-3 | 322 | 242 | 1.883184 | 21.942649 |

13,650sampled surface points and754seam chains checked. Maximum surface deviation
1.051417e-7mm, maximum ordered-guide deviation5.823682e-8mm, within unchanged1e-6mm
fidelity gate. Numerical cap residual maximum2.753067e-13 and sampled material
metric residual maximum5.672192e-16. Native interpolation and complete physical
certification remain separate from these measured checks.

Full numerical elapsed is below matched generation for both changed cases.
Against unchanged268generation timings, Gym1 also fits and Gym2 misses the timing
goal (2.784594s vs1.602406s). This is a goal miss, not permission to expand work.
Native phase53.079671s including builds, audits, hidden original guide retention
and review. No profile, material appearance, healing or output repair was added.
Earlier variants and original body revisions remain intact.

## Reference display —272

All four cases have visible magenta unconstrained guides on their latest268bodies;
the two changed271bodies also show the same respective guide. Six views represent
four independent configurations. Each component retains a hidden exact native
cubic sketch named `Reference - Unconstrained endpoint spline270`. Native reference
sample error<=2.826167e-14mm. The graphics are a129point display polyline; neither
the graphics nor native reference sketch is a compliant ribbon route.

Six captures were visually reviewed; Gym3's271result is left framed. Previous
visibility/body revisions preserved. Display phase8.833119s,0solves/builds. Maximum
sampled RSS over271/272was948,464KiB, below the4GiB ceiling. Exact in-flight peak
and token/usage costs are unmeasured. No extra documents were opened.

## Verification and remaining question

Focused profile:34tests passed (eight guide checks plus18bend-reduction and eight
radius-allocation checks), scoped Ruff lint/format, IDE inspections on all nine
new Python files and complete source review. No full repository suite or full
native physical audit was run. Following the metadata-only runner correction,
its lint/format/IDE checks also passed; the earlier numerical sources remain archived.

Supported: an inexpensive reference can select different initial bend directions
and, in this examined comparison, improve two of four routes without regressing
the retained outputs. Unsupported: shortest distance, minimum bend count, general
reliability, arbitrary spline projection, whole-route attraction, or unseen-case
improvement. The remaining architectural question is how to let the physical
construction follow guide direction through its middle, rather than merely rank
the existing translation/orientation module families. No further batch is launched.

Commands use the configured project SDK via `uv run --python <SDK>`:

```text
-m experiments.experiment_ribbon_spline_guide.runner --output artifacts/verification/ribbon_guide270
-m experiments.experiment_ribbon_spline_guide.native_runner --output artifacts/verification/ribbon_guide271
-m experiments.experiment_ribbon_spline_guide.display_runner --output artifacts/verification/ribbon_guide272
```
