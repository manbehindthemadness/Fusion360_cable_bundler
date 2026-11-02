# Guide-derived tight feature insertion — 420–423, 2026-11-02

Five existing gym configurations planned/evaluated in each numerical phase, with
matched baseline and inserted variants: not ten independent configurations per
phase. No compact contact-safe added-feature success is established. Three421
matched tight baselines improve on saved working outputs. One improved baseline
is natively attempted/built and passes named fidelity; four other configurations
are natively unattempted. Zero inserted variants natively attempted, zero full
physical audits and zero untouched holdouts. Selected solver/live gym unchanged.

## User question and fixed procedure

The user directs bend-feature insertion before radius relaxation, using the
pre-planner to avoid guessed station/angle banks. A feature here is one steering
rotation stage with incoming/outgoing material frames. Baseline has two stages;
one added stage gives three. A stage may require two legal fold primitives:
four versus six in these generic constructions. Counts of native faces/child
operations never count as independent route coverage.

Both variants derive the same material-frame references:257sampled guide tangents,
minimal tangent transport of entry width, and shortest signed terminal roll spread
by approximate guide arc length. Positive pi resolves an ambiguous half-turn.
Endpoint-only inputs carry no extra winding prescription. This is a placement
reference, not a physical ribbon prescribed to follow the cubic; sampled stationary
or unresolved opposite tangent steps remain unresolved.

Keep guide parameter1/2for the existing site. Choose the half with greater absolute
heading variation, ties toward entry, and insert its cumulative-turn midpoint.
Only this one station is offered. Exact algebraic root ambiguities of that same
frame sequence are enumerated, at most8chains/6primitives. This is not an angle
grid, route seed bank or a set of guessed alternative landmarks.

Both matched variants lock every fold radius to the declared radius floor from
the input contract. No radius growth, relaxation, cleanup or aesthetic pass runs.
Saved381working references may have enlarged radii; comparison with them is a
different mode, not a matched radius ablation. The new transport-width convention
is common to baseline/insertion, so insertion-only comparisons do not silently
change frame policy.

The shared steering site is the midpoint of the full constant-orientation flat
interval between adjacent stages, including intrinsic flat leads. Guide positions
are soft preferences; endpoint XYZ equations are hard. Nonnegative straight
allocation enumerates at most128active masks/7slots, solving each mask's interior
constrained least-squares optimum through a nullspace. Mean squared shared-site
position error ranks first, material length breaks ties. This is actual spatial
placement over interior allocations, not nonlinear scoring of LP vertices alone.
Positive sub-native-tolerance explicit straights reject instead of changing cap
targets or radii. Only an exact closed route with valid material metric proceeds
to thick-profile contact. Two contact attempts per variant,1024subdivisions each;
all other derived roots remain explicitly unattempted for contact.

420and421freeze input/source/rule/script hashes before execution. Five saved381
working routes supply fixed target/profile/radius-floor inputs and reference
metrics. Limits4s/case,20s/phase,4GiB local RSS; one extra stage,8root combinations
per variant,6primitives,128straight masks per chain,2contacts/variant,4contacts/case.
First source/resource/harness/accepted-cap/material error stops remaining work.
No scope, time, candidate-bank or physical-tolerance expansion occurs in-flight.

## Preserved420: guide orientations held fixed

All five complete with no compact insertion gain,0native attempts. Hairpin has no
fixed-radius nonnegative closure in either variant. Trigger baseline is separated
at30.380548mm; inserted variant exhausts its two contact proposals. Recent baseline
and insertion fail conservative contact acceptance. Gym-one insertion is separated
at36.940523mm, much longer/worse than its11.870847mm working reference, while its
matched baseline cannot close. Gym-six variants exhaust contact acceptance.

420contact outcomes: baseline1separated/2unresolved/1penetration; inserted
1separated/6unresolved/1penetration. The one inserted feasible result is not a
compact routing success. Phase3.061349s wall/3.054831s CPU; all failures/untested
root contacts retained. Executable package snapshot is preserved as `.py.frozen`
under the420evidence before the explicitly reviewed421revision.

## Reviewed421: bounded coupled angular closure

The user was informed before renewal that exact fixed guide orientations still
overconstrain spatial feasibility. Keep the same stations and all radii fixed;
allow shared internal joint orientations to adjust by endpoint-residual-derived
corrections. This is bounded first-construction constraint solving, not a second
optimization/smoothing pass or guessed angle discovery.

Initially unclosed roots project the endpoint into the current straight-direction
cone using at most64supports of up to three rays in XYZ. Differentiate actual
endpoint placement at that allocation with six fixed1e-5rad probes per shared
joint. Solve the three linearized endpoint equations for a minimum-norm angular
correction, norm capped pi/4. At most2corrections/2step halvings per root; finite
steps must reduce the real reprojected residual. Preserve root indices/group sizes;
branch loss remains unresolved. Refit the coupled straight allocation only after
cone closure, and accept geometry only after exact cap/material and contact gates.
Station origins remain on the same pre-planner targets; their desired headings
initialize angular variables rather than being treated as inflexible physical
constraints. Total case/phase/contact/RSS budgets remain identical to420.

