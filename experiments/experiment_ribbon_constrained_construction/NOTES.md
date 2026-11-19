# Simultaneous constrained construction prototype

Unselected experiment, checkpoint 3387. This package does not repair an existing
route and is not called by the gym or production solver.

The existing guide-feature constructor fits one straight allocation per exact
rotation branch, prioritizing guide-site error before length, then checks hardware
and contact. A rejected selected allocation cannot exclude other allocations of
that same branch. This is distinct from choosing the correct signed fold branch;
solving the first deficiency does not establish the second.

For fixed fold angles, banks, radii and profile, endpoint position is affine in
nonnegative straight lengths. A fold's intrinsic shape is fixed and its translation
is affine too. Thus an explicitly chosen support-separation arrangement gives
linear constraints. The new kernel solves those supplied constraints together:

`minimize sum(straight lengths), subject to endpoint equations and clearance rows`.

Clearance faces participate in the active intersections. This includes optima
inside edges of the old closure-only allocation polyhedron, which post-filtering
its original vertices would miss. This is finite algebraic active-set enumeration,
not coordinate guesses or a stored route bank. It has at most seven coordinates
and an explicit active-set allowance. Numerical rank/residual gates are internal
robustness dependencies, not revised physical acceptance tolerances. `complete`
means completed enumeration for the supplied linear problem, not global route
optimality or a physical certificate. Interrupted minimization remains incomplete;
no checked vertex is not a proof of geometric infeasibility.

`support.py` derives whole-fold guidance from the existing analytical occupied
width/thickness projection. World-dependent outward-rounding margins prevent
claiming that its transported intervals are independent physical certificates.
The resulting geometry must undergo independent contact/hardware checks. The
separating axis is retained with each support to reject mismatched projections;
the two sides of a hardware exclusion are alternatives, not simultaneous rows.

Unfinished: straight-piece support constraints, legitimate adjacent material-cap
handling, principled separation-arrangement selection and signed bend branches,
end-to-end constructor integration, complete physical checking and fresh gym
validation. Fixed-fold allocation cannot reverse F4. No success on E is claimed.
No source of a retained failure is used as a production decision rule.

`DiagnosticClock` implements the November 18 CPU policy for this new prototype:
0.4 CPU seconds is a measured target; an overrun does not raise. A separate finite
wall deadline and caller memory/source/cancellation guards still stop work. Old
gym/recovery CPU-stop behavior has not been modified or silently monkey-patched.

Verification: `uv run pytest tests/test_ribbon_constrained_construction.py`, plus
Ruff lint/format and IDE inspections on this package and that test. Tests cover
length-optimal coupled inequalities at three scales, inconsistent dependent rows,
finite-work incompletion, geometric fold-support translations including zero
straight slots, and CPU-warning versus wall/host-stop behavior. These are
analytical mechanism checks, not independent complete-ribbon geometry coverage.
No native builds or new Fusion scene are part of checkpoint 3387.

## Checkpoint 3388: one retained E input, trunk-only geometry demonstration

The user authorized one diagnostic on the existing isolated Git branch. Added
`envelopes.py` to declare whole-fold and two-cap straight-prism support alternatives
against both connectors and nonneighbor logical material parts. All constraints
are prepared before allocation, with intrinsic-frame support axes. Immediate
neighbors remain outside this conservative construction relaxation and are fully
included in the independent final contact audit; omission gives no clearance.

`disjunction.py` explores these declared alternative halfspaces with one shared
4096-active-intersection / 64-node allocation. All exact bend roots come from the
existing endpoint/guide rotation factorization, not saved route angles or fold
sign permutations. Within an arrangement, the linear objective is total straight
length; no guide-error priority, witness-created constraint, post-hoc bend repair,
added event or physical length cap enters this constructor. Finite search order
can still produce poor overall length and incomplete branch coverage.

One run on E004/057 N3 used endpoint/profile/radius inputs only. Four algebraic
roots were derived; root (0,0) consumed 4096 intersections over57nodes and returned
one supplied-constraint allocation before exhaustion. The other three roots were
unattempted. No root was completely explored. The initial construction receipt's
`roots_completed: 1` counts a returned allocator call, NOT a completed root search;
its `work_limit` disposition is authoritative. Preserve that receipt and this
explicit clarification. No automatic retry or enlarged budget followed.

