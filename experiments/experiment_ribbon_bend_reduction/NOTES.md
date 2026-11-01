# Bend-first simplification experiment

The user directed reducing unnecessary bend features before optimizing straight
runs. This experiment starts from the four original frozen gym routes, without
applying the previous straight-contraction pass. Production routing, native
material construction, joined profiles and material limits remain unchanged.

## Fixed rule

Consecutive bends with the same carried crease direction, radius and width have
a net rotation given by their summed signed angles. Replace a compatible group
with one principal-angle bend, or a flat connection for an identity rotation.
Both half-turn signs are explicit algebraic branches. This applies to solver-owned
intermediate geometry; these fixtures have no prescribed winding or intermediate
landmarks. Prescribed winding/order must not be discarded in future integration.

The replacement changes positional offsets. Reclose the whole route by solving
`A l = endpoint - fixed_fold_offset`, with nonnegative straight lengths. Retain
outside straight lengths as the reference and assign zero reference to new
connector slots. Enumerating all zero/free active sets yields the unique
least-squared-change feasible closure; this is not a length optimization or a
stochastic route guess. Adjacent straight pieces merge after closure.

Process largest bend reductions first, then route order. Accept only strictly
fewer bends with the fixed ordered endpoint frames, preserved material geometry
and a separated full thick-ribbon contact result. Length is measured, not ranked
or used to reject a structural improvement. There is no subsequent straight
contraction in this comparison.

Rotation equivalence alone is insufficient: diagonal crease folds have required
flat leads whose positional offsets may not be reproducible by the remaining
straight directions. Those closures reject. Initial positive unit-test assumptions
for two such fixtures were disproved; their rotation checks now remain positive,
and the independent positional-closure rejection is explicitly tested. No physical
constraint or numerical tolerance was relaxed.

Bounds: at most 24 structural proposals and three passes per complete case;
at most ten straight slots/1024 active sets per projection; existing 20,000-pair,
depth-36 thick contact gate. Numerical rank threshold `1e-10`, equation residual
`1e-8`, negative-length uncertainty `1e-9`, omitted straight slots `<=1e-10`.
The unchanged independent cap check remains `1e-7`. These are numerical bounds,
not physical routing allowances.

## Results, 2026-11-01

All four independently authored configurations were already examined development
cases. There is no unseen holdout or universal minimal-bend claim. One unchanged
procedure and budget applied to all four, with no specimen-specific adjustments.

| Case | Bends | Length mm before → after | Length reduction | Native faces | Structural pass s |
|---|---|---|---:|---|---:|
| Calibration N3/D1.5 | 8 → 6 | 101.834899 → 76.951553 | 24.435% | 202 → 172 | 0.069814 |
| Gym 1 N1/D0.75 | 8 → 8 | 21.560472 → 21.560472 | 0% | not rebuilt | 0.001523 |
| Gym 2 N3/D1.5 | 8 → 6 | 59.331644 → 44.641054 | 24.760% | 212 → 182 | 0.173762 |
| Gym 3 N6/D3 | 8 → 7 | 327.651197 → 326.935947 | 0.218% | 338 → 322 | 0.672497 |

- Independent configurations planned/evaluated: **4/4**. **3/4** reduced, **1/4**
  unchanged. Native selection: all **3/3** changed configurations attempted,
  built and passed the named fidelity audit. Gym 1 deliberately not rebuilt:
  its original route was retained. **0/4** complete physical audits. No numerical
  resource/harness failures, native failures or unattempted selected cases.
- Twenty-four total proposals: three accepted and 21 rejected as infeasible
  nonnegative positional closure. No proposed closed route required rejection for
  penetration/unresolved contact in this run. Final contact: 4/4 separated.
- All four stopped because this rewrite family offered no further accepted
  replacement, rather than reaching a pass/proposal budget. This does not prove
  global minimal bends, shortest length, or infeasibility of other rewrite families
  or other straight allocations.
