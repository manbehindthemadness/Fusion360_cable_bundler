# Historical aggregate baseline

These are preserved first-attempt statistics, not historical geometry to replay.
The fresh-input policy and mechanisms are in [GENERALIZED_RULES.md](GENERALIZED_RULES.md).

| Population | Attempted | First-attempt passes | Failures | Qualification limits |
| --- | ---: | ---: | ---: | --- |
| Completed checkpoint | 100 | 97 | 3 numerical | Mixed sources and adapted after failures; descriptive only |
| Last 26 new inputs of checkpoint | 26 | 24 | 2 numerical | Mixed sources; overlaps the row above |
| Final unchanged-source segment | 12 | 12 | 0 | Small sample; overlaps both rows above |

The 97 ordinary native builds passed named fidelity and precise gym bounds, with
zero accuracy warnings. Maximum measured native error was 1.808111458e-8 mm over
753,760 named native points. Three separate repaired layouts add no first-attempt
passes. 57 of 97 ordinary solves missed the CPU-time-versus-native-generation goal.
Full physical audit remained unmeasured. Point counts are measurement scope, never
independent ribbon coverage. These overlapping populations must not be pooled.

The historical completed checkpoint is archived at
`artifacts/verification/resume1735/final-result.json`. Previously repeated or tuned
campaign prefixes cannot establish an unseen-layout reliability baseline. The
user's earlier experience of 100+ random successes is relevant context, but no
matching frozen independent-run dataset has been established for that claim here.

New fresh runs will report their own first-attempt denominator and unchanged-source
identity. A new failure remains in its original run's statistics even after a
future generalized solver improvement. Finite first-failure runs measure the
observed run, with substantial uncertainty when few inputs have been attempted.

## First fresh validation run

Run `fresh-71392399c25d466096e5de15e5cdb2a3` reserved 100 unique layouts before
solving and excluded all 169 registered historical geometries. It stopped on the
second layout: **1 pass, 1 post-build boundary failure, 98 unattempted**. All 100
reservations remain used. There were no solver changes, repairs, retries, source
epochs, historical geometry replays or accuracy warnings.

Both numerical solves passed strict contact and terminal-hardware checks. Both
native attempts built and passed named fidelity; maximum measured native error was
2.328643521e-9 mm. The second body exceeded the unchanged ±60.625 mm gym envelope
by 29.577602149 mm. Its final route length was 364.097750144 mm versus a
60.636355089 mm guide, after a separated fallback recovery. Those receipts locate
the observed failure in post-build compactness, not in native representation.
They do not establish which solver change caused it or physical infeasibility.

The unchanged-source run lasted 43.83 seconds; one of two solves missed the timing
goal. All original input/source, strict contact/hardware, native fidelity and
screenshot provenance checks passed. Full physical audit remains unmeasured.
Raw first-attempt evidence: `artifacts/verification/resume1737/final-result.json`.

This early unseen-layout failure supports the concern that current generalization
is inadequate. Two attempts cannot establish a population failure rate of 50%,
prove that all earlier improvements collapsed, or support a comparable 100-case
reliability claim. The old 97/100 mixed-source result remains descriptive only.

## Second fresh validation run

Run `fresh-3cdf9fd5d6de46749f099e48d6e4e60b`, seed 2636487172, reserved another
100 unique layouts against all 269 earlier registrations/reservations. It stopped
on layout 3: **2 passes, 1 post-build boundary failure, 97 unattempted**. Solver,
settings, physical checks and resource limits stayed unchanged; no retries or
historical geometry replays occurred. The unattempted tail remains reserved.

All three numerical solves passed strict contact and terminal hardware. All three
native attempts built and passed named fidelity, with zero accuracy warnings and
maximum measured native error 4.761764824e-9 mm. Layout 3 exceeded the unchanged
±38.125 mm gym envelope by 0.639862218 mm. Its final material length was
129.720028551 mm versus a 36.394100795 mm guide. The run lasted 46.12 seconds;
two of three solves missed the timing goal. Receipt/source/input/novelty checks
passed. Full physical audit remains unmeasured. Evidence:
`artifacts/verification/resume1738/final-result.json`.

