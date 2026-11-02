# Selected material solver and gym integration — 2026-11-01

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
