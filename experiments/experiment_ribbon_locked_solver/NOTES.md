# Selected material solver and gym integration — 2026-11-01

## Material solver v2 gym promotion — 2026-11-02

User explicitly authorized adding the measured431method as solver v2 for gym
testing. `versions.py` advertises `guide-material-v2` as default and preserves
`joint-material-v1` as a selectable comparison. V1's numerical construction and
cleanup policy remain; its aesthetic sequence is shared through `smoothing.py`.
The source bundle now pins174files and both method identities. The former160-file
lock and exact source bytes are retained under ignored
`artifacts/verification/solver_v2_promotion/source_v1/` with `.frozen` suffixes.
Old jobs retain their original pins; do not silently rebuild them against v2.

V2 runs the421/430two-stage guide-frame tight constructor, at most two contact
certificates and four seconds for first construction. No extra-feature insertion,
historical route/v1 fallback or first-phase radius growth/sliver repair. Defaults:
smoothing0%, first-pass optimization on, optional material UV off. The optimization
toggle switches bounded monotonic branch selection versus original midpoint
selection; its UI description changes with version. It does not invoke v1's
contraction pass. Fusion's measured point tolerance is frozen in each job and
forwarded to v2's tiny-straight rejection gate. Unknown/malformed versions and
controls fail before launching work.

Optional smoothing retains the original radius/merge/layout/merge sequence and
one0..10%shared material allowance; v1 defaults5%. V2's unchanged certified first
pass avoids a redundant contact audit. Changed aesthetic geometry receives a fresh
conservative certificate. Optional UV metadata and native attribute storage remain
separately timed and create no texture/appearance. Joined profile, conductor/face
ordering and native fidelity gates are unchanged. Gym Solve and build, numerical
cancellation, transparent scaffold controls, counters, progress log, clear geometry
and recorded-result selection remain available. This is development gym promotion;
ordinary product harness routing is unchanged.

Installed owned workspace `gym433`, preserving the current draft and prior owner.
432installation stopped before any solve/build: stale loaded gym renderer lacked
the current prepath keyword. Host log confirmed it;433coherently reloads graphics,
viewer and workspace dependencies, same30s/4GiBscope, completes3.985820s. No
application-code workaround or source/tolerance relaxation. All setup failures
remain recorded.434's optional nonexistent refresh helper raised after its one
successful dispatch launch; dispatch had already sent state, so normal palette
polling completed that same worker/build, without another launch. Its script
transaction also invalidated a cached context graphic;435display selection reports
the deleted handle.436resets that invalid cache and redraws the same immutable
result,0solves/builds. Original draft and older native geometry remain retained.

434smoke: **1planned/1numerically evaluated/1native attempted/1built/1named-fidelity
audited/0full physical audits**, same examined gym08, not a new holdout. V2 reproduces
33.150386mm. Route/checks.714317s, numerical CPU.606925s, native generation1.222210s,
generation counter1.936527s; separate fidelity audit20.987426s, native operation
23.723710s, sampled peak579760KiB.226faces,7840surface points,434seam chains,
0seam flags, max surface error6.965238e-9mm. No v1 native comparison or positive
smoothing/native UV smoke in this phase. Complete rule compliance remains unmeasured.

82focused tests pass, including12new v2 dispatch/toggle/coordinate/tolerance cases;
Ruff check/format pass on affected packages/tests and viewer HTML is IDE-clean.
IDE checks cover all changed Python files; pre-existing duplicate-fragment weak
warnings remain in unchanged adapter sections, plus the documented broad native
fail-soft exception. No new IDE errors/findings in v2 implementation/tests. Full
repository QA and standalone type checker were not run. A native screenshot shows
v2 heading, selector, matching completed counters and optimization control; backend
version selection is unit-tested. Optional live keyboard switching hit a computer-
use transport timeout, so no extra comparison solve was launched. Evidence and
all setup/display dispositions: `artifacts/verification/solver_v2_promotion/`.

Four fresh complete gym configurations planned and numerically evaluated in314;
two natively attempted and built, **one passed the named fidelity checks and one
failed**. The other two remain natively unattempted after the stop. Zero complete
physical audits. This is a locked development baseline, not production promotion
or a claim that arbitrary endpoint configurations are solved reliably.

## Selected policy and controls

The user selected the joint first pass and the approved composite aesthetic pass.
`joint-material-v1` constructs from immutable endpoint poses, conductor dimensions
and the existing pinch radius floor. No successful historical route is required.
It derives finite direct/guide-middle orientation families, jointly allocates
nonnegative travel and radius growth, and checks contact in length order. Six
families and at most twelve contact attempts retain the existing finite bounds.
An unsuccessful construction is unresolved, not proof of infeasibility, and has
no retired-search fallback. A guide ranks candidates; global optimality is unproven.

The second pass preserves the selected composition: radius easing, compatible
turn merging, layout-scaled angle/bank/radius/runway easing, then compatible merging.
Fixed ordered caps, equal local material increments,99.6%pinch, no lateral bending,
thick self-contact separation and the existing joined profile remain unchanged.
Gym objects are visual context, not avoidance boundaries.

`Settings.smoothing_percent` accepts finite numbers from0to10, default5. It is a
maximum percentage of extra material length relative to the first pass. All stages
share that one ceiling; growth is not compounded. Zero skips the entire second
pass. More allowance permits smoothing but does not guarantee monotonically better
visible results under finite contact/iteration bounds. Straightaways are runway.

`Settings.material_uv` is optional, default false. True retains continuous material
coordinates `U=s/total_length`, `V=(q+half_width)/(2*half_width)` and thickness b,
plus the exact route, ordered profile and per-native-face source records. This
creates **no textures or appearances**. On the passing native case, all86face
attribute records and the component map read back exactly, with no new appearance
or geometry revision. Numerical metadata creation took0.208..0.294ms across314;
Fusion attribute storage/read-back took0.450s on its one fully verified UV case.
These optional costs are recorded separately from geometry generation.

These are application material coordinates. Fusion's renderer charts remain
read-only and face-specific. Later optional appearance baking uses the existing
verified physical inverse in `experiment_optional_appearance/material.py`; see
that experiment's notes for appearance-family limits and texture creation costs.
Endcap mapping differences remain accepted. This does not promise writable native
UV charts or reproduction of arbitrary procedural shaders. Per-conductor exterior
appearance assignment remains supported through the unchanged profile face order.

`solver-lock.json` hashes the selected numerical/native/coordinate implementations
and shared diagnostic/gym sources. Workers and native launches reject source drift.
Review changes, complete checks and explicitly write a new lock **before** freezing
a new run plan; never update a lock to continue an in-flight run. Historical
comparison `joint_route.solve` keeps its previous fallback contract; the new
endpoint-only `construct` entry point does not invent a provisional route.

The maintained `fidelity_base.py` copies the221audit, removing the selected
runtime's dependency on ignored artifact source. The existing strict actual-trim
adapter is shared through `audit_with`; measurement gates and tolerances are
unchanged. No native body repair or profile change is included.

## Frozen gym evidence and retained failures

All four inputs were generated and pinned before outcomes, with default5%smoothing
and UV enabled. Seeds2026110101..104; standard void/zone300%except case4void900%,
zone150%. Each phase allows four cases,120s/case,600s total and4GiB RSS, with3.8GiB
native launch headroom. Source/resource/API/harness/native-fidelity failures stop
the affected phase; no retry or search enlargement is automatic.

The initial313batch stopped on case1before native work: `Boundary.half_width_mm`
used `(N+.2)*D/2`, whereas `FoldRoute` used `N*D/2+D*.1`. At D=.75 these differed by
one floating-point step, rejecting a boundary sample. The correction uses exactly
the established route expression; no physical dimension or tolerance changes.
Fractional-diameter analytical regressions cover.75/1/1.5/3mm.313retains its failed
first case and three unattempted cases.314is a new source-pinned plan using the
same four fixed inputs; these repeats are four configurations, not eight.

| Case | N / D mm | Numerical | Native | Named fidelity | Solve CPU s | Solve wall s | Generation s |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| gym-cold-1 |1 / .75|pass|built|pass|.561|.561|.813|
| gym-cold-2 |3 /1.5|pass|built|failed|1.256|1.259|.902|
| gym-cold-3 |6 /3|pass|unattempted after stop|unmeasured|1.846|1.863|unmeasured|
| gym-cold-4 |3 /1.5, larger layout|pass|unattempted after stop|unmeasured|1.449|1.450|unmeasured|

CPU uses the host worker's `process_time`; native generation uses wall time for
translation+definition+kernel. This does not measure Fusion CPU utilization.
Full numerical phase5.713s, native phase17.485s. Case1audit7.633s is development
verification overhead and excluded from generation. Solve-versus-build timing goal
passes case1and misses case2; cases3/4comparison remains unmeasured. Numerical
solver timing includes optional metadata and final numerical checks; worker totals
also include diagnostic snapshot construction. No full physical audit was run.

