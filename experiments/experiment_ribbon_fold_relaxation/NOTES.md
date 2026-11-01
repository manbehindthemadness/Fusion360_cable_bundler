# Straight contraction with compensating fold angles

The user requested collapsing straightaways and allowing the folds to compensate,
after the bend-first simplification experiment. This bounded experiment starts
from the four frozen 263 routes, including unchanged Gym 1. It is geometric
relaxation of an existing valid material plan, not an elastic simulation or a
restart of endpoint-seeded route discovery.

## Fixed procedure

Coordinates are explicit straight lengths divided by conductor diameter and the
signed angle of each existing fold. Radii, crease banks, widths and flat leads
remain fixed. Recompose the original isometric material primitives from the fixed
start cap. Nonnegative straights and fold angles in `[-pi, pi]` are required;
numerical zero pieces can disappear and adjacent straights merge. The accepted
bend count may not increase.

Project the negative combined-straight-length gradient into the nullspace of six
endpoint equations: normalized XYZ displacement and a local ordered-frame
rotation residual. Use bounded finite differences, active coordinate bounds and
a maximum 0.2-radian angle change per step. Retract each nonlinear trial onto
endpoint closure using bounded minimum-norm Newton corrections. This corrects
the mathematical trial before acceptance; it never repairs a built solid or
moves the requested targets.

Accept only when the combined explicit straight length and complete material
length both strictly decrease, complete ordered cap vectors pass the original
`1e-7` check, bend count does not increase, and the unchanged thick-ribbon contact
checker reports separation. The local rotation residual also vanishes at a
half-turn, so it is never a substitute for the full cap-vector gate.

Individual straight lengths may redistribute during endpoint closure. Flat leads
inside diagonal folds are retained; reducing them would require a separate change
to crease direction. This version therefore tests angle relaxation only, not all
possible ways of changing folds. It guarantees measured gains for accepted steps,
not a globally shortest route, a minimum-bend proof, equilibrium, or a continuous
collision-free assembly motion.

Frozen bounds: eight iterations, six proposals per iteration, six Newton
corrections/four correction halvings per proposal, 120s/case, 600s/batch, 4GiB local
peak RSS. Contact retains 20,000 pairs/depth 36. Finite difference is `1e-5` in
diameter-scaled/radian coordinates; affine rank/consistency `1e-10`/`1e-8`;
normalized closure residual `1e-10`; joint length gain must exceed `1e-8 D`.
Numerical zero pieces `<=1e-12` mm/radians are omitted. No physical rule or budget
was loosened after outcomes were observed.

## Numerical results, 2026-11-01

All four are previously examined gym-created development configurations, with no
untouched holdout. One procedure/budget applied to every case.

| Case | Material length mm before → after | Further reduction | Explicit straight mm before → after | Pass s |
|---|---|---:|---|---:|
| Calibration | 76.951553 → 74.417193 | 3.293% | 32.933069 → 30.827457 | 51.186386 |
| Gym 1 | 21.560472 → 19.387921 | 10.077% | 11.186927 → 9.189195 | 15.179288 |
| Gym 2 | 44.641054 → 43.449976 | 2.668% | 16.631904 → 15.743323 | 5.667423 |
| Gym 3 | 326.935947 → 301.411917 | 7.807% | 257.332563 → 231.808532 | 7.244114 |

Four planned/evaluated, 4/4 contract, 0 unchanged, 0 case failures/unattempted.
Fifty proposals: 12 accepted, 26 contact-unresolved, two penetrating, four failed
nonlinear closure, six without joint length gain. All rejected proposals are
retained in per-case JSONL files. Contact uncertainty is not classified as physical
impossibility: 11 proposals exhaust the pair budget and 15 exhaust near-contact
interval resolution. All four stop after six unsuccessful proposals at a step,
not at a demonstrated optimum. No automatic refinement or budget renewal followed.

Final thick contact reports are 4/4 separated. Calibration's final audit uses
19,964 of 20,000 contact pairs, illustrating its verification cost. Maximum
complete cap check residual `2.080e-14`; sampled material metric/no-lateral-bend
residual `5.552e-16`; pinch utilization remains below 99.6%. Endpoints, conductor
order/profile, radii, banks and local equal material increments remain unchanged.
Maximum fold-angle changes are approximately 9.15/13.23/11.51/4.12 degrees.
Fold counts remain 6/8/6/7. No explicit straight reaches zero in the accepted
results: the requested collapse is partial within this rule and budget.

