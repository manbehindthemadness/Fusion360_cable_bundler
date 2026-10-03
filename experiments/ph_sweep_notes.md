# PH centerline and Fusion sweep experiment — 2026-10-03

These are experiments, not a routing policy or a product-code change. Run
`experiment_ph_quintic.py` with the project Python environment, then run
`experiment_ph_fusion_sweep.py` with Fusion `Python.Run` while no command is
active. The latter leaves a new unsaved scratch design open. Detailed ignored
reports are `artifacts/verification/ph_quintic_math.json` and
`artifacts/verification/ph_fusion_sweep.json`.

## Construction and controls

The local script implements planar quintic PH C1 Hermite interpolation via a
quadratic complex preimage, enumerates its four branches, and integrates speed
exactly. It measures curvature and nonlocal separation at 513 samples, using
12 mm as the example minimum bend radius, a 1.5 mm circular-wire radius, and
0.5 mm clearance. Nonlocal distance excludes pairs less than one quarter of
the route length apart *along the route*. These sampled values are screening
heuristics, not certified extrema or exact swept-envelope intersection tests.
One branch is chosen by legality, then total absolute turn, sampled bending
energy, and length. A cubic Bézier with the same endpoint derivatives is a
local comparator; clothoid, biarc, and spatial PH were not implemented here.

| Case | PH branch-0 length (mm) | Sampled minimum radius (mm) | Sampled legal | Fusion circular sweep |
| --- | ---: | ---: | :---: | :---: |
| Straight | 80.000 | infinite | yes | solid |
| 90° turn | 92.663 | 39.970 | yes | solid |
| 135° turn | 106.936 | 22.582 | yes | solid |
| 180° hairpin | 85.000 | 17.523 | yes | solid |
| Tight 180° hairpin | 13.333 | 1.487 | no | failed: `ASM_SWEEP_ILLEGAL_SURFACE` |
| S-turn | 83.007 | 63.562 | yes | solid |
| Offset reversal | 56.924 | 9.469 | no | solid |

All successful circular sweeps produced one three-face solid. Fusion's success
on the offset reversal demonstrates that a CAD-valid sweep can still violate
the *chosen* 12 mm engineering bend limit. The tight 180° case fails both the
sampled 12 mm limit and the circular-profile local offset test; its sampled
nonlocal clearance margin is -0.669 mm. The wide hairpin's margin is +17.017
mm. The straight and 180° circular solid volumes match `πr² × exact PH length`
to the reported precision, corroborating unit conversion and the degree-five
control-point path representation.

The 10 × 0.5 mm rectangular profile swept on the wide and tight hairpins as
one six-face solid in both cases, with volumes 0.425000 and 0.066667 cm³.
The tight ribbon's success despite the tight circular-wire failure illustrates
why local sweep screening must use the profile's extent *toward the center of
curvature*, not a generic half-width or equivalent circular radius. Both tight
paths still fail the example 12 mm bend policy. These rectangular sweeps did
not test lane colors, contact geometry, ribbon roll, or global self-contact.

Construction of four PH branches took about 0.01–0.02 ms per case locally;
the 513-sample, quadratic-pairwise-distance analysis took about 12–14 ms per
branch. The latter cost is dominated by the illustrative nonlocal-distance
scan and should not be interpreted as optimized solver performance. Exact PH
arc length agreed with Simpson integration to about 1e-12 relative error or
better in the selected cases. Hermite endpoint interpolation and speed identity
are mathematical properties of the construction, but the curvature and
clearance *bounds* here are only sampled.

## Critical Fusion path finding

`SketchControlPointSplines.add` takes a Python list of `Point3D`/`SketchPoint`
objects, not `ObjectCollection`. More importantly, passing the spline to
`features.createPath(spline)` with the default chaining made even the straight
case fail with `ASM_SWEEP_PATH_SEGMENTS_ANTIPARALLEL`. The observed behavior is
consistent with Fusion chaining connected control-polygon geometry, but this
was not separately inspected at the path-entity level.
`features.createPath(spline, False)` isolated the spline and produced the
results above. The failed trial and corrected designs were separate unsaved
scratch documents; the corrected result remains open.

## Hypotheses retained or rejected

- PH quintics provide exact polynomial arc length, four C1 Hermite branch
  choices, and a CAD-compatible degree-five Bézier path for these planar cases.
- Endpoint positions and tangents alone do **not** imply zero endpoint
  curvature or G2 continuity when segments are chained. The wide 180° case
  has about 0.0571/mm curvature at both endpoints. A global G2 construction
  would need further constraints/solving.
- A PH path does **not** guarantee a successful sweep. Profile extent,
  curvature, nonlocal proximity, and Fusion path semantics remain independent
  concerns. A successful Fusion sweep also does not prove design-rule legality.
- Planar PH rational offsets are mathematically useful, but no exact offset
  envelope or collision proof was implemented. Spatial PH/ribbon framing and
  a fair clothoid comparison remain untested.

Next controlled comparisons should hold the same endpoint states and profile
sizes while varying derivative magnitudes, evaluating *certified* curvature
extrema, applying profile-aware envelope checks, and testing G2 joins and 3D
roll. A clothoid comparator would need the same bounds and validation before
any ranking is meaningful. Do not infer a production routing choice from this
first planar benchmark.

Mathematical construction: [Farouki's PH interpolation lecture](https://faculty.engineering.ucdavis.edu/farouki/wp-content/uploads/sites/41/2013/02/Interpolation-with-PH-curves.pdf).
Fusion API contract: [control-point spline creation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_SketchControlPointSplines_add.htm).