Case2failed surface membership on face79, region `before`, fractions.33/.50/.71
at v=.03. Pointwise positional errors there are2.48e-15..4.61e-15mm; overall sampled
maximum6.365e-9mm. The native trim checks still rejected these points. Do not
misreport this as a proven trajectory deviation or relax the membership gate.
The body is hidden and partial measurements retained. The host log was inspected;
the operation completed normally. Root cause remains unresolved. Cases3/4were
not built. Earlier308calibration surface-distance failure remains separately
unresolved; it is not replaced by this different trim-membership failure.

Evidence: `artifacts/verification/solver_gym313` and `solver_gym314` retain plans,
sources, exact inputs/routes, every proposal, timings, partial native audits and
dispositions. There were no expected-invalid controls and no feasibility oracle.
After examining these results they are development regression cases, not untouched
holdouts. One passing case does not establish general reliability.

## Gym use and boundaries

`gym.install(owned_directory, configured_python, document_id, scene)` installs a
retained workspace in the explicitly owned idle Fusion design. Open the gym layout
in diagnostics, then use **Selected material solver v1 → Solve and build**. Changing
the gym alone never launches a solver. Smoothing and UV controls are frozen with
the endpoint/gym payload before the worker starts. Native construction follows
numerical acceptance once; native failure remains visible as a failed disposition.
Cancellation is cooperative during numerical work, not an in-flight kernel abort.

The ordinary diagnostic controller still rejects retired procedures. The selected
controller advertises a separate `active_solver` contract; historical archives
remain replayable. No production harness command, schema or material profile was
replaced. Complete physical compliance, containment, optimality, generalized native
reliability and arbitrary UV rendering remain outside the measured evidence.

The initial315palette round-trip reached the selected worker but its configured
SDK inherited Fusion's embedded `PYTHONHOME`/`PYTHONPATH` and failed interpreter
initialization before numerical work. Evidence and log are retained. The launcher
now removes those two variables; the controller regression verifies that boundary.
A separately pinned316integration run repeats only314case1with UV disabled:
numerical CPU.559s, native generation.863s, named fidelity pass. No UV file or face
attributes are created in this mode. This repeat adds no independent coverage.

Selecting its result then exposed an existing diagnostic-only normalization bug:
very short cubic intervals have tiny raw acceleration despite finite curvature.
The generic `unit` cutoff rejected their bend witnesses. The witness now normalizes
the already positive finite curvature normal by its measured magnitude, preserving
the original curvature threshold. Analytical tests retain the same parabola's
radius/plane at parameter intervals1and1e-7in two spatial orientations. Display
recovery317freezes new source pins before refreshing the **same** completed316body;
its revision is unchanged. No solve, native build, tolerance or historical manifest
is altered by this recovery.

The live316workspace remains retained in the owned design; its accepted body and
selected diagnostics are visible. Gym/diagnostic navigation and explicit run/poll/
select were exercised through Fusion's HTML bridge; native UI pointer actuation
and cancellation during a long solve remain unmeasured. Sources match the final
lock. Maximum sampled Fusion RSS across314/316was713392KiB, below4GiB. Source/UI
launch/display corrections are recorded separately from the unchanged numerical
policy.62focused solver/controller/handoff tests and27affected witness/pinch/
constraint tests pass across scoped invocations; Ruff lint/format, changed-file
IDE inspections, JavaScript syntax and diff checks pass. No repository-wide suite
was run. The native trim-membership failure remains the next bounded investigation.

## Excursion report: conversion parity audit318

The user identifies the large departure/U-turn excursion in the displayed316case.
A frozen numerical-only replay covers that case plus the three distinct earlier
Gym1/2/3configurations, with their original targets and declared radius bounds.
Four planned/evaluated, zero native attempts/builds/full physical audits. No solver
source, budget, tolerance, target or live body changed. Every stage/proposal is
retained under `artifacts/verification/ribbon_port318`; these are examined cases,
not fresh coverage. No invalid controls or general reliability claim.

The cold selected entry point reproduces both first-pass and final archived
geometry with **zero measured difference** on all four cases, sampling129material
stations on center and both ordered edges. Earlier first-pass references are285;
final references are307. The observed case compares to316. This supports numerical
port parity on those configurations, not a continuous equivalence proof. The
approved radius/merge/layout/merge stages were not omitted in the gym conversion.

On the reported case, first-pass length21.888787mm grows to22.983226mm at5%smoothing,
with endpoint chord6.855122mm. Initial explicit departure straight4.899480mm grows
to5.187876mm; total explicit straight15.481740->16.129061mm.65station corresponding
guide RMS4.016938->4.333689mm and maximum6.996649->7.518347mm. These ordered arc
correspondence metrics are not nearest-distance or continuous deviation bounds.
The large excursion exists before smoothing and increases during smoothing.

The first pass uses guide-middle orientation and guide RMS only after material
length in candidate ranking. It has no continuous guide-attraction/deviation
trimming pass. The second pass minimizes curvature and permits up to5%growth,
without a non-worsening guide-deviation gate. Thus unchanged approved mechanics
can retain a long departure on new poses and increase deviation while easing
curvature. Increasing smoothing allowance is not an evidenced solution. Future
compactness work should separate first-pass fold/runway placement from smoothing
deviation preservation, using normalized rules and all four frozen cases. No such
algorithm change or additional native build was performed for this diagnosis.

## Visible pre-path319

User requests the pre-path beside the other gym diagnostics. Gym drafts and frozen
diagnostic contexts now draw it in magenta, even without a route result. The native
display uses the exact cubic; both palette canvases use129samples. The original
chord/3endpoint controls were moved unchanged into shared `prepath.controls`, used
by both `Guide.create` and the renderers. Arrival travel direction is preserved.
The diagnostic Gym layout checkbox controls this reference with its other context.
Display state carries it separately; frozen gym payload bytes/identities, profiles,
solver settings, material geometry and native bodies are unchanged.

319refreshes one already examined316result using fresh, explicitly named viewer
classes and its existing native manifest/controller. Old stateful viewer objects
and archives remain retained. Zero solves, native ribbon attempts or physical
audits. The body revision is unchanged and displayed controls exactly match the
solver's guide. The viewport capture shows the magenta reference crossing the
central gym area alongside the long-excursion route. Display10.519s; this includes
new diagnostic helpers/profiles/palettes and capture, not route-generation time.
Evidence: `artifacts/verification/ribbon_prepath319`. New source lock records the
shared helper/display changes without overwriting historical run fingerprints.

47focused pre-path/guide/solver/handoff/witness/thickness tests pass. Changed Python
and HTML files pass IDE inspections, scoped Ruff lint/format and JavaScript syntax
checks. No repository-wide suite or new geometry generalization test was run.

## Conductor count and performance counters320/321

Both gym palettes now show conductor count plus generation total, route/check wall
time, numerical CPU, first-pass and smoothing subsets, geometry build, optional UV
preparation/storage and fidelity audit timings. Generation is measured solve/check
wall time minus optional UV preparation, plus native geometry construction. Audit
and optional UV storage are excluded. CPU is the numerical worker only. Missing,
negative, boolean, malformed or nonfinite measurements display as unmeasured;
measured zero remains zero. A partial native failure does not fabricate an audit
or total time. The latest job remains explicitly addressable after layout
navigation, while exact endpoint and complete gym-context matching prevents stale
timings from being attributed to a changed draft.

Read-only counter fields are cached by file timestamp/size. Gym counter polling
updates only the counter panel; it does not reset in-progress editor values,
redraw geometry, collect a worker or start a solve. UI counter refresh and source
locks were adopted through fresh palette/controller-view objects, retaining the
same live session, controller state, geometry handles and native body revision.
Zero solves, native ribbon attempts or physical audits. Current316recorded values:
1conductor; generation1.426s=route/check.563s+geometry.863s; CPU.559s; first.158s;
smoothing.340s; separate fidelity audit8.223s; UV off. These remain original run
measurements, not a new benchmark. Initial palette refresh.908s; no geometry work.
Evidence: `artifacts/verification/ribbon_counters320` and `ribbon_counters321`.

20focused counter/controller/handoff tests pass, covering cost exclusion, layout
attribution, partial results/cache refresh and navigation identity. Scoped Ruff
lint/format, changed-file IDE inspection, JavaScript syntax and a bridge-function
check that polling leaves editors intact pass. The live diagnostic panel was
visually reviewed; palette requests acknowledge without errors. No full suite or
new solver/geometry validation was run. Source lock includes the counter display.

