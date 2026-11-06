# Keep certified construction when later optimization fails — 2026-11-06

The user's next stopped range run exposes a lost-baseline selection error, rather
than a timeout or native kernel failure. Seed 2355999392, N8, D0.75 mm is the exact
existing `prior-case-01` configuration. Its new job/run provenance is appended to
that identity in `gym-v2.json`; the inventory remains **57 unique configurations**.

Original job `selected-83855dec395d473096ca9ac9a8062695`:

| Stage | Material length | Self-contact | Terminal hardware |
| --- | ---: | --- | --- |
| Original construction | 66.236324947 mm | Separated, matching certificate | Clear, 12 cells |
| Contracted first pass | 53.053567577 mm | Separated | Start proxy intrusion |
| Smoothed proposal | 53.584101774 mm | Separated | Start proxy intrusion |

Contraction changes the angles/banks and introduces a collision into a previously
cleared route. The measured first-pass witness is 0.067291659 mm behind the start
mating plane. Smoothing does not resolve it. The old final selector considered
only the last two stages, discarded the earlier certified construction and stopped
without accepted geometry. Its rejected native inspection still builds; that is
not clearance or a fidelity audit. The old failed run/body/journal remain retained.

## General selection safeguard

After final smoothing and completed-first-pass hardware checks both fail, v2 may
retain the **exact original construction** only if its own recorded contact result
is strictly separated and the same shared terminal gate clears that immutable
route. Prefer already acceptable final/first-pass geometry as before. No already
accepted result is replaced merely to choose the original construction.

The retained route, first-pass provenance, self-contact certificate and optional UV
source all refer to that same construction. `terminal_hardware_fallback` logs both
discarded proposals and the retained route/certificate. Contraction records
`selection: declined_for_terminal_clearance`; quality records `construction_retained`.
No route is lengthened, healed or rerouted by this selection, and a candidate cannot
borrow another route's certificate. Unresolved contact cannot supply this fallback.

No additional solver search, joint update, smoothing or certificate phase is added.
The existing shared 0.1 CPU/0.25 wall seconds/1,024 terminal-cell limit still applies.
Cached clearance in the current case requires no new material measurement. This
preserves usable geometry; it does **not** improve the shorter invalid proposals
or claim to minimize a valid route's length.

## Bounded evidence and costs

862 stops on a duplicate-input guard before creating geometry; 863 records the
exact existing alias, fixed sources, failed route and three pre-fix accepted
collateral controls (N4 case164, N9 case162, N10 case107). No duplicated coverage.
Source bytes are retained as `.frozen` data before edits.

865 evaluates all four complete inputs: trigger now accepted at exactly
66.236324947 mm; three prior accepted final/first-pass routes remain exact.
866 then completes **57/57** frozen numerical inputs in **56.516 s**:

- **43 accepted / 14 unresolved**, previously 35/22 with hardware enabled.
- All **35 previously accepted final AND first-pass routes are exactly unchanged**.
- Eight former rejections retain independently hardware-cleared, self-separated
  original constructions. These are existing geometry, not eight new bend repairs.
- Seven of those changed cases have no new native build, fidelity or native-boundary
  validation. In particular `rangec59-case-63` retains an 854.374 mm route: numerical
  acceptance does not establish compactness or a gym boundary pass. Keep those
  limitations visible rather than counting 43 problem-free complete builds.

867–870 launch one ordinary fresh worker and one unchanged native build for the
current trigger only, guarded to equal the exact reviewed construction. Job
`selected-f912c6a026ba4976993e08340fcdfd3c` passes:

| Evidence | Result |
| --- | --- |
| Native attempts / builds / named fidelity passes | 1 / 1 / 1 |
| Native surface samples / seams | 9,800 / 540 |
| Maximum sampled native error / precision warnings | 7.541769400e-10 mm / 0 |
| Whole numerical CPU / wall | 1.224075 / 1.364103 s |
| Native generation / separate audit | 2.116763 / 2.055890 s |
| Terminal checking CPU / cells | 0.008525 s / 71, unchanged measured cells |
| Native precise bounds, ±55 mm | Pass, zero excess |
| Full physical audits | 0 |

The matched numerical-CPU ≤ native-generation timing goal passes on this replay.
Independent coverage remains 57 inputs. New full numerical executions are
**62** (4 collateral + 57 corpus + 1 live), not 62 independent cases or a test streak.
The original tester remains stopped with its existing one-attempt/zero-pass journal
unchanged; the later manual verification is separate evidence, not a rewritten pass.

869's body/bounds are correct, but its inspection capture briefly shows the prior
N4 diagnostic gym group after forcing that old group visible. Native-first browsing
had skipped its redraw. 870 replaces only the owned context group from the exact
current frozen gym and prepath, updates the identity cache and preserves the native
revision. The corrected viewport is reviewed; 869 remains stale-context evidence.
No maintained display code or new body was introduced for this inspection correction.

Focused verification: **38 solver/gate/dispatch tests + 14 corpus tests pass**.
The new regression requires matching route/certificate/UV provenance, refusal on
blocked/unresolved original evidence and preservation of already-clear final output.
Scoped Ruff lint/format and diff checks pass. The changed test is IDE-clean; the
legacy solver retains its two pre-existing duplicate-fragment weak warnings.
Source lock verifies 227 files. No required focused check is unavailable; full
repository QA, the other seven native cases and full physical audits are unperformed.
Raw plans, source bytes, trials, errors and views are retained in ignored
`artifacts/verification/ribbon_terminal863` through `870`, with adjacent QA reports.
