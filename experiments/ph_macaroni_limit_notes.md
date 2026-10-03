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

## Production-profile sweep check

`experiment_product_profile_sweeps.py` uses the application's
`_add_solid_section` sketch builder for one- and three-trace lobed Solid
ribbons and FFCs, plus a 1 mm diameter circular control. FFC dimensions
are 2 mm pitch, 1.5 mm trace width, 0.5 mm spacing, and 0.5 mm thickness;
lobed ribbons use 1 mm diameter and 2 mm trace pitch. The three-trace
profiles are centered on the PH path. An initial **off-center** probe was
discarded because it put the first trace, not the profile midpoint, on the
path. The corrected 30-case matrix used 5/10 mm PH reversals and 0°/90°/180°
Fusion sweep twist, in a separate unsaved design. It did not exercise the
production multi-station loft, color assignment, or saved harness routing.

| Section | 5 mm, 0°/90°/180° | 10 mm, 0°/90°/180° |
| --- | --- | --- |
| Circle, 1 mm diameter | 3 solids; all 1-wire/1-edge midpoint sections | Same |
| Lobed, one trace | 3 solids; all 1-wire/4-edge sections | Same |
| FFC, one trace | 3 solids; all 1-wire/16-edge sections | Same |
| Lobed, three traces | fail / fail / **solid with 2-wire, 17-edge section** (input 12) | 3 solids; all 1-wire/12-edge sections |
| FFC, three traces | fail / fail / **solid with 2-wire, 59-edge section** (input 40) | 3 solids; all 1-wire/40-edge sections |

In total Fusion made 26/30 solids, but only 24 had the expected single-wire
midpoint topology. Both anomalous tight 180° solids had near-nominal volume:
relative errors were -0.083% for the lobed profile and -0.427% for FFC.
Therefore **volume, face count, and solid status together still do not
certify a usable section**. The wide 10 mm FFC 180° control measured exactly
the input 40 edges, one wire, and nominal volume to numerical tolerance.

The 5 mm path's maximum curvature is 0.6723/mm. Bounding-envelope support
loads for a parameter-linear 180° bank are at most approximately 0.745 for
the three-trace lobed profile and 0.723 for FFC, below the local-fold value
of 1. Nonetheless their endpoint section widths are about 5.2 and 6 mm,
respectively, exceeding the 5 mm return-leg separation. The anomalous
sections are thus consistent with **nonlocal return-leg interference**, not
proof of a local curvature fold. At 10 mm both endpoint gaps are positive
and all three-trace midpoint sections match. The exact Fusion twist law and
whole-body nonlocal topology remain unproven; this is a controlled sweep
observation, not a general sufficiency theorem.

The section-checking approach catches false-positive solids for the
application's own shapes and helps classify the missing condition: local
bend clearance and nonlocal profile-envelope clearance must be checked
separately. It does **not** itself fix the original Solid ribbon/FFC loft
face-correspondence or coloring problems. No production generator was
changed. Detailed ignored report:
`artifacts/verification/product_profile_sweeps.json`. The corrected scratch
is left open; earlier experimental documents were not modified or closed.

## Discrete ribbon section comparison

`experiment_discrete_ribbon_sweeps.py` repeated the controlled PH reversal
with the application's actual joined, moderate-groove **Discrete** section
builder (`_add_section`). The 1 mm-diameter sections had three or five lines;
their outer widths were 3.2 and 5.2 mm. The 15 cases combined 3/5/10 mm
return-leg separations with 0°/90°/180° sweep twist, as applicable. Each
result was cut by a temporary plane at the PH midpoint and compared with its
input profile topology. This isolated sweep deliberately omitted the
production banking guide rail and folded multi-station loft; it tests the
section's behavior, not a complete generated harness.

