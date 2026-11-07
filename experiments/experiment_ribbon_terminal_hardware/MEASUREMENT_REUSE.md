# Reuse exact terminal-bound preparation — 2026-11-06

The next tester stops at **12 attempted / 11 passed / 0 warning passes**, on N6
seed 626433965, A zone 14/face 8/roll 40°, B zone 2/face 9/roll 23° (stored zero-based
zone/face indices). Original failed job `selected-2a439abb02a54bd6a694d2decb45a74e`
and its rejected native inspection remain. This is a measurement-budget stop
masking another real intrusion, not native construction failure or physical infeasibility.

The contracted 39.960988219 mm and smoothed 40.360598102 mm routes enter start
hardware. Checking the raw 42.451500232 mm fallback consumes its full 512 cells and
stays unresolved. The original terminal ledger reaches 0.100042 CPU s at 818 cells;
the first coupled correction is still unmeasured. A separate bounded cached probe
finds that correction enters the neighboring start fold. Both measured feature
constraints are necessary; additional diagnostic work never grants solver acceptance.

## General implementation

The correction algorithm, targets, profile, fold signs/radii, material rules,
clearance dimensions, axis directions, subdivision order and acceptance policy
are unchanged. `contact_bounds.prepare_projection` separates immutable piece/axis
transforms from the original analytic material-cell calculation. Ordinary
`projection` retains its entry point and delegates to that shared implementation.
Correlated edge extrema, guards and interval-arithmetic fallback are unchanged.

Each terminal `inspect` invocation owns an LRU of at most 64 prepared evaluators.
There is no global geometry cache. It compares each immutable mating frame once
per box, while still requiring the analytic cap-side proof for every affected cell.
Existing box-axis projections stop as soon as one proves separation. No additional
SAT axes, skipped material, shortened checks or guessed bend candidates are adopted.

The original **0.1 CPU s / 0.25 wall s / 1,024 cells** remains shared across the solve;
each full check is still at most 512 cells and the initial probe at most 32. Recovery
retains **4 updates / 0.35 CPU s / 2 wall s**, original construction pairs and the
four-second construction deadline. Contact and every other physical gate remain hard.
The current case needs 1,021 cells, so its cell margin is only three; this change
does not promise that another geometry cannot exhaust the same finite allowance.

## Retained unsuccessful work

- 910 tries additional whole-piece SAT directions on cached routes. It reveals
  the second intrusion but saves insufficient work; not adopted.
- 911 adds cached SAT axes per cell. It processes fewer cells but spends more CPU;
  not adopted.
- 912's namespace import accidentally replaces the scalar-value memo wrapper, so
  its result measures only projection short-circuiting. 913 corrects that harness;
  scalar memoization adds little benefit and is not adopted.
- 914 reuses fixed projection coefficients; the same cached reports/witnesses
  complete in 0.07553 CPU s versus 0.09884 s, but this is partial measurement only.
- 915 solves the trigger and three actual preceding cases: three controls remain
  exact, trigger still unresolved at its second correction. 916 separately clears
  that exact second candidate in 168 cells; its extra allowance is diagnostic only.
- 917 also reuses immutable mating-frame comparisons. All four configurations
  accept; three prior final/first-pass routes remain exact.
- 919's initial unit run catches a provenance-label error: range completion labels
  were compared with the string `accepted`. 920 corrects only newly enrolled control
  labels using actual accepted route-file presence. The actual baseline snapshots
  and geometry comparisons were already correct. Original generated plans/failure
  XML remain; no real historical result is relabelled.

## Breadth and numerical results

The four cases and actual baselines are frozen before integration. Two controls are
existing `new-case-10` / `new-case-11` aliases, with appended history; N8 passed case 9
and the N6 trigger are genuinely new. All prior 63 inputs/settings/history prefixes
remain. Inventory is **65 unique development configurations**, with reviewed replay
capacity 65 and unchanged 120 s phase / 103 s launch cutoff / 15 s case limits.

921 compares 150 analytical bounds across varied bank/angle/axis/cell values with
the archived original projection: every span is bit-for-bit identical. These are
analytical unit checks, not independent gym configurations. 923 accepts 4/4; all
three controls are exact. 924 completes **65/65 in 66.250 s: 51 accepted / 14 unresolved**.
All **50 previously accepted final AND first-pass snapshots are exact**. Only the
trigger is newly accepted; each acceptance independently clears both finite boxes.
No numerical case is skipped or unattempted. This is examined development evidence,
not untouched validation, universal feasibility or a 1,000-case streak.

## One current native result

926–928 run one ordinary fresh worker and one unchanged native build, guarded to
match the frozen route. Job: `selected-5c526238be984b98a5bff69400f89018`.

| Measurement | Result |
| --- | ---: |
| Length | 41.722852532 mm |
| Recovery CPU / Newton corrections | 0.216155 s / 9 |
| Final self-contact pairs / all construction pairs | 353 / 620 |
| Terminal CPU / cells | 0.088627 s / 1,021 |
| Complete numerical CPU / wall | 1.854487 / 1.968098 s |
| Native generation / named audit | 0.809359 / 1.679038 s |
| Whole native operation | 13.150395 s |
| Native attempts / builds / named fidelity passes | 1 / 1 / 1 |
| Faces / surface samples / seams | 242 / 8,400 / 464 |
| Maximum native error | 7.560695164e-10 mm |
| Precision warnings / full physical audits | 0 / 0 |
| Native precise outer bounds, ±43.75 mm | Pass; zero excess |
| Maximum sampled native RSS | 1,990,240 KiB |

The matched numerical-versus-generation goal **misses**: 1.854487 CPU s exceeds
0.809359 s generation. Reduced checking cost is not a demonstrated end-to-end speedup
over a formerly unresolved solve. Named audit and retained profile/display overhead
are separate from generation. No native retry or timing-budget increase occurs.

Only this trigger is natively rebuilt. Other 50 accepted inputs and all 14 unresolved
inputs have no new native attempt in this comparison. Full physical compliance
remains unmeasured. Full numerical executions total 78 (4 + 4 + 4 + 65 + 1) over 65
unique inputs; cached measurement variants and analytical checks are separate.

Corrected native body, exact current gym/prepath and both hardware proxies are visible;
viewport reviewed and body revision unchanged by display. Original failed body,
input and **11/12 tester journal** are preserved, ordinary callbacks restored and
tester stopped. Evidence is under ignored `artifacts/verification/ribbon_terminal910`
through `928` and adjacent final/QA files. No production or standards change.

Affected verification: **155 tests pass**, including thick projection, contact,
budget/recovery, terminal, solver and corpus consumers. Scoped Ruff lint/format
pass on 42 files. Changed code is IDE-clean apart from two duplication hints in
unchanged `Span`/`Cell` and `interval_projection` blocks; those bodies are unchanged.
Complete source and append-only corpus diff reviewed; source lock verifies 231 files.
930 confirms final files exactly match the full65/native source fingerprints.
929's first final audit used Git HEAD, which advanced externally to the current
work; it stops on the expected inventory mismatch. 930 instead uses the original
frozen 63-case snapshot, with no geometry rerun or source retuning. Required focused
checks are available; repository-wide QA, broader native and full physical audits
were not run.