The retained route is295.6961095mm for a14.4151078mm endpoint chord. A separate
full occupied-material self-contact check reports separated (523pairs), and both
finite connector proxies are clear (28cells), including adjacent material checks.
Cap position error1.38e-13mm; frame-vector error5.27e-16. This is a useful clearance
result with an excessive detour, not a reasonable-shortest route, proof of correct
F4 sign selection, complete physical qualification, native BRep or fresh validation.
Whole-piece conservative envelopes and depth-first branch ordering are remaining
limitations. Root-first work exhaustion prevents a length comparison across roots.

Measured CPU: preparation.126388s, allocation.175007s, independent audit.113431s;
sum.414826s, excluding cold import/startup and graphics. The measured construction
subtotal is.301395s; including the audit exceeds.4s by.014826s and is retained for
inspection under the user's test policy. Do not label this an overall timing pass.

The Fusion scene is one amber sampled material mesh with A/B and E-NEW-F1..4
labels, grey proxies and an explicit excessive-detour warning. Ownership
ribbonDiagnostic/owner=resume3388 replaces the verified3385/3386five-stage scene;
no persistent BRep/sketches or hidden old geometry. Receipts and final viewport
are under artifacts/verification/resume3388/.18focused tests pass; changed code
Ruff/format and IDE checks clear. Old gym/selected solver behavior is unchanged.

## Checkpoint 3389: length-bound frontier comparison — unsuccessful

One separately authorized diagnostic retained the same E input, support constraints,
4096-intersection/64-node limits and2wall-second construction allocation. New
`frontier.py` compares all root endpoint relaxations first and maintains a shared
best-first frontier of separation arrangements. Priorities include fixed fold
material plus diameter-scaled optimized straight length. Children inherit only
completed parent bounds; incomplete LP costs cannot establish a pruning bound.
The old depth-first implementation is preserved for historical provenance and is
not modified or selected by this change.

All four endpoint-only roots were measured. Root0produced a37.537907mm relaxation;
roots1..3returned `no_checked_vertex` under the unchanged fixed-angle affine model.
That is not a physical infeasibility proof. Search then reached64LPnodes/2320active
intersections with no allocation satisfying all supplied constraints. Root0used61
nodes; the other roots used one each. No work/time limit was expanded and no replay
followed. The visible37.54mm route is the rejected endpoint-only inspection point,
NOT a feasible or improved solution from this traversal.

Independent checks confirm actual self-penetration (201pairs, pieces1/3) and End B
proxy intrusion (16cells, piece4). Both endpoint poses close: position error3.0e-14mm,
frame-vector error5.07e-16. Numerical timing: preparation.122745CPU, allocation
.097246CPU, audit.077501CPU, named-stage sum.297492CPU seconds, excluding startup and
graphics. LocalRSS32672KiB/minimum56%free; displayRSS439392KiB/minimum38%free.
No native construction, endings, fresh validation or full physical qualification.

This trial does not improve geometry reliability or establish that ordering fixes
F4. It shows the fixed-angle alternative roots did not furnish usable closed
allocations here, while exploring the sole checked root more broadly did not reach
a feasible arrangement in the finite pool. Do not continue traversal-only tuning
or silently enlarge its budget. The remaining construction question is coupling
bend/guide orientation choices with position and clearance from the outset; that
requires a separately frozen design/test, not another post-hoc sign correction.

Fusioncurrentowner=resume3389, numbered1rejectedmesh/A/B/E-BF-F1..4labels. Red
identifies involved material pieces, not penetration extent; crosses/leaders locate
exact witnessed intersections. Prior3388owner is hidden numbered2as the sole
immediate comparison; both are in the same scratch with0persistentBRep/sketches.
22focused tests pass, changed code Ruff/format and6IDEchecks clear. Executed runner
and packet snapshots retained before import/format-only cleanup. Final receipts
under artifacts/verification/resume3389/. No selected gym/production changes.