| Lines / return separation | 0° | 90° | 180° |
| --- | --- | --- | --- |
| 3 / 3 mm | self-intersection rejection | self-intersection rejection | **solid; 2 wires, 13 edges** (input 8) |
| 3 / 5 mm | self-intersection rejection | solid; 1 wire, 8 edges | solid; 1 wire, 8 edges |
| 3 / 10 mm | solid; 1 wire, 8 edges | solid; 1 wire, 8 edges | solid; 1 wire, 8 edges |
| 5 / 5 mm | self-intersection rejection | self-intersection rejection | **solid; 2 wires, 17 edges** (input 12) |
| 5 / 10 mm | solid; 1 wire, 12 edges | solid; 1 wire, 12 edges | solid; 1 wire, 12 edges |

Fusion accepted 10/15 as single solids. Eight had the expected single-wire
midpoint topology; the two bold cases had an extra disconnected section wire
and extra edges despite near-nominal volumes (relative errors -0.275% and
-0.073%). Both had nominal return-leg overlaps of 0.2 mm. Thus the Discrete
profile is **not categorically immune** to the same false-positive-solid
failure under deliberately impossible clearance. Its narrower pitch gives
more margin than the three-line Solid/FFC profiles in the previous test,
consistent with the user's observation that ordinary Discrete ribbons have
not shown this defect. This is not evidence that the production guided sweep
or folded loft exhibits it under feasible routed conditions.

No production geometry was changed. The isolated scratch remains open;
earlier documents were not modified. Detailed ignored report:
`artifacts/verification/discrete_ribbon_sweeps.json`.

## Single fitted-spline Discrete outline and seam

`experiment_discrete_spline_seam.py` approximates the same 1 mm Discrete
ribbon lobes with **one periodic fit-point spline**, rather than the distinct
arc segments. Its first fit point is deliberately placed at the outer tip
of the first end cap, so the intended seam has a measurable location. The
test repeats the PH 180° reversal with three or five lines, 0°/90°/180°
sweep twist, and 3/5/10 mm return separations. It reads the actual start
and end cap seam vertices from the resulting BRep, checks for one edge
joining them, and compares the end vertex to the banked end-tip position.

Eight of 11 sweeps made solids. **Every successful body had exactly three
faces: two caps and one continuous side face.** Each had one side seam edge
joining the two cap seam vertices. The start seam coincided with the first
fit point, and the end seam landed at its corresponding transported cap tip
within 0.000001 mm (the measured differences were numerical roundoff).
Their temporary midpoint sections each had one wire and one edge. The three
failures were Fusion `ASM_SELF_INTER` rejections: three-line/5 mm/0° and
the deliberately overlapping three-line/3 mm/180° and five-line/5 mm/180°
cases. Unlike the segmented Discrete outline, the latter two did **not**
yield false-positive solids in this controlled fit-spline test.

Thus a single periodic section curve preserved the designated seam from
start to finish in the tested sweeps, including 90° and 180° bank. It also
collapsed the side into one face, which by itself cannot carry separate
per-line **face** appearances; the texture-mapping milestone below offers a
different route to visual per-line colors. This does not yet establish seam
stability for the application's multi-section loft, production guide rail,
arbitrary routes, or edits/regeneration. The spline only approximates the
arc contour, so any future use would need a profile-fidelity and coloring
strategy.

No production geometry was changed. The isolated unsaved scratch is left
open, and earlier documents were not modified or closed. Detailed ignored
report: `artifacts/verification/discrete_spline_seam.json`.

## Milestone: longitudinal stripes survive the one-face sweep

In the user-supplied Fusion image of the fitted-profile U-turn, a rainbow
texture remains organized as lengthwise bands across the single swept side
face. The bands visibly follow the bend and 180° reversal without an obvious
perimeter-order swap. Together with the measured one-face BRep and its
start-to-end seam edge above, this establishes a **promising visual route to
per-trace color on one face**, without requiring one BRep face per trace.

This is an observed rendered result, not a numerical UV-coordinate audit.
It does not show that stripe widths remain exact everywhere, that the texture
origin/scale survives edits or regeneration, or that a multi-section **loft**
maps the material the same way as this **sweep**. Localized visual compression
and rippling are visible near the tight bend, so quantitative registration
and minimum-clearance checks remain necessary before this becomes a product
rule. No production material or geometry behavior was changed.

