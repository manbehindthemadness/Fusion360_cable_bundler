# PH-projection spaghetti sweep stress test (2026-10-03)

Experiment only. No product-routing rule or Fusion feature was changed. The
unsaved Fusion stress scratch was left open. Reports are under ignored
`artifacts/verification/`.

## Construction and scope

- The XY centerline is branch 0 of the planar PH quintic Hermite solver.
  Hairpins start at `(0, 0)` with +X tangent and end at `(0, H)` with -X
  tangent. Except where noted, each endpoint derivative has magnitude 25 mm
  per parameter unit.
- Circular sections have 3 mm diameter. Ribbon sections are 10 mm wide and
  0.5 mm thick. Fusion uses a single degree-five control-point spline and a
  perpendicular-orientation solid sweep for each isolated case. Ribbon roll
  is the sweep's explicit `twistAngle`, not additional profile gates.
- Lateral displacement adds a polynomial Z component with control values
  `(0, 0, 1.6A, 1.6A, 0, 0)`. This has zero endpoint displacement and Z
  tangent but generally **is not a spatial PH curve**. The planar PH metrics
  therefore do not certify its 3D bend radius or envelope. Inspection of
  Fusion's world control points confirmed that the Z component is retained.
- Each case is offset from its neighbors in the scratch. `solid` means Fusion
  returned exactly one solid body; it is not an independent collision,
  physical-bend, or face-identity certificate. Failed cases retain their
  sketches for diagnosis.

## Broad matrix

`experiment_ph_spaghetti.py` and `experiment_ph_spaghetti_sweep.py` generated
69 cases: 24 untwisted hairpin/profile combinations, 18 rolled ribbons, and
27 ribbons with combined lateral displacement and roll. Fusion returned 28
single solids and 41 failures. The following are observations for this exact
profile, branch, and endpoint-derivative choice, **not universal thresholds**.

| Series | Observed solid cases | Observed failures |
| --- | --- | --- |
| Circle, no roll, H = 2–60 mm | H = 6, 8, 10, 12, 15, 20, 30, 60 | H = 2, 3, 4, 5 |
| Ribbon, no roll, H = 2–60 mm | All 12 tested H values | None |
| Ribbon, H = 5 mm | No tested 45°–360° roll | All tested 45°–360° roll |
| Ribbon, H = 10 mm | 45°, 90° roll | 135°, 180°, 270°, 360° roll |
| Ribbon, H = 20 mm | All tested 45°–360° roll | None |
| Ribbon, H = 5, 10, 20 mm, A = 5, 15, 30 mm | None | All 27 lateral/roll combinations |

The circular failures at H = 2–4 mm were reported by ASM as
`ASM_SELF_INTER`; H = 5 mm reported `ASM_SWEEP_ILLEGAL_SURFACE`. The planar
sampled minimum radius is nonmonotonic in H when the derivative magnitude is
fixed: about 1.49 mm at H = 5, 7.23 mm at H = 15, and 2.71 mm at H = 60.
Thus separation alone is not a monotonic bend-radius control. All 12
planar cases fail the experiment's illustrative 12 mm minimum-bend criterion,
even some that Fusion can model. Also, the sampled circular nonlocal-clearance
heuristic marks H = 6 mm negative while Fusion accepts it; this screen is
insufficient as a kernel-success predictor.

## Follow-up and narrowed transitions

The eight-case follow-up established that a 3D control-point spline is not
inherently unsweepable: an 80 mm straight path with A = 5 mm swept with both
profiles, and a wider H = 60 mm hairpin with 75 mm endpoint derivatives and
A = 5 mm also swept with both. The H = 60 mm, derivative-75 ribbon without
lateral displacement swept with 180° roll. In contrast, the H = 60 mm,
derivative-25 ribbon failed with A = 5 and 15 mm, while H = 20 mm,
derivative-25 succeeded with A = 1 mm.

The 33-case refinement narrowed the observed boundaries:

| Fixed setup | Highest sampled success / lowest sampled failure |
| --- | --- |
| 3 mm circle, derivative 25, zero roll/lateral | H = 5.2 mm succeeds; H = 5.0 mm fails |
| 10 × 0.5 mm ribbon, H = 5 mm, derivative 25, zero lateral | 30° roll succeeds; 40° fails |
| 10 × 0.5 mm ribbon, H = 10 mm, derivative 25, zero lateral | 90° roll succeeds; 100° fails |
| 10 × 0.5 mm ribbon, H = 20 mm, derivative 25, zero roll | A = 3 mm succeeds; A = 4 mm fails |
| 10 × 0.5 mm ribbon, H = 60 mm, derivative 75 | A = 5, 10, 15, 20, 30 mm each succeeds at 0°, 90°, and 180° roll |

The four neighboring transition pairs at H = 5 and H = 20 were each repeated
three times in isolated locations; all 18 repeated outcomes agreed with the
first observation (9 solids, 9 failures). This checks basic repeatability,
not tolerance or behavior under arbitrary profile placement.

The 100°–130° roll cases at H = 10 all failed. The wider H = 60 mm,
derivative-75 family had no observed failure up to the tested A = 30 mm and
180° roll; its actual boundary was not found. Lateral displacement and
roll interact with the path and ribbon envelope, so a single angle or
offset limit cannot be inferred from these results.

## Reproduction and artifacts

Run `python -m experiments.experiment_ph_spaghetti` locally for planar
screening. Run `experiment_ph_spaghetti_sweep.py` in Fusion via `Python.Run`
with no active command to create a new unsaved scratch. Run the inspection,
follow-up, refinement, and repeat scripts in the same scratch. All live
scripts are in `experiments/`; normal test collection does not run them.

Detailed evidence:

- `artifacts/verification/ph_spaghetti_math.json`
- `artifacts/verification/ph_spaghetti_fusion.json`
- `artifacts/verification/ph_spaghetti_followup.json`
- `artifacts/verification/ph_spaghetti_refine.json`
- `artifacts/verification/ph_spaghetti_repeat.json`

No fixed-radius, twist-per-length, or 3D-clearance production rule is yet
supported. A next experiment would compute actual 3D curvature and
nonlocal swept-envelope clearance for the spatial curves, then compare those
metrics against Fusion's repeated boundary outcomes.