## Checkpoint 3390: displacement-directed exact factorization — closure declined

The user clarified that backwards means the broad spatial turn, not merely the
sign of a local fold angle. A retained-direction readback shows F1/F2 progressively
improving projection on the A-to-B chord and F3/F4 worsening it; both prescribed
terminal tangents themselves have negative chord projection. Therefore requiring
every bend to increase that projection would conflict with the input. No such
new physical acceptance rule was added.

Source inspection found a concrete missing construction input: the balanced-bank
rotation factorization matches frame rotation without using stage displacement.
`directed_orientation.py` instead derives an exact position-directed factorization.
For relative quaternion q=(w,x,y,z), first factor p=(a,b,c,0), its intermediate
forward tangent is h=(1-2c²,2bc,-2ac). The second factor's crease-plane condition
is a*z-b*y+c*x=0, equivalently (x,y,z).h=x. Feasible unit h lie on a circle with
center x*v/|v|² and radius sqrt(1-x²/|v|²), where v=(x,y,z). Projecting the desired
stage displacement into this circle's plane gives the maximizing heading directly.
Reconstruct p=(-h.z/(2c),h.y/(2c),c,0), then p^-1*q. No sign trials, added events,
angle grid, target adjustment or post-hoc reversal is used. Degenerate exact
constructions remain explicit; unsupported longitudinal creases raise.

Nine analytical tests pass: known asymmetric fold pairs recover their feasible
requested intermediate heading; alignment dominates both legacy balanced roots;
proper rigid transformations preserve local factors; pure longitudinal degeneracy
retains the exact existing three-fold construction. Initial five test failures
were Vector3-versus-pytest.approx comparisons, not geometric mismatches (components
agreed around1e-15); replaced with vector-distance checks at the same1e-10arithmetic
tolerance. This numerical rotation-contract tolerance is not physical acceptance.

One frozen E diagnostic then changed only this initial orientation construction.
The intermediate stage alignment dots improved from[-.509365,-.383400] in the
previous selected balanced branch to[.999939925,.999939925]. However, the resulting
single fixed-angle chain had no checked nonnegative endpoint closure. Only10active
intersections/oneLP were needed; no clearance search, route output, physical audit,
native construction or display change followed. Preparation.033803CPU/.033807wall;
allocation.000472CPU/.000472wall. LocalRSS27648KiB/minimum54%systemfree.

A separate read-only algebraic explanation reconstructed those exact factors
without an allocation retry. An exact rational dot-product certificate on the
stored floating affine columns finds an axis for which every nonnegative straight
ray projects nonnegatively while the required displacement projects negatively,
even including the original1e-8component residual allowance. This excludes THIS
fixed-angle allocation independent of length/CPU; it does not prove the physical
layout infeasible. Full receipt and rational coefficients:3390/explanation.json.

Outcome: FAILED construction, not a corrected ribbon. Direction alignment and
orientation matching alone do not guarantee positional closure. Do not pursue
another sequential heading-first/length-second tuning loop. The derived heading
circle supplies the missing continuous construction freedom, but its choices must
be solved jointly with nonnegative lengths and clearance before a new trial.
No claim that all four backwards bends, shortest-path behavior or generalization
are resolved. Existing3389rejected scene and3388immediate comparison are unchanged.
All31related focused tests, changed-file Ruff/format and IDE checks are recorded
under artifacts/verification/resume3390/. Selected gym and production remain unchanged.

## Checkpoint 3393: existing added-stage mechanism — complete route, rejected

The user requested exercising new bend events with new angular and crease freedom,
not simply reordering existing bends, and keeping complete A-to-B routes as the
diagnostic output. The proposed natural placement-and-trimming construction is
recorded as an alternative, not selected or implemented. Passing through B would
still require its full ordered frame; trimming alone cannot correct orientation.

This checkpoint changes no maintained solver implementation. One bounded retained
E diagnostic exercises the existing `Frames.inserted_parameters` and `chains`
entry points with the unchanged affine clearance frontier. The cumulative-turn
rule adds a guide site at0.095654452 beside0.5, deriving eight exact algebraic roots
with six folds each. Angles/banks are newly derived, not permuted old bends. Within
each root they remain fixed during allocation; this is NOT the missing continuous
joint angular/clearance solver and does not establish that six bends suffice.