| Fresh run | Attempted | Overall passes | Boundary failures | Unattempted |
| --- | ---: | ---: | ---: | ---: |
| First | 2 | 1 | 1 | 98 |
| Second | 3 | 2 | 1 | 97 |

Across these two unchanged-source runs, the five distinct attempted layouts
produced three overall passes and two boundary failures; all five built and passed
named fidelity. These are descriptive counts from two first-failure runs, not a
fixed-size reliability estimate. The source and sampling contracts match between
the fresh runs; the historical 97/100 mixed-source cohort remains separate.

## Fixed sample: 100 additional unique layouts

The Nov9 goal explicitly requested another 100 layouts and a failure rate. Run
`fresh-5129e947eb8543d49a2d1846601f77e4`, seed **3618545976**, precommitted 100
new layouts against all 369 earlier registrations/reservations. It continued past
preserved geometry failures, without retries, tuning, changed inputs or solver
source changes. **All 100 were attempted and collected: 84 passed, 16 failed;
observed failure rate 16%.** There are no skipped, unattempted or uncollected cases.

| First-attempt disposition | Configurations |
| --- | ---: |
| Passed existing measured checks | 84 |
| Unresolved numerical solves | 12 |
| Solver exceptions | 2 |
| Native fidelity failure | 1 |
| Post-build gym boundary failure | 1 |

The numerical failures occurred at 8, 9, 11, 30, 33, 34, 38, 49, 67, 83, 98 and
100. Exceptions were feature-plane degeneracy at 13 and out-of-bounds material
coordinates at 46. Case 58 built but failed native face/cap coverage; its fidelity
audit did not complete. Case 62 passed named fidelity but exceeded the unchanged
gym envelope by 5.0853 mm. Finite unsuccessful solves do not prove infeasibility.

86 configurations were numerically accepted and received ordinary native attempts;
all 86 built, 85 completed named fidelity checks, and 84 also passed the gym bounds.
Another 12 failed numerical configurations received separate diagnostic native
inspection builds, with zero acceptance/fidelity credit. The two solver exceptions
had no native attempt. These remain 100 complete-ribbon configurations, not 98
additional coverage units for the native operations. Full physical audit is
unmeasured on every configuration.

The 85 completed fidelity audits measured 656,110 native points with maximum error
9.178316715e-9 mm and zero completed accuracy warnings. The failed partial audit
at 58 measured another 5,460 points and reached 9.008828880e-6 mm; do not pool that
partial maximum into a passing-fidelity claim. The aggregate registry's raw
`maximum_native_error_mm` includes this failed partial measurement.

45 of 86 ordinary numerical solves missed the CPU-versus-native-generation goal.
Median solve CPU was 0.62809 s over all 100 attempts; median ordinary native
construction was 0.690699 s over 86 attempts. Total tester wall time was 1,730.57 s,
including inspection, previews, polling handoff and reviews. Peak recorded
native-stage RSS was 1,393,936 KiB, below the 4 GiB cap; sampled physical/compressed
footprint was about 19–21 GiB and is not inferred from RSS. Actual in-flight peak
memory remains unmeasured. The twenty-minute review verified unchanged solver and
helper sources and the resource bounds.

All 100 original ordinals/jobs and geometry fingerprints, source/settings,
strict numerical contact/hardware acceptance, native provenance and screenshots
verified with zero receipt errors. Failures retain original receipts. Two reviewed
solver exceptions and one native audit rejection required explicit orchestration
handoffs; a palette refresh restored polling after stopped cases. No failed case
was retried and no solver implementation changed. Final runtime is idle, no worker
or keep-awake process remains, and the final failed inspection geometry is retained.

Evidence: `artifacts/verification/resume1739/final-result.json`,
`completion-audit.json`, `aggregate-comparison.json` and `novelty-after.sqlite3`.
The comparison registry now holds 469 layout fingerprints and four finalized
aggregate runs. This fixed-size sample has a different stopping contract from the
two earlier first-failure runs; their outcomes are not pooled into its denominator.
The older 97/100 mixed-source checkpoint remains descriptive history, not evidence
that the same unchanged solver had a 3% unseen-layout failure rate.
