# Actual-profile rigid sweep limits

**Current interpretation:**204..206confirm that the native sweep follows the center
guide but misses the ordered edge trajectories by up to4.799915mm, including an
ordered179.318545degree arrival reversal. The ratios below characterize a different
rigid-sweep representation, not validated minima for the intended material plan.
Resolve [plan/output fidelity](trajectory-fidelity.md) before promoting these limits.

The user rejected198's excessive deviation and requested the real limit, including
different thicknesses and conductor counts. Its enclosing disk was sufficient,
not necessary. Keep that experiment as conservative construction evidence.

## Local geometric contract

`sweep_transport.inspect_sweep(route, arcs, reverse=True)` models the end-first
ordinary perpendicular sweep. It uses exact helix parallel transport through each
G1 fold and continuous contour-support extrema over the original circular arcs.
`sweep_profile.joined_profile_arcs(lines, diameter)` describes the unchanged native
joined contour mathematically; it does not replace the native profile builder.
Its directional support matches the captured three-conductor native contour to
roundoff, and independent contact-profile height tests cover count/thickness changes.

At each station the dimensionless utilization is
`actual inward profile reach / centerline curvature radius`; local rigid Jacobian
is `1-utilization`. Zero is local collapse. The configured99.6% utilization retains
J>=0.004. Width enters through actual transported orientation, not an enclosing
disk at every turn. This is separate from the material fold's thickness pinch.
The centerline curvature radius of a cylindrical fold is `R/cos(bank)^2`;
reported common fold radius R is the cylinder radius, not that centerline radius.

`construct_candidate`/`connect` accept `minimum_radius_mm` for explicit dimensional
boundary studies. It cannot lower the existing material or selected construction
policy radius. The existing default and conservative policy remain unchanged.
199/202 use the material reference plus an explicit measured radius; there is no
new universal radius multiplier, native fallback or seed-based route discovery.

## Measured ratios

202 freezes nine gym-authored inputs before solving: the same133seed/zones/faces/
roll/void%/zone%, with1/3/6conductors and D=0.75/1.5/3mm. The gym regenerates target
positions and environment dimensions from nominal width. These are three aspect
variants and three dimensional scales of one endpoint arrangement, not nine
independent geometry families or untouched holdouts.

The same continuous-angle procedure uses one shared fold radius. Ordered radius
checks and bounded scalar bisections locate its first observed local crossing;
coarse responses are monotone. This does not prove monotonicity across all hidden
branch changes, a global minimum route, or that every turn needs the shared radius.
All nine selected material-volume contact checks separate. No obstacle avoidance
is added. Fixed targets, equal material increments, no lateral material bend and
the original material pinch rule remain.

| Conductors | R at D=.75mm | R at D=1.5mm | R at D=3mm | R/D | R/nominal width |
| ---: | ---: | ---: | ---: | ---: | ---: |
|1|0.376518|0.753036|1.506073|0.502024|0.502024|
|3|0.902843|1.805686|3.611372|1.203791|0.401264|
|6|1.742245|3.484491|6.968981|2.322994|0.387166|

These are99.6%-margin values for this procedure/arrangement. R/D is invariant
across the three tested thickness scales; normalized length differs by<=8.01e-11.
Count/aspect and turn orientation affect the ratio. Do not install this table as
universal cable bend constants.

For the original three-conductor D1.5mm layout,199brackets modeled collapse at
R=1.797946424..1.797948114mm and99.6%-margin at1.805684226..1.805685915mm.
The measured-margin route is101.834899mm/8folds, versus198's132.577433mm at
R2.524556mm. This reduces radius28.47% and length23.19% within this common-radius
procedure; additional local allocation/route optimization remains unestablished.
Exact transport predicts198's native terminal axis roll within5.11e-8degrees.

## Native outcomes and retained stops

199's first host setup stops before guide authoring or native calls: a reordered
half-width arithmetic expression rounds above the stored material bound. After
application-log review,200uses the original arithmetic and identical frozen input.
The199empty owned component and all failed setup evidence remain.

200attempts the registered below-boundary probe at R1.796947269mm, predicted
J=-0.000519058. Fusion returns a positive solid in18.078694s, so the next above
probe (R1.798947269mm) stays unattempted under the mismatch stop. Do not call this
a passing physical route or an observed native failure bracket. The modeled local
rejection remains; successful kernel construction is insufficient acceptance.

201makes one read-only transient plane intersection at the limiting Fold8 section.
Sixty-four predicted contour points are within7.306e-6mm of native section chords
(1e-5mm chord tolerance); the limiting point is within2.113e-6mm. This corroborates
the local contour but does not measure longitudinal progress, prove injectivity
or establish an exact repair/healing mechanism. Native build threshold remains
unmeasured. No further native threshold refinement is scheduled.

203preselects count/thickness extremes plus the original triple for positive-margin
construction, after reviewing the mismatch. Same profiles, zero added twist/taper,
one joined solid per complete layout; no per-conductor bodies or alternate builder.

|202input|Count / Dmm|Native seconds|Native outcome|
|---:|---:|---:|---|
|0|1 / .75|59.549972|Built; cap centers/planes match|
|4|3 /1.5|11.670859|Built; cap centers/planes match|
|8|6 /3|22.087561|Built; cap centers/planes match|

All three arrival axis rolls differ0.681455degrees modulo180. The single/round
conductor remains informational under the user's exception; multi-conductor
correspondence is not relaxed. Native equal material lengths, no-wide-axis bending,
interior pinch and global contact remain incompletely audited. Zero fully accepted
physical cables. The other six dimensioned inputs have no native attempt.

203shows the tighter triple, retaining all three original guides and Start/End cap
sketches. Other two variants and prior187/193/198/199/200views remain hidden intact.
Solver captions/details keep measured ratios, native outcomes and missing audits;
viewport reviewed. All saved documents remain read-only, count0editable; only the
owned unsaved scratch changes. No production/profile/native-builder change.

## Resources and verification

199's50dependent scalar candidates (48boundary evaluations plus2probe preparations)
take0.529632s.202's nine dimensional variants take4.486805s, with5s/case60s phase,
<=50radius evaluations/case,20kcontact pairs/depth36. No numerical budget expands.
200host19.920336s;201inspection1.855372s includes0.563149s transient intersection;
203host100.093509s includes93.308391s total native sweep calls. Native calls remain
below120s each;203's3call/420s phase holds. Peak retained native RSS637248KiB,
local19312KiB;4GiB ceiling/3.8GiB launch headroom hold, in-flight peaks unmeasured.
Token/cost data are unavailable. None of these timers is total investigation time.

Source pins, frozen gym inputs, every scalar/host outcome, stops and source copies
remain under ignored artifacts/verification/ribbon_sweep199..203.199/201host
formatting and202's synchronous-loop lint annotation were applied after execution;
byte-exact executed copies retain their original fingerprints.81distinct focused
tests pass across the core and profile additions; scoped Ruff and changed-file
IDE checks pass. FullQA/generalized native/material validation were not run.