## Single fitted-spline FFC outline and seam

`experiment_ffc_spline_seam.py` repeats the Discrete one-face test with a
2 mm-pitch FFC section (1.5 mm nominal trace width, 0.5 mm spacing,
0.5 mm thickness). One closed fit-point spline approximates the flat trace
lands and shallow spacing grooves; its first point lies at the first outer
edge's mid-thickness and designates the seam. This is an **approximation** of
the production FFC section, not exact straight lands or V notches.

The isolated PH 180°-reversal sweep used one, three, and five traces with
0°/90°/180° twist and deliberately varied return-leg spacing:

| Traces / return separation | 0° | 90° | 180° |
| --- | --- | --- | --- |
| 1 / 5 mm | clean | clean | clean |
| 3 / 5 mm | rejected | rejected | rejected |
| 3 / 10 mm | clean | clean | clean |
| 5 / 10 mm | rejected | **2 midpoint wires** | rejected |
| 5 / 20 mm | clean | clean | clean |

Ten of 15 cases made solids. Every successful body had exactly **one side
face, two cap faces, and one longitudinal seam edge**. The start seam
coincided with the designated fit point, and the end seam landed at its
expected transported location to numerical precision (largest recorded
error below 0.000001 mm). Nine successful cases had one midpoint-section
wire and one edge, matching the fitted input profile. The five-trace,
10 mm-separation, 90°-twist case made a single three-face solid but its
midpoint section had **two wires and four edges**. It is therefore not a
confirmed single-pass section merely because Fusion reported one solid. A
plane can also intersect two nonadjacent stretches of a valid folded sweep;
the wire count alone does not establish a fold. All five rejected
cases reported `ASM_SELF_INTER`.

The measured fitted profile areas were approximately 1.013, 2.990, and
4.968 mm² for one, three, and five traces, versus nominal flat envelopes of
1, 3, and 5 mm². The small mismatch reinforces that a fitted spline does
not exactly enforce trace width, thickness, or notch dimensions. The
one-face/seam behavior is encouraging for a texture-based FFC display,
but **UV registration itself was not measured here**. This neither validates
the application's multi-section loft nor provides a general clearance
guarantee. No production geometry or appearance code changed. The unsaved
FFC test design remains open. Detailed ignored report:
`artifacts/verification/ffc_spline_seam.json`.

## Section-valid textured FFC rebuilds

`experiment_ffc_texture_rebuild.py` read the user's textured FFC scratch
without editing it, copied its `Rainbow` appearance into a new unsaved test
design, and rebuilt the fitted one-face FFC sweep twice for each of two
previously section-valid, generous-gap cases: three traces with 10 mm return separation,
and five traces with 20 mm separation, both with 180° twist. All four bodies
had one side face, one midpoint-section wire/edge, and the expected seam end
location. This is not a whole-body clearance certificate. The source
document's modified flag was unchanged.

For each pair, Fusion's side-face display meshes had the same node count
(173 for three traces, 318 for five). After removing the intentional
8 cm placement difference, corresponding mesh positions differed by at
most 0.000001 cm, and the reported mesh **texture coordinates matched
exactly to seven decimal places at every node**. This is a deterministic
fresh-build result for these particular shapes, not an edit/regeneration
test of an existing feature. The visual rainbow bands also appeared on all
four new bodies, but their default body-level projection does **not** yet
establish one correctly registered color per trace. Copying an appearance
does not by itself prove that the user's original visual mapping settings
or lane boundaries are reproduced; the map-control transform and stripe
registration still need an explicit policy and test.

The scratch was left open, and no production code changed. Detailed ignored
report: `artifacts/verification/ffc_texture_rebuild.json`.

