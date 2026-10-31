# Endpoint gym and solver diagnostics

**2026-10-31 reset:** The user rejects the current macaroni application and view155
as a basis for further work. Paired-edge growth/shortening/contraction results below
are preserved historical checks of an unvalidated material-map assumption. They
must not be reused as a known-good geometric baseline or physical validation.
Stop refining this route. Re-establish the constraint directly against the user's
Macaroni demo, actual profile thickness/width and inner/outer bend geometry before
restarting route generation. The precise defect remains under investigation;
agreement between implementations of the same assumption does not validate it.

The subsequent restart is documented in [pinch.md](pinch.md#restarted-reference--2026-10-31).
Read-only158measures the user's demo;159checks six authored elementary normal-
profile references, without endpoint solving or native builds.160displays a
single-conductor compound S turning90degrees laterally alongside near-limit and
expected-invalid bends. These are calibration fixtures, not routes/seed families.
The old coupled-sheet acceptance remains rejected. The new restricted local check
matches the unchanged perpendicular-profile assumption. The later bounded endpoint
prototype and its limits are recorded in
[pinch.md](pinch.md#endpoint-normal-profile-prototype): view162 connects the same
gym targets with a39.448mm centerline. Five examined inputs have ideal-polynomial
curvature certificates; complete physical/native validity remains unestablished.

The equal-material-length clarification adds an essential restriction:163audits
the same5frozen curves, finding2compatible and3incompatible. Gym edges are45.143mm
each versus39.448mm center; its old curvature certificate does not establish ribbon
compatibility. View162is labeled curvature-only. View164instead shows two authored
finite-radius bank/fold references with equal material increments and unchanged
material contour dimensions. These calibrate the new representation, not a gym
endpoint solution. Details and limits are in
[pinch.md](pinch.md#equal-material-lengths-and-banked-fold-calibration).

The subsequent endpoint fold construction is now recorded in
[pinch.md](pinch.md#endpoint-construction-from-material-folds). View167connects the
same fixed gym targets with three58.110068mm material paths and9rounded folds.
All5examined inputs clear the named local material/pinch/cap checks in168;
no native cable construction or global physical acceptance follows. The procedure
uses pose decomposition and algebraic displacement closure, with no route seeds
or retired discovery execution. Its fold count is conservative, not minimal.

The subsequent self-contact gate changes acceptance:169/171check those same five
frozen routes against the full joined-profile width/thickness. Straight and planar
controls separate; gym has a demonstrated interior penetration; spatial roll and
N1Sremain unresolved and are blocked. View171shows the unchanged gym rejected,
with pieces4and6red and the actual occupied witness located. View167and its local
checks remain historical evidence. A bounded170uniform-runway repair fails all
three spatial cases;all trials remain,repair is disabled by default. No collision-free
gym route or impossibility is established. See
[the contact gate and its limits](pinch.md#mandatory-thick-volume-self-contact-gate).

The user's subsequent correction addresses construction itself:179shows the gym
with outward fold returns and displacement-derived steering angles,50.114071mm
and7folds. The same fixed gym now clears local material/pinch/cap checks and thick
envelope separation, as do straight/planar/spatial controls. N1Sstill penetrates and
is rejected:4/5clear within the measured scope, not a general physical guarantee.
All intermediate failures and the178tuple/list comparison stop remain;180reconciles
captured evidence without rerouting. See
[outward construction and complete accounting](pinch.md#outward-fold-construction-instead-of-inward-cancellation).

The user-directed Rubik gym starts from its environment and two connection faces.
It does not author a reference cable, supply a witness route, run a solver or add
physical validity rules. The planar second gym is deferred.

Path search and all seed-based discovery were removed from active diagnostics on
2026-10-30, including the endpoint-seeded local refinements and shooting methods.
The diagnostic palette retains historical results, search playback, measurements,
macaroni shapes, thickness and local frames. New endpoint solving and fresh rule
comparisons are unavailable until a replacement geometric procedure is implemented.
The macaroni/pinch calculation, structural no lateral bending, sweep profiles,
conductor identity/order and geometry construction remain unchanged. Old evidence
keeps its recorded scope; historical mode cannot re-enable retired execution.

Choose **Create/edit gym layout** in diagnostics, author the endpoints, then choose
**Open in solver diagnostics** in the gym. The frozen layout opens without a route.
Existing archived paths remain viewable through the recorded-result selector and
search playback. The gym's randomized layout seed remains an input-generation
control, independent of the retired route-discovery seeds.

Each handoff freezes the complete layout, including seed, percentage dimensions,
selected zones/faces, roll, exact target frames and drawing coordinates. The
**Example / frozen gym layout** selector retains the original examples and every
distinct layout. Returning to an unchanged draft reopens its existing session and
history; editing a face, orientation or dimension creates a separate case. Old
results never follow later draft edits. **Gym layout (both views)** toggles the
same geometry in Fusion and the diagnostic canvas, including before any solver
has produced a path. This is visual context: no new collision, containment or
other physical rule is introduced, and routing boundaries remain undecided.

`devtools.ribbon_analysis.gym.generate(Config(...))` produces a seeded, immutable
layout. The central empty cube has side `void_percent / 100 * lines * diameter_mm`,
with `void_percent >= 300`. Its 26 surrounding cells form a 3×3×3 arrangement.
The independently configurable outer-layer depth is `zone_percent / 100` times
ribbon width. Both controls default to300%; the complete gym side is the void
side plus twice the zone depth. Tangential central-band dimensions follow the
void side, so cells need not remain cubes when the percentages differ.
Two distinct zones receive regular dodecahedra wholly inside their cells.
Each solid touches every inward cell boundary on the nonzero axes of its zone:
one plane in a face zone, two in an edge zone, three in a corner zone. Seeded
variation remains along free tangential axes and in uniform solid scale; the
polyhedra are never stretched to fit. Zone choice, solid size, face and connector
orientation depend only on the seed and dimensions. No solve, fitted route or
success filtering enters generation.

This first preview uses nominal width `lines * diameter_mm`; it introduces no
new bonded contour or profile-padding policy. Virtual dodecahedra are shared graphics,
not native cable solids. Each selected face hosts ordered conductor-circle markers
at its center. Arrows show outward face normals; a future route departs A along
its normal and arrives at B opposite its outward normal. The exposed `Targets`
retain these signs and conductor order.

There are twelve selectable pentagonal faces per solid. The shared renderer
triangulates each polygon as a fan for Fusion and uses the same polygons for
canvas picking. Version2 layout archives record percentage dimensions and
regular-dodecahedron metadata; earlier version1 box snapshots stay unchanged.
Tiny zones can leave insufficient room for a connector marker on a face; the
preview does not resize them to manufacture a feasible routing input.

Launch in an idle Fusion session with an explicitly owned component:

```python
from pathlib import Path
from experiments.experiment_ribbon_test_gym import launch

view = launch(owned_component, Path(unique_ignored_run_directory))
```

Keep `view` alive for the palette callbacks. Use **Generate new layout** or replay
an explicit seed, change either selected zone/face/orientation, or click a colored
face in the canvas. Drag to orbit and scroll to zoom. The palette and native view
consume identical millimeter geometry. Input changes archive new write-once
`layout-####.json` records before replacing the owned graphics. An input failure
does not silently resize the void or move the other goal.

To connect an existing diagnostic viewer without replacing its sessions:

```python
from experiments.experiment_ribbon_test_gym.workspace import Workspace

workspace = Workspace(
    diagnostics, diagnostic_occurrence, gym_occurrence,
    Path(unique_ignored_run_directory),
)
workspace.open_gym()
```

Keep `workspace` alive. Both occurrences must be explicitly owned siblings in the
same development design; `diagnostic_occurrence.component` must be the viewer's
root, and the viewer must have a `ProcedureController`. Connect while no worker is
active. Switching to another example or sending a new gym case is refused until
an active numerical job has stopped and been collected. The workspace archives a
source-pinned layout plan. Archived results retain the context, and imports reject
missing or mismatched layouts. Pure helpers in `gym.handoff` provide write-once
input manifests and validated replay without importing Fusion.

Per edit: 10 seconds, 4 GiB sampled Fusion RSS, 3.8 GiB launch headroom. No native
cable attempts or automatic numerical experiments. The outer grid is visual
context; whether routing is confined to the central void/approaches or uses the
surrounding space remains undecided. Rendering is not a feasibility judgment.

Search diagnosis (`artifacts/verification/ribbon_search134` through `136`) separates
recorded transports from actual exploration. Gym playback contained ten tiny
derivative probes and only one trial; the unchanged broad bank still supplied
sixteen distinct families. The demonstration's128-path excerpt spends110paths
screening before fitting. Compatible shooting refines one seed and does not switch
families after failure. In archived V07, fine-grid damping reset enlarged steps;
full/half trials missed descent available at a much smaller scale. The local
derivative direction was checked independently. Gym bend-cap ablation reproduced
all fourteen paths exactly. These are five existing-case diagnostic observations,
with no solver fix, physical-rule change, new full solve or native validation.
These findings describe the retired search procedures; no new discovery algorithm
is implied by retaining their records.

## Coupled edge deviation prototype

The initial opposing-edge prototype is experiments/experiment_ribbon_edge_pair, outside
the active discovery catalog. Its input is the supplied diagnostic edge, not a
seed bank. B is derived by A - full_width * (W + eta*T) from the same material
frame. Both attachments retain their ordered target sides. At each shared
fraction, A has material progress1 and B has 1-full_width*eta_s; the smaller
positive progress controls the common thickness-pinch demand. Nonpositive progress
is a fold, never a safe negative utilization.

The prototype deforms the existing polynomial with fixed endpoint positions,
tangent directions, width directions and zero cap ruling slope. Terminal speed/
curvature scales and four interior controls can move. Damped local gradient
corrections reduce only the two edge-pinch deficits. This remains numerical
iteration with a limited curve representation; it does not implement a guaranteed
event-driven geometric construction. No containment, contact, length or loop
objective is added. The existing99.6%limit is retained; no extra J reserve is used.
The final513station check is denser sampling, not a continuous certificate.

Runs140/141/142 retained the same four examined configurations: the current gym,
straight, planar quarter-turn and spatial roll. The two simple controls remained
within sampled limits. Neither spatial case was solved; adding degree15freedom
made the spatial outcomes worse. That representation was not retained. Baselines,
every evaluated polynomial, failed results and exact source archives remain under
ignored artifacts. There are four inputs, not twelve independent validations.
No complete native cable was attempted or audited.

View143 displays the retained lower-deficit gym pair from141: A blue, B orange,
failed intervals red, target attachments magenta and target-width bars green.
All four endpoint positions/tangents match;56of513sections still reverse material
progress. Both native original cubic guides are retained hidden. They are
diagnostic sketches, not cable bodies or physical acceptance. View139 and the
four historical sessions remain intact. Sources/math helpers are shared without
changing sweep profiles or conductor identity/order. Active discovery controls
remain retired.

## Shared growth after fold-reversal reset

The subsequent user correction removes any length constraint and requires the
original guide to deform with its opposing guide. `edge_pair.growth` resets to
the supplied original curve. It applies Q=P+(g-1)*(P-C), where C is a degree-seven
endpoint bridge with zero first three derivatives at both caps. Both target
positions remain fixed; the endpoint derivatives scale together, preserving
tangent/width directions and zero cap ruling slope. B and its material progress
are recomputed from the grown A on every evaluation. This grows real geometry.
No length penalty, contact, containment or loop objective is introduced.

A bounded scalar growth bracket and feasibility refinement retain an upper
factor satisfying both sampled edge limits. They do not prove shortest length,
minimal growth, continuous compliance or generalized route feasibility. A final
4097-station check is mandatory; dense rejection switches subsequent evaluations
to that denser grid within the original budget. No seed bank is used.

Run144 resets to139 and reuses the same four development configurations from140.
All four clear the local sampled tests in2.857s total; the gym takes1.367s.
Gym A grows from33.848mm to9235.678mm, with B also9235.678mm. The very large result
must accompany any report of cleared folds. Straight/planar controls stay at
factor1; spatial roll grows to416.044mm per edge. The independent16385half-step
audit finds no sampled folds; gym minimum progress is0.0949621 and peak pinch
99.47913% against99.6%. This audit is sampling, not a continuous certificate;
its runner did not record RSS. The growth run retained resource checkpoints.

View146 displays the grown gym pair (A blue/B orange);139 and143 remain hidden
and intact with all four historical sessions. A1024-interval approximation of B
introduced100.132% sampled display pinch and was retained undrawn as145. Refining
only B's drawing to4096intervals brings that proxy to99.52253%; underlying144
geometry is unchanged. Native guide-point translation error is below1e-12mm.
Display preparation took2.081s and display1.202s, separately from normalization.
Plans, every growth evaluation, source ZIP, independent audit and failed drawing
approximation remain under ignored artifacts. Zero native cable constructions or
post-build physical audits were attempted; native failure rate is unmeasured.

## Local shortening and narrow-peak rejection

The user subsequently rejects the excessive loop. `edge_pair.compact` supplies a
local shortening preference without a hard length bound. It differentiates length
and both signed pinch inequalities, projects the length descent against those
inequalities, and rebases the fixed-cap chart after each retained deformation.
Both guides still come from one changed material frame. This is a bounded local
numerical method, not the intended generalized geometric construction or a proof
of minimum length. Active discovery controls remain retired.

Uniform checks alone missed a narrow B peak in150:4097stations reported98.713%,
but independent16385half-step samples found99.62564%, above99.6%. Preserve that
false acceptance and the frozen regression fixture. `edge_pair.extrema` now refines
dense local-maximum brackets of both pinch utilizations and negative progress
before retaining a pair. It adds finite extremum witnesses, not a continuous
certificate. Nonuniform cached samples retain explicit fraction correspondence.

Run151 examines the same four development inputs; it continues the last dense149
gym checkpoint while the other three start at144. All four clear the new checks
and independent16385half-step audit. Gym length is1279.184mm,86.15%shorter than144,
but still excessive; local shortening stalls. The spatial control shortens from
416.044to249.787mm; planar31.532to30.349mm; straight remains60mm. Gym audit peak
pinch97.40373%, minimum progress0.00105299; spatial audit peak99.55825%.
Targets/frames remain fixed. No practical compact-route or general-success claim.

Failed/stopped accounting:147was blocked at the first RSS read before shortening;
148stopped on a singular straight sensitivity after gym5855.988mm, with planar and
spatial unattempted.149hit12s on gym, other three unattempted.150's independent
audit stopped after the gym miss, other three unaudited.151finished in7.978s;
its independent audit took13.924s. Numerical148..151total31.793s excludes audits,
display and the unmeasured147setup. Plans, source ZIPs and every proposal remain.

View153 shows the retained151gym pair, with146hidden intact.152's A1024/B4096
drawing proxy failed and was not drawn;153uses A1024/B16384, proxy97.85197%,
without changing the151curve. Preparation15.490s, display2.956s; native guide
point translation error1.28e-13mm. A single multiline billboard keeps the labels
readable. Four historical sessions/snapshots/selection remain unchanged. These
are diagnostic guides:0native cable attempts/builds/full audits, failure rate
unmeasured. No further numerical run or native build is scheduled.

## Contraction to an observed constraint

The next user-directed diagnostic contracts the current153pair until a rule
triggers. `edge_pair.contraction` scales displacement from the same clamped
endpoint bridge, recomputes B, and retains both sides of an observed boundary.
All cap positions and tangent/width directions remain fixed. This is one
examined gym configuration with passing/failing variants, not additional coverage
or a globally shortest route. Scalar bisection does not prove the first continuous
crossing in a potentially nonmonotone family. Shared `growth.rescale` preserves the
old growth-only entry point's validation while allowing positive contraction.

Run154:1planned/1evaluated/0native attempts/builds/full physical audits.26evaluations,
5.480s. Primary distance1279.183712to1279.154636mm: only0.029076mm reduction.
Refined B pinch99.598939414%passes; the neighboring shorter1279.154598mm shape
fails at99.601757988%. Both still have positive material progress around0.001027;
A pinch stays22.82182%. The bottleneck is B macaroni, not a completed fold.
Independent deCasteljau evaluation of16385halfsteps plus23extremum witnesses per
variant finds zero violations in the passing shape and one in the failing shape,
in4.887s. Passing B radius10.437266mm
versus minimum10.437155mm. Both ordered cap poses remain numerically unchanged.
The large loop is trapped by this particular geometry; it is not established as
necessary cable length. No seed bank, native profile/build change or extra rule.

View155 shows the last passing source as8192sampled intervals per edge, with
minimum bend circle red, actual B circle blue and a green limiting-point locator.
The circles use analytical source values. Display segments and their individually
hidden native cubic-line guides have no curvature certificate; they are explicitly
sampled geometry. Maximum sampled midpoint position errors A0.00002211mm and
B0.00159181mm; drawing approximation is separate from source-rule acceptance.
Preparation2.730s/display2.530s, native guide translation error1.28e-13mm,
RSS426928KiB. All prior views (including153) are hidden intact; four historical
sessions/snapshots/selection remain unchanged.0native cable attempts, failure rate
unmeasured; continuous/native physical validation absent. No further run scheduled.
