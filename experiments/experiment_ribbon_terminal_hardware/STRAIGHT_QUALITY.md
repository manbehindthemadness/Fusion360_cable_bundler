# Constrained straight-feature recovery — 2026-11-06

Trigger: monitored case 16, N3 seed 1104480256, A zone 3/face 5/roll 9°, B zone
24/face 4/roll 78° (stored zero-based). Original failed job
`selected-722ca30937de431383159613e8489682` and its native inspection remain.
The tester journal stays **16 attempted / 15 passed / 0 warning passes**. This
change is a separate manual verification, not a rewrite of those statistics.

## Cause and bounded investigation

A straight before the last fold enters the end connector proxy. Existing fixed
reversal chooses that last fold, fixes its reflected angle magnitude/bank, and
closes at **34.259482245 mm**, exceeding the original **27.152196424 mm** ceiling.
Terminal checking used only 0.003172 CPU s, so this is not measurement timeout.

The user asks to test freeing angle/bank while retaining the chosen reversal
direction and limits. The trigger and three actual preceding passed configurations
are frozen before implementation. Every unsuccessful cached trial remains:

| Phase | Result; no native attempt |
| --- | --- |
| 935 | Free reflected angle/bank: exact caps, 32.123482461 mm; quality rejection |
| 936 | Same reflected family with caps/gap/length together: projection infeasible |
| 937 | Nearest upstream fold reflected with free angle/bank: closure incomplete in remaining updates; length drifts to 77 mm |
| 938 | That upstream reflected family with all constraints: remaining Newton limit |
| 939 | Original-sign feature projection: caps/gap close, but post-filter length rejects |
| 940 | Original-sign caps/gap/length solved together: 27.152196324 mm; strict self-contact and both boxes clear |

The selected downstream fold cannot directly move a preceding straight in a
start-anchored chain; its endpoint closure must compensate upstream. This is a
kinematic inference from material order, not a proof that every reversal fails.
The free reflected tests do not establish infeasibility. They show that merely
removing two fixed coordinates does not fix this case within the unchanged work.
No experimental free-reversal class or alternative fold-selection search is merged.

## General rule

Preserve successful existing output. Only when actual **straight** evidence drives
a fixed deferred reversal that closes above the original construction-length
ceiling may its **unused** work move the original signed joints instead.

The shared feature solver already frees angle magnitudes, banks and runway slots,
preserving all original fold signs, radii, profile/order and fixed targets. Actual
intrusion selects the complete straight and upstream neighboring bend through the
existing feature-plane rule. Solve six ordered endpoint equations, measured full
feature gaps and the **original length ceiling as an active equation** together.
This lets clearance motion redistribute material without first making a detour
and rejecting it afterward. There is no forced reflection or guessed angle/event
candidate in this fallback, and no new bend or radius relaxation.

`StraightQuality` keeps the quality target just inside that ceiling using the
existing 1e-7 mm shortening margin, scaled down for tiny layouts. It grants no
physical tolerance or local growth allowance. Ordinary fold-evidence recovery
retains its previous overlap-based preference. Existing working fixed reversals
and accepted fallback/smoothed routes never enter this new action.

The whole feasibility phase still permits **4 updates / 0.35 CPU s / 2 wall s**
inside the original four-second construction deadline. Deduct fixed-reversal
updates, elapsed CPU/wall and actual contact pairs before calling the shared
solver; six Newton corrections per remaining update. Both stages' counts/times
are combined, and the declined action stays in the ledger. Contact retains the
original remaining 2,048 pairs, at most 1,024 per certificate. Terminal checks
share **0.1 CPU s / 0.25 wall s / 1,024 cells**. Native-sliver cleanup recloses all
equations, followed by strict actual-geometry contact and both-box checks.
No second contraction/smoothing, phase renewal or source-dependent seed special case.

## Breadth