`experiment_ffc_texture_edit.py` then used a **parametric** scratch for the
five-trace, 20 mm, 180° case. After assigning the copied texture, it edited
the existing sweep feature to 170° and restored 180°. The restored body
remained a three-face solid with one midpoint-section wire and one side
face, retained its appearance, and placed the seam at the same end point.
Its 318 local display-mesh positions and all reported UVs matched the
pre-edit values exactly at seven decimal places. This directly tests a
feature recompute, but only for this one controlled sweep and round-trip
twist edit. It does not certify material-to-trace registration, changes to
the path/profile, or application-level route regeneration. The source
document remained untouched and the parametric scratch was left open.
Detailed ignored report: `artifacts/verification/ffc_texture_edit.json`.

## Live contact-to-contact FFC: one-face sweep gate

`experiment_live_ffc_one_face_sweep.py` read the saved `Wire creation tester
v110` FFC through the product's planner (19 traces, 40 stations, 2.5067 mm
pitch, 1.5 mm thickness). All attempts were built in separate unsaved
scratch designs; the saved source's modified flag remained false. A free
one-face sweep on the full 40-station fitted spine failed `ASM_SELF_INTER`
for every centered trace count tested (1, 3, 5, 9, 13, 17, 19). Even circular
sections of 0.05, 0.25, and 0.75 mm radius failed on that spine. The full
19-trace banking-rail sweep failed `ASM_SWEEP_ILLEGAL_SURFACE`.

Read-only inspection of the plan found a concrete local reversal near the
ending contact: center Z went 2.784 → 4.104 → 0.790 mm across stations
35–37. The experiment omitted only intermediate ending-lead stations 36–38
from the *scratch* spine while retaining the first and final contact
stations. On that 37-station spine a 0.05 mm circular sweep and the
one-trace FFC sweep made three-face solids with one wire and one edge in
each of three interior section cuts. The circular control establishes that
the original full-spine failure was not simply ribbon width.

With the width-edge banking rail on the trimmed spine, centered 1, 3, 5,
9, and 13 trace sections each made one three-face solid and one loop/edge
at all three sampled sections. At 17 traces Fusion rejected the sweep with
`ASM_SWEEP_ILLEGAL_SURFACE`. At 19 traces it made one three-face solid, but
the middle section contained **two wires and three edges**; this is not a
proof of a local fold or unusable visual result because the plane may cut
two distinct stretches of the swept ribbon. Free (unrailed) sweeps
passed the sampled section check for only one and three traces; five and
more failed `ASM_SELF_INTER`. The closest end seam vertex on the banked
accepted cases was 0.014–0.173 mm from the planned tip, increasing with
width, so contact-relative registration is still not exact. These are
three-cut topology screens, not full-length clearance certificates.

The backtracking end lead is a deterministic spine-construction defect to
resolve before a production sweep. The 17-trace rejection and ambiguous
19-trace section still call for route/bank/envelope validation; simply
substituting a one-face profile for the production loft on the original
40-station spine would not fix this live route.
No production geometry or material code was changed. Detailed ignored
report: `artifacts/verification/live_ffc_one_face_sweep.json`.

`experiment_ffc_procedural_stripes.py` then generated a 1216 × 16 PNG with
19 distinct color bands and dark gaps from the measured 1.5147 mm trace width
and 0.9920 mm spacing. It copied a generic opaque appearance in the active
unsaved 19-trace scratch, connected the PNG as its color texture, set the
texture width to the 47.6267 mm ribbon width, and assigned it only to the
single lengthwise face. Fusion reported the connected texture and assigned
appearance, and the viewport showed crisp stripes running parallel through
the sweep; the end caps retained their prior appearance. This confirms the
procedural-texture route is viable for a visual test. It does not establish
contact-to-color registration, top-only coloring, or a production-safe
appearance API. The convenient `Appearance.colorTexture` setter is a Fusion
preview API, so the script remains experiment-only. The scratch stays open;
the saved source and production add-in were not changed.

