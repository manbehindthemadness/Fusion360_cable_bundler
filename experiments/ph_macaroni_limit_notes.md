# PH ribbon sweep: inward-reach experiment

This is an experiment, not a production routing rule. The proposed local
"macaroni" screen is the maximum along a planar PH centerline of

`M = |curvature| × inward profile reach`.

For the 0.5 mm-thick rectangular profile initially spanning the Z direction,
the reach under roll `θ` is
`(width / 2) |sin θ| + 0.25 |cos θ|` mm. For a 3 mm circular
profile it is 1.5 mm. A regular normal-offset construction would require
`M < 1`; this is a *geometric local-fold screen*, not a published Fusion sweep
acceptance criterion. Fusion's internal distribution of `twistAngle` is not
known, so the calculation tests both roll linear in PH curve parameter and
roll linear in traveled arc length. Curvature is sampled at 8193 positions.

## Evidence

`experiment_ph_macaroni_limit.py` evaluated the 56 zero-lateral-displacement
cases from the existing broad and refinement Fusion reports. Both roll models
matched the recorded single-solid/failed outcome in 54 of 56 cases. The two
exceptions are informative:

| Case | Fusion | Parameter M | Arc-length M | Screen |
| --- | --- | ---: | ---: | --- |
| 5 mm reversal, 10 mm ribbon, 30° roll | single solid | 1.067 | 1.044 | fold predicted |
| 10 mm reversal, 10 mm ribbon, 360° roll | failed | 0.974 | 0.917 | no local fold predicted |

Before running new Fusion sweeps, the same script wrote a 12-case holdout plan
with fixed geometry and predictions. `experiment_ph_macaroni_holdout.py` then
ran those cases in the open unsaved Fusion scratch, adding separate sketches
and sweeps without clearing earlier geometry. Results:

| Reversal separation | Width | Roll | Arc-length M | Predicted | Fusion |
| ---: | ---: | ---: | ---: | --- | --- |
| 5 mm | 10 mm | 25° | 0.901 | solid | solid |
| 5 mm | 10 mm | 27.5° | 0.973 | solid | solid |
| 5 mm | 10 mm | 32.5° | 1.115 | fail | solid |
| 5 mm | 10 mm | 35° | 1.185 | fail | fail |
| 5 mm | 10 mm | 37.5° | 1.254 | fail | fail |
| 10 mm | 10 mm | 92° | 0.966 | solid | solid |
| 10 mm | 10 mm | 95° | 0.985 | solid | solid |
| 10 mm | 10 mm | 97° | 0.997 | solid | solid |
| 5 mm | 8 mm | 35° | 0.979 | solid | solid |
| 5 mm | 8 mm | 40° | 1.090 | fail | solid |
| 5 mm | 12 mm | 25° | 1.049 | fail | solid |
| 5 mm | 12 mm | 30° | 1.221 | fail | fail |

The arc-length model matched 9/12 holdouts; parameter-linear roll matched
7/12. Neither reproduces a hard Fusion acceptance boundary. The three
arc-length mismatches were all conservative: Fusion produced one solid where
the screen predicted a local fold. The 10 mm reversal at 360° remains a
failure that the local screen cannot explain. Fusion reported
`ASM_SELF_INTER` or `ASM_SWEEP_FACES_INTERSECT` for the three failed holdouts.

## Interpretation and limits

The underlying dependency is strongly supported: at the same 5 mm reversal,
the 12 mm ribbon failed by 30° roll, the 10 mm ribbon failed by 35°, while
the 8 mm ribbon still made a body at 40°. Greater inward reach at a tight bend
is therefore a useful *risk predictor*. It is not a sufficient or necessary
test for Fusion success at `M = 1`. Fusion may use a different twist law,
deform or trim the swept surface, or reject for a different local/nonlocal
intersection. These data do not distinguish those mechanisms. A single solid
also does not establish a manufacturable bend, adequate clearance, or correct
trace surfaces. This test covers only the planar branch-zero PH reversal,
normal rectangular/circular profiles, and Fusion's perpendicular sweep mode;
it does not validate lateral 3D bends.

Ignored detailed reports:

- `artifacts/verification/ph_macaroni_limit.json`
- `artifacts/verification/ph_macaroni_holdout_plan.json`
- `artifacts/verification/ph_macaroni_holdout_fusion.json`

The Fusion scratch is intentionally left open and unsaved. No production
routing or sweep behavior was changed.

## Circular-profile pivot control

`experiment_ph_circular_pivot_controls.py` selected the three failed 5 mm
holdouts, three nearby 5 mm ribbon solids (including the reach-screen
exceptions), and the failed 10 mm/360° case. For each identical branch-zero
PH path it ran a circular sweep at radii 0.25, 1.0, and 1.5 mm, both without
twist and with the ribbon's original `twistAngle`: 42 new controls total.