## Stale diagnostic cleanup322/323

The user reports old gym objects/pre-path remaining after a layout change. Live
inspection322finds two visible gym-context groups in the active diagnostic root,
only one tracked by the viewer, plus a visible retired workspace. Root cause:
`enable_gym` reset the already-created `_gym_group`/`_gym_id` when attaching the
workspace, orphaning that initial group. It now preserves both handles and manual
layer visibility. Normal context replacement can therefore remove its prior group.
Selected installation also retires previous owned workspaces in the same document,
with an active-job guard. Retirement hides view/palette handles and the old owned
native output; it does not delete histories or ribbon bodies.

323creates one current replacement before removing the two identified stale
transient context groups, and hides the two retired workspace views. The current
body revision is unchanged. An acknowledged HTML-bridge switch to another existing
gym context and back leaves exactly one gym group after each change, with no event
error or retired view visible. The original user layout/body visibility are restored.
No solves, native ribbon attempts or physical audits; this is display verification,
not added geometry coverage. Cleanup.266s; source pins and partial evidence are in
`artifacts/verification/ribbon_cleanup323`; initial inspection is `inspection322.json`.

16focused palette/handoff tests pass, including repeated binding/layout replacement,
manual layer visibility, retained case histories and refusal to retire an active
job. A test fixture initially lacked its fake root; that setup was corrected before
the passing run. Scoped Ruff lint/format and changed-file IDE inspections pass;
the live cleaned viewport was reviewed. No full suite or new complete workspace
installation/native build was run for this fix. The selected solver/source lock
is retained with these display-lifecycle changes.

## Smoothing contact certificate324–330

The user's N3/D.75 gym layout (seed719117695) spent35.446s at5% and41.404s
at10% smoothing while returning the original route unchanged. Each pass rejected
its proposals as contact-unresolved: easing inserted short straights between folds,
so the original shared-cap certificate no longer applied to those fold pairs.
The interval checker exhausted its unchanged20,000-pair/depth36 bounds.

`contact_caps.straight_bridge_pairs` extends the same half-space argument across
continuous, straight-only bridges. The first cell must remain behind its end cap
and the second ahead of its start cap, using the existing cell-specific tests.
Their rigid frames must join, cap normals must agree, and positive signed plane
separation must exceed a conservative floating/frame-error envelope. Tiny gaps,
malformed joins, intervening folds and returning interiors retain subdivision.
No adjacency-wide exemption, clearance tolerance, geometry repair or budget increase
is introduced. This remains a floating analytical certificate, not exact arithmetic
or a complete physical audit. The shared checker can also resolve previously
unresolved first-pass candidates; first-pass geometry need not remain identical.

Four independent, examined gym development layouts were frozen before the fix:
the triggering layout plus priorGym1/2/3. They are not untouched holdouts.325uses
the same frozen first passes/settings: trigger andGym1improve; Gym2/3reproduce their
previous routes. Trigger smoothing.585s; curvature score220.575→38.319 (82.63%lower),
peak2.484→.460; maximum sampled trajectory movement2.872mm. Eight radius and eight
layout steps are accepted. Length21.206→22.266mm respects the original shared5%
ceiling. Gym1further improves score131.952→120.050; smoothing1.839s. Gym2/3timings
.417/.216s. All4final numerical cap/metric/contact gates pass.

326cold entry-point verification reproduces first/final geometry for trigger,
Gym1andGym2. Trigger cold solve/check.786s CPU.785s, including first.209s and
smoothing.573s. Gym1solve2.378s/smoothing1.786s; Gym2solve.534s/smoothing.408s.
Gym3hits the deliberately strict archive-parity assertion: the new checker accepts
rank0at154.186705mm instead of the previously accepted rank1at154.190348mm.
The stopped report is preserved.327reviews its retained trace without another
solve: first sampled difference.08322mm; final.00754mm; final cap3.15e-11mm,
metric3.33e-16, contact separated and5%ceiling retained. Its curvature score changes
slightly (69.893→69.900, each normalized to its first-pass length); this is not an
additional smoothing gain. Gym3was numerically attempted, despite326erroneously
leaving it in its unattempted list after the assertion. Its missing cold timer is
unmeasured. No cold or smoothing retry was run.

After stopped-run review,327/328attempt only the two changed cold-parity results.
Native construction2/4attempted,2/2built and passed unchanged named surface,
ordered-guide, seam and cap fidelity checks;0full physical audits. Gym2is unchanged
and has no fresh native claim; Gym3's changed cold variant remains diagnostic and
natively unattempted. Trigger geometry.862s, separate audit12.012s; Gym1geometry
.814s, audit7.890s. The solve<=construction timing goal passes trigger and misses
Gym1(2.378>.814s). Optional UV is off; no appearance/texture expense is counted.
The old308/314fidelity failures remain unresolved and are not reclassified.

329/330imports the trigger as an explicitly labelled5%variant through the existing
HTML bridge, preserves editor settings/history, and replaces only the owned native
display with its verified body. The body revision is unchanged by display movement;
matching counters and selected result acknowledge without event errors. Both native
captures and the live viewport were reviewed.52focused contact/aesthetic/selected
solver tests pass across scoped runs; scoped Ruff lint/format and changed-file IDE
inspections pass. No full QA suite or production promotion. Frozen sources, plans,
all dispositions and the parity-stop review are under
`artifacts/verification/ribbon_smoothing324`; source lock includes the certificate.

## Diagram orientation331–338

The diagnostic canvas used Y-up; Fusion uses Z-up. Both canvas presets now use
the native isometric camera at (+X,-Y,+Z), with a right-handed camera basis and
matching back-to-front depth sorting. Reset restores that preset. Canvas orbit
remains independent of the Fusion camera; world targets and routes are unchanged.
The initial Z-up-only correction still faced the opposite XY direction; live
review caught that intermediate mismatch before the final camera correction.
Both scripts parse,20translated/orbited projection comparisons pass, the preset
matches the native camera basis, and both HTML files have clean IDE inspections.
The refreshed diagnostic diagram was reviewed beside the same native ribbon;
body revision, selected result, histories and counters are retained. The current
local review page adds only initial scrolling to center the canvas. No solves,
native attempts or added geometry coverage. Updated source lock and evidence:
`artifacts/verification/ribbon_diagram331` and `ribbon_diagram334`.

## Unresolved sub-resolution topology339–347

The new N3/D.75 gym layout in jobs `selected-b61f749b2d6c486683bca3f933ebbfc4`
and `selected-6e6fd8a3140b47f488467f101d1ecfa3` passes numerical checks and builds
a solid, but the strict native audit rejects142faces where152were authored.
These two user builds repeat one independent configuration. Its terminal straight
is8.613755e-8mm long. Read-only340inspection retains the same body revision and
confirms matching retained NURBS controls, followed by two planar caps; a complete
ten-face terminal band is absent.339first used the generic surface getData layout
on a Plane and failed without changing geometry;340uses explicit surface families.

341freezes that trigger plus three distinct gym collateral maps before changes.
342exact flat-run/lead coalescing preserves sampled full-thickness positions within
2.20e-14mm across4/4maps and all numerical cap/metric/contact gates. One cold trigger
solve1.172s includes smoothing.958s; others are frozen-map replays, not new solves.
343builds the trigger with the expected122faces and passes4200surface samples
(maximum4.12e-9mm), ordered guide positions/tangents and both caps, but fails one
strict shared-edge seam check between faces118/119. The subnanometre tip lead
has no shared native edge. The three collateral native attempts remain unattempted.

After separate frozen reviews,345uniform1024construction-unit conditioning still
fails the seam gate.347exact bend/positive-exit NURBS consolidation instead returns
122native faces where its authored compact layout expects102: the kernel partitions
the composite surface again. Its surface/guide/cap audit is therefore unattempted.
Neither experiment relaxes an audit tolerance, moves a target or drops material.
Each stops on its first native failure; no alternative scale or automatic retry.

Independent scope:4planned/numerically evaluated,1/4natively attempted (three new
attempts of that same trigger),1/4built but unaccepted,0/4named-fidelity passes and
0full physical audits. Three collateral configurations remain natively unattempted
in every stopped phase. No untouched holdouts or generalized construction claim.
New construction times1.904/3.950/2.913s; native phases15.950/26.896/3.660s including
audits. Retained RSS samples remain below4GiB; in-flight peak is unmeasured.

Candidate unit checks validate resegmentation, exact surface span concatenation
and optional material inverse coordinates; they do not validate native topology.
117focused candidate tests pass across scoped runs. Ruff passes. IDE checks find
pre-existing archive-duplication/shadowing/Fusion-method-name/broad-boundary warnings;
newly introduced shadowing was corrected. Full QA was not run.

