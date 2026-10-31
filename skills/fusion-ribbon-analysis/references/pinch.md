# Normal-profile restart and historical sheet pinch

## Restarted reference — 2026-10-31

The user rejected the paired-edge model after view155. The percentage itself
remains99.6%; the geometry to which it is applied must match the preserved profile.
Read-only inspection158 confirms the user's demo contains a torus of major radius
25.0000003725mm and minor radius24.9000003748mm, plus a nominal25mm sketch arc.
This is the intended R25/h24.9 example below, with native numerical roundoff.

The rejected strip map explicitly allows curved material cross-sections
(`material_strip.py`). The retained experimental native sweep uses a perpendicular
constant profile (`trunk_sweep.py`). These are different geometry assumptions.
The historical sheet's ruling-slope multiplier is not automatically a constraint
on that preserved normal-profile sweep. Nor can its sheet-coordinate progress
be treated as progress of a different profile mapping.

`devtools.ribbon_analysis.normal_profile.inspect_normal_profile` is a new isolated
local reference for the preserved geometry. It does not replace historical
policies or restart any retired route solver. For
`Y(s,a,b)=r(s)+a*W(s)+b*H(s)`, unit orthogonal profile axes normal to the actual
center tangent, and no width-direction curvature, the normalized volume
determinant is `1-b*kappa_H`. Profile-frame rotation contributes only transverse
terms, which cancel from this determinant. The thickness condition is therefore
`h*|kappa_H| <= p`, with `R_min=h/p` and `R_inside=R-h`. Inputs with lateral bend
or an invalid normal frame reject instead of silently using this restricted rule.
The circular-tube coordinate factor also appears in the [tube-coordinate
derivation](https://link.springer.com/article/10.1186/s40687-016-0053-1), section2.2;
the constant-profile extension here is our explicit geometric derivation/check.

Run159 freezes six authored reference configurations before measurement. Direct
finite differences of world-space swept-profile points agree within3.86e-10 in
normalized determinant. Four positive controls meet the local check, one
negative-inside control is rejected, and the exact demo-boundary reference is
retained separately: its raw floating result can exceed99.6%by roundoff. The
near-limit positive fixtures use a declared1e-9relative radius inset, not a new
physical safety margin or relaxed acceptance tolerance. No endpoint solving or
complete-ribbon/native validation occurred.

For one1.5mm conductor, minimum center radius is0.7530120482mm and the inside
radius is0.0030120482mm at99.6%. View160 shows that near-limit bend, a rejected
R0.74mm bend, and one authored compound S with a90degree lateral turn. Its three
G1 pieces count as one reference configuration. This does not establish smooth
curvature joins, global self-contact, strain, noncircular ribbon compatibility or
Fusion's intermediate frame field. Native profiles/builders remain unchanged;
at that stage the local check did not implement endpoint routing.

## Endpoint normal-profile prototype

`experiments/experiment_ribbon_normal_route/solver.py` now constructs a centerline
from the fixed endpoint poses alone. Its prescribed septic cap jets are
`v=D*T`, `a=D*(W cross T)`, `j=-D*T`, with endpoint chord D. A zero-jet endpoint
bridge C supplies the scalar family `Q=C+s*(P-C)`. Bounded doubling/halving and
bisection retain a certified member near an observed family boundary. This is
one chosen polynomial family, not a seed bank or universal feasibility solver.
Neither monotonic feasibility nor globally shortest length is proved. The
retired discovery procedures remain disabled; this prototype has its own entry.

The ordered guides are `r +/- half_width*W`, with perpendicular fixed sections.
The width is the regular Frenet binormal, or an exactly detected constant planar
width through inflections. No historical `W+eta*T` material-sheet offset is used.
The preserved joined-profile guide extent is `N*D/2+0.1D`; its additional0.1D is
the native profile's side-cap extension, not a routing clearance reserve.

`polynomial_certificate.certify_curvature` uses rational Bernstein arithmetic
on the exact stored float controls. For `G=|r'|²`, `A=|r' cross r''|²`, it proves
`G>0` and `(p/h)²*G³-A>=0` over the entire interval. A nonplanar Frenet frame
also requires `A>0`. Subdivision exhaustion is unresolved. This closes the
between-sample curvature gap for this ideal polynomial and restricted profile
model; it does not certify a cubic edge drawing or native sweep frame.

Run161 freezes five examined development inputs: the original gym, three prior
collateral cases and one known-feasible N1 S/lateral90 endpoint control. All5
produce certified members;0failed/0unresolved. Total solve plus checks6.147s,
maximum sampled local RSS21264KiB. Gym39.448mm/1.555s, straight60mm/0.131s,
planar28.499mm/1.398s, spatial roll47.274mm/1.495s, N1control20.057mm/1.567s.
The N1 route still has an excessive loop: this exposes a family limitation and
is not evidence that such length is necessary. No untouched validation cases.

Run162 recertifies these same frozen controls after QA-only math sharing and
strict subdivision-node scheduling; no new solve. Its refined peak witnesses
are99.599993/0/99.599969/99.599932/99.599998percent, separately from the interval
certificates. View162 retains all five components, with only gym initially
visible, plus15hidden original guides. The center guide is exact degree7;
the two offset guides are approximate512-cubic drawings. Their sampled position
errors range up to0.01923mm (gym0.000696mm); they have no curvature certificate.
The illustrated joined lobe section follows unmodified `ribbon_builder._add_section`
dimensions. Profile creation, native builders and production are unchanged.
Preparation3.051s, display6.895s, Fusion RSS155200KiB, guide translation error
1.44e-14mm; four old sessions/snapshots/selection retained. Screenshot review was
unavailable because computer use returned `cgWindowNotFound`; API display and
guide translation checks succeeded. Zero native cable attempts/builds/post-build
audits; native failure rate unmeasured. Strain, contact, native interpolation,
global feasibility, minimum length and complete physical validity remain unproved.

## Equal material lengths and banked fold calibration

The user now explicitly requires left, center and right to have equal material
lengths, with common total length still free. Apply this locally to corresponding
material increments, not merely equal final totals. This supersedes the earlier
exclusion of three-path length balance. Existing1%mechanical goals are not a
tolerance for this requirement. The distinction between a developable surface
and an isometric material mapping is also explained in
[Chen and Fried, 2016](https://royalsocietypublishing.org/doi/10.1098/rspa.2016.0459).
The tests below use explicit world-coordinate maps and derivatives.

For the former rigid normal-profile map, no lateral bending gives
`r' dot W'=0`, so `|(r+qW)'|²=|r'|²+q²|W'|²`. Rotating W therefore lengthens
both edges relative to the center. `normal_route.compatibility.planar_controls`
tests the exact stored-float control polygon's coplanarity. For a certified
regular Frenet frame, this is equivalent to constant W and equal material steps.
`solve` now returns `length_incompatible` for the nonplanar member even when its
curvature certificate succeeds. This rejects that representation; it does not
declare the endpoint layout impossible or implement a replacement fold router.

`material_lengths.measure_lengths` integrates all three actual path speeds and
reports local speed spread. Nested Simpson-grid differences are convergence
observations, not certified error bounds or physical slack. Run163 audits the
same5frozen161curves, with no new solves:2compatible/3incompatible/0unresolved
within this named rigid-profile test. All five old curvature certificates remain.

| Examined input | Left / center / right length, mm | Material compatibility |
| --- | --- | --- |
| Gym |45.142933 /39.448105 /45.142933|Fails|
| Straight |60 /60 /60|Passes|
| Planar quarter |28.499018 /28.499018 /28.499018|Passes|
| Spatial roll |59.382930 /47.273620 /59.382930|Fails|
| N1 S/lateral90 control |22.372155 /20.057342 /22.372155|Fails|

The spatial and N1 quadrature differences are0.000107mm and0.0000114mm;
do not present the printed digits as rigorous integration bounds. The gym
difference is1.10e-10mm. Exact geometric incompatibility is separate from sampling.

`isometric_fold.CylindricalFold` authors a finite-radius plane-cylinder-plane
reference. Rotate flat material coordinates to
`xi=s*cos(a)+q*sin(a), eta=-s*sin(a)+q*cos(a)`, then wrap xi around a cylinder.
This preserves `|X_s|=|X_q|=1, X_s dot X_q=0` throughout each piece. Bend entry
and exit are staggered across width. Transverse material lines curve through the
fold, while the two terminal profiles remain flat and unchanged in material
coordinates. This is a physical banking/folding reference, not another rigid
normal-section twist, seed bank or endpoint-discovery family.

The true thickness-offset determinant is `1-b/R` (with signed fold orientation),
where R is the cylinder/fold radius. Centerline curvature alone is `cos²(a)/R`
and can miss an excessive fold.163's three positive fold references pass; the
R0.74mm negative-inside variant is correctly rejected, despite its center-only
pinch being50.676%. The positive radius uses the declared1e-9relative numerical
inset at99.6%. Material metric error<=2.23e-16; independent world-space thickness
determinants agree<=3.01e-10. These four authored variants calibrate one fold
family, not four independently solved endpoint layouts. Full163audit3.796s,
localRSS21312KiB;0new solves/native attempts/builds/post-build audits.

View164 shows the diagonal90 and180references, with common lengths7.972772mm
and9.645544mm respectively. It reuses the preserved3-conductor joined contour
in material coordinates and shows actual1.5mm thickness. Preparation1.008s,
display3.610s,FusionRSS535360KiB. Six original approximate guides remain hidden;
sampled guide-position error<=0.00000358mm, native translation error<=7.11e-15mm.
Labels/camera were adjusted after screenshot review; final viewport reviewed.
162is renamed curvature-only and hidden; all4old sessions/snapshots retained.
Original profile creation and native builders remain unchanged. The rigid-profile
sweep does not yet reproduce these material folds. G1 joins, contact, equilibrium,
native interpolation and arbitrary-target fold construction remain unvalidated.
Focused QA:44distinct tests pass; scoped Ruff/IDE checks clean. After163/164,
one compatibility comprehension was line-wrapped by Ruff only; final provenance
records AST equality to its frozen source. No further solver run is implied.

## Endpoint construction from material folds

This subsection records the166..168construction. The displacement-derived steering
and outward returns below supersede its fixed steering angles for new candidates.

`experiments.experiment_ribbon_fold_route.solver.construct_candidate` connects both ordered
target poses using the calibrated material map, before the mandatory contact gate
in `connect` described below. It is host-only Python3.9+ code, with no
Fusion dependency, no route seeds, no optimizer and no retired discovery calls.
The old diagnostic execution catalog remains retired; this experiment has its own
entry point. Production, original profile creation and native builders are intact.

Straight and feasible one-plane turns receive direct straight/bend/straight
closure. Other orientations use a proper A-B-A Euler decomposition about two
orthogonal45degree material creases. The finite-fold offsets are evaluated first;
signed straight distances then close the residual position in the departure frame.
Width/height steering folds return that frame before the arrival folds are applied.
Negative displacement uses two rounded transverse half-turns around a forward run,
never negative material progression. Zero residual axes omit their steering pieces.
This gives algebraic cap closure with at most13folds, not a minimum-fold or
shortest-route method. It does not establish self-clearance or physical impossibility.

`FoldRoute` composes the same material map through rigidly placed, flat-ended
pieces. One cumulative material coordinate drives all lanes. Each piece preserves
`|X_s|=|X_q|=1, X_s dot X_q=0`; joins retain matching position/tangent/across
directions. True fold radius is `(D/2)/p*(1+1e-9)`, preserving the declared numerical
inset. Thus local thickness pinch stays below99.6% without independently stretching
guides. Tiny-angle planar closure uses a signed-sine equation; parameter derivatives
scale by total/exact-piece length to avoid cancellation at very short pieces.

Runs166/168 evaluate the same five examined development inputs, not holdouts.
Final168:5planned/5evaluated/5clear the named local checks/0failed/0unresolved;
0native cable attempts/builds/post-build audits, native failure rate unmeasured.

| Input | Common material length, mm | Folds | Construction, ms | Audit, ms |
| --- | --- | --- | --- | --- |
| Gym |58.110068|9|0.447|208.245|
| Straight |60|0|0.057|157.000|
| Planar quarter |39.676804|1|0.116|161.886|
| Spatial roll |80.869455|11|0.419|209.265|
| N1 S/lateral90 control |40.030343|11|0.437|215.534|

All cap-profile errors<=6.16e-15mm; local material metric error<=5.56e-16.
Independent position derivatives and thickness-offset determinants were checked;
maximum determinant discrepancy3.50e-9. Full168time1.013s,RSS18832KiB; no search.
165is retained as an audit-harness stop: one gym route was constructed but a
finite-difference probe crossed a zero-lead piece boundary. No result accepted;
four remaining inputs unattempted.166corrected probe placement under unchanged
geometry/budgets and completed in0.973s.168rechecks final numeric fixes; all five
serialized piece sequences are exactly identical to166, validating display transfer.
Cumulative165/166/168numerical work2.166s, excluding display and local unit tests.

View167 retains all five case components, gym initially visible, and individual
piece mesh groups. It shows the unchanged joined material contour,1.5mm thickness,
three guides, cap XYZframes, fold-radius circles and frozen solver values. Fifteen
original approximate guides and eight constraint helpers remain individually hidden.
Nonuniform guide cubics split at every lane's actual fold entry/exit and use a
maximum0.025rad angular step; sampled position discrepancy<=7.63e-10mm. These
rendering approximations are not curvature proofs. Native point translation error
<=2.14e-14mm. Preparation5.071s/display10.720s,FusionRSS297376KiB; viewport reviewed,
four earlier sessions/snapshots/selection and164references preserved.

Scoped QA:37distinct tests, Ruff lint/format and five changed-file IDE inspections
pass, including rigid-frame covariance, Euler poles, backward displacement and the
near-parallel regression. G1 joins are explicit. Contact, containment, equilibrium,
native interpolation and complete physical validity remain unmeasured. The9/11fold
spatial results are conservative; no additional compactness refinement is scheduled.

## Mandatory thick-volume self-contact gate

The user adds self-intersection prevention after view167. Public `solver.connect`
now returns a route only when `inspect_contact` reports `separated`; both
`penetration` and `unresolved` raise `SelfContactError`, retaining the rejected
route, report and completed trial history. `construct_candidate` is explicitly
unchecked diagnostic geometry. Existing tests of local algebra use that entry point
without implying global contact acceptance. Gym geometry remains outside avoidance.

`contact_bounds` encloses the thick material map analytically, subdividing material
boxes rather than testing display triangles or only three guide lines. The full
width includes the original side-cap extension. A rectangular +/-D/2 envelope
contains the actual joined-lobe contour. Envelope separation is conservative;
overlap alone is not penetration. `contact_inverse` confirms penetration only when
one world point has two strictly interior preimages in the actual joined contour,
with forward reconstruction agreeing within the declared numerical guard. Profile
arcs match the preserved builder; native profile creation is unchanged.

A single regular plane-cylinder-plane piece is injective for |angle|<=pi and R>h.
Adjacent pieces may share their terminal material cap. The checker excludes only
cap neighborhoods proved to occupy opposite half-spaces, using nonnegative
longitudinal projection within90degrees of each flat cap. Entire adjacent pieces
are never ignored. All other piece pairs require separated projected envelopes.
The20,000-node/depth36 budget returns unresolved on exhaustion. The floating bounds,
outward arithmetic and guards are numerical evidence, not an exact-arithmetic proof,
native-solid validation or complete physical simulation. Conservative profile
envelopes can leave actual clearance unresolved.

169 audits the same five frozen168piece sequences without rerouting. Final171
repeats that fixed audit after adding forward reconstruction to inverse witnesses.
No new independent configurations or untouched holdouts were added.

| Input | Final contact disposition | Checked pair nodes | Final time, ms |
| --- | --- | --- | --- |
| Gym | Penetration |755|236.243|
| Straight | Separated |0|8.339|
| Planar quarter | Separated |3|8.397|
| Spatial roll | Unresolved at depth limit |3209|702.936|
| N1 S/lateral90 | Unresolved at node limit |20000|3279.507|

All5evaluated,0unattempted. Final171takes4.240s,RSS18496KiB. The gym witness is
world(12.1893206692,-2.7546893824,17.2243763510)mm, occupied by original pieces4and6
(one-based). Their local(u,q,b) coordinates are(0.5,0,0)and
(0.5009559488,-1.2955267819,-0.0477076385). Prior local material/pinch/cap checks
are retained; those checks alone never established contact clearance.

170tests a bounded geometric repair: extend every fold's flat leads by the same
runway and recompute algebraic closure. Up to3corrections at width+thickness support
increments give14dependent candidates across the same5configurations. Before/after
records preserve all attempted geometry, including failures. Straight/planar clear
unchanged. All3spatial cases remain blocked; each corrected spatial candidate
penetrates. Final corrected gym length685.262mm, spatial491.867mm, N1S340.664mm.
This repair fails and is opt-in only; default `maximum_corrections=0` rejects
immediately. It does not prove another route impossible, and no extra budget or
automatic follow-up is scheduled. Fixed targets, equal local material increments,
true99.6%pinch and no lateral bending are preserved throughout these changes.

View171shows the original58.110068mm gym as rejected, with both penetrating pieces
red and the occupied witness located. It retains the same frozen meshes/guides;
167is hidden intact. Four historical sessions, snapshot identities and selection
remain unchanged. Display0.953s,RSS766848KiB;viewport reviewed. All169..171records,
plans, source ZIPs and170failed trial ledgers remain under ignored verification
artifacts.0native cable attempts/builds/post-build compliance audits; native failure
rate unmeasured. No collision-free gym result, generalized success or complete
physical-validity claim.51focused tests, scoped Ruff and7changed-code IDE inspections
pass; fullQA remains unrun.

## Outward fold construction instead of inward cancellation

The user correctly distinguishes detecting a collision from constructing a route
that avoids it. The original steering overshoots small transverse displacements:
two45degree diagonal half-turns have a finite lateral offset before any straight
run. Subtracting that offset can make the signed run negative, adding two more
half-turns that fold the route back into its own occupied region. Merely flipping
one arbitrary sign or increasing every runway does not fix the coupled sequence.

`experiment_ribbon_fold_route.steering` now derives the crease angle from the
required displacement. With total contour width W, radius R, extra runway r and
positive bank a, the pair's lateral offset is
`2W*sin(a)^2 + 4r*sin(a)*cos(a) + 2*pi*R*sin(a)`.
It increases on0..45degrees. At default r=0, a quadratic in sin(a) gives the angle
directly; explicit nonzero runway uses52bounded bisections of this monotone scalar
equation. This calculates one dimension, not a bank of route guesses. Larger
displacements keep45degree creases and a nonnegative intervening run. Height
steering similarly inverts `2R*(1-cos(theta)) + 2r*sin(theta)` below90degrees,
then uses a nonnegative height run for larger offsets.

The diagonal pair bends away from the subsequent height move. Its second fold
uses the opposite local angle, continuing outward in world space into another
layer rather than returning into the first occupied layer. Its exact signed4R
normal offset enters height closure. Whole-module analytic width/thickness bounds
determine the positive advance between modules and the arrival folds. The separator
uses the existing2(R-h)inner-radius clearance. That advance is subtracted from the
initial forward displacement; it is not arbitrary global runway growth. A genuinely
negative remaining forward displacement may still require a reversal and can still
fail the mandatory contact gate. This construction is not a universal routing proof.

177runs the same five examined inputs with one candidate each and no runway repair:

| Input | Previous contact | New contact | Length, mm | Folds |
| --- | --- | --- | --- | --- |
| Gym | Penetration | Separated |50.114071|7|
| Straight | Separated | Separated |60|0|
| Planar quarter | Separated | Separated |39.676804|1|
| Spatial roll | Unresolved | Separated |68.005317|7|
| N1 S/lateral90 | Unresolved | Penetration, rejected |40.041258|9|

Gym improves from58.110068mm/9folds while retaining the exact targets and99.6%pinch.
Final178geometry is byte-for-byte equal in serialized piece values to177. Its
independent position-derivative, thickness-determinant, metric, cap and G1 audits
complete on all5. Max cap gap9.57e-15mm, metric error4.45e-16, determinant discrepancy
3.36e-9. Gym construction1.121ms, contact210.134ms, local audit193.528ms. Four routes
clear the measured local/contact scope; N1has a demonstrated penetration and remains
blocked. No claim of physical impossibility, optimality or unseen-case success.

Failed intermediate policies172..176remain source-pinned: reversal sign alone,
paired sign changes, displacement angles alone, opposite occupied half-space alone,
and module spacing without an outward return all fail to clear the gym. The same
five inputs were retained throughout.172..178total35dependent constructions across
5independent configurations,19.112s numerical case time, excluding tests/graphics.
178retains a last-case harness stop after its completed contact check: comparing a
dataclass tuple witness with JSON list values falsely reported outcome drift.
180reconciles the already captured reports under unchanged source/geometry hashes;
all5reports exactly match177after JSON serialization, with N1still rejected. That
reconciliation takes0.052s and performs0new solves/audits; the stopped178record remains.

179shows all5frozen final routes, gym initially visible, with15hidden original
material guides and8hidden constraint helpers. The failed N1component highlights
penetrating pieces red.167and171remain hidden intact;4historical sessions, snapshots
and selection are unchanged. Guide sample error<=7.63e-10mm, native guide-point
translation error<=2.14e-14mm. Preparation3.600s, display8.666s,RSS286640KiB;
viewport reviewed.61focused tests, scoped package Ruff lint/format and4changed-file
IDE inspections pass.0native cable attempts/builds/post-build audits; native failure
rate unmeasured and fullQA unrun. Profiles, native builders and production unchanged.
No further routing batch is scheduled. Artifacts:ribbon_fold172..180.

## Optional continuous-angle construction

The next user-directed trial generalizes the remaining construction choices.
`solver.connect(..., strategy=FoldStrategy.CONTINUOUS)` selects it explicitly;
`FoldStrategy.OUTWARD` remains the default measured179construction. This is a
comparison mode, not a replacement justified by shorter paths or broader success.
Both modes retain the same exact target poses, joined material profile,99.6%pinch,
local equal-length metric and mandatory contact gate. No retired discovery runs.

`orientation.orient` factors the endpoint quaternion into two material-plane
rotations with equal/opposite crease banks. A quadratic supplies exact algebraic
roots; complete analytic closure determines their material cost before any contact
check. These are rotation-equation solutions, not a predefined bank of route seeds.
`construct_candidate` accepts `record_candidate` to retain every completed ordered
primitive sequence and its cost. The comparison runner flushes/fsyncs each branch
before evaluating the next. A singular longitudinal roll uses three smaller
derived bends; a pure normal rotation uses its derived two-half-turn factorization.
General rotations no longer require +/-45degree crease directions. Single-fold
unit controls include63degree creases, within the primitive's existing regularity.

`lateral.dimensions` also derives the S-pair's bend angle. For s=sin(bank), bend
angle t, contour width W, radius R and explicit extra runway r, zero-middle-run
lateral displacement is
`(W*s*s + 2r*s*sqrt(1-s*s))*(1-cos(t)) + 2R*s*(t-sin(t))`.
The pi-boundary stationary bank solves the strictly increasing cubic
`2*pi*R*s^3 + 2*(W+distance)*s^2 - distance = 0`.
If that implies a negative middle run, bounded scalar inversions follow the
zero-run family to its material-length stationary bracket. Every inversion is
capped at52bisections; there is no random initialization or contact retry. This
is a local dimension choice within one S-fold family, not proof of a globally
shortest route. Height steering's90degree solution remains the local stationary
choice for sufficiently large offsets;180degree lateral bends can likewise remain
boundary solutions. These angles can arise naturally without limiting the primitive
to an angle grid. Actual height offset is measured from the composed pair and
enters subsequent closure; the old hardcoded4R assumption is baseline-only.

Final183evaluates10mode variants across the same5independent development inputs:

| Input | OUTWARD/default | CONTINUOUS | Contact disposition |
| --- | --- | --- | --- |
| Gym |50.114071mm /7folds|62.196139mm /6folds|Both separated|
| Straight |60mm /0|60mm /0|Both separated|
| Planar quarter |39.676804mm /1|39.676804mm /1|Both separated|
| Spatial roll |68.005317mm /7|77.108416mm /7|Both separated|
| N1 S/lateral90 |40.041258mm /9|27.473537mm /8|Default penetration; continuous unresolved, both blocked|

All10variants evaluated,0unattempted; default lengths and contact dispositions
match178. Each mode clears4/5within the named numerical scope. The generalized gym
and spatial cases are longer, so the original default is preserved. Generalized
gym construct+branch recording2.966ms, contact182.400ms, local audit188.957ms;
case wall383.991ms. Its arrival bends are-124.855/+145.349degrees, with crease banks
-41.578/+41.578degrees; its derived lateral pair selects180degree boundary bends
at31.048degree banks. No shortest-path or generalized physical-validity claim.

181is retained as an unsuccessful intermediate comparison:3/5clear, spatial/N1
unresolved and gym59.195mm. Initial unit checks correctly flag compactness
regressions when continuous geometry was temporarily the default.182clears4/5
after the smaller roll factorization and lateral equations, but gym62.196mm remains
longer. It is therefore kept opt-in rather than weakening the baseline regression.
181..183total20selected mode variants over5inputs,8.362s numerical phase time;
extra exact algebraic roots are subordinate workload, not independent coverage.
Maximum numerical sampledRSS24448KiB. All source plans, ZIPs, branches and failures
remain under ignored artifacts/verification/ribbon_fold181..184.

184renders the5continuous variants, with actual bend/crease angles and default
length comparisons.179is hidden intact for comparison. N1is amber/unresolved,
not labeled demonstrated penetration. Fifteen hidden original material guides and
eight hidden constraint helpers remain, plus4historical sessions with unchanged
snapshots/selection. Guide sample error<=7.58e-10mm, native guide-point translation
error<=2.14e-14mm. Preparation3.273s/display7.762s,RSS618096KiB;viewport reviewed.
84distinct focused tests pass;50affected tests rerun after final shadow-name fixes.
Scoped package Ruff lint/format and6changed-file IDE inspections are clean.0native
cable attempts/builds/post-build audits; native failure rate unmeasured,fullQA unrun.
Original profiles, native builders and production remain unchanged. No further
routing batch or automatic promotion is scheduled.

## Close-endpoint departure direction

The N1 S/lateral90 control originated in160's authored single-conductor circular
calibration, `experiment_ribbon_profile_basics.geometry.compound_s`. Three quarter
arcs place the end at `(3R,2R,R)`, with `R=0.75/0.996*(1+1e-9)`mm: endpoint centres
are2.82mm apart.161retained those poses, later frozen in
`tests/fixtures/ribbon_fold_targets.json`; the original authored path is not supplied
to this solver. This is not a gym-generated layout. The legacy fixture name
“known-feasible” overstates its evidence under the current ribbon rules: circular
profile calibration did not establish the equal-material frame and contact checks.
187therefore displays “N1 S/lateral90 - close calibration endpoints” while retaining
the original fixture identity and coordinates in its evidence.

`steering.signed_distance` now mirrors a backward departure's half-turn pair away
from the opposite cap's coordinate along the departure normal. The actual cap
offset includes the following orientation pieces. Mirroring preserves the pair's
total length and final pose. When backward closure and matching normal signs would
bring the later height run through that departure, height steering precedes lateral
steering. Existing full-profile support spacing and the final mandatory contact
gate remain. This changes construction direction/order, not targets, thickness,
99.6%pinch, material metric, contact budgets or a route-seed bank.

185retains the unsuccessful mirror-only correction: OUTWARD5/5clear, CONTINUOUS4/5;
N1's backward straight and height straight penetrate (zero-based pieces1and7).
Its failed unit expectation and witness remain recorded.186then evaluates the same
5development configurations in both modes,10dependent variants: all complete local
material/cap/G1/pinch/no-lateral audits and the thick-volume separation gate;
0unattempted. Both modes clear5/5within this numerical scope. N1 is40.041258mm/9folds
in OUTWARD and28.333775mm/8folds in CONTINUOUS (previously27.473537mm, blocked).
Other four lengths remain unchanged. N1 continuous construct/branch record4.727ms,
contact275.333ms, local audit209.109ms; complete case501.908ms.186total3.948s,
sampledRSS19360KiB.185and186together examine20mode variants of the same5inputs,
not20independent layouts. Frozen sources, plans, all branches and failures remain.

187renders the five continuous results without new solves; N1 is initially visible,
its first three pieces green to identify the outward departure.184's amber failure
is retained hidden. Fifteen hidden original material guides, eight helpers and all
four historical sessions/snapshots/selection remain. Guide sample error<=7.58e-10mm;
native guide-point translation error<=2.14e-14mm. Preparation3.422s/display8.710s,
RSS630432KiB; viewport reviewed.187's source attributes point to186continuous
cases5..9;184's historical attributes erroneously pointed to baseline cases0..4,
although its displayed geometry and measurements were the continuous results.

87focused tests, scoped Ruff lint/format and all three changed-file IDE inspections
pass. No native cable attempts/builds/post-build audits; native failure rate remains
unmeasured and fullQA unrun. This is not a universal collision guarantee, shortest
route proof or production promotion. Original profile/native builders are unchanged.
No additional batch is scheduled. Artifacts:ribbon_fold185..187.

## First native sweep of the retained close-endpoint case

The user explicitly requested one sweep of187.189uses the same frozen186case9
center guide (2011control points) and the unchanged production
`ribbon_builder._add_section` joined contour: one conductor,1.5mm thickness,
1.8mm overall width, four arcs, area2.1527217276mm2. Both target profiles remain
exact references. The construction is a standard perpendicular sweep with zero
added twist; no guide rail, loft, rerouting, profile thinning or fallback. A rigid
perpendicular sweep does not enforce the diagnostic fold's material map.

One independent retained development configuration: existing numerical evidence
reused,0new solves;1native attempt/1positive-volume solid/0fully audited. Kernel
prediction was unknown. The native call takes41.689881s; setup0.272604s, limited
cap audit0.006098s, host total42.936867s. Volume60.975277mm3. Feature health reports
Unknown (enum5), with no error/warning message; valid solid status is separately
observed and must not be called a healthy-feature certificate.

Both native cap centres match their target within5.56e-16mm, planar normals align
exactly and areas agree. However, end profile roll differs66.626703degrees modulo
180; corresponding target-to-native cap vertex-set error is0.759223mm. Start
vertex error<=1.25e-16mm. Thus native construction succeeds but terminal orientation
compliance fails1/1; interior material lengths, banking/no-lateral bend, pinch and
full-volume contact remain unaudited. This is not a faithful native reproduction
or acceptance of the diagnostic ribbon, nor evidence of route infeasibility.

188is retained as a setup-only failure before any sweep call: an omitted RIBBON
group type rejected the one-line profile settings. Application logs were inspected;
189corrects that setup under a new frozen plan with identical geometry and limits.
188has0native attempts and is not a second independent case or kernel failure.
No native retry occurs. Highest recorded Fusion RSS across setup/build/inspection
is526864KiB; in-flight kernel peak is unmeasured. Limits120s/4GiB with3.8GiB launch
headroom were frozen before execution. Plans, source fingerprints, events and both
outcomes remain in artifacts/verification/ribbon_sweep188..189.

189's single native body starts hidden, then is revealed for inspection with the
exact target end sketch and a roll-mismatch caption.187and188are hidden intact;
four historical sessions/snapshots/selection remain unchanged. Inspection0.851s,
RSS522448KiB; viewport reviewed. No production, profile or solver source changed.
Scoped harness Ruff passes; IDE semantic checks pass, with duplicate-code advisories
between frozen188/189archive copies retained. Application tests/fullQA were not run
for this one-off native operation. No further native attempt is scheduled.

## Historical percentage policy

This is the geometric rule clarified with the user's **Macaroni demo v1**. It
replaces the historical `reach / 0.78` and `3.1D` radius restrictions for new
percentage-policy routing experiments. Those historical records remain legacy.

For a circular section with thickness/diameter `D`, half-thickness `h = D/2`,
path radius `R` and allowed fraction `p`:

`utilization = h / R`, `inside radius = R - h`, and `utilization <= p < 1`.

The demo has `R = 25 mm`, `h = 24.9 mm`: utilization is 99.6% and inside radius
is 0.1 mm, or 0.4% of R. The configured default is 99.6%; it is adjustable and
does not represent a material/strain rating. Exactly 100% is singular and rejects.

## Historical developable-sheet assumption

The archived compatible chart uses perpendicular unit directors T and W, normal
`N = W × T`, centre progress `c`, tangent turn `b`, ruling slope `eta`, and its
parameter derivative `g`. Its nominal thickness envelope is:

`X(u,q,v) = r(u) + q*(W + eta*T) + v*N`, with `-D/2 <= v <= D/2`.

Material-lane progress is `s(q) = c + q*g`. The chart's director equations give
the normal-offset volume Jacobian, up to orientation:

`J_thickness(q,v) = s(q) - v*b*(1 + eta²)`.

Therefore the coupled local pinch utilization is:

`h * |b| * (1 + eta²) / min_q(s(q))`.

The turn bound uses the configured p. Width enters through material progress,
not an orientation-independent enclosing full-width radius. The factor
`1 + eta²` accounts for maximum principal curvature of this developable surface;
checking only the three path curvatures would miss it. Circular tubes use their
perpendicular circular sections instead and have no ruling-slope factor.

At the same material station, ideal path radii are `R(q) = s(q)/|b|`. The red
reference radii use `s(q)/b_allowed`. Both vary linearly across symmetric material
offsets, so the centre lies between A and B. The circles follow the selected
station; independent worst points are not mixed into a new-policy triplet.

## Independent inspection and limits of the evidence

`inspection/pinch_geometry.py` obtains principal curvatures from first and second
fundamental forms of the frozen cubic ruled surface, independently of the chart's
eta/J expression. It checks three guides plus two interior width samples, at four
fractions of every cubic. It retains pinch/order violations without repairing the
interpolation. A 65-point graph is a separate display sample, not the audit grid.

This establishes sampled local thickness regularity for the nominal envelope.
It does not establish global self-clearance, the unspecified bonded outer contour,
elastic equilibrium, native construction or complete physical acceptance.

New seed lengths use the percentage rule's half-thickness scale. They no longer
inherit the legacy reach/ruling length allowance. The solver still fits endpoint
poses; this change does not add a shortest-route objective or prove loops necessary.
