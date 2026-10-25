# Endpoint-first prototype — 2026-10-25

The user requested fixed endpoints before procedural path construction, one pass
without length equalization, and single-object candidates in one Fusion document.
The approved scope is four development trunks, at most four numerical evaluations
and four native attempts, no search/retries, 120 seconds per case, 600 seconds per
batch and 2 GiB measured Fusion RSS. The straight control calibrates scheduling.
There are no split endings in this scope and no complete-ribbon validation claim.

`endpoint_first.py` freezes positions, tangent directions and ordered width axes.
Its one fixed recipe generates a quintic using chord-scaled endpoint speeds and
curvature. Nonstraight sections follow the analytic bend binormal, satisfying the
modeled no-wide-axis-bend invariant. Fixed-depth Bernstein hull checks bound the
input curvature/enclosing reach by 0.8, occupied 5x-width sphere containment, and
nonzero bend-frame cross products. Subdivision verifies the unchanged polynomial;
it does not search for a better shape. Conductor radius is checked at finite
stations. Native spacing, banking, cap flow, strain and equilibrium are unmeasured.
Endpoint roll labels do not establish a winding class. The approximate observed
half-width-per-quarter-turn corkscrew ratio is not imposed as a physical law.

## Stopped batch

Evidence: `artifacts/verification/ribbon_cap_transition/endpoint_first/`
`aab4896fadeb4cff9800e21132942227/`.

| Case | Numerical | Native construction | Post-build audit |
| --- | --- | --- | --- |
| control | No detected named preflight violation | Not attempted: setup error | Absent |
| quarter_plus | Unattempted after stop | Unattempted | Absent |
| quarter_minus | Unattempted after stop | Unattempted | Absent |
| half_oblique | Unattempted after stop | Unattempted | Absent |

Independent trunk cases: 4 planned / 1 evaluated / 0 natively attempted / 0 built /
0 fully audited. Overall: 0 accepted, 1 unsuccessful harness outcome, 3 unattempted,
denominator 4. No invalid controls. Native failure rate unmeasured.

The harness instantiated `CableGroupDefinition` with its default `LOOSE` group
type while specifying 19 ribbon lines. Domain validation rejected this before any
section or loft. This is a harness error, not geometric rejection or kernel failure.
The batch is latched and has not been restarted. The control took 0.060 seconds,
including 0.00256 seconds numerical work; native build and post-build audit were
not attempted. Wall time through archive was 43.527 seconds; final RSS 590128 KiB,
in-flight peak and account usage unmeasured. No search ran.

`Endpoint-first ribbon candidates` remains open with one empty owned component;
the existing `Untitled` document is unchanged. The empty result was archived and
photographed; no candidate solids were delivered. Six pure unit checks, Ruff
lint/format and IDE diagnostics passed. These checks did not cover native harness
setup. No production or standards files changed. This report remains preserved;
the later user-directed renewal is recorded below.

## User-directed setup correction and renewal

The user reported missing geometry and requested delivery. The metadata helper now
explicitly chooses `CableGroupType.RIBBON`, with a regression test exercising a
nondefault line count. Both new experiment modules were coherently reloaded. The
renewed runner verifies the historical report is finished with zero native attempts
and that the one owned document contains no bodies or sketches before reuse. The
earlier empty component and report remain unchanged; nothing was deleted.

Renewed evidence: `artifacts/verification/ribbon_cap_transition/endpoint_first/`
`425d40b0a2c14399b5e6ff0ea798a8b9/`.

Question and fixed procedure: can the same endpoint-derived quintic/binormal recipe
construct four single-object trunks? Inputs, algorithm and limits are unchanged.
The new plan records its parent and source fingerprints before execution.

Independent trunk cases: **4 planned / 4 evaluated / 4 native attempts / 4 built /
0 fully audited**. These are examined development inputs, not holdouts. Overall:
0 accepted / 0 known hard-rule failures / 4 unresolved, denominator 4. No invalid
controls, failed builds, skipped or unattempted renewed cases. Numerical acceptance
means only no detected violation in the named checks. Native predictions were
unknown before every build. No split endings or complete-ribbon audits occurred.

| Case | Input certificate bound | Sampled lane radius mm | Sampled length spread | Sections s | Loft s | Partial audit s | Total s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| control | 0 | Straight | 0% | 2.086 | 0.216 | 0.003 | 2.416 |
| quarter_plus | 0.241140 | 6.1294 | 42.981% | 2.283 | 1.086 | 0.068 | 3.638 |
| quarter_minus | 0.350028 | 5.3360 | 45.288% | 2.321 | 1.016 | 0.075 | 3.632 |
| half_oblique | 0.482920 | 7.0997 | 26.336% | 2.364 | 0.740 | 0.076 | 3.401 |

Numerical preparation seconds: 0.019758 / 0.002354 / 0.002567 / 0.002346. Native
loft times exclude section authoring. Positive solid volumes and one planar face
at each prescribed endpoint plane were checked for every body. This is not an
audit of native cap flow, inter-station banking, continuous spacing or strain.
The three twisted candidates visibly concentrate rotation. Their substantial
sampled lane length differences are retained as mechanical warnings. Neither the
image nor successful lofts establish physical realism. Orientation labels do not
certify accumulated twist. No shape adjustments or length searches followed.

Wall time through archive was 65.600 seconds, including orchestration and
finalization; maximum sampled RSS 851296 KiB, final RSS 696464 KiB. In-flight peak
and account cost are unmeasured. All 120-second case, 600-second batch and 2-GiB
RSS gates held. All four renewed slots are consumed. Including the preserved
setup failure, cumulative work is five numerical evaluations of four unique
inputs, four native attempts and four built trunks, zero full audits.

The active `Endpoint-first ribbon candidates` document has four visible positive
solids in named components; its fitted isometric screenshot was inspected. The
F3D archive and PNG are beside the plan/report. The prior empty component remains,
and unrelated `Untitled` is unchanged. Seven focused unit checks, changed-code
Ruff lint/format and IDE diagnostics passed. Full QA and native complete compliance
remain unrun. No production or standards changes occurred. Further physics or
shape refinement requires a new bounded decision; no work is automatically queued.
