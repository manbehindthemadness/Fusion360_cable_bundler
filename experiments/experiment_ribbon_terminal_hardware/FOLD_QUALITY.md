# Fold-feature length constraints — 2026-11-06

Monitored case 56, N10 seed 975394730, A zone 9/face 8/roll 14°, B zone
19/face 1/roll 24° (stored zero-based), stops with a demonstrated start-proxy
fold intrusion. The original journal remains **56 attempted / 55 passed / zero
warnings**. This repair is separate manual verification, not another streak pass.
Original job `selected-21b7d893e206439282bd0abff2cce757` and its rejected native
inspection remain available. The tester stays stopped; the 1,000-pass goal is unmet.

## Cause and retained unsuccessful trials

Raw construction is 138.780118133 mm. Ordinary terminal reversal does not shorten
it. Existing signed-joint fold recovery closes caps and its first measured feature
gap at 140.308662146 mm, then rejects that route against its unchanged
139.785199235 mm ceiling: raw length plus 1.005081103 mm of measured initial
complete-feature penetration. Terminal measurement uses only 0.013605 CPU s / 55
cells, so this stop is geometric/quality rejection, not measurement exhaustion.

| Frozen cached phase | Outcome; zero native attempts |
| --- | --- |
| 962 | Add the existing ceiling inside the same joint solve; a nearly zero runway throttles the step. |
| 963 | Canonicalize outward sub-native slots and reclose; another actual straight enters the start box. Second constraint reaches no descent. |
| 964 | Group that straight with its upstream fold; still no descent. Grouping change is not adopted. |
| 965 | Clip satisfied gap/length residuals; derivative disappears near an almost active clearance boundary, so no descent. |
| 966 | Instrument the proposed step; confirms the first cleared gap is only 0.000003586 mm while the second gap is -0.493637 mm. |
| 967 | Release fixed zero slots on new evidence; equality-only correction still fails. |
| 968 | Differentiate raw constraints, project scalar inequalities together, and use clipped violations only for merit. Accepted at 139.785199135 mm in 0.292139 CPU s. |

The first feature need not return to exactly its clearance margin while another
opens. Conversely, discarding its derivative just because it currently clears
allows the next step to re-enter it. These are lower clearance bounds and an upper
length bound, alongside six endpoint equalities. Treating them consistently lets
one correction redistribute the existing bends/runways without changing signs.
The finite failures do not establish infeasibility of their alternative families.

## General rule and unchanged limits

Only when the ordinary closed fold-feature proposal would fail its existing
length ceiling, activate that ceiling on the **same model, coordinates and
measured planes**. Original fold signs, radii, joined profile, ordered conductor
identity and target poses stay fixed. No guessed bend, event, angle, axis-family
or seed-specific candidate is added. Existing successful routes never enter this
branch; the older straight-evidence equality fallback also remains unchanged.

Use raw finite differences for the six cap equations and at most three scalar
inequalities: up to two measured complete-feature gaps and length. At most eight
scalar active subsets produce bounded algebraic projections of that one Jacobian;
select the least-norm feasible proposal among them. These are not eight geometry
solves. Only violated inequalities contribute to nonlinear merit. The small
linear feasibility comparison does not relax final cap/material/contact gates.

An outward sub-native runway can otherwise force the whole step to zero through
roundoff. Canonicalize it to exact zero, charge one Newton correction and reclose
the original equations. Release those fixed slots when genuinely new feature
evidence appears, since the changed constraint may require positive runway there.
Final native minimum lengths, cap/material closure, original fold identity, both
finite boxes and full thick-envelope self-contact still gate acceptance.

No phase restarts: deduct the already spent six-correction updates before
activating quality. Current activation has spent five corrections, leaving three
updates and at most 23 total corrections; it succeeds at 15. The whole feasibility
phase retains **4 updates / 0.35 CPU s / 2 wall s**, within four-second first-pass
construction. Original construction shares 2,048 contact pairs, at most 1,024 per
certificate; terminal checking shares **0.1 CPU s / 0.25 wall s / 1,024 cells**.
Strict exhaustion remains unresolved. No smoothing, contraction or hardware budget
is renewed. Native construction, optional material UV and appearance are unchanged.

## Breadth and one native result

969 freezes/enrolls the trigger and its three actual preceding passes. All four
are new exact input signatures; prior 68 inputs/settings/history prefixes remain.
The development corpus now contains **72 unique inputs**, not holdouts. Replay
capacity 72 retains the same 120 s phase / 103 s launch cutoff / 15 s case limits.

970 accepts 4/4 in 3.870 s, preserving all three prior final/first-pass snapshots.
971 evaluates **72/72 in 72.743 s: 59 accepted / 13 unresolved**. All **58 previously
accepted final AND first-pass routes are exact**. Current case is the sole new
acceptance. Every accepted result independently clears both finite boxes and
retains strict separated self-contact. No inputs are skipped or unattempted
numerically. The 13 unresolved IDs remain in `ribbon_terminal971/result.json`.

972–974 launch one ordinary fresh worker and one unchanged native build, guarded
to equal that exact reviewed route. Job `selected-9aa15211254e430c97ffced9a2550086`:

| Measurement | Result |
| --- | ---: |
| Length / unchanged quality ceiling | 139.785199135 / 139.785199235 mm |
| Recovery CPU / wall | 0.336537 / 0.352179 s |
| Recovery updates / Newton corrections | 3 / 15 |
| Recovery pairs / all construction pairs | 623 / 1,114 |
| Shared terminal CPU / cells | 0.018097 s / 295 |
| Complete numerical CPU / wall | 0.998664 / 1.143246 s |
| Native generation / named fidelity audit | 2.715459 / 2.708375 s |
| Whole native operation | 19.329359 s |
| Native attempts / builds / named fidelity passes | 1 / 1 / 1 |
| Faces / native samples / seams | 362 / 12,600 / 696 |
| Maximum native dimensional error | 7.602955914e-10 mm |
| Precision warnings / full physical audits | 0 / 0 |
| Native precise outer bounds against ±66.25 mm | Pass; zero excess |
| Maximum sampled native RSS | 2,072,160 KiB |

The solve-versus-generation timing goal passes on this one case. The whole native
interval includes other work and is not the generation benchmark. Other 58
accepted and all 13 unresolved configurations have **no new native attempt** here;
their native failure rate and full physical compliance are unmeasured. Across the
four-case replay, full corpus and fresh native-worker solve there are 77 complete
numerical executions over 72 unique configurations; the seven cached diagnostics
and unit checks are separate work. No native retry or claim of shortest routing,
general reliability, production readiness or 1,000 consecutive passes follows.

Corrected body, exact frozen gym/prepath and two hardware proxies are visible;
viewport reviewed, native revision unchanged. Original failure body/journal are
preserved and ordinary callbacks restored. Sources match the reviewed 233-file
lock. Evidence, failed trials and frozen source copies remain under ignored
`artifacts/verification/ribbon_terminal962` through `974`.

Affected QA: **85 tests pass**; scoped Ruff lint/format pass on 29 files. All six
changed/new Python files complete IDE inspection without findings. Initial unit
mock omission and formatter/IDE findings are corrected before geometry trials.
No required scoped check is unavailable. Repository-wide QA and broader native or
full physical audits were not run. Standards content and production code are unchanged.