All candidate executable/test changes were reverted after the native failures;
the selected source lock is restored to its prior accepted implementation. No
failed policy was installed in the live workspace. Failed bodies/reports and source
copies remain under `artifacts/verification/ribbon_flat341`, with read-only evidence
in `ribbon_topology340`. The original user's failed job remains rejected/hidden.
This case is unresolved: preserving a sub-resolution native seam requires a new
construction investigation, not relaxing the gate or claiming the solid passed.

## Low-cost solver alternative349–351 — proposal only

The user asks whether the unresolved topology can be addressed cheaply. A change
to the planned route requires an explicit exception to the recorded fixed-material-
plan construction investigation. No accepted solver or native geometry changes
were made while measuring this alternative; native feasibility remains untested.

349/350try existing bounded Newton retraction after zeroing the8.61e-8mm straight.
Reclosure takes6.53ms CPU but increases peak curvature3.588e-9/mm and is rejected
by the unchanged peak gate.349fails to retain individual gate values before its
assertion;350preserves the same algorithm/settings and records them before stopping.
Both stopped outcomes remain; the three collateral cases are unattempted there.

351uses fixed fold angles/banks and nonnegative radius growth instead. Existing
positive straight slots may redistribute, tiny slots at/below the existing1e-7mm
cap-closure scale are fixed at zero, and absent slots remain zero. A bounded affine
projection solves XYZ closure, with the original total-length ceiling added when
needed; no new routing/smoothing pass or alternate thresholds. Four examined gym
layouts are screened: the trigger changes, three others remain exactly unchanged.
Trigger cleanup takes1.186ms CPU/1.187ms wall with two linear projections. Maximum
sampled full-thickness movement1.721e-7mm; cap error1.602e-14mm; material metric
4.44e-16; contact separated; peak curvature unchanged; total length changes only
by floating roundoff(-7.1e-15mm). Unchanged cases cost11–16microseconds each.
Trigger checking/diagnostic sampling.0617s is separate from the cleanup timer.

These are4numerical development checks,0native attempts,0native fidelity passes,
0full physical audits; no native success is implied. This deliberately changes
the planned material path slightly, unlike339–347. Approval was requested for
that specific solver-policy exception and one bounded native check. Evidence:
`artifacts/verification/ribbon_cleanup349`, `ribbon_cleanup350`, `ribbon_cleanup351`.

## Approved numerical cleanup352–358

The user's “yeah, lets try it” approves the351microscopic reclosure exception and
one bounded native check. The selected solver now applies this deterministic rule
after aesthetic smoothing and before final validation/optional UV metadata. The
1e-7mm sliver floor follows the existing cap-closure scale; it is not a universal
Fusion minimum-feature certificate. Fold angles/banks/order/profile remain fixed,
radii may only grow, existing positive straights may redistribute and absent slots
stay zero. At most2*(variable count+1)linear projections run, with no new search or
smoothing pass. Unresolved closure fails explicitly instead of sending the original
sliver to construction. Smoothing0still disables aesthetic smoothing; numerical
cleanup remains active. The original native builder and all audit gates are unchanged.

353replays the four frozen341development configurations:4/4numerical checks pass;
only the trigger changes, with exact sampled parity to351. Cleanup costs1.312ms CPU
(1.313ms wall); the three unchanged maps retain object identity and cost7–9microseconds
CPU. These are development cases, not untouched holdouts. Its additional cold solve
stops at2seconds because the harness hashes every source at every checkpoint.
354rejects the missing completed prerequisite before any native attempt.355reviews
that monitoring overhead and uses the existing worker's0.5second source-check
interval, retaining the same2second cold bound/search budgets. Cold solve passes
with exact sampled replay parity:1.16949s wall/1.16855s CPU, including first pass
.18756s, smoothing.95507s and cleanup.001246s wall. Cap error1.602e-14mm, material
metric4.44e-16 and contact separated. Maximum sampled movement versus the original
route remains1.721e-7mm; peak curvature is unchanged and total length changes only
by roundoff. Optional UV metadata is off for this check; when enabled it is computed
from the cleaned route, without creating textures or appearances.

356executes exactly one native attempt of that trigger under the120second/4GiB
limits: built and all named fidelity checks pass. Expected/actual142faces;
4900surface samples maximum4.121e-9mm,270seams without failures, ordered guides and
both caps pass. Geometry generation2.58502s (translation.24843s, definition.99652s,
kernel1.34008s); audit19.12234s; native-operation wall23.84451s. These are separate
timers, not all generation expense. Sampled RSS remains below4GiB; in-flight peak
is unmeasured. Scope:4independent numerical configurations,1native attempted/built/
named-fidelity pass,3native unattempted by agreement,0full physical audits. Earlier
user failures and339–347stopped constructions remain rejected historical outcomes;
this success follows the explicitly approved microscopic change to the planned path.
The separate308/314native failures are not resolved by this check.

357imports the accepted result into its matching idle gym, preserves1%smoothing/
UV-off preferences and existing histories, and updates counters to this exact job.
358confirms the selected ID, clear event error, source pins and unchanged native
revision after display translation; the accepted body is visible and captured.
The source lock includes cleanup.23focused selected-solver/cleanup tests pass;
Ruff lint/format pass. IDE inspections introduce no findings; solver/settings retain
pre-existing archive-duplication weak warnings. Full QA, other native configurations
and full physical audits remain unrun. No production promotion or further batch.
Frozen plans, monitoring-stop evidence, native audit and live review are retained
under `artifacts/verification/ribbon_cleanup352`.

## Outward terminal bends359–363 — routing quality unresolved

The user rejects the visible backwards exterior curvature in the356/357result.
Construction/fidelity success does not establish acceptable route shape; the earlier
handoff understated that distinction. Keep the result as built/fidelity-passing
development evidence while treating this layout's routing quality as unresolved.

359read-only live inspection confirms the selected355trigger, matching targets,
idle owned document and no event error.360compares the same four frozen development
maps before/after cleanup, with no solves or builds. Trigger first-pass snapshots
before/after the cleanup implementation are exactly identical. All four routes
retain identical fold angles/banks; trigger maximum sampled full-thickness movement
is1.7213429e-7mm and the other three maps have zero movement. The first and last
curved center-lane directions versus directed cubic cap curvature have cosines
-.89549/-.71413 in the original first pass, the original smoothed route and the
cleaned route. The visible outward turn predates cleanup; removing that cleanup
would retain the turn and restore the native sliver failure. This does not establish
that all possible future cleanup inputs preserve route quality.

361archive harness stops on a smoothing row with no `stage`; no solve/build occurs.
362reviews that error and reads optional stage tags under the same2second bound.
All11closed first-pass candidates have the outward start. Eight `guide-0-1`
candidates have both outward terminal signs; three `guide-0-0`candidates reverse
only the exit sign and are longer. The direct and two remaining guided families
have no nonnegative basic position closures. This is a limitation of the offered
frames/rotation families, not proof that better endpoint routing is impossible.
Changing candidate ranking alone cannot select an absent inward-start candidate.

363screens one explicit representation alternative across those same four fixed
gym inputs: both signs of the free intermediate width, preserving ordered endpoint
frames and all existing algebraic rotation/nonnegative-position equations. The
screen broadens to at most10families instead of the selected6and records that cost
rather than silently changing the solver budget. Trigger9families/23closed supports
still offer no pair of positive terminal guide-curvature signs; neither does Gym1.
Recent/Gym6already have such candidates. No contact attempts, smoothing or native
builds run; this representation experiment is unsuccessful and is not installed.
Guide-curvature signs remain diagnostic preferences, not new physical rejection
rules: one previously liked Gym1also has negative signs, so a blanket sign gate
would not be justified by this evidence.

Scope:4/4archived maps compared and4/4inputs numerically screened,0new native
attempts/builds/fidelity audits/full physical audits. All screened candidates have
contact unmeasured. No invalid-control cases or holdouts. Trace.193s, archive.039s,
representation screen.584s wall; no native or end-to-end generation benchmark.
Selected solver, source lock, live geometry and native history remain unchanged.
The remaining correction belongs in first-pass fold-direction construction; no
successful correction or renewed solver-quality acceptance is claimed. Evidence:
`artifacts/verification/ribbon_curvature359`. Prose diff reviewed; application QA
and IDE code inspections are not repeated for this documentation-only change.

## Second excursion365–366 — 2026-11-02

The user identifies another visibly excessive hairpin in the live gym. Read-only
365captures its distinct fixed input: seed557726847, Aface8/roll0/zone20 and
Bface8/roll2/zone17, N3/D.75, endpoint separation5.266593mm. Job
`selected-7265ad6611b54fbbbe2c9dd2242dc699` is completed with named native fidelity
passing, while the diagnostic selector is `input`. The photographed native body
and latest counters belong to that job; no display or geometry is changed.