Numerical batch elapsed 88.692509s; peak local RSS 21,676,032 bytes (about 20.7MiB).
Per-case elapsed including initial/final contact, metrics and recording is
56.036807/17.617639/6.232715/8.801508s. The table's pass timer is a subset including
trial projection/retraction, proposal contact and ledger writes, excluding the
initial/final audits. Contact cost was not separately instrumented; do not invent
a kernel-only or numerical-only split from these combined timers.

## Native replay and verification

Replay uses the unchanged material constructor/profile and archived 221 surface,
ordered guide, seam and cap audit. Four changed configurations are selected once,
with 120s/case, 600s/phase, 4GiB sampled Fusion RSS/3.8GiB launch headroom and a
separate 45s/case guide/display bound. No retries, native rerouting, textures or
geometry corrections are permitted. Native and full physical outcomes are
reported separately in `artifacts/verification/ribbon_relax266/`.

Independent configurations planned/evaluated/native-attempted/built/named-audited:
**4/4/4/4/4**. All four pass the named checks; zero native failures, skipped or
unattempted cases, and **zero complete physical audits**. The audit checks 27,860
surface points and 1,550 seam chains plus ordered A/center/B trajectories and both
cap frames. Maximum surface residual `8.376e-9 mm`, maximum ordered trajectory
residual `5.152e-9 mm`. These sampled fidelity checks are separate from the final
numerical contact checks; continuous native volume contact/strain remain unmeasured.

Full native face counts **172/128/182/322** are unchanged from the bend-first input
routes. No additional bend or surface reduction occurred. The shared replay's
`original_face_count` and corresponding panel comparison refer to the original
221 bodies (202/128/212/338), not to an additional reduction in this relaxation
phase. Native generation times are 4.950344/2.107369/1.372168/2.058085s, excluding
audit, guide authoring, display and optional appearance work. All four numerical
timing goals miss: even the proposal pass alone costs more than matched native
generation. This is not yet an inexpensive production finishing pass.

Native phase elapsed 118.563919s, including 27.010633/11.367859/17.382999/29.093575s
of audit and separately recorded 2.382079/3.462901/3.237955/3.706278s of guide/display
review. Maximum sampled native/review Fusion RSS 1,840,448KiB; in-flight peaks
unmeasured. The 4GiB ceiling and 3.8GiB launch headroom held. Maximum sampled guide
display approximation error `1.831e-9 mm`; body revisions remain unchanged through
inspection. Numerical plus native phase totals are 207.256428s, not generation
time or a token-cost estimate. No additional refinement/budget renewal follows.

Originals and 259/264 variants are retained. New components use
`266 - Coupled fold relaxation - <case>`, with native bodies visible, hidden
original material guides and fixed cap sketches. Measurements remain available
in retained panels, hidden for the user's geometry view. Display translations do
not change the stored local target poses.

The shared affine projection helper was given a public name and reused without
changing the earlier nonnegative closure algorithm. The existing native review
adapter accepts optional title/pass/stop captions while retaining old defaults.
Production routing and native construction are unchanged.

Focused verification: six new relaxation checks plus 18 bend-reduction and 13
straight-contraction checks, **37 passed**, with scoped Ruff and IDE inspections.
Tests include actual contact-checked coupled shortening, material/cap preservation,
active parameter bounds, the half-turn residual ambiguity, and conservative
contact rejection. Full QA, unseen geometry, generalized reliability and complete
native strain/contact/equilibrium are not established.

Evidence: `artifacts/verification/ribbon_relax265/` and `ribbon_relax266/` retain
immutable plans, source/input snapshots, every proposal, final routes and native
results. Use the configured project SDK and a new output directory to reproduce:

```text
uv run python -m experiments.experiment_ribbon_fold_relaxation.runner --output artifacts/verification/<unused>
uv run python -m experiments.experiment_ribbon_fold_relaxation.native_runner --output artifacts/verification/<unused-native>
```

The native runner intentionally replays the recorded 265 results in the owned
idle Fusion design through local MCP port 27182. It is not a production API.