All five complete,0skipped/unattempted configurations,0resource/source/harness
stops. Added-feature variants:0/5compact contact-safe successes within the two-root
contact budget. Ten tested inserted proposals give3demonstrated penetrations and
7unresolved certificates (budget or near-contact resolution). Other derived closed
root contacts remain unattempted: no infeasibility claim follows. These failures
are retained, with exact full-profile witness points where available.

The matched baselines improve three layouts without an extra feature:

| Layout | Working381 → tight baseline mm | Longest flat381 → baseline mm | Construction s | Contact s |
| --- | --- | --- | ---: | ---: |
| new-excursion |37.130034 →23.779318|14.264242 →6.548796|.049676|.089291|
| trigger |35.646795 →30.380548|13.889401 →10.738430|.058085|.167549|
| gym-one |11.870847 →9.865556|6.212633 →4.110665|.056210|.118827|

Each has shorter material and lower ordered guide RMS/direction loss than its
saved381reference. Guide RMS respectively9.423→5.318mm,5.865→4.153mm,1.728→1.636mm.
Recent and gym-six matched baselines remain contact-unresolved. Baseline trials
total3separated/4unresolved contact outcomes. Frame preparation adds4.5–4.7ms/case.
Both-variant totals per case.633–1.297s;421phase4.642013s wall/4.633515s CPU.
Construction times are subsets excluding contact, not cold full-process timings.
Combined420/421CPU7.688346s excludes SDK startup, imports/source-plan preparation
and orchestration. No comparison to old381's different budgets is a matched speed
benchmark. Improvement in baselines must not be credited to feature insertion.

These outcomes identify a useful cheap spatial/frame-closure change, but the
extra feature still needs contact-aware placement. Seven unresolved proposals
are not known collisions. Three actual penetrating proposals must not be accepted
or relabelled as precision warnings. No third numerical tuning run is scheduled.

## Separately reviewed native422 byproduct and display423

Because no inserted variant earns native construction under the prior scope,
freeze a new one-body plan explicitly for the improved four-primitive/two-stage
tight baseline on the original hairpin. This is a byproduct construction check,
not insertion validation. Limits1attempt,120s/case,130s/phase,4GiB Fusion RSS/
3.8GiB launch headroom; first failure stops, no retries. Other four configurations
are unbuilt. Predicted native outcome unknown before construction.

Preserve the unchanged strict fidelity audit. The user's bounded shared-seam
precision-warning preference is registered separately, with topology/surface/
guide/cap checks remaining hard. No warning exception is needed: native422passes
the original named checks, one positive-volume152-face body,5250surface samples,
290seam chains,0seam failures, maximum surface error5.864080e-9mm. Three guide
positions/tangents and both ordered caps meet the existing thresholds. No full
physical or downstream-operation audit is claimed.

Translation.337077s, definition1.309356s, kernel1.622000s, generation3.268433s;
audit30.043926s, native operation35.186152s, phase35.196837s, sampled peak724704KiB.
These are wall timers; native CPU is unmeasured. Incremental accepted baseline
construction/contact plus frame preparation is about.144s on this layout, below
matched generation; this is not a cold process-time or general performance claim.
UV/textures/appearance generation remains off.

423 is display-only:30s/4GiB plan,0solves/builds,1.032730s actual. Accepted baseline
at display x1040cm retains three hidden original material guides, both existing
hidden joined cap profiles and the magenta exact pre-planner cubic. Capture reviewed.
It remains an excursion, but appreciably smaller; no global-optimum claim. Native
revision `2da13e75-7ed9-48cd-b68c-09376a22ac84` unchanged. Graphics/browser labels
explicitly say added feature disabled. Earlier bodies/views/history are preserved.

## Verification and retained state

Eleven new analytical tests pass; eight existing joint-route tests passed in the
shared-helper check. New tests cover covariant guide sites/terminal frames, no
invented insertion on a straight guide, interior allocation, fixed radii and exact
closure, real three-stage construction, conservative mocked contact/work bounds,
resource propagation, nearest-cone residual and algebraic rotational reclosure.
Contact is real in420/421and mocked only for unit boundary tests.

All seven new package Python files plus their tests pass focused Ruff check/format
and IDE inspections; complete code/diff reviewed. Tuple-return typing and import
ordering findings corrected before421; no physical gate softened. No full repository
suite or standalone type checker. Selected160-file source lock verifies unchanged;
no production, selected policy, native builder, runtime configuration or standards
change. Nothing is installed as the active gym solver.

Evidence: ignored `artifacts/verification/ribbon_features420` and `ribbon_features421`,
including both numerical variants/all rejected roots and masks, source pins,
native422plan/results and inspected423capture. Executed runners `features420.py`,
`features421.py`, `features422-native.frozen`, `features423-display.frozen`. Historical
strict failures remain. The added-feature goal is not achieved by these experiments.