Archived first-pass length72.876677mm, final73.605444mm. First-pass explicit straights
are9.816056/16.422036/31.171350mm. Maximum sampled ordered guide deviation increases
33.259502->33.464300mm during smoothing. The excursion exists before smoothing;
cleanup reports `not_needed`, zero projections/removed slots. Existing cold timing:
first pass.102549s, smoothing.560580s, total numerical.670823s/.670289s CPU. These
are archived measurements, not a new solve or comparative performance claim.

366freezes route/trial/native hashes and the unchanged selected source pins before
one bounded diagnostic screen (2seconds, at most8exact half-turn factor branches,
one contact attempt maximum,0native attempts). Both endpoint tangents and ordered
widths are antiparallel. Each direct fold is exactly pi; its signed alternatives
and mirrored banks represent the same terminal frame but different spatial
displacements. All8symmetries of that direct two-fold representation are screened
through the unchanged nonnegative affine allocation and full-cap guard. Zero closed
candidates: the missing-sign hypothesis supplies no correction in this representation.
Actual.02117s wall/.02115s CPU. Contact is unattempted because no candidate closes;
there is no contact or physical infeasibility claim. No family/solver change is
installed and no smoothing, native build or fidelity audit is repeated.

Scope:1new independent gym input archived/numerically screened,0new native attempts,
0new builds/audits/full physical audits. This increases the retained diagnostic
inventory, not successful geometry coverage or holdout evidence. The old successful
native fidelity status is preserved separately from unacceptable route compactness.
Keep this fixed case alongside359's outward-turn case for the general first-pass
correction; do not infer a physical excursion/length cap from endpoint distance.
Evidence:`artifacts/verification/ribbon_excursion365`. This turn changes maintained
notes only; prose/diff checks apply, application tests/IDE code checks are not rerun.

## Guide influence traced367 — 2026-11-02

The user asks why the pre-pass guideline is being ignored. Read-only selected-call-
path inspection identifies a concrete gap between continuous loose directional
guidance and the implemented policy. `prepath.controls` supplies the same cubic
to solving and drawing; the guide is not missing or independently rotated.
`joint_route.frames.middle_frame` samples only parameter.5for tangent and computes
an intermediate ordered width. Its origin is explicitly informational; orientation
factorization uses the frame vectors. The resulting topology retains folds and
`middle_after`, not a positional guide anchor. In the selected path `middle_after`
is written to trial metadata but never used to constrain allocation.

`allocation.Model.equations` solves final endpoint XYZ only. It has no guide or
interior positional/directional objective. Nonnegative basic supports can therefore
carry the correct middle orientation far from the cubic. `construct` ranks length
first and guide RMS second, so distance matters only for ties in length rounded
to10decimal places. Measured mean direction loss is archived but never used in
selected candidate ordering/acceptance. The selected aesthetic stages receive no
guide; their curvature objectives and physical/cap/length gates do not preserve
guide agreement. This is the implementation's limited influence, not a failed
guide load or Fusion translation problem. Family limitations also remain: changing
the ordering cannot choose a close route absent from the generated candidates.

367freezes sources and the365case archives before a2second read-only measurement.
At its derived middle boundary after two folds, first-pass tangent matches the
cubic middle tangent exactly (vector error0), ordered width error2.388e-16, but
that boundary is18.912718mm from the guide midpoint. It occurs at32.511%of route
material length. This directly demonstrates orientation matching without spatial
following; it does not prescribe a rigid midpoint landmark or certify a replacement.
Actual measurement.00754s,1archived case inspected,0new solves/native attempts/
builds/audits/full physical audits. No solver, source-lock or live-display change.
The correction should give ordered guide position/direction influence during first-
pass construction and preserve that preference during smoothing under unchanged
physical gates. No new weights, deviation threshold, algorithm or successful fix
is asserted by this diagnosis. Evidence:`ribbon_excursion365/{plan367,result367}.json`.
Documentation diff reviewed; application tests/IDE code checks unrun for prose only.

## Guide tuning368–372 — rejected and restored

The user requests stronger pre-pass guidance. Five fixed gym development inputs
are frozen before this work: the365hairpin,359outward-turn/sliver trigger, and
the three collateral maps retained in352. Repeated variants are these same five
independent configurations, with no holdouts or invalid controls. Native/profile/
material rules remain fixed and no new native operation or appearance is scheduled.

368adds exact single-fold tangent steering at ordered guide arc fractions1/4and3/4,
with balanced algebraic middle rotation roots, followed by unchanged nonnegative
XYZ closure. It retains existing families and ranks by squared chord-normalized
guide RMS plus directed tangent mismatch. Limits3s/case,15s/phase,9families/six
folds,12contact attempts/case,4GiB RSS. All5first-pass screens complete. None of the
new endpoint-steering families supplies a closed candidate for either trigger; guide-priority ordering
does improve the large retained case through a different existing family. Both
problem cases retain their original first-pass branches. No promotion follows.

369reviews the large bank-dependent leads of the middle two-fold rotation and
adds the existing exact orthogonal three-fold decomposition, retaining the same
case/time/family bounds. All5screens complete; neither trigger improves. This
representation alternative is rejected and remains artifact-only.

370then tests an implementation retaining the original6families/12contact budget:
up to16affine projected steps fit ordered fold-cap points toward guide positions,
followed by distance+direction-first ranking. All original basic allocations remain
available; contact/cap/material checks stay unchanged. A first-pass-relative guide
cost allowance across aesthetic stages prevents drift, with candidate stage outputs
explicitly provisional. Matched baseline uses the exact prior constructor hash,
same current cleanup/metric instrumentation and1%smoothing/UV-off/radius settings,
with the new aesthetic guard disabled. Its instrumentation is not an uninstrumented
historical speed benchmark. Limits5s/solve,40s/phase,10cold solves over5inputs,4GiB.

All5matched baseline/candidate pairs complete numerically, but tighter guide costs
reject entire aesthetic stages. Candidate full-cylinder curvature exceeds matched
baseline in all5cases; peak lane curvature also increases. This reintroduces sharp
features and is unacceptable despite improved guide metrics. Candidate cold solve
times.514–3.388s;35focused prototype tests pass, but do not certify route quality.
No native build is attempted or inferred from these passes.

371uses saved routes only to check monotone guide correspondence:33route samples
match65guide samples through a prefix-minimum dynamic program, endpoints fixed,
interior guide indices nondecreasing. It addresses rigid same-percentage matching
without requiring positional landmarks.5archived pairs examined,.07092s,0solves.

372reviews/replaces the overly restrictive cost allowance with one shared sampled
spatial corridor (first-pass maximum plus profile half-width and the configured
extra material length), and uses monotone distance/direction preference in fitting
and ranking. Same5s/40s/4GiB/five-input matched plan. The new hairpin is exactly
unchanged; the359trigger has better guide metrics but much higher curvature because
its layout-easing stage is still rejected. Recent gym guide cost worsens slightly
.06203666->.06256330 despite lower curvature, triggering the registered stop. Both
remaining matched comparisons(Gym1/Gym6)stay unattempted in372. Four focused tests
of the revised preference/corridor pass; this does not override the geometry stop.

Independent accounting:5/5inputs screened in368/369/370,3/5matched pairs completed
in372and2/5unattempted there;0/5native attempted/built/fidelity-audited/full physical
audited. Across phases there are10first-pass screens and16complete cold solves,
not26independent configurations. Selected outputs pass numerical gates, but no
candidate meets the combined routing/aesthetic improvement goal. Measured phase
wall total22.0941s includes the read-only371check, excludes implementation/QA and
orchestration; no token/usage cost or in-flight memory peak is measured.

All tuning code/tests are removed from the selected implementation after the
regressions. Rejected sources remain in`ribbon_guide372/rejected-source` with plans,
trials and unsuccessful/stopped reports retained in368/369/370/371/372directories.
The pre-existing accepted cleanup/source lock is restored exactly and lock.verify
passes; earlier sliver/build fix and live Fusion geometry are untouched. Candidate
IDE warnings are not installed; only prior archive-duplication findings remain in
the restored code. No full QA or new Fusion checks run. Documentation diff/check
passes; unchanged restored checks are not repeated. The next investigation must
give construction joint orientation/placement freedom against the ordered guide;
merely stronger ranking or post-stage rejection is insufficient on these inputs.
No successful guide correction, solver-quality acceptance or further run is claimed.

## Explicit contraction373–374 — missing objective isolated

