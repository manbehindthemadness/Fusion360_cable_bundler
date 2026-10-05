# Production Split-ribbon comparison

An isolated baseline comparison, not a solver repair. Production is unchanged.
The six `.py.source` files are byte-identical copies of production at `09d9e60`:
frame transport, banking, lane shape/folding, cable-end guide fitting, public
ribbon builder, and split-exit builder. `sources.py` checks both copies and
production against pinned SHA-256 values before running. Original relative
imports are preserved under private module names; only private copy dependencies
are wired together. Stable geometry, models, material helpers, and Fusion remain
shared. No production module binding is replaced.

The shared endpoint-bounded curved-terminal matrix and independent audits are
reused through a private harness instance. All 18 positive 3/5/19-lane fixtures use the copied
`build_discrete_ribbon_solid` public entry point, including its original coloring,
metadata, notices, and fallback policy, followed by copied split-exit creation.
Every ordered lane at both caps flows to an explicit round connection profile.
The nine known-negative controls remain unconstructed under the shared test
safety policy and are labelled `not_run_safety_control`, not production rejections.
This does not test the full production harness/branch route planner.

Matrix version 4 constrains both complete cable-end guides to one sphere of
diameter five cable widths. The sweep may stay inside or extend outside;
neither is an acceptance requirement. The shared fixture generator retains
the stress interiors and curved terminal transitions, adding a uniform return
to the nearby outgoing cap. Split connection profiles remain unconstrained.
No production-copy source or existing geometry audit is changed.

The public builder's fitted-loft return is observed only to retain the actual
sketch references for the landmark audit. The observer forwards every argument
and the original result unchanged and restores the private copied binding on
success or failure. This avoids dependence on Fusion's automatically suffixed
sketch names. An initial name-based adapter incorrectly omitted those references;
that pass is not a valid solver comparison. Adapter version 2 passed a live
one-case smoke test: 32 actual loft sections, six audited exits, no fallback.
Production source bytes and algorithm behavior were not changed to repair the
test adapter. Missing fitted sections and fallback notices cannot silently count
as an ordinary fitted-loft pass.

Run `uv run python -m experiments.experiment_production_split_ribbon_runner`
with Fusion, the add-in, and the local MCP server running and no active command.
`--smoke` runs only `straight_3x1`, writing a separate smoke report. The full
comparison requires the completed identical-input matrix/audit version 4/4
secured report. Its report is preserved. Generated comparison reports go under
ignored `artifacts/verification/production_split_ribbon_bounded/`; smoke reports go under
`artifacts/verification/production_split_ribbon_bounded_smoke/`. The baseline is
`artifacts/verification/secure_discrete_ribbon_bounded/report.json`. Earlier
unbounded matrix reports are preserved in their original directories; their
pass/failure counts below do not describe the bounded matrix.

The runner replaces only our experiment scratch documents and leaves
`Production Split ribbon comparison` active. Existing user designs are not
saved, discarded, or modified. Failed fixture occurrences are removed; successful
ones remain for review. The retained geometry is a finite-audit result, not a
continuous proof of macaroni-rule compliance. A section-location finding remains
unresolved until its cause is established; it is not automatically a diagnosis
of physical self-contact or a Fusion kernel failure.

Focused regression coverage is in `tests/test_experiment_production_split_ribbon.py`:
source identity/drift, private dependency isolation, the public entry point,
unchanged observer inputs/returns, binding restoration, and missing-section
rejection. Do not edit or format the byte-pinned source copies.

## Completed comparison (2026-10-04)

Adapter version 2 completed the same-input comparison. All 18 positive cases
completed the production public fitted loft with 32 returned sections, and all
324 numbered split exits passed section and connection-cap/rim checks. No
production fallback or cap-matching exception occurred. Nine negative controls
(162 transitions) remained explicitly excluded from construction.

Four trunk-section findings remain, at exactly the same locations as the secured
baseline. The other 14 cases cleared the finite audits and remain in the final
scratch (214 solids). The comparison reports no changed positive-case
classifications. This demonstrates successful geometry construction, not a
resolution of those four findings or a continuous macaroni-rule proof.

| Unresolved trunk finding | Cubic / total | Station |
|---|---|---|
| `near_return_5x1` | 3 / 6 | 2 / 40 |
| `broad_hairpin_19x0.5` | 1 / 6 | 2 / 40 |
| `helix_360_19x0.5` | 1 / 6 | 8 / 40 |
| `near_return_19x0.5` | 2 / 6 | 37 / 40 |

All four failed the sampled local-contour locator. Their cause remains unresolved;
these results do not by themselves establish physical self-contact or a bad
generated solid. The full application routing workflow and original user-design
failure are not reproduced by this explicit-fixture comparison.

Four focused provenance/isolation/adapter tests, changed-wrapper Ruff lint and
format checks, and IDE inspections passed. No repository-wide suite was run.
The final report is `artifacts/verification/production_split_ribbon/report.json`.
The comparison scratch is active; existing user documents remain open, including
modified `Wire creation tester v112`. Production and user geometry are unchanged.

## Endpoint-bounded comparison (2026-10-04)

Matrix version 4 / audit version 4 completed on identical secured inputs. All
27 fixtures passed the shared cable-end boundary check. None of the 18 positive
cases passed all geometry audits: 14 had audit failures and four had construction
failures. The nine known-negative controls were not constructed. All 232 built
split exits passed their independent section and connection-cap/rim checks;
that does not cancel their parent trunk failures.

The unchanged production fallback was attempted on the three near-return cases
and the 19-lane straight/spatial cases. Four fallback sweeps were rejected by
Fusion with `ASM_SWEEP_ILLEGAL_SURFACE`. The 19-lane straight fallback constructed
a body, but failed the trunk audit and had no fitted loft sections for the
landmark audit. Its classification changed from secured construction failure
to production audit failure, not to success. No fallback is counted as a pass.

No solids remain under the existing failed-case cleanup policy. The final
comparison scratch remains open for review; existing user documents are
untouched. The bounded report is
`artifacts/verification/production_split_ribbon_bounded/report.json`. The older
14-pass report above remains preserved and is not evidence for these new inputs.
The focused 110 experiment tests, changed-code lint/format checks, and IDE
inspections passed. No solver fix, rule relaxation, or repository-wide suite
was performed; continuous geometry compliance remains unproven.