941 enrolls the four pre-fix cases. Case 13 is the exact existing
`historical-208c6aa74e2e` alias; passed cases 14/15 and trigger 16 are new. All prior
65 inputs/settings/history prefixes remain, giving **68 unique development inputs**.
Reviewed replay capacity becomes 68 with unchanged 120 s phase / 103 s launch
cutoff / 15 s case limits. No missing input is regenerated from a seed.

943 accepts 4/4; the three previous final/first-pass snapshots are exact. 944
evaluates **68/68 in 69.336 s: 55 accepted / 13 unresolved**. All **53 previously
accepted final AND first-pass routes are exact**. Current case and older
`range697-case-138` are newly accepted; each acceptance independently clears both
finite boxes. Case 138 closes at 22.912546054 mm, recovery 0.085477 CPU s / 70 pairs,
within its remaining two-update allocation after the fixed attempt. It has no new
native build or outer-boundary measurement here.

These are examined development cases, not untouched holdouts, universal reliability
or a 1,000-pass streak. No case is skipped or unattempted numerically. Other 54
accepted inputs and all 13 unresolved inputs have no new native attempt in this
comparison. Full physical compliance remains unmeasured.

## One current native result

947–949 use one ordinary fresh worker and one unchanged native build, guarded to
equal the exact reviewed result. Job `selected-d07f0706d7bc4d06a2ae040654966c05`:

| Measurement | Result |
| --- | ---: |
| Length / original construction ceiling | 27.152196324 / 27.152196424 mm |
| Preserved original fold signs / radii | All / all |
| Combined recovery CPU / wall | 0.225864 / 0.234712 s |
| Combined updates / Newton corrections | 2 / 12 |
| Recovery certificate / all construction pairs | 197 / 616 |
| Shared terminal CPU / cells | 0.006600 s / 56 |
| Complete numerical CPU / wall | 0.711291 / 0.830195 s |
| Native generation / named audit | 1.772226 / 0.970502 s |
| Whole native operation | 11.390341 s |
| Native attempts / builds / named fidelity passes | 1 / 1 / 1 |
| Faces / surface samples / seams | 152 / 5,250 / 290 |
| Maximum native error | 7.636705495e-10 mm |
| Precision warnings / full physical audits | 0 / 0 |
| Native precise outer bounds, ±26.875 mm | Pass; zero excess |
| Maximum sampled native RSS | 1,831,424 KiB |

The matched solve-versus-generation timing goal passes for this one current case;
do not use the larger whole-native interval as the generation benchmark or claim
an end-to-end speedup over an earlier unresolved solve. No native retry occurs.
Full numerical executions total **73** (4 + 68 + 1) over 68 unique inputs; the six
cached variants and unit checks are separate work, not additional geometry coverage.

Corrected body, exact current gym/prepath and both hardware proxies are visible;
viewport reviewed, body revision unchanged by display. Original failure body,
input and 15/16 journal remain, ordinary callbacks restored and tester stopped.
UV, appearance, conductor/profile identity and native construction are unchanged.
No production or standards changes. Evidence stays under ignored
`artifacts/verification/ribbon_terminal935` through `949` and adjacent final/QA files.

Focused/affected QA: **79 tests pass**, including ceiling validation, successful
legacy-path preservation, remaining-work/counter accounting, feature grouping,
contact/UV/solver/corpus consumers. Scoped Ruff lint/format pass on 22 files.
Changed implementation/tests are IDE-clean; two pre-existing solver duplication
hints remain. Increasing the IDE inspection wait exposes two newly introduced
local-shadowing weak warnings; local names are corrected and inspection completes
cleanly. Initial timed-out scans are not counted as completed checks.

951 proves final contract-doc edits and the two inner residual local-name changes
are executable-equivalent to the frozen full68/native implementation by scope-local
AST normalization. No numerical expressions or control flow changed. Earlier source
bytes/fingerprints remain in their plans; final source lock verifies **232 files**.
Complete source diff and append-only corpus audit pass. No required focused check
is unavailable; repository-wide QA and broader native/full physical audits were not run.
