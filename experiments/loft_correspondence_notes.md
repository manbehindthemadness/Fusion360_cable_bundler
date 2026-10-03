# Rectangular loft correspondence probes

These are observations from the local Fusion session on 2026-10-02, not a
documented Fusion solver limit or a production subdivision policy. The live
scripts create unsaved scratch designs; their JSON reports are written under
ignored `artifacts/verification/`. No product geometry code was changed.

The experiments use right-angled rectangular sketch profiles with a consistent
corner construction order. A "clean" result means one solid body with six faces
and four lateral faces whose start and end corners match the same logical
section edges. This is stricter than simply obtaining a visible solid, but it
does not prove anything about interior self-intersections or physical ribbon
shape.

- Earlier straight-center tilted-profile tests in
  `experiment_sub45_multiaxis_loft.py` swapped opposite lateral faces after
  sufficient cumulative X/Y tilt, including a 30.1-degree neighboring step
  in a forward progression. Therefore a per-step angle by itself is not a
  reliable global guarantee.
- `experiment_tangent_spaghetti_loft.py` placed each section normal on the
  local route tangent. Planar 180-degree U-turns and 360-degree helices,
  using 1:2 and 1:5 sections and 20–60-degree path steps, were clean in all
  18 baseline cases. No guide rail was used.
- Adding 180 degrees of roll about the tangent was clean on both paths and
  both aspect ratios at 30-degree path steps. A 360-degree roll on the planar
  U-turn at those same steps produced eight faces in both aspect ratios;
  adjacent complete frames differed by about 66.5 degrees. At 20-, 15-, and
  10-degree path steps the U-turn returned to six clean faces; maximum frame
  changes were about 44.5, 33.5, and 22.3 degrees respectively. The helical
  full-roll cases were clean at all tested 10–30-degree steps, including a
  maximum 46.9-degree frame change at the coarsest spacing.
- Four gates on two straight legs, with no gate precisely at their mathematical
  corner, were clean across 30-, 45-, 60-, 90-, and 120-degree tangent kinks
  for both aspect ratios. This checks topology and end-edge correspondence;
  it does not establish that the loft follows an exact sharp corner.

The working inference is that section density should consider the *full local
frame change* (bend plus roll) and the positions of centers relative to gate
normals. Tangent alignment appears important; a simple "under 45 degrees"
rule is contradicted by the straight-center tilted-profile probe and by some
clean larger-step tangent-following cases. Before adopting a production policy,
test actual ribbon dimensions, mixed bend/roll/kink paths, nearby self-contact,
and intermediate lane-surface identity rather than relying on end faces alone.

## Irregular-profile follow-up

`experiment_irregular_loft_profiles.py` tested asymmetric five-edge polygons and
five-edge profiles whose second edge is a true circular arc. It varied sketch-
internal rotation independently of the route frame, and separately enabled or
disabled station-to-station corner/arc-bulge changes. Fusion produced one solid
body in all 28 final cases; 17 retained five consistently mapped lateral faces
and two caps, while 11 split faces or reassigned start-to-end edge identity.

- On a straight path with changing corners, the polygon was clean at 15, 20,
  about 25.7, 30, and 36 degrees of internal rotation per gate, but mapped
  different edges at 45 degrees and split a face at 60 degrees.
- With a changing circular-arc bulge, the profile was clean through about
  25.7 degrees per gate, split a face at 30 and 36 degrees, and remapped edges
  at 45 and 60 degrees. The same arc profile with *fixed* bulge and corners
  stayed clean at 0, 20, 30, and 45 degrees. Thus the observed failure at
  30 degrees is not an arc-only or rotation-only limit: shape evolution matters.
- The changing polygon stayed clean on a 360-degree helix with a 360-degree
  route-frame roll (about 46.9 degrees maximum between frames), but not on a
  planar U-turn with the same roll and about 44.5-degree frame steps. The
  changing-arc profile split faces on both paths. A 90-degree kink plus
  30-degree internal step was clean for the polygon and split an arc face.

The practical inference is that subdivision must account for *within-profile*
deformation as well as rigid frame rotation and route geometry. Even then,
these sparse cases do not establish a safe formula. Autodesk documents that
`SketchArcs.addByThreePoints` always creates a counterclockwise arc and may
reverse queried endpoints, so the probe uses geometric vertex labels rather
than the sketch curve's reported start/end order:
<https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_SketchArcs_addByThreePoints.htm>.

## Seam and parameterization hypothesis (not an implementation rule)

The proposed model treats a loft as one or more parameterized surface patches
`S(u, v)`, with `u` moving around a section and `v` moving between sections.
It proposes storing a logical seam (`u = 0`) and traversal direction on each
generated gate, then connecting corresponding seam points with a rail. This is
a useful *design hypothesis*, not a description of Fusion's proprietary solver
or a verified way to force face identity.

What Autodesk documents:

- Fusion's modeling operations use Autodesk ShapeManager (ASM), per
  [Autodesk's modeling overview](https://www.autodesk.com/products/fusion-360/blog/get-smart-with-fusion-360-3d-modeling-terminology/).
  The [Loft
  reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-EC6CECCD-55C1-4B08-95E4-5B1EEDE78D07.htm)
  says matching corners on closed sections are mapped predictably; it does not
  promise preservation of our chosen vertex zero, physical trace identity, or
  one BRep face per corresponding edge. Our irregular tests found face splits
  and remappings even with five nominally matching corners.
- Rails must intersect every controlled section, reach the first and last
  sections, and be tangent-continuous. They influence the entire loft shape;
  they are not documented as an explicit `u = 0` or face-identity constraint.
  A centerline holds sections normal to its path and need not intersect them.
  The [Fusion API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_LoftCenterLineOrRails_addCenterLine.htm)
  removes existing rails when a centerline is added, so a centerline-plus-seam-
  rail configuration is not available in one ordinary loft input.
- The [Profile API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Profile.htm)
  exposes computed profile loops, not a setter for the loft's seam or traversal
  direction. An add-in can store *its own* logical labels but cannot assume
  that Fusion will adopt them from sketch creation order. Arc start/end
  direction can be reversed by the API itself, as noted above.

The `S(u, v)` picture, B-spline/NURBS skinning, common parameterization,
edge-splitting, and the proposed processing order are plausible explanatory
models; Autodesk does not publish the exact Fusion loft equations or that
step-by-step sequence. In particular, neither a stored seam nor a single rail
has yet been shown to prevent the face splits caused by changing arc bulge or
combined bend and roll. Likewise, equally spaced values such as `u = 0.25`
are not necessarily equivalent *features* on unequal or irregular profiles.
Trace boundaries would need explicit logical landmarks, not just perimeter
fractions.

## Controlled seam-rail comparison (2026-10-02)

`experiment_loft_seam_rail.py` reused the same five-labeled-vertex section
generator for seven geometric cases. Each was independently lofted with no
rail, one rail through vertex 0, and two rails through vertices 0 and 2. The
rail curves were fitted through the *model-space* gate corners and checked
against every gate before lofting; maximum measured gate misses were below
`2.5e-13 cm`. Fusion accepted all 21 lofts as one solid body. The experiment
closes its own unsaved scratch design after writing the report.

| Geometry | No rail | Vertex 0 rail | Vertices 0 and 2 rails |
| --- | --- | --- | --- |
| Changing polygon, 30° internal step | clean, 7 faces | clean, 7 | clean, 7 |
| Changing polygon, 45° internal step | remapped, 7 | split/remapped, 9 | clean, 7 |
| Changing arc, 30° internal step | split, 8 | split, 8 | clean, 7 |
| Fixed arc, 30° internal step | clean, 7 | clean, 7 | clean, 7 |
| Changing polygon, planar U-turn + 360° roll | split, 9 | split, 9 | clean, 7 |
| Changing arc, planar U-turn + 360° roll | split, 8 | split, 8 | clean, 7 |
| Changing arc, helix + 360° roll | split, 8 | split, 8 | clean, 7 |

Here, “clean” means exactly one solid body, seven BRep faces (five lateral
faces plus two caps), and each lateral face connects the same *labeled edge*
at the first and last gate. Thus the one-seam-rail proposal is **falsified as a
sufficient condition** for stable face identity in these cases. Two separated
vertex rails were sufficient for all five previously failing cases and did
not damage either clean control. They constrain two perimeter landmarks,
which is a stronger correspondence signal than one seam point alone.

This is a finite empirical result for these seven shapes, spacings, and rail
locations—not a general solver theorem or a production rule. A follow-up
used `BRepFace.isPointOnFace` at the midpoint of every labeled edge of each
intermediate gate. All seven two-rail lofts had zero misses; the five
previously failing no-rail and one-rail cases had intermediate misses as well
as end-face deviations. The check still does not prove absence of
self-contact or preservation under later gate edits. Nor does it show that
two rails always suffice for other vertex choices or unequal topology.
Raw case reports are under ignored
`artifacts/verification/loft_seam_rail.json`; no product geometry or saved
design was changed.

## Finite ribbon rule matrix (2026-10-02)

`experiment_loft_ribbon_rules.py` created tangent-normal, four-right-angle
rectangles at two FFC-like dimensions: 10 x 0.5 mm and 1 x 0.1 mm. Each was
lofted along a 20 cm-radius planar U-turn with 180 or 360 degrees of roll, or
a 20 cm-radius rising helix with 360 degrees of roll. Each path was sampled at
4, 8, 12, and 24 intervals, with no rail, one corner rail, and two opposite-
corner rails. The rails met every labeled gate to far better than 0.001 cm.
The 72 trials ran in one self-closing scratch document. A clean result requires
one solid body, exactly six faces, four identified lateral faces, and every
gate-edge midpoint on the same lateral face as its starting labeled edge.
End caps are excluded from midpoint hits at the final gate.

| Path / roll | Four intervals | Eight, twelve, or twenty-four intervals |
| --- | --- | --- |
| U-turn / 180° | all 6 clean | all 18 clean |
| U-turn / 360° | no rail: 2 remapped; one rail: 2 ASM self-intersection errors; two rails: 2 clean | all 18 clean |
| Helix / 360° | no rail: 2 remapped; one or two rails: 4 ASM self-intersection errors | all 18 clean |

The full matrix has 62 clean cases, four correspondence deviations, and six
Fusion rejections. At four intervals, adjacent complete frames changed about
62.8°, 98.4°, and 134.8° respectively. At eight intervals those maxima fell
to about 31.7°, 50.0°, and 69.9°; at 24, to about 10.6°, 16.7°, and 23.5°.
All 18 twenty-four-interval cases were clean. In contrast, the irregular
five-edge experiment found that one rail can leave split faces even with
smaller angular steps, so a universal angle threshold is not established.
Each rectangular case records its observed expected result and a regression
flag on rerun; `unexpected_cases` in the JSON report should be empty. A
changed outcome deserves inspection even if it improves a formerly failing
case, because Fusion or the experiment's behavior may have changed.

### Candidate rule set for a future implementation experiment

1. Give every gate stable, oriented logical edge/vertex labels and identical
   topology. Build planes normal to the route tangent; do not infer identity
   from Fusion profile-curve order.
2. For color-critical faces, use two separated keyed perimeter rails, each
   verified to intersect every gate. A seam rail alone is not sufficient for
   changing irregular profiles. Rails do not repair a self-intersecting skin.
3. Place enough gates to keep the *full* neighboring frame change (bend plus
   roll) modest. **About 25° is a conservative experimental target, not a
   proven Fusion limit:** it covers the dense rectangular cases and leaves
   margin below the observed coarse failures. Shape change within a gate
   remains a separate variable; no current formula bounds it.
4. Treat construction success as insufficient. Verify one solid body, expected
   face count, labeled side identity at both ends and every gate, and a
   separate geometric self-contact/interference check before using face IDs
   for per-trace colors. Reject or flag ambiguous results instead of silently
   assigning a neighboring trace's color.

The finite matrix tests gate locations, not every point between gates. It has
only two sizes, three paths, one rail-pair choice, and no changing profile
width/thickness, nearby nonlocal self-contact, regeneration, or multi-trace
connectors. Therefore these are *testable design criteria*, not an authorized
product change or proof of reliable arbitrary lofts. The ignored raw report is
`artifacts/verification/loft_ribbon_rules.json`.

## Actual 19-trace FFC counterexample (2026-10-03)

`experiment_live_ffc_correspondence.py` and its one-case
`experiment_live_ffc_dense_unrailed.py` follow-up used the saved FFC group in
the open `Wire creation tester v109` design. Planning used the current route,
contact, and FFC-dimension code; each section was drawn by the production FFC
section builder in an unsaved scratch design. The source was already modified
and remained modified; the experiment did not save or change it. The scratch
design stays open for inspection. Raw results are in ignored
`artifacts/verification/live_ffc_correspondence.json`.

The real plan has 19 numbered traces and 40 stations. Its resolved dimensions
are 1.515 mm trace width, 0.992 mm spacing, 2.507 mm pitch, and 1.5 mm
thickness. The production loft selects stations `0, 4, 12, 20, 28, 35, 39`.
Two proposed rail curves were measured to meet all seven or all forty profile
corners within `6e-15 cm`.

| Exact profile and gate selection | Fusion result | Face-identity result |
| --- | --- | --- |
| Production seven gates, no rails | One solid | 324 side faces instead of the 232 unsplit contour edges; 190 of 228 top/bottom trace-land samples did not remain on their starting face |
| Same seven gates, two opposite-corner rails | `ASM_BAD_UV_SKIN_DIR` rejection | No body to inspect |
| All forty gates, two opposite-corner rails | `ASM_LOFT_SURFACE_SELF_INTERSECTS` rejection | No body to inspect |
| All forty gates, no rails | `ASM_LOFT_SURFACE_SELF_INTERSECTS` rejection | No body to inspect |

Sparse selected gates rotate as much as 89.8° in section normal and 79.7° in
width axis between neighbors. Using all forty lowers those separate maxima to
28.6° and 11.8°, yet both dense lofts are rejected. These are *individual
axis* angles, not the complete frame-rotation metric used in the rectangular
matrix. More important, neither a gate-count rule nor a two-rail rule is
sufficient for this actual ribbon. The unrailed dense control shows that the
rails alone do not cause the self-intersection rejection; it does not tell us
whether the intended wide ribbon physically self-overlaps or ASM infers a
different skin correspondence. The sparse body's extra faces and failing
trace-land samples make per-trace face coloring unreliable even though its
solid is valid.

The previous candidate rule set should therefore be treated as *necessary
checks and experimental levers*, not a recipe for this route. Before changing
production geometry, a further experiment would need to localize the dense
loft's failing interval or nonlocal overlap, and separately test a controlled
construction that retains continuous trace-land faces. Do not infer success
from the 25° target or from the two-rail seven-shape controls.