All eight endpoint relaxations were attempted. The shared4096active-intersection
pool exhausted at39LPnodes, with zero allocations satisfying all supplied
exclusions. The retained26.554763747mm endpoint-only relaxation closes both frames
(position8.79e-15mm, vector3.61e-16), but independent full-material checks witness
self-penetration on actual pieces3/5(191pairs) and START connector intrusion on
piece1(8cells). The hardware audit stops at that witness; it does not establish
End B clearance or an exhaustive violation inventory. The first four fold angles
change while the final pair's angles remain the prior midpoint-to-B factorization.
Extra guide stages alone therefore do not resolve spatial placement/clearance.
No automatic station/sign retry, larger budget, native build or fresh credit.

CPU preparation.538129s, allocation.304494s, independent audit.091607s; named-stage
sum.934230s, exceeding.4s by.534230s, excluding startup/graphics. The CPU-warning
policy allowed output; this is not a timing pass. Local minimum56%free/RSS54912KiB;
display minimum58%free/RSS647488KiB. Four artifact helpers pass Ruff/format and IDE
inspection. No application tests repeated for reuse of unchanged solver machinery.

Fusion now owns visible resume3393 six-bend rejected mesh(10320triangles), labels
E-6-F1..6/A/B and exact failure markers. Red denotes involved material, not full
penetration extent. The sole hidden immediate comparison is resume3389four-bend
rejected route. Exactly owned obsolete resume3388was retired after preserving its
receipts; no BRep/sketches exist in either retained component. Separate callback
verified both owners and idle document8aea1905-1e8b-4f6f-bd5f-6107d1a26d7e.
Receipts/viewport: artifacts/verification/resume3393/. No production promotion.

Checkpoint3392 inspected the retained3389complete route through the shared Ledger
and four distinct instant-camera Fusion exports, without a probe/solve/audit.
Initial animated exports repeated one frame; instant exports are authoritative.
Checkpoint3391unclosed preparation was cancelled before any live Fusion mutation.

## Checkpoint 3394: two outward terminal approaches — clear, excessively long

The user authorized testing outward unwrapping before replacing route discovery.
New unselected `terminal_approaches.py` derives a common bridge direction between
the existing endpoint guide's outward handles A+tA*chord/3 and B-tB*chord/3. Its
ordered width bisects independently transported endpoint widths; degeneracy stays
explicit. Existing exact rotation roots factor A-to-bridge and bridge-to-B. New
whole-fold support rows keep each terminal turnaround on its own open mating
halfspace, using +tA and -tB while preserving A-to-B material order. Both terminal
frames and corridor/clearance rows are solved simultaneously in the existing
affine allocation. B is constrained by fixed endpoint equations, not post-build
reanchoring. No random heading, angle/sign retry, radius growth or target motion.

These outward corridors are a restrictive construction choice, not an additional
physical rule. The chord/3 guide-handle and width-bisector conventions do not
discover arbitrary routing corridors. Angular factors remain fixed during length
allocation; a continuous coupled angle/length/clearance solver is not implemented.
Six analytical tests pass: exact ordered terminal rotations at three scales,
proper rigid covariance, full-width/thickness sampled support containment with
the correct B outward sign, and explicit ambiguity/resource failures. Tests do
not establish physical compliance or fresh-layout generalization. Focused Ruff,
format and six changed-code IDE inspections are clear. No full QA run.

ONE historical E diagnostic, four roots/fourfolds each. All four endpoint/corridor
relaxations were attempted; only root0returned a checked allocation. Its initial
49.615928mm corridor relaxation is NOT clearance-certified or displayed. The
shared4096intersection pool exhausted at56LPnodes after retaining a376.213037mm
allocation satisfying all supplied corridor/exclusion rows. No global or even
completed supplied-model minimum is claimed; other fixed-angle roots returning
no_checked_vertex do not establish layout infeasibility. No limit enlargement.