The user emphasizes the dominant straightaways and rejects inference that the route
cannot contract. Selected-call-path inspection confirms a missing objective:
layout easing differentiates full-cylinder fairness; its direct straight-coordinate
gradient is zero. Straight travel changes only through projected closure while
rounding folds. Length appears as a ceiling derived from the already long first
pass, not a descent target. Merging considers compatible common-crease turns only.
The separate historical angle/straight contraction is not invoked by the selected
pipeline. These are numerical/representation choices, not material impossibility.

373freezes the same five fixed maps and source lock, then probes one negative total-
length gradient projected onto exact-cap closure, suppressing first-order aggregate
curvature growth. Same signed folds, bank/radius/model bounds and physical floor;
four halvings with existing bounded nonlinear retraction. Limits2s/case,10s/phase,
one direction and at most one contact attempt/case,4GiB,0native attempts. A shorter
candidate must retain cap/material, nonincreasing peak lane curvature and initially
also nonincreasing full-cylinder fairness. All5probes complete in.25108seconds.
Each offers
a negative length derivative, but no candidate passes all those acceptance gates.
The report label`no_length_descent`means no ACCEPTED contraction in this probe;
it does not mean no decreasing direction or no shorter trials were found.

For the new hairpin, first trial73.605444->72.065943mm preserves caps(error9.305e-10mm)
and material metric5.573e-16; peak lane curvature improves.763226->.734410/mm.
Its full-cylinder fairness7.128075->7.139008increases only.15337%, which vetoes
contact in373. Thus an aesthetic monotonicity condition blocks a physically
promising shortening move. This is not proof of complete compliance or the ability
to remove the whole excursion. Center-lane flat material includes explicit
straight42.254432mm plus fold flat leads10.768969mm,72.04%of the final route;
the original first pass is78.78%explicit straight travel alone.

374reviews that distinction and repeats the SAME one-direction/four-halving probe,
reporting aggregate fairness as a goal rather than a physical veto. All physical
gates and nonincreasing peak lane curvature remain. Three of five candidates now
shorten and pass thick-contact checks: new hairpin73.605444->72.065943mm,
recent19.265524->18.889226mm and Gym1 12.464389->12.255655mm. CPU per successful
probe.02663/.03146/.03867s, including numerical checks/contact; phase wall.18951s.
Aggregate fairness
increases are retained, not hidden. The359trigger and Gym6 remain unaccepted due
to peak-lane-curvature growth; their contact checks are unattempted. No resampling,
extra iterations, physical-gate relaxation or further refinement occurs.

Independent scope5/5numerically probed in each phase,3/5accepted numerical
contractions in374,2/5unaccepted there,0native attempts/builds/fidelity audits/full
physical audits. No invalid controls or holdouts. No selected code, source lock,
live display or earlier native result changes. This supports a bounded contraction
test as a distinct stage before final smoothing, with total length as the primary
objective; it does not establish convergence, visual quality or full contraction.
It also refines372's conclusion: a larger orientation-family redesign is not yet
shown necessary for incremental length gains. Sources/plans/all dispositions and
candidate maps:`artifacts/verification/ribbon_contraction373`and`374`. Prose-only
maintained changes; diff checked, no application QA or new Fusion checks required.

## Historical contraction trace375 — requested comparison with the original change

The user explicitly requests returning to the modification that successfully
contracted the original geometry, rather than proposing another small move. This
review distinguishes the historical stages and their current call paths.

`2a94f63`introduced fixed-fold straight-only nullspace contraction(258/259), then
bend-first rewriting(263/264). `f5d978d`introduced radius/straight LP allocation
(267/268), guide-branch selection(270), and the major joint first-pass replacement
(285/289). Radius allocation minimizes explicit straight travel FIRST, then total
material, while only growing radii and never increasing the input material budget.
It reduced straight travel in all four original267inputs; accepted contact fractions
and the native evidence remain as recorded in its own NOTES. This is different
from later curvature-only radius easing, despite both changing radii/straights.

`d6b1538`and`068acbb`added curvature/aesthetic easing and layout-relative banks/
angles/radii/runway freedom(296/307). The307scale/zero-runway corrections remain
in the active source. On the new hairpin the layout pass runs to its eight-iteration
budget; the combined radius/layout second pass reduces explicit straight travel
57.409442->42.254432mm. It is not being skipped. Its objective, however, is curvature
rather than total-length contraction.

The `c669883`gym handoff calls `joint_route.construct` directly, then radius easing,
merge/layout easing/merge. It calls neither the original straight contraction nor
the straight-first radius allocator. The radius allocator's model/program/solve
files still match`f5d978d`byte for byte; there is no implementation regression in
those files. Inclusion in the source lock does not mean they execute.

The joint first-pass math is also retained across that handoff: rotation families,
guide midpoint orientation, affine allocation and length-first ranking were not
replaced. The substantive entry-point difference is comparison-based improvement
versus cold construction. Historical `solve(source,guide)` rejects longer/more-fold
candidates and retains the prior accepted route if nothing improves. The gym
`construct(boundary,guide)`has no prior route/comparison and selects among whatever
closed finite families it generates. Continuous positional guide following was
not present in the earlier successful joint implementation either. Earlier good
comparison results therefore do not establish that the cold routine has an effective
excursion-repair pass for every new input.

375freezes the unchanged sources, original four267inputs and both current problem
inputs(first/final variants). It replays only the original pure radius LP and
straight-only nullspace diagnostic, with1s/map/8sphase and no contact/native calls.
All original four controls again offer their original full LP straight reductions:
32.933069->24.814734,11.186927->7.243102,16.631904->3.043508and257.332563->0mm.
These are unconstrained-contact optima; the original Gym2/Gym3accepted half-steps
remain the historical contact-verified outputs, not replaced by this replay.

For the new hairpin first pass, the exact old allocator retains57.409442mm straight
travel and72.876677mm total: no straight reduction under its fixed-angle/bank/
nonincreasing-length contract. Straight-only nullspace descent is also zero.
On the smoothed new hairpin, it offers only42.254432->41.597576mm straight travel,
with total material unchanged73.605444mm; contact is unattempted. The outward-turn
trigger offers no old-LP reduction either before or after smoothing. Thus merely
reconnecting that allocator would not remove the new long detour. The current
first pass has already selected a basic minimum-material allocation inside its
fixed rotation family; the old downstream move cannot freely relocate those bends.
This is a limitation of that representation/move set, not geometric infeasibility.

Independent scope:6saved gym configurations,8maps evaluated(original4plus2variants
of each current input),0contact attempts/native attempts/builds/fidelity audits/
full physical audits. Actual.11245s; no failed/unattempted trace maps. Original
native successes remain historical, not new coverage. No source/lock/live geometry
change; current lock verified before/after. This corrects the earlier oversimplified
claim that a missing contraction call alone explains the full excursion. The
next investigation should target the fixed orientation/placement contract and
length-vs-curvature objective in this existing chain, with the original controls,
rather than invent guide weights or infer physical impossibility from no-op output.
Evidence:`artifacts/verification/ribbon_history375`. Prose diff checked; no new
application QA or Fusion operation required for this read-only historical trace.

## First-pass optimization repaired376–384 — 2026-11-02

The user explicitly requires this repair inside first-pass routing; second-pass
smoothing remains aesthetic. `joint_route.construct` keeps the existing bounded
coarse rotation/allocation/contact construction, then jointly adjusts signed bend
angles, banks, radii and straight runway before returning its first-pass result.
Angles are no longer frozen to the coarse family or its original sign. Radius
can move down to the unchanged declared physical floor; the original peak/fairness
is not a routing restriction. There is no diameter/endpoint-distance shortcut or
case-specific coordinate rule. Production harness code and native construction
are unchanged. Historical rejected guide tuning368–372 remains removed.

Total material length is the descent objective. Projection preserves six cap
equations; bounded Newton retraction and independent complete ordered-cap checks
retain closure. Every accepted trial strictly shortens material, passes sampled
local metric and separated thick-profile contact, and does not exceed the original
coarse route's sampled guide cost. Guide correspondence uses33material stations
matched to65ordered reference samples with nondecreasing indices and fixed ends;
cost combines chord-normalized squared distance and directed tangent mismatch.
This is a sampled preference, not a continuous proximity or feasibility proof.
It does not veto the later aesthetic stages, unlike rejected370/372.

Limits:16iterations,6proposal halvings,12optimization contact proposals and1024
contact subdivisions. Construction steps allow25%of initial layout length and
pi/4angular changes; six Newton corrections/four correction halvings retain the
existing smaller correction steps. Coarse and final contact retain20000pairs and
depth36. A separated coarse certificate already exceeding1024pairs retains that
route without further optimization contacts. This resource gate is conservative,
not proof that improvement is impossible. Exhaustion retains the latest accepted
route; external time/source/memory stops propagate. No automatic budget increase.