| Path | Circular radius | Maximum `curvature × radius` | Zero twist | Original twist |
| --- | ---: | ---: | --- | --- |
| 5 mm reversal (all six ribbon cases) | 0.25 mm | 0.168 | 6/6 solids | 6/6 solids |
| 5 mm reversal (all six ribbon cases) | 1.0 mm | 0.672 | 6/6 solids | 6/6 solids |
| 5 mm reversal (all six ribbon cases) | 1.5 mm | 1.008 | 0/6 solids | 0/6 solids |
| 10 mm reversal, 360° ribbon failure | 0.25–1.5 mm | 0.061–0.364 | 3/3 solids | 3/3 solids |

Thus the circular controls made 30 solids and failed 12 times. Every
zero-twist/twisted pair had the same outcome. For the successful pairs, the
largest relative body-volume difference was `3.1e-13`. At 1.5 mm radius the
5 mm path failed with `ASM_SWEEP_ILLEGAL_SURFACE` regardless of twist, matching
its sampled local curvature limit. The original rectangular sweep can still
make one body on that path at 32.5° roll, and fail at 35°, so a circle's
single radius cannot reproduce the rectangular outcome. The 10 mm/360°
rectangle failed with `ASM_SELF_INTER` while every circular control made a
body; centerline curvature and the mere presence of a 360° twist request
do not explain that failure.

This supports a profile-shape/banking interaction, not a demonstrated
mislocated banking pivot. A circular cross-section is rotationally symmetric,
so these controls cannot identify where Fusion places the pivot on a
rectangle. A circular fallback would remove this specific shape sensitivity,
but is not a substitute for the ribbon's width or trace surfaces. The
single-body caveat above still applies. The detailed ignored report is
`artifacts/verification/ph_circular_pivot_controls.json`; the unsaved Fusion
scratch remains open.

## User-built limiting bend: Macaroni v1

Read-only inspection of the saved Fusion document `Macaroni v1` found three
sketches, one sweep, and one valid solid body (five faces, five edges). The
document remained unmodified. Sketch1/Sketch2 contain earlier paths and
measurement shapes. Sketch3 occupies X = 70–85 mm and spatially matches the
body (X = 62.432–92.463 mm): its sweep path consists of two nearly vertical,
tangent straight legs and a 7.5 mm-radius, approximately 180° circular arc.
The sketched swept circle has radius 7.462765 mm, or diameter 14.925531 mm.
The 7.5 mm-radius measurement circle corresponds to the nominal 15 mm size.

The circular arc's local inward reach is therefore `r/R = 0.995035`, just
below the regular-offset threshold of 1. The nominal radial clearance at the
arc pivot is `R - r = 0.037235 mm`; the nominal gap between the two parallel
15 mm-separated legs is `15 - 2r = 0.074469 mm`. These are very small but not
mathematically zero. That slight positive margin is consistent with Fusion
accepting the solid at an almost maximally tight 180° reversal. The body
bounding box and five-face topology are consistent with this three-segment
circular sweep; Fusion's feature-level path/profile property getters raised
`InternalValidationError`, so the exact feature references were inferred
from sketch/body location rather than read directly.

This example strengthens the geometric interpretation of the *local* limit:
for a banked or twisted noncircular profile, measure its farthest occupied
point toward the instantaneous inside normal at each station, then compare
that reach with the centerline's local radius of curvature. The limiting
point moves around the profile as it banks. Equality is a singular boundary,
so a production rule needs positive numerical and manufacturing margin.
This local condition still does not address distant-leg collisions, trace
surface correspondence, or Fusion's noncircular sweep behavior observed
above. Ignored detail: `artifacts/verification/macaroni_document_inspect.json`.

## Banked-profile angular-extreme experiment

`experiment_banked_profile_extremes.py` preregistered 36 fixed-bank cases
before the fixed-bank Fusion run, then 18 variable-twist cases before the
twist Fusion run. Two identical branch-zero PH
180-degree reversals had 5 and 10 mm endpoint separation. Cross-sections
were a 2 mm-radius circle, an 8 × 0.5 mm rectangle, and an asymmetric 8 × 1
mm triangle. Fusion created isolated new-body perpendicular sweeps in a new
unsaved scratch, leaving the saved `Macaroni v1` document untouched and open.

For a profile point `(normal, vertical)` and bank angle `θ`, its signed bend-
normal coordinate is `normal cos θ - vertical sin θ`. The inward and outward
reaches are respectively the maximum and negative minimum of this quantity
over the profile. A convex polygon attains both extrema at vertices; a circle
has equal angle-invariant reaches. This is a *signed support* calculation,
not a bounding-circle radius or a half-width approximation.

