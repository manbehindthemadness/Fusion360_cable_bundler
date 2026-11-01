# Deterministic straight-run contraction experiment

This is an experimental second pass over existing isometric material-fold routes.
It does not change production routing, the native builder, profiles, target poses,
conductor order, pinch limits, or fold geometry. It addresses length contraction;
fold reversal, bend elimination and replacement of entire excursions remain open.

## Geometric rule

For fixed folds, every straight has a fixed world direction. Moving earlier
straights translates later folds without rotating them. Consequently the final
position is `p = c + A l`, where columns of `A` are straight unit directions,
`l` contains straight lengths, and `c` is the fixed folds' net displacement.
The terminal orientation is independent of these lengths.

Total material length is `L = L_folds + sum(l)`. Project the negative length
gradient into the nullspace of `A`: `d = -P_null(A) 1`. Then `A d = 0` and
`dL/dt = -||P_null(A) 1||²`. A nonzero projected direction therefore shortens the
route while retaining its endpoint displacement in exact arithmetic. Numerical
closure is independently checked after recomposition, including both ordered
outer lanes, center, tangent and width direction.

The unchanged fold objects preserve their radii, angles, banks, flat leads and
local isometric material maps. Full thick-profile contact must be checked because
their placements change. Only a `separated` contact result can be accepted;
penetration and unresolved results both retain the preceding route.

The deterministic step initially reaches the first positive numerical straight
floor, `1e-7 * diameter`. A rejected step is halved, with eight proposals maximum
per iteration. Four iterations maximum are allowed. These are computational
bounds, not physical dimensions or evidence of an optimum. The row-rank threshold
is `1e-10`; numerical endpoint checks retain the existing `1e-7` threshold.

The rule guarantees strict measured shortening for accepted updates. It does not
guarantee an update on every configuration, an optimal feasible direction after
contact blocks descent, a collision-free continuous assembly motion, or a globally
shortest route. Active straight floors are held fixed; this is not a complete
linear-program active-set solver. Fold topology is fixed, so an unnecessary bend
cannot disappear in this version.

## Frozen comparison, 2026-11-01

Four independently authored, previously examined gym configurations: the retained
N3/D1.5 calibration plus gym-1 N1/D0.75, gym-2 N3/D1.5, gym-3 N6/D3. All are
development evidence, with no untouched holdout. The same algorithm, numerical
bounds, contact checker and budgets applied to all four.

| Configuration | Before mm | After mm | Reduction | Contraction s | Native generation s |
|---|---:|---:|---:|---:|---:|
| Calibration | 101.834899 | 92.982060 | 8.69% | 3.239 | 3.703 |
| Gym 1 | 21.560472 | 19.861769 | 7.88% | 2.990 | 2.394 |
| Gym 2 | 59.331644 | 52.436013 | 11.62% | 4.774 | 1.791 |
| Gym 3 | 327.651197 | 297.189171 | 9.30% | 11.467 | 2.318 |

- Independent cases planned/evaluated/native-attempted/built/named-fidelity-audited:
  **4/4/4/4/4**. All four shortened; none unchanged, failed or unattempted in the
  completed comparison. No expected-invalid geometry controls were included.
- All stopped at the declared four-iteration budget, not a demonstrated optimum.
  Sixteen accepted updates out of 56 proposals; 18 penetration and 22 unresolved
  contact proposals were rejected and retained in the per-case JSONL ledgers.
- Final thick numerical contact reports: 4/4 separated. Maximum cap check residual
  `5.391e-14`; maximum sampled material metric/no-lateral-bend residual `4.441e-16`.
  Fold objects and targets compare unchanged. Numerical evidence is separate from
  native surface fidelity and full physical compliance.
- Four native solids built with unchanged full face counts **202/128/212/338**,
  including caps. Every route still has its original eight folds. This experiment
  demonstrates neither bend elimination nor native surface-count reduction.
- Unchanged archived 221 native audit: 30,520 surface samples, 1,702 seam checks,
  ordered left/center/right trajectory samples and both endpoint frames. Maximum
  surface residual `6.824e-9 mm`; maximum trajectory residual `2.414e-9 mm`.
  Four pass the named checks; zero complete physical audits. Native continuous
  strain, volume contact, equilibrium and universal construction remain unproved.
- Native generation includes profile/surface translation, BRep definition and
  `createBody`; geometry retention, audit, cap sketches, guides, camera and captures
  are separate costs. No appearance extraction/baking/assignment was performed.
  Contraction includes proposal contact checks and ledger writes, excluding the
  separately timed initial and final numerical audits. Its cost exceeds matched
  native generation on 3/4 cases; inexpensive contraction is not established.

## Bounds, failures and retention

Numerical phase: 120s/case, 600s/batch, four iterations/eight proposals each,
20,000-pair/depth-36 contact checks, 4GiB local peak RSS. Actual completed batch
27.827s, approximately 18.8MiB peak local RSS. No endpoint solves or native calls.

Native phase: at most four `createBody` attempts, one per frozen result; no retry
or refinement. 120s/case, 600s/batch, 4GiB sampled Fusion RSS and 3.8GiB launch
headroom. Case elapsed times 26.516/15.424/21.825/33.475s include audits/display.
Maximum sampled native-phase Fusion RSS 727,536KiB; in-flight peaks unmeasured.
Timing-goal misses are retained rather than changing budgets or acceptance.

The first numerical launch, 257, stopped before any complete case evaluation:
the archived calibration uses `policy_radius_mm` rather than `radius_mm`. Phase
258 accepts either explicit field, preserving both source snapshots and the stop.
No algorithm parameter, radius or physical rule was changed to obtain the result.

Display-only phase 260 stopped at the first panel because its anchor was off the
XY sketch plane; the Fusion application log corroborates the API error. Its
response and partial ledger remain. Phase 261 uses a planar annotation anchor,
verifies/reuses complete guide sketches when present, and adds all four panels
without new solids or solves. All four finish with six sketches: two fixed cap
profiles, three hidden original material guides, and one visible measurement
panel. Maximum sampled native guide approximation error `1.814e-9 mm`; body
revisions remain unchanged. Six final sketches do not establish that Fusion
retained a separate failed panel from 260.

Results are in owned components `259 - Deterministic contraction - <case>` in the
existing development design. Occurrence translations only arrange the display;
stored local route targets remain unchanged. Bodies finish individually hidden,
originals untouched. Native captures are under 259. No production promotion or
additional solve/build batch follows automatically from these results.

Evidence: `artifacts/verification/ribbon_contract257..261/`, including immutable
plans, source/input snapshots, every contact proposal, numerical results, native
audit records, failures and captures. Focused verification: 13 tests, scoped Ruff
lint/format and IDE diagnostics. Full QA and production integration were not run.

## Reproduction

Use the configured project SDK and uv. Each output must be a new directory under
`artifacts/verification/`. Original frozen inputs and the archived 221 audit are
required; no network is needed for numerical execution. Native phases require the
local Fusion MCP at port 27182, the pinned owned idle design and original native
body revisions. They are deliberately tied to this recorded comparison, not a
general-purpose production runner.

```text
uv run python -m experiments.experiment_ribbon_contraction.runner --output artifacts/verification/<unused>
uv run python -m experiments.experiment_ribbon_contraction.native_runner --output artifacts/verification/<unused-native>
uv run python -m experiments.experiment_ribbon_contraction.native_runner --annotate --output artifacts/verification/<unused-display>
```