Shared flexible geometry/retraction moves out of the aesthetic module, while its
original sign/radius restrictions, curvature objective, peak gate, trust defaults,
length allowance and stage order remain intact. Immutable initial layout data is
cached. Zero-angle folds become flat leads and adjacent flats coalesce. Existing
numerical sliver cleanup still precedes final checks/optional UV metadata. Thus
smoothing0runs the repaired routing and cleanup, while disabling aesthetic easing.
UV remains optional/off in this experiment; no appearance or texture is created.

### Frozen phases and retained unsuccessful outcomes

376stops during input preparation because an old Gym3first-pass archive is absent:
zero case evaluations/native attempts.377reviews that prerequisite and uses the
original285Gym3map, with its distinct hash recorded. Its prototype shortens the
first three cases but times out during the small Gym1contact check under4s/case,
20s/phase; the last Gym6case is unattempted. Completed/partial accepted trials and
the stop remain recorded. This motivates bounded optimization-only contact work,
not loosening physical separation or continuing the stopped phase.

378uses the implementation with construction-size steps and1024pair optimization
budget:5/5numerical replays complete,4shorter/1retained,0native. It also proves exact
parity against the prior committed aesthetic model on these five initial maps,
including geometry/labels, gradients, residuals and Jacobians.379completes5cold
endpoint solves at0%smoothing plus two1%native-input solves,0native attempts.
381adds the coarse-contact work gate, verifies the current source lock and repeats
the same seven solves under the frozen6s/solve,40s/phase,4GiB plan. Every final
geometry matches379exactly. The copied original plan narrative is retained; the
new source hashes and this explicit work-gate disposition distinguish381.

All repetitions are the same **five independent examined gym configurations**,
not new holdouts or additional coverage. Cold solves start from endpoints and the
pre-path, not archived successful geometry. Here are381zero-smoothing results;
the comparison length is that run's separated coarse candidate, not a historical
body or the slightly different original285Gym3route:

| Case | Coarse -> optimized first pass mm | Optimization s | Cold numerical wall s | Disposition |
| --- | --- | ---: | ---: | --- |
| new-excursion |72.876677 ->37.130034|1.272601|1.475161|49.05%shorter,12accepted/contact budget|
| trigger |41.756299 ->35.646795|1.706230|2.042943|14.63%shorter,7accepted/contact budget|
| gym-recent |19.123811 ->17.310350|1.278890|1.523652|9.48%shorter,12accepted/contact budget|
| gym-one |11.870847 ->unchanged|.003045|1.110327|Coarse contact work gate,0optimization contacts|
| gym-six |154.186705 ->153.666098|.102908|.226670|.338%shorter,1accepted/proposal budget|

All five final numerical cap/material/contact gates pass; maximum cap residual
8.927e-9mm, maximum sampled metric6.019e-16. Trigger at0%smoothing still needs the
existing4.809e-8mm sliver cleanup, which succeeds. The two1%native-input results
need no cleanup. The coarse work gate reduces Gym1's otherwise wasted~1.95s of
optimization to~3ms while retaining the identical validated route. It does not
establish an across-the-board speed gain or physical inability to contract Gym1.

### Native382 and matching live gym383/384

382freezes exactly two native attempts,120s/case,250s/phase,4GiB RSS/3.8GiB launch
headroom; stop on the first failure, no retries. Both1%smoothing/UV-off problem
configurations build once and pass the unchanged named native fidelity policy.
Three other numerical configurations are natively unattempted by this scope.
No failed/skipped/unattempted case within the two-case native plan; phase37.924s.

| Case | Final mm | Numerical wall / CPU s | Native generation s | Named fidelity audit s |
| --- | ---: | --- | ---: | ---: |
| new-excursion |37.501335|2.003402 /2.001286|1.771372|17.382903|
| trigger |36.003263|3.378555 /3.318026|1.199254|14.069132|

Generation includes translation, surface definition and kernel construction;
audit/graphics are separate. New-excursion numerical first pass1.363381s (of which
optimization1.256523s), aesthetic smoothing.627070s. Trigger first pass2.110159s
(optimization1.896643s), aesthetic1.235346s. Full numeric time exceeds matched
native generation in both cases: the speed goal is still missed. This is bounded
extra routing work, not an assertion that the old route was geometrically necessary.
New-excursion gym generation counter totals3.775s (numeric2.003+native1.771).

Both bodies have142faces; combined9800surface samples,540ordered seam chains and
four complete caps pass. Maximum surface error2.838e-9mm; ordered guide position
error2.467e-9mm; zero failed points/seams. Trigger uses four existing actual-UV trim
certificates; new-excursion uses none. No tolerance/policy extension. **Zero full
physical native audits**; continuous native volume/strain/manufacturability remain
unmeasured. Numerical/constructive/fidelity success is not a global route-quality
certificate. Both captures were visually inspected; significant flat travel and
terminal excursions remain. Neither problem case reached a proven optimum.

383imports the exact verified new-excursion result into the matching idle gym,
after checking owned document, targets/gym, source pins, native revision and idle
worker. QA occurrence receives only the gym display translation. Existing bodies,
histories and1%/UV-off preferences are preserved; no rebuild.384confirms selected
result `run-firstpass381-new-excursion:joint-material-v1`, clear event error,
matching job/counters, visible body and unchanged revision; live capture inspected.
The other verified body remains hidden as development evidence. Source lock updated
to the reviewed implementation without changing the version/UI defaults.

56focused tests pass across scoped runs:7first-pass,8joint-route,14locked-solver,
18aesthetic and9sliver-cleanup tests. Scoped Ruff lint/format pass. IDE inspections
find no new semantic findings; shared extracted geometry/retraction retains weak
duplicate-fragment reports against immutable historical source archives. Those
archives are preserved, not rewritten. Complete code/new-file/diff review performed.
The verify-change skill's referenced `.agents/VERIFICATION.md` is unavailable;
the explicit AGENTS focused profile supplies the checks. No standalone type or
documentation checker, full repository QA or complete physical audit was run.
No new generalized-success, shortest-route, minimal-feature or production claim.
Evidence: `ribbon_firstpass376` through `379`, final
`artifacts/verification/ribbon_firstpass381` plus `adopt383.py`/`review384.py`.

## Diagnostic first-pass switch385–387 — 2026-11-02

The selected solver panel now has **Enable first-pass optimization**, checked by
default. It controls the bounded joint length optimizer inside first-pass
construction independently of smoothing. Unchecked returns the selected separated
coarse route; configured aesthetic stages, numerical sliver cleanup, final checks
and optional UV preparation still follow normally. It applies on the next run,
does not reroute the displayed result when clicked, and disables while a job runs.

`Settings.first_pass_optimization` is an explicit boolean, defaults true and is
recorded in new controller plans and worker result settings. Existing two-control
records remain parseable with the enabled default. Other unknown/malformed keys
still reject. Run counters show recorded On/Off, or an em dash for an older plan
without an explicit flag; they do not infer the setting from current checkbox state
or silently rewrite historical plans. The selected381body therefore retains its
old plan and displays an unrecorded flag, despite known optimization provenance.

61focused tests pass across first-pass, joint-route, selected-solver/controller,
sliver-cleanup and performance consumers. Coverage includes disabled dispatch,
independent0/1%smoothing, boolean validation, legacy parsing, serialized on/off
plans and counter attribution. Ruff check and format check pass on nine affected
Python files. Palette JavaScript syntax and a simulated DOM check pass for enabled
default, draft retention, true/false run payloads and busy-state disabling. The
initial DOM harness lacked a selected method and failed before exercising controls;
its corrected fixture includes the normal input method. No application fix was
needed for that harness setup error.

IDE inspection is clean on the HTML and new toggle tests. Existing performance
type warnings (`float(value)`/optional disposition), the unchanged controller-test
optional-job warning, and historical-source duplicate-fragment weak warnings
remain out of scope. The verification skill's relative document resolves through
its managed symlink to `standards/VERIFICATION.md`, read for this change; the prior
376–384logical-path lookup incorrectly reported it unavailable. No full QA or
standalone type checker was run.

386refreshes the idle owned Fusion palette and only its settings/performance
bindings; selected method, job, visible body revision and geometry are unchanged.
The new checkbox is visibly enabled in the live panel,1%smoothing was restored and
UV remains off. Live parsing accepts explicit false. The executable source lock
was reviewed/refrozen. This is settings/UI verification, **0new geometry solves,
0native attempts and0new physical-audit coverage**. Previous381/382geometry evidence
remains historical. Evidence: `artifacts/verification/checkbox385.cjs`,
`refresh386.py`/`.json` and `review387.py`/`.json`.

## Accessible scaffold visibility388/389 — 2026-11-02