Independent full occupied-material audit on that retained376.213mm route reports
self-contact separated497pairs, both finite connector proxies clear24cells,
cap position4.78e-13mm and frame-vector4.92e-16. This opens the knot under the named
checks but uses an excessive detour for a14.415108mm chord: it is NOT a reasonable
short usable solution, native result, full physical qualification or fresh pass.
Preparation.114767CPU + allocation.186902CPU + audit.106187CPU = .407856seconds,
.007856over .4target, excluding startup/graphics. CPU warning preserved output.
Minimum systemfree55%/localRSS33264KiB; displayfree56%/RSS468512KiB.

Fusion visibleownerresume3394 is the complete outward route, labelsE-O-F1..4,
explicit excessive-detour/no-fullqualification warnings and0BRep/0sketches.
Sole hidden comparisonresume3393 is the preceding sixfold rejected knot.
Exactly owned obsolete3389was retired after receipts; no unrelated geometry
changed. Separate callback verifies same idle document and2owned graphics groups;
viewport.png reviewed. Receipts: artifacts/verification/resume3394/.
No native/endings/probe/newvalidation/production promotion. Next unresolved issue
is compact spatial discovery with changing angular placement, not more straight
growth or another guide-stage insertion under the same fixed-angle construction.

## Checkpoint 3395: soft waypoints and movable hinges — no accepted step

The user authorized trying waypoint-guided kinematics. New `waypoints.py` supplies
soft position balls at the original outward guide handles, with radius equal to
profile half width and ordered material landmarks after the departure hinge group
and before the arrival group. Intermediate orientations are free. `Hinges` reuses
the finite-radius material model's angle/bank/straight coordinates, fixed radii
and material order, but uses full ordered-frame rotation residuals and does not
lock fold signs. Removed-fold landmark ambiguity is explicit. A free ball-joint
swivel or arbitrary ribbon strain is not introduced.

New `waypoint_solve.py` tests local mobility of an ALREADY COMPLETE route. It does
not plan an initial route, insert required hinge events from arbitrary waypoints,
or search different hinge counts/corridors. Starting here from3394is a selected
diagnostic, not fresh route discovery or generalization. Its objective is squared
radial excess outside the two waypoint balls plus squared complete material
length, normalized by immutable initial length. Finite joint sensitivities drive
a projected gradient with six cap constraints; existing bounded Newton retraction
restores actual ordered caps before certification. Every accepted proposal needs
full occupied-material self-contact and both connector certificates. Clearance
currently VETOES proposals; it does not yet steer the projected joint direction.
Certificates concern individual configurations, not swept motion between them.

Six analytical tests pass: free fold/crease coordinates with fixed geometry
identity, nonzero half-turn residual, zero preference inside a waypoint ball and
explicit landmark loss, objective derivative consistency, and actual closed-cap
motion with both accepting and rejecting certificate stubs. Stub tests verify
control flow, not physical clearance. Ruff/format and all seven changed-code IDE
inspections clear. No broad/application QA or production integration.

ONE E diagnostic spent1action/4Newton/2closedproposals,0accepted. Full proposal
313.957822mm versus376.213037mm baseline, score.397825436 versus.563236379;
half proposal345.032962mm/score.476703262. Both exact closed proposals had actual
straight0/straight4penetration, using376+330=706sharedpairs. Hardware was unattempted
inside the run after those self-contact failures. Original complete clear baseline
is the solver result; it receives no new pass/progress credit. Geometry/certification
.100562CPU/.100659wall, minimum57%free/RSS26480KiB; no CPU/work/resource exhaustion.
The ordinary two halvings failed; no retry or allowance expansion followed.

The FIRST chronological closed proposal was separately frozen for inspection,
not substituted for the result. Its one independent audit confirms the same
0/4penetration376pairs AND EndB intrusion onpiece6in54cells; caps2.65e-12mm and
frame7.89e-16. Audit.100536CPU/.100546wall, min53%free/RSS26160KiB. Named-stage sum
.201098CPU excludes startup/source-freeze/render. No native/endings/fullqualification.

