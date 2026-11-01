# Joint radius and straight allocation

The user requested a first-pass construction rule that absorbs unnecessary
straightaways into genuinely gentler folds. This experiment tests a joint linear
allocation on the four bend-reduced 263 skeletons. It does not use the later 265
angle-relaxation outputs or integrate a new production routing pass.

## Fixed rule and scope

Angles, crease banks, flat lead lengths, width, thickness, conductor order and both
ordered endpoint frames remain fixed. Existing radii are conservative lower bounds;
only nonnegative growth above those values is permitted. Explicit straight travel
is nonnegative and may reach zero. Original material-isometric primitives and the
unchanged native material constructor remain authoritative.

For this representation, orientation is independent of radius and straight length.
Terminal position has the affine form `p = p0 + A s + B g`, with straight lengths
`s`, radius growth `g`, and fixed minimum-radius/lead offset `p0`. Material length
is also affine: each straight has unit cost and each radius increment has cost
`abs(angle)/cos(bank)`. Normalize lengths by diameter and solve:

- Exact endpoint position equations, `s >= 0`, `g >= 0`.
- Total material length no greater than the input route.
- Lexicographically minimize explicit straight travel, then material length.

Enumerate supports of size0..4 for the three positional equations plus one
material-budget/slack equation. A basic optimum needs at most four positive
coordinates. The implementation also evaluates consistent dependent supports;
these are feasible points, not extra geometric families. At most15allocation
coordinates plus slack give2517supports. Numerical tie rounding is1e-10.

Test the full allocation once. If full thick-ribbon contact is unaccepted, test
fractions1/2,...,1/128 on the exact-closure segment from the initial allocation to
the linear optimum. All fractions preserve the linear equations and length
budget; every material plan is independently checked for ordered caps and volume
contact. This is a fixed rule, not nonlinear endpoint fitting or seed discovery.
It does not certify the globally best contact-constrained radius allocation or a
collision-free continuous deformation/assembly motion.

Numerical bounds: affine rank1e-10/equation residual1e-8; nonnegative uncertainty
1e-9; explicit straight omission<=1e-10D; complete ordered cap check1e-7; material
budget uncertainty1e-8D; accepted straight gain>1e-8D. Existing contact checker:
20,000pairs/depth36. Budget120s/case,600s/batch,4GiB local peak RSS. No changes to
physical limits, numerical tolerances or budgets were made after outcomes.

## Results, 2026-11-01

Four independent, previously examined gym-created development configurations;
no holdout or universal reliability claim. Same procedure/budgets on every case.

| Case | Explicit straight mm before → after | Explicit reduction | Largest radius growth | Material length mm before → after | Allocation/contact s |
|---|---|---:|---|---|---:|
| Calibration | 32.933069 → 24.814734 | 24.65% | 1.805686 → 5.864853 | 76.951553 → 75.209343 | 0.062007 |
| Gym 1 | 11.186927 → 7.243102 | 35.25% | 0.376506 → 1.274153 | 21.560472 → 20.436687 | 0.110083 |
| Gym 2 | 16.631904 → 9.837706 | 40.85% | 0.753012 → 1.889529 | 44.641054 → 44.641054 | 0.302864 |
| Gym 3 | 257.332563 → 128.666281 | 50.00% | 1.506024 → 53.344424 | 326.935947 → 321.265942 | 4.845201 |

All4planned/evaluated/allocated;0unchanged/failed/unattempted cases. The full linear
solution passes contact for calibration/Gym1. Gym2/Gym3 full proposals remain
contact-unresolved; each half-fraction passes. These are not demonstrated
penetrations or impossibility results. Six geometric contact proposals total:
4separated,2unresolved. One linear solve/case;386/1471/562/1093supports evaluated,
3512total,235feasible support projections. No automatic refinement or renewal.

Fold counts remain6/8/6/7. Explicit straight-piece counts3→1,5→2,4→4,5→5. One,
one,three,three folds respectively grow; other folds retain their original radii.
All fixed angles/banks/leads compare unchanged. Maximum complete cap check residual
1.033e-13; sampled metric/no-lateral-bend residual5.673e-16; final numerical contact
4/4separated. Growing radii cannot worsen the existing local pinch utilization.

### Count all flat material, not only explicit straights

Diagonal fold primitives retain flat leads. Their combined material length is
constant while banks/leads remain fixed; minimizing explicit travel also minimizes
total flat travel within this restricted family, but the percentages differ.
Each lane's staggered entry/exit shifts cancel in their sum, so total flat material
is explicit travel plus the sum of every fold's before/after leads.