The existing thickness-envelope layer control moves from beneath the diagram to
directly below the run counters, labeled **Show transparent ribbon scaffold (both
views)**. It retains the same single `envelope` identity and existing seven-layer
visibility protocol. It switches the complete translucent native Custom Graphics
group and the diagram mesh without rebuilding the route or native conductor body.
Other layer controls remain independent. No numerical or Python implementation
changes; the executable source lock is refrozen for the maintained HTML change.

388JavaScript syntax/DOM checks pass for unique control identity, accessible
location, off/on boolean visibility dispatch and immediate diagram redraw. HTML
IDE inspection passes (an initial timeout was repeated successfully).389checks
the live native group off/on/off, verifies matching palette state and retention
across a ready request, and preserves selected method/job/body revision/visibility
and all other layers. The live checkbox is visibly unchecked and the transparent
ribbon mesh absent; conductor geometry remains visible. No FPS benchmark or native
renderer profiling is claimed.0new solves/native attempts/physical audits.

Refreshing the palette reinitializes the smoothing draft to5%. An attempt to
restore1%was interrupted by Fusion reporting user-driven app changes; automatic
approval review then rejected a final UI state query for stale-state risk. Further
UI interaction stopped. Final draft smoothing value is unconfirmed; no solve was
started and the existing1%built result is unchanged. This UI recheck is the only
blocked check; the prior native visibility/HTML checks are retained. No full QA
or repeated Python tests were needed for this HTML-only control relocation.
Evidence: `artifacts/verification/scaffold388.cjs`, `scaffold389.py`/`.json`.

## Clear generated geometry390–392 — 2026-11-02

**Clear geometry** appears beside Solve and build. It removes only the latest
generated output occurrence retained by this gym's NativeOwner, including its
auxiliary end-profile sketches. Other outputs/components, frozen layouts, numeric
records and diagnostic graphics remain. It works for a hidden latest output too;
it does not scan names or delete all historical bodies. NativeOwner releases its
handle only after successful deletion; missing/invalid output is harmless.

The generic diagnostic viewer accepts an explicit empty `clear_geometry` action
through ownership/availability callbacks installed by SelectedWorkspace. Both
palette and native dispatcher block it during running/cancelling jobs. The native
owner also requires its own active idle document. The button disables when no
native body remains, and shows a completion message after success. Normal Solve
and build remains available afterward; clearing never deletes job records or
changes historical fidelity/performance measurements.

22focused tests pass:8new deletion/dispatch checks,8gym-handoff and6selected-
controller consumers. Native API deletion is mocked: latest-only handle usage,
repeat/no-output, wrong document/active command, failed deletion retaining ownership,
empty-action validation, busy rejection and session retention. JavaScript syntax
and simulated DOM checks pass for clear-button availability, empty action and busy
state. Ruff check/format pass on four changed Python files. IDE has no introduced
findings; existing historical-source duplication and the native builder's documented
fail-soft broad exception remain. Full QA and actual native deletion are unrun.

391installs the new callbacks/classes into the owned idle live gym and refreshes
the maintained palette.392rebinds the retained navigation callback to the refreshed
workspace class, then checks source lock, clear availability, callback ownership,
navigation binding and clear event error. Current selected result/job/body revision
and hidden-scaffold preference are unchanged. **0deletions,0solves,0native builds**;
the current body is deliberately left for the user's button click. This palette
refresh reinitializes draft controls to their usual defaults; it does not change
the existing1%built result. No new CUA interaction or FPS/physical-audit evidence.
Evidence: `artifacts/verification/clear390.cjs`, `clear391.py`/`.json` and
`clear392.py`/`.json`. Executable source lock reviewed/refrozen; production unchanged.

## Solve/build control failure and progress393–400 — 2026-11-02

393read-only inspection finds an actual control failure, before any worker launch:
the last request is `run`, but its event error is `Supply smoothing_percent and
material_uv only`. The live runner is an archived
`counter_controller321.Controller`, with the old two-field Settings binding, not
the maintained controller tested locally. Its latest job is still381historical
evidence and no worker exists. Clear geometry had successfully removed the old
output. Thus the user's missing new body is not evidence of an exhausted solver.
The earlier controller-binding check exercised the maintained module alias, not
this actual live runner; that verification gap is acknowledged and corrected.
Fusion application logs were inspected before host-side changes.

The selected panel now exposes an open **Build progress log**. It shows control
submission/rejection, worker validation, numerical stages/route acceptance, native
patch/definition/kernel stages, fidelity checking, optional UV and completion or
failure. Request errors are visible here even if no job can be created. Accepted
jobs retain UTC events in `build-progress.jsonl`; at most100events/64KiB are read
for the UI, tolerating partial writes. Numerical stage updates are throttled;
full trials/tracebacks remain separate. Native events also push to the palette
while the synchronous native call runs. Optional palette delivery cannot abort
construction, and durable logging remains available if it closes.

Controller collection now exposes worker crash output and distinguishes an
unresolved no-route result from successful completion. Native exceptions outside
the existing fail-soft adapter stop the control stage explicitly. Last successfully
launched controls are retained in controller state, so palette reconnects no longer
replace the last1%setting with the default5%. Malformed requests or failed launches
do not replace those controls. Solver geometry, physical gates and native fidelity
tolerances are unchanged; this is diagnostic/control work, not a solver tuning fix.

395class-only repair stops before a solve because the old runner also has a
per-instance `state` override, whose old class closure makes `super()` invalid
after class reassignment. Its error response is retained.396instead creates a fresh
maintained Controller and copies only explicit historical/job/layout state, never
bound method overrides. This preserves methods, targets, jobs and native ownership.
The actual controller contract now advertises and accepts all three settings.
No solve/native attempt occurs in395/396.

397freezes one current gym case,120s numerical/120s native/250s phase,4GiB RSS with
3.8GiB launch headroom, at most one native attempt/no retries. It launches through
the actual `DiagnosticViewer.dispatch('run',...)` path; the palette's ordinary
polling collects the worker and performs native construction. At default5%smoothing,
numerical routing succeeds and a152-face solid builds, but named fidelity rejects
six shared-seam endpoint discrepancies, each4.420389e-6mm. Surface samples themselves
pass (maximum1.615e-9mm). The solid remains hidden and its failure preserved. This
is a native seam-fidelity failure after construction, not a missing route/control
failure, and remains unresolved. Generation2.241300s; native-operation17.099224s;
partial audit timer is not separately retained. Numerical2.436148s/CPU2.186866s.
No gate is relaxed and no geometry retry is appended to that stopped phase.

A separately reviewed3981%verification refuses scheduling because the latest job
changed while the user was operating the panel: its prerequisite deliberately
does not replace that job.0new solves/native attempts there.399then inspects the
user-driven1%run `selected-eecd3dee1f3e472ca75af09d589731b8`: completed numerical,
native construction and named fidelity pass. Targets and gym match397exactly;
these are two settings variants of **one independent examined configuration**,
not two independent successful cases. At1%:142faces, numerical1.984736s/CPU1.980530s,
generation.988163s, named audit13.701331s, full controller elapsed18.860809s. Both
variants miss the numerical<=generation timing goal. Sampled native RSS peaks
612352/727536KiB, below4GiB; in-flight peak unmeasured.0full physical audits.

400retains that successful user job and installs last-used-controls persistence
without another build, deletion, layout change or forced diagnostic selection.
The body is visible with its unchanged native revision, scaffold remains hidden,
event error is clear, and29progress events end with named-fidelity completion.
Current source lock verifies. The successful job's full source hash differs only
in `controller.py`, whose subsequent edit retains launched preferences; its
numerical/native implementations and logged geometry remain the executed versions.
Do not relabel the old plan as a new exact full-source verification.

Coverage for this diagnostic: one independent current gym layout, two numerical
variants/native attempts/builds (one agent397launch and one user-driven run), one
named-fidelity pass and one named-fidelity failure;0full physical audits/holdouts.
395/398stopped setup/guard work and all historical failures remain recorded. No
generalized construction or5%reliability claim. No further geometry run scheduled.

23focused tests pass across7progress/worker/collection,7controller and9clear/UI
boundary checks. Covers bounded/partial log reads, worker crash traces, no-route
classification, native completion/error, launch failures, retained controls and
optional progress-display failure. JavaScript checks verify visible control
rejection, polled worker logs and pushed native events. Scoped Ruff check/format
and IDE inspections pass with only existing archived-source duplication, the
documented native broad exception and unchanged optional-job test warning. Complete
diff/new-file review done. No full repository QA or standalone type checker.
Evidence: `inspect393.json`, `log394.cjs`, repair395/396 responses,
`ribbon_dispatch397`, stopped398response, `inspect399.json`, `retain400.json`, plus
the original selected-job directories. Production harness/profile code unchanged.