At 0°/90° bank the rectangular normal reaches are 0.25/4.0 mm. At 30° the
triangle reaches 1.783 mm inward and 2.217 mm outward, showing that an
asymmetric section cannot use a single half-extent. A 180° bank reversal
exchanges its two reaches. The local geometric fold load is the maximum of
signed curvature times the corresponding inward reach at every sampled
station; below 1 is the regular-offset condition, not a Fusion guarantee.

The fixed-bank Fusion comparison produced 20/36 solids, and the `load < 1`
screen matched all 36 observed solid/failed outcomes. All 18 wide (10 mm)
cases succeeded, including 90°-banked rectangle/triangle cases with sampled
load 0.971. On the tight (5 mm) path, all six circle cases failed at load
1.345; the rectangle and triangle succeeded only at 0° bank (loads 0.168
and 0.504), and their 30°–150° cases failed. This supports the moving
angular-extreme interpretation while keeping path geometry fixed.

The twist comparison produced 11/18 solids. Both assumed twist laws matched
16/18 solid/failed outcomes; the two mismatches were the tight triangular
90° and 180° cases. The circular controls again
ignored twist: all three 5 mm cases failed and all three 10 mm cases
succeeded. On the 5 mm path, rectangular 90°/180°/360° twists failed, but
triangular 90° and 180° twists each produced one five-face solid despite
both parameter-linear and arc-length-linear support calculations predicting
local load above 1. Triangle 360° failed. All nine 10 mm twist cases
succeeded. Therefore, the support formula correctly identifies *geometric
extremes of an assumed rigid moving frame*, but Fusion's successful solid
is **not proof** that it transported that exact frame or retained all
intended profile material without trimming/deformation. Fusion's actual
twist distribution and section behavior need direct body-surface inspection
before converting this geometric screen into a hard acceptance rule.

The estimated return-leg gap in the reports uses endpoint section reaches;
it is not a complete nonlocal collision test. In particular, a positive
endpoint gap did not save the 5 mm circular sweep: its tighter mid-bend
curvature caused self-intersection. The angular-extreme method must be
evaluated at each path station and against the relevant exterior boundary,
not solely at the two ends.

Ignored reports: `artifacts/verification/banked_profile_extremes_math.json`,
`artifacts/verification/banked_profile_extremes_fusion.json`, and
`artifacts/verification/banked_profile_twist_fusion.json`. The experiment
scripts are repeatable; production sweep behavior is unchanged.

## Milestone: a solid can conceal a folded triangular sweep

`experiment_banked_triangle_section_audit.py` made **temporary, read-only**
plane intersections of the existing 31-body scratch at each path midpoint.
The PH centerline crosses that midpoint plane only once (the centerline's Y
coordinate is monotone), so the extra section edges below are not caused by
multiple centerline visits. The saved `Macaroni v1` document was not touched.

| Sweep | Midpoint section edges | Expected profile edges | Body | Measured volume |
| --- | ---: | ---: | --- | ---: |
| 5 mm reversal, triangle, 90° twist | 12 | 3 | one five-face solid | 52.811 mm³ |
| 5 mm reversal, triangle, 180° twist | 11 | 3 | one five-face solid | 54.021 mm³ |
| 10 mm reversal, triangle, 180° twist | 3 | 3 | one five-face solid | 73.333 mm³ |
| 10 mm reversal, rectangle, 180° twist | 4 | 4 | one six-face solid | 73.333 mm³ |

The sections of the two tight triangular solids are **not transported
triangles**. Their single section wire contains extra turns/vertices and has
a much larger vertical range than its nominal 1 mm section. At 90° twist its
X range even reaches 0 mm, whereas the assumed rigid midpoint section starts
at about 2.913 mm. At 180° twist its section starts at 2.669 mm rather than
the assumed 1.565 mm. These are direct body-geometry observations; they do
not determine exactly how ASM parameterized, intersected, or trimmed the
sweep. The 10 mm controls match their intended profile edge counts and
midpoint extents to numerical tolerance. The triangle's nominal area is 4
mm², so area times exact PH path length predicts 53.333 mm³ on the 5 mm path
and 73.333 mm³ on the 10 mm path; the anomalous tight volumes differ from
the former, while both wide controls match the latter. This reinforces the
section evidence without treating volume alone as a shape validator.

The application does not use triangular cable sections, so this particular
counterexample does not directly invalidate its circle, ribbon, or FFC
geometry. It **does** establish an acceptance-rule boundary: `body.isSolid`
and face count are insufficient to validate cross-section fidelity, even
when a support-based local-fold screen predicts trouble. Circle and wide
rectangle controls behaved as expected, but neither proves all nontriangular
sections safe. The application's FFC has shallow V notches and its solid
ribbon has lobed arcs, so sharp or changing section features still warrant
targeted section checks when an actual cable sweep is investigated. No
production rule or generator was changed. Ignored detailed report:
`artifacts/verification/banked_triangle_section_audit.json`.