| Case | All flat material mm before → after | All-flat reduction | Flat share of final material |
|---|---|---:|---:|
| Calibration | 46.997049 → 38.878714 | 17.27% | 51.69% |
| Gym 1 | 14.118064 → 10.174239 | 27.93% | 49.78% |
| Gym 2 | 31.778290 → 24.984092 | 21.38% | 55.97% |
| Gym 3 | 300.076613 → 171.410332 | 42.88% | 53.35% |

The desired full straightaway reduction is therefore **not achieved**: three
layouts remain more than half flat. Radii visibly broaden, but some original
folds and the large routing excursion remain. Fixed crease/lead structure and
contact-unverified full allocations remain limitations. Gym3's full linear
solution eliminates explicit straights, but it was not accepted or natively built;
only the separated half-fraction is shown as valid experimental output.

## Native evidence and cost

Four independent configurations selected/attempted/built/named-fidelity-audited:
**4/4/4/4**. Zero native failures/skips/unattempted cases; **0completephysicalaudits**.
Unchanged archived221audit checks26,530surface points,1,474seam chains, ordered
left/center/right guides and both cap frames. Maximum surface residual6.139e-8mm,
maximum ordered trajectory residual3.394e-8mm. Continuous native volume contact,
strain and equilibrium remain unmeasured; sampled fidelity is a separate result
from numerical material compatibility/contact.

Native full face counts versus the bend-first input:172→152,128→110,182→182,
322→322. The shared host's original_face_count/caption compares to the older221
source bodies202/128/212/338; it must not be read as this pass's face reduction.
All four retain original guides, fixed cap sketches and hidden measurement panels.
Bodies and earlier variants remain; no native repair/healing/profile changes.

Numerical batch7.302021s, local peak22,331,392bytes (21.3MiB). Per-case elapsed
including initial/final audits and recording0.188012/0.264851/0.657603/6.187595s.
The table's allocation/contact timer is a subset. Individual linear enumeration
and contact costs were not separately instrumented.

Native generation (surface translation+definition+kernel):2.769961/2.342635/
1.602406/2.071099s. Matched full numerical timing goal passes3/4, fails Gym3.
Native audit times28.960490/10.856796/17.555009/28.746616s and guide/display review
2.471526/3.560709/3.140620/3.640682s are separate, not generation. Native phase
118.130595s, bounded120s/case600s/phase plus45s/case review; sampled Fusion RSS
max1,026,400KiB,4GiB ceiling/3.8GiB launch headroom held. In-flight peaks and token
costs unmeasured. No optional texture extraction/baking/assignment was performed.

268components remain visible. Display-only269moves those four owned occurrences
away from earlier arrays for clean captures and focuses Gym3. It performs no
solve/build/local-geometry edit, retains body revisions and preserves earlier
visibility. Occurrence translations do not move stored local target poses.

## Implementation and verification

`program.py` owns finite LP support enumeration; `model.py` owns the affine material
geometry; `solve.py` owns fixed contact fractions; `runner.py` pins the numerical
procedure. Shared experimental native replay now accepts a typed ReplaySpec, with
the265/266wrapper retaining its previous CLI/defaults. This avoids duplicating
the material replay implementation for another solver experiment. No production
routing or constructor change, and no additional automatic solver/build batch.

45focused tests pass:8allocation,6angle-relaxation,18bend-reduction,13straight-only.
Allocation tests cover a known degenerate LP optimum, material-budget rejection,
planar/diagonal affine recomposition, actual contact-checked radius growth, direct
straight preservation, conservative contact rejection and resource interruption.
Scoped Ruff lint/format and IDE inspections pass. Full QA, unseen geometry,
production integration and complete native physical compliance were not run.

Evidence: artifacts/verification/ribbon_radius267..269, including pinned plans,
source/input snapshots, full LP solutions, rejected/accepted contact plans, native
audits, all outcomes, summaries and captures. Use the configured project SDK/uv:

```text
uv run python -m experiments.experiment_ribbon_radius_allocation.runner --output artifacts/verification/<unused>
uv run python -m experiments.experiment_ribbon_radius_allocation.native_runner --output artifacts/verification/<unused-native>
```

The native runner replays the recorded267allocations in the owned idle Fusion
development design through local MCP port27182; this is not a production API.