`experiment_ffc_interface_contacts.py` resolved both saved Interface banks
through the planned, persistent contact and attachment IDs, then copied all
38 source contact faces into separate, pin-numbered components in that same
unsaved scratch. The largest centroid difference after copying was below
`2e-14` mm; the source design remained unmodified. Pin 1 is magenta, pin 19
cyan, and the other pins gold. Most exact sheets lie behind the opaque sweep
from the current camera angle, so `experiment_ffc_contact_standoffs.py` also
placed visibly labeled *display copies* 4 mm straight outside each end
(`-Y` at START, `-Z` at END), with no lateral displacement. All 38 display
offsets matched within `2e-15` mm. The exact copies remain in the scratch,
and the offset components can be hidden independently. This exposes the
contact ordering for visual alignment checks; it does **not** yet prove the
texture's color bands land on their intended pin centers. Ignored reports:
`artifacts/verification/ffc_interface_contacts.json` and
`artifacts/verification/ffc_contact_standoffs.json`.

`experiment_ffc_texture_calibration.py` adjusted only the unsaved scratch's
material mapping. The initial 47.6267 mm texture repeat spanned roughly 17
contact pitches instead of 19. With `texture_RealWorldScaleX = 4.035` cm and
`texture_RealWorldOffsetX = -0.10` cm, 19 color-band centers at the visible
contact bank differed from the 19 display-contact centers by 0–2 viewport
pixels (about 0.11 mm at that zoom), with no cumulative pitch drift. The
opposite bank was viewed normal to its contact plane: the color order remains
continuous through the twist and the bands visually meet that row, but this
view has not been quantitatively registered to the individual contacts. The
camera was restored afterward and the scratch left open. These material
coordinates are specific to this scratch's UV mapping, not a general formula
for all FFC widths or paths. Ignored evidence:
`artifacts/verification/ffc_texture_calibration.json`,
`ffc_calibrated_offset_neg010.png`, and `ffc_opposite_end.png` in that folder.

## Perimeter-aware FFC texture experiment

The 19-band image above repeats one ordered palette over the entire closed
side face, although its sweep UV traverses both broad sides and both rounded
edges in a single loop. The new `experiment_ffc_perimeter_stripes.py` encodes
19 colors across the first broad side and the same 19 in reverse order across
the return side. This is one image and one appearance on the existing
three-face solid; no extra bodies or grooves are introduced.

The first mirrored trial used a doubled `texture_RealWorldScaleX` of 8.07 cm
and retained the prior `texture_RealWorldOffsetX` of -0.10 cm. In matched
orthographic screenshots, the first side showed 19 complete bands, but the
return side showed 19 complete bands **plus partial bands at both edges**.
The return-side pitch remained consistent with the contact pitch; its phase
was displaced by about 19–22 viewport pixels against a 54-pixel pitch.
Shifting only that half of the generated image by +0.35 pitch cells removed
both extra bands, but **clipped the outermost return lane** at the image
boundary. Counting 19 bands alone was therefore an insufficient acceptance
test. The revised image reserves 0.35 pitch cells at one rounded edge and
0.65 at the other, with 19 complete lane cells on each broad side: its total
repeat width is `2*N + edge_right + edge_left = 39` cells, not 38. Keeping
the original per-cell image scale gave a real-world repeat of 8.28237 cm;
the measured global offset is +0.118 cm. These values are empirical for this
scratch, not assumptions about a documented Fusion UV formula.

In the final matched start-contact views there are exactly 19 full-width
colored runs and 19 contact marks on **each** side. The first and last bands
are 35–37 viewport pixels wide, comparable with the interior bands, and
the rounded-edge intervals remain dark. Stripe-center minus contact-center
errors are -3.5 to +1 pixels on one side and -2 to +3 pixels on the other,
about 0.16 mm maximum at the 2.5067 mm / 54-pixel contact pitch. The stripe
palette is mirrored in UV so the same physical lane receives the same color
when viewed from opposite sides. The opposite end retains the same mesh U
interval, but its contact plane is skewed against the sweep end and overlapping
route portions occlude a clean pixel-level contact test; this experiment does
not certify that interface geometry.

