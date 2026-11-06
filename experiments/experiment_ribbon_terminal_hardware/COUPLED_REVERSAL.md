# Coupled incident-fold correction — 2026-11-06

The subsequent [construction fallback](CONSTRUCTION_FALLBACK.md) preserves an
earlier certified clear route when later optimization collides. Its current
comparison is 43/57 numerical acceptances; the 35/57 figures below describe 857.

The user-authorized 848–860 investigation changes first-pass geometry, following
the earlier inspection-only correction. It is included in v2's opt-in **Terminal
hardware clearance (trial)** when first-pass optimization is enabled. Other gym
primitives remain visual context.

## Rule and work allocation

1. Probe for demonstrated intrusion into either declared finite terminal box.
   A witnessed fold selects itself. A witnessed straight selects the fold joining
   it toward the hit terminal. A terminal straight without such a fold has no action.
   This selects one material event, without enumerating alternative fold indices.
2. Negate that angle, fixing its bank and every radius. Couple the remaining angle
   magnitudes, banks and nonnegative straight lengths to the original endpoint
   position and ordered frame. Other fold signs cannot change. Missing zero-length
   straight slots may grow; material profile, fold order and targets stay authoritative.
3. Accept only a strictly shorter route with accurate caps/material, unchanged
   fold count/radii, no explicit native straight slivers, full self-contact
   separation and clearance from both finite terminal proxies.
4. Retain the baseline on any unsuccessful action, allowing ordinary smoothing
   to finish before strict final acceptance. A failed action does not try another
   index/sign branch or start another contraction allowance.

`reversal.correct` **substitutes for** ordinary first-pass contraction. It retains
the existing 0.35 CPU/2 wall seconds within the four-second first pass, four updates
of at most six Newton/four scalar-halving corrections and the 0.2-radian free-angle
trust bound. One full self-contact certificate uses at most 1,024 pairs. No new
feature, radius growth, relaxed physical rule or target movement is introduced.
The SO(3) logarithm detects half-turn frame mismatches that the historical local
skew residual cannot detect. Actual final cap-vector checks remain authoritative.

`Gate.probe` spends at most **32 cells** from the same shared 0.1 CPU/0.25 wall
seconds/1,024-cell measurement pool. Incomplete probes are not cached as final
verdicts. Demonstrated intrusion or completed clearance can be reused for that
exact immutable route. Full first-pass/final checks retain their 512-cell limits.
Optional UV metadata remains downstream of route selection, without creating
appearances or bitmaps.

## Retained unsuccessful phases

- 849–850 reflect the terminal-most fold. Six inner Newton steps leave nanometer
  cap residuals that prevent the local mating proof. Finishing closure within the
  original four-update allowance clears the smoothed current variant, but grows
  it from 39.476 to 56.158 mm; its tight first-pass variant still collides. This
  selection rule is not adopted. No dimensional tolerance is relaxed.
- 851 uses witness incidence: current tight first pass clears at 30.203884958 mm,
  its smoothed variant stalls closure, and the N5 final variant remains blocked.
- 852 evaluates first-pass geometry only and requires shortening: current repaired,
  N5/N9 actions rejected for growth, N3 already clear. These are four examined
  configurations with dependent variants, not four new successful repairs.
- 854 cold-replays those four through the integrated solver: current accepted,
  N9/N3 previous finals exact, N5 still unresolved.
- 855 stops the full corpus at **17/57** because a full early initializer check
  consumes 512 cells and the shared CPU allowance on range697-case-107. Geometry
  is unchanged, but final clearance cannot finish. Forty inputs are unattempted.
  All source bytes, raw failure and denominator remain saved. The 32-cell probe
  repairs measurement scheduling without increasing the allowance.

No failed phase is erased, treated as success or combined into a test streak.
Raw plans, source pins, route proposals and outcomes are under ignored
`artifacts/verification/ribbon_terminal848` through `860` and their frozen drivers.

## Full comparison and current native result

857 completes **57/57** exact development inputs in **56.411 s**:

| Outcome | Current | Previous enabled hardware policy |
| --- | ---: | ---: |
| Accepted complete numerical routes | 35 | 34 |
| Unresolved / no accepted output | 22 | 23 |
| Previous accepted finals exactly unchanged | 34 | — |

Every accepted result independently clears the finite terminal boxes. Seven inputs
trigger correction: one shorter cleared replacement; six retain their baseline
(two closure limits, two nonshortening moves, one native straight sliver, one
hardware failure). Those six remain rejected at final acceptance. This demonstrates
one new repair plus control preservation, not universal reversal repair, a holdout,
a global optimum or a 1,000-case success streak. Other 34 accepted routes receive
no new native attempts; all 22 unresolved configurations remain unbuilt.

Current N4 seed 321914440 shortens **39.084683057 → 30.203884958 mm**, about **22.7%**.
All four radii stay exactly **0.3765060244728916 mm**; fold count/order and endpoint
poses remain fixed. Smoothing is enabled at 1%, but its proposed result is
hardware-unresolved, so the cleared first-pass route and its own contact certificate
are retained. Cold correction uses **0.142477 CPU s**, 18 Newton corrections and
296 self-contact pairs; complete cold numerical solving uses **1.369834 CPU s**.

858–860 launch one ordinary fresh SDK worker and one unchanged native build,
guarded to equal that exact reviewed route before native work. Current job:
`selected-3c2e7e40b446482aba78a48d9d1ee8f0`.

| Native evidence | Result |
| --- | --- |
| Attempts / positive-volume builds / named fidelity passes | 1 / 1 / 1 |
| Surface samples / seams | 7,140 / 396 |
| Maximum sampled native error | 7.473313531 × 10⁻¹⁰ mm |
| Precision warnings | 0 |
| Generation / separate audit | 0.584982 s / 1.074664 s |
| Live correction / complete numerical CPU | 0.145313 s / 1.463707 s |
| Native precise outer bounds, ±32.5 mm | Pass, zero excess |
| Full physical audits | 0 |

The matched numerical ≤ native-generation timing goal is **missed** and retained;
audit time is not generation time. Native fidelity verifies construction of the
selected geometry; it does not replace the separate self-contact/proxy certificates
or establish complete physical feasibility.

The corrected body and declared terminal boxes are visible. Earlier rejected
bodies, original tester journal/statistics and stopped state remain preserved;
ordinary callbacks are restored. No automatic tester restart or production
promotion occurs. Integrated phases contain **79 fresh numerical executions**
(4+17+57+1) over **57 unique inputs**, separate from cached-route prototypes/unit
fixtures. Source lock contains **227 executable files**.

Focused QA: **46 tests pass** in `terminal856-pytest.xml`, covering the half-turn
residual, incident event selection, fixed radii/signs, growing zero slots, closure
failure/cancellation, substituted budget and incomplete-probe cache behavior.
Scoped Ruff lint and format checks pass on all six affected Python paths. The new
correction modules, gate and tests are IDE-clean; two pre-existing duplicate-fragment
weak warnings remain in the legacy v2 solver. Source copies are preserved as
`.frozen` data with byte-hash relocation manifests to avoid whole-file IDE duplicate
findings. Complete diff reviewed; repository-wide QA was not requested. No required
focused check is unavailable; complete physical feasibility and broader native
coverage remain unmeasured. Final verification records are `terminal861-*`.