- Maximum complete ordered cap check residual `1.476e-14`; sampled material
  metric/no-lateral-bend residual `4.538e-16`. Peak pinch utilization remains below
  99.6%, with existing radii/banks/dimensions and conductor order retained.
- The unchanged archived 221 native audit checks 23,450 surface points, 1,304 seam
  chains, ordered left/center/right trajectories and both endpoint frames on the
  three new bodies. Maximum surface residual `4.560e-9 mm`; maximum ordered
  trajectory residual `2.415e-9 mm`. All named checks pass. Native continuous
  contact/strain/equilibrium and general construction robustness remain unproved.
- The calibration's question-mark return is removed. Gym 3 loses an elbow bend
  while its large excursion remains. Gym 1's three proposed changes all fail
  positional closure; this rule provides no improvement there. Other visible
  unnecessary features and bend-direction choices are not declared solved.

## Cost and limits

Numerical batch: 120s/case, 600s total and 4GiB local peak RSS. Actual total
2.945134s, peak 18,530,304 bytes (about 17.7MiB). Per-case elapsed including
initial/final numerical contact, metrics and ledger work:
0.199384/0.127914/0.537369/2.076573s. The table's structural timer is a subset,
including proposal closure/contact/recording but excluding initial/final audits.

Native generation (translation + definition + kernel) is
3.062229/1.507713/2.190093s for calibration/gym-2/gym-3. Initial solve plus all
numerical work fits within matched native generation on these three changed
cases. The previous straight-only comparison used different degrees of freedom
and budgets; its timings are not a matched algorithm-speed benchmark.

Native phase: three attempts, zero retries/refinements; 120s/build-and-audit case,
600s phase, plus separately bounded 45s/case guide/display review. Actual phase
103.277466s. Native audit times 33.145402/16.708082/28.907186s are separate from
generation; guide/display review 2.582630/3.338317/3.850321s is also separate.
Maximum sampled Fusion RSS across native/review work 794,512KiB; 4GiB ceiling
and 3.8GiB launch headroom held. In-flight peaks and token/cost accounting unmeasured.
No appearance extraction, texture baking or material assignment was performed.

New bodies remain visible in `264 - Bend simplification - <case>`, with calibration
framed for inspection. Each retains two fixed cap profiles, three hidden original
material guides and a measurement panel hidden for the user's geometry view.
Maximum native-guide display error `1.814e-9 mm`; body revisions unchanged through
review. Original bodies and earlier 259 variants are preserved. Display occurrence
translations do not modify the stored local endpoint targets.

## Files and verification

`closure.py` solves the finite nonnegative projection; `rewrite.py` owns geometric
identities; `reduce.py` owns deterministic rule order/contact acceptance; runners
pin and record the numerical/native phases. Native replay reuses the existing
experimental host with optional result-source/display metadata, retaining legacy
defaults; the native material builder/profile and production code are unchanged.

Evidence: `artifacts/verification/ribbon_bends263/` and `ribbon_bends264/` contain
plans, exact source/input snapshots, every proposal, final routes, all outcomes,
native audit measurements, guide review, summary and captures. Resource limits
were not renewed and no further solver/native batch follows automatically.

Focused verification: 18 new tests plus 13 existing contraction tests, **31 passed**;
scoped Ruff lint/format and IDE inspections. Tests cover impossible nonnegative
closures, material/frame preservation, contact rejection, merging, coordinate
invariance and physical scaling. Full QA, production integration, unseen geometry
and native validation of the unchanged Gym 1 variant were not run.

Reproduce only with the configured project SDK/uv and frozen inputs present:

```text
uv run python -m experiments.experiment_ribbon_bend_reduction.runner --output artifacts/verification/<unused>
uv run python -m experiments.experiment_ribbon_bend_reduction.native_runner --output artifacts/verification/<unused-native>
```

The native runner deliberately replays the recorded 263 results in the owned idle
Fusion development design through local MCP port 27182; it is not a production API.