Candidate generation rule: obtain the sweep's transverse UV direction and
its seam; partition the closed perimeter into first broad side, neutral
outer-edge interval, reverse broad side, and neutral other-edge interval;
write the same lane palette in forward and reverse order; size each interval
from its transverse UV extent; then fit one material pitch and global phase
to known contact centers. Reject a mapping unless both sides have exactly
the expected number of full-width bands, dark edge zones, correct color order,
and acceptable center error. The numeric 8.28237 cm repeat, +0.118 cm offset,
and 0.35/0.65 pitch edge intervals are **specific to this scratch**, not
constants to carry into the add-in. Other widths (including one trace),
profile shapes, seam locations, route regeneration, and Fusion version changes
still require experimental validation before this becomes a production rule.
Ignored captures: `artifacts/verification/ffc_edgezone_top_final.png` and
`ffc_edgezone_bottom_final.png`.

## FFC count, width, and thickness matrix

`experiment_ffc_texture_matrix.py` built 11 independent straight, one-face
fitted-spline sweeps in a new unsaved Fusion test design. Cases covered 1, 3,
7, 9, and 19 traces; pitches 1.2–3.5 mm; trace widths 0.7–2.2 mm; and
thicknesses 0.2–3.0 mm. Every case produced one solid, three-face body,
including both single-trace cases. The existing saved source design was not
modified; the unsaved matrix remains open. These are straight-sweep texture
tests, **not** a validation of routed contact-to-contact placement.

The first pass extrapolated the 19-trace scratch's image width, neutral-edge
cells, texture scale, and offset using physical pitch and thickness ratios.
That hypothesis failed: the 19-trace 0.2 mm case showed only 6 colored bands
on each side, and the 3.0 mm case showed 28, rather than 19. Thin single-
and three-trace cases also lost bands on one side. The unchanged 1.5 mm
19-trace control showed 19 bands on both sides but still had center offsets
of up to 1.34 mm. Do not reuse the previous numeric scale and offset as a
general material-mapping formula.

`experiment_ffc_texture_matrix_uv.py` measured each side face's rendered
mesh UV span. With the same nominal 47.6267 mm width, the 19-trace U span
was 6.129 at 0.2 mm, 20.779 at 1.5 mm, and 31.683 at 3.0 mm thickness.
The initial band's count varied in the same direction and approximate ratio.
`experiment_ffc_texture_matrix_uv_fit.py` therefore tested the narrower
hypothesis `scale = 8.282368421 cm * (measured_U_span / 20.779499)` and
scaled the empirical offset by the same ratio. In matched top/bottom captures,
**all 11 cases then had exactly the requested number of distinct color
bands on each side**, including one-trace ribbons. This establishes a useful
UV-normalized repeat rule for these test sweeps, not a universal formula for
arbitrary Fusion UV layouts.

The corrected band count does not certify registration. At the start-contact
view, the worst stripe-center error among these cases was 1.34 mm; the
single-trace thin case was within 0.05 mm, but the thick single-trace case
missed by up to 0.83 mm. Seven-trace cases stayed within 0.31 mm on both
sides; 19-trace cases ranged up to 1.34 mm. The residual appears to include
phase and edge-allocation error; it must be fitted against the actual contact
centers and checked on **both** broad sides, with neutral outer edges and
correct mirrored lane colors. Per-trace widths also need validation against
the requested width, not just band count: across the 11 cases, the mean
measured colored-width ratio ranged from about 0.63 to 1.11. Use measured
UV positions of contact centers and trace edges to construct or calibrate
image intervals rather than assuming a linear millimeter-to-UV relation.

Ignored evidence: `artifacts/verification/ffc_texture_matrix/matrix.json`,
`uv_ranges.json`, `uv_fit.json`, `matrix_analysis.json`,
`matrix_analysis_uv_fit.json`, and the matching top/bottom PNG captures.