Fusion visibleownerresume3395shows only this rejected313.958mm complete proposal,
E-K-F1..4/A/B, red involved material/witnesses, green soft-waypoint regions and
preference lines explicitly NOT material. Original clear3394is the sole hidden
comparison; obsolete owned3393retired after receipts. Two0BRep/0sketch components,
same idle document. Displaymin49%free/RSS308816KiB. Initial black labels had poor
contrast with current dark background; a separate presentation-only callback
changed text/leader colors, leaving material unchanged. Authoritative screenshot
viewport-contrast.png; contrast-result.json preserves this display-only provenance.
Receipts under artifacts/verification/resume3395/. Selected361/production unchanged.

This proves bounded coordinated kinematic motion is available, not that it yields
a usable route. The immediate missing mechanism is clearance constraints in the
joint-motion equations. More attraction/shortening steps would repeat collision,
and arbitrary waypoint/hinge discovery remains a separate unimplemented capability.

## Checkpoint 3396: clearance inside hinge motion — restoration declined

User authorized one clearance-guided diagnostic on the same complete3394baseline.
`waypoint_motion.py` extracts the prior cap-only strategy without changing its
admission/work rules. `clearance_planes.py` derives full-width/thickness moving
projection bounds from current material and finite connector proxies, using
intrinsic axes/cross products and stable ordered material regions. For each
nonneighbor material pair or material/box relation it retains the largest existing
signed separation; the thirteen closest supported relations fit the existing
sixteen-update inequality projector. Own mating straights use connector-outward
planes. Unsupported and capacity-omitted relations remain explicit audit duties.
No saved collision coordinates, specimen-specific pair list or angle trials.

`clearance_motion.py` projects the unchanged waypoint/length gradient with six
terminal-frame equations, selected clearance rows and coordinate bounds jointly.
The reference translation is algebraic only; no material is placed at a potentially
out-of-domain reference. The SAME selected planes remain in bounded nonlinear
restoration. Actual ordered caps and nonlinear plane bounds precede independent
contact/hardware certification. Scalar support extrema can be nonsmooth; linear
feasibility is never a physical certificate. The tighter existing mating guard
supports contact arithmetic; the1e-8mm support guard is internal bound consistency,
not a change to inclusive0.01mm dimensional acceptance.

ONE source-pinned E diagnostic: all46guidance relations supported, thirteen selected
and33capacity-omitted. Selected rows include the prior failing material0/4relation
and both own-terminal mating relations. One joint descent direction was obtained,
but BOTH permitted proposal scales failed bounded nonlinear restoration:
1action/6corrections/2proposals/0accepted, no_accepted_step. No closed proposal
reached the independent audits:0contactpairs/0hardwarecells. The unchanged clear
376.213037mm baseline remains the result; no new pass or improvement credit.
Geometry-stage.132376CPU/.132389wall, within.4CPUtarget/2wall; minimum56%systemfree,
maximumsampledRSS26960KiB. No resource stop, retry, budget expansion, native build,
new display, fresh configuration or full physical qualification.

This narrows the immediate failure to joint nonlinear restoration; it does NOT
prove physical infeasibility, insufficient hinge count, or a particular numerical
cause. Current receipts retain the selected planes and proposal dispositions but
not intermediate correction vectors/residuals, so they cannot distinguish a
nonsmooth derivative, working-set decline, conservative-plane restriction or
per-proposal correction exhaustion. Preserve this failed attempt. Before another
geometry experiment, improve stage-level evidence rather than changing limits or
adding route events without that distinction. The viewport is still3395's rejected
313.958mm proposal, not new3396geometry;3394remains its hidden comparison.

Nine focused analytical tests pass (six existing kinematics, three new projection,
relation-accounting and nonlinear-admission checks). Initial new test incorrectly
required unsupported relations on a separated analytic fixture; corrected to count
ALL relations, without changing solver behavior. Ruff check/format and six changed
code/runner IDE inspections clear. Historical3395solver source archived before
strategy extraction; old receipts unchanged. Production/selected361/852unchanged.
Receipts: artifacts/verification/resume3396/. Goal2979 remains unachieved.
