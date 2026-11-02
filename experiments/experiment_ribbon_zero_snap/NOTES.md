# Native-tolerance zero snapping — 410–414, 2026-11-02

Five existing gym configurations planned/evaluated in each numerical phase. Final
413 operation changes one route, re-closes it and passes conservative contact;
four remain identical. One native attempt builds the corrected solid with the
expected142faces, resolving the prior topology-count failure, but fails the later
seam endpoint fidelity guard. Four other cases are not rebuilt. Zero new named
fidelity passes, zero full physical audits and zero untouched holdouts. The working
selected solver/source lock and live gym controls are unchanged.

## Question, threshold and shared calculation

The user requests testing near-zero connector snapping followed by exact reclosure,
with close attention to CPU. Keep the five407material plans fixed as inputs;
do not rerun its joint optimization, selected first-pass optimization or aesthetics.
The three non-triggering layouts retain their407baselines as collateral comparisons.
This is incremental canonicalization, not a cold routing benchmark.

410 reads the live application's `pointTolerance`:1e-6cm, or1e-5mm/10nm. Autodesk
documents this as the internal point-comparison tolerance, in centimeters:
[Application.pointTolerance](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_pointTolerance.htm).
Using it as an experimental connector cutoff does not establish a universal
minimum constructible feature size. No safety multiplier or specimen-tuned
threshold is used. Read-only410 takes.005840s,0solves/builds. Owned document ID
remains `86e5d125-ed43-4b89-b175-dcca0966fae6`, now named `Even more ribbons v2`, idle.

The isolated package uses public `close_lengths`/`affine_projection`, without
changing selected cleanup's1e-7mm threshold or calling its protected helper.
Fix every existing positive straight <=native point tolerance to exact zero;
keep absent straights zero. Preserve fold count/order, angles, banks, profile,
conductor identity and both target frames. Free coordinates are surviving straight
lengths and nonnegative radius growth above the input fold radii. Enumerate at
most1024active masks/10free coordinates, choosing least squared parameter change
subject to all three affine endpoint equations. No angle bank, new feature,
nonlinear fitting or native-solid repair is involved.

Reject remaining tiny straights, cap/material/join errors, increased peak curvature
or unresolved contact. One fresh full-profile1024-pair contact certificate is
required for changed geometry; unchanged plans retain their object and historical
certificate without new projection/contact. All route coordinates are millimeters.

## Preserved rejection411 and explicit revision413

411 freezes all five407input hashes, selected/experimental sources and rule files:
4s/case,20s/phase,4GiB local RSS,one snap operation,1024projection masks and at most
one new contact check per changed case,0native attempts. It completes all five:
one numerical rejection, four unchanged. The near-zero connector is removed and
reclosed, but an added no-length-growth preference rejects the candidate before
contact. No corrected output/native attempt is published for that case.

412 is a frozen one-replay/1s diagnostic,0contacts/builds. It confirms common material
length grows1.105001927e-5mm/11.05nm, exceeding411's7.5e-9mm comparison allowance.
Other measurements are sound: cap4.794e-14mm, material metric5.665e-16, join0,
peak curvature unchanged, surviving minimum straight14.851mm. Replay.003213s.
411 source bytes are preserved under `source_snapshot/*.py.frozen` to avoid
indexing archived code as a duplicate executable implementation.

The user was informed before413 that the failed no-growth condition was an added
optimization preference, not a physical requirement: the ribbon has one shared
free material length. A fresh413plan explicitly replaces it with a hard bound on
each absolute straight-length/radius adjustment <=the unchanged10nm native point
tolerance. Report common length change separately. No physical rule, cap/material/
contact tolerance or native fidelity guard is weakened. Retain411's rejection.
The least-change projection itself is unchanged; neither a second length objective
nor a new search is added.

## Final numerical outcomes413

All five evaluated,0skipped/unattempted numerical cases; no resource/source/harness
stop. New-excursion: one1.295257039e-6mm connector is removed;7pieces become6 and
152authored faces become142.64active masks, maximum straight/radius adjustment
5.413703800e-6mm/5.414nm, common length51.343298968→51.343310018mm (+11.05nm).
Cap error4.794e-14mm, material metric5.665e-16, composed join error0 and separated
full-profile contact. Radius changes are nonnegative; angles/banks remain fixed.

Trigger, gym-recent, gym-one and gym-six remain identical:0projection/contact work,
with only1.6–2.9microseconds each for the no-op scan. This does not revalidate their
historical contact/native outcomes. No additional optimization or uniform feature-
placement improvement is claimed. Hairpin guide RMS changes13.508692786→13.508695943mm;
it retains its large excursion. Parameter bounds do not prove a continuous bound
on every surface point's displacement relative to407.

Reclosure and numerical gates take.003092s; fresh contact.098740s, about.102s for
the changed-route operation. Diagnostic patch-count/guide measurement and artifact
work are separate from that operation.413phase1.378643s wall/1.372545s CPU, peak
28,098,560bytes.411phase.955701s wall/.954052s CPU, peak27,951,104bytes.
These timings exclude prior coarse/joint solving, SDK startup and orchestration;
they are not a cold end-to-end speed claim.

## Native414: topology corrected, seam precision still rejected

After review,414 freezes only the changed hairpin: one native attempt,120s/case,
130s/phase,4GiB Fusion RSS/3.8GiB launch headroom; first failure stops. Four unchanged
routes are not rebuilt. Prior408trigger fidelity is retained historically and is
not counted as a new pass. Predict142authored/native faces after removal of the
tiny ten-face band; complete native fidelity remains unknown before construction.

The unchanged builder returns one positive-volume142-face solid, matching the
new142-face material plan. This resolves the old142-vs152topology guard failure.
Translation.640056s, definition.834568s, kernel4.086100s, generation5.560724s.
Native operation26.008669s; phase26.188957s, sampled peak486784KiB. Timers are wall
time; separate native CPU and audit duration are not retained on this failure.

4900surface samples have maximum error1.066958e-9mm with no failed surface points.
270seam chains checked,20fail endpoint positioning. All20have one shared edge:
connectivity exists, but planned-versus-native vertex endpoints differ by up to
6.071320e-6mm/6.071nm, exceeding the unchanged1e-6mm/1nm seam guard. The live native
point-comparison tolerance is10nm. This suggests a precision-policy mismatch worth
investigating; the property alone does not prove these displacements acceptable
under the project's stricter fidelity contract. No threshold is changed here.

Recorded guide position errors <=3.792e-10mm and tangent errors <=4.294e-8degrees;
both cap records have negligible position/frame errors. The combined seam/tangent
guard raises before final cap enforcement, so these measurements are not a complete
named-fidelity pass. Result is `stopped`, fidelity_audited0, full physical audit0.
Host application logs inspected. No further native attempt, tolerance relaxation,
repair or promotion follows. Failed body remains hidden and report retained.
Its revision is `766a675e-5725-486d-b088-2cffe7c9445b`; other geometry is preserved.

## Verification and retained evidence

Eight new unit tests pass, and nine existing cleanup tests passed in the shared-
projection dependency check. Tests cover native units/invalid policy, unchanged
identity/no extra work, real affine cap reclosure with controlled contact outcomes,
finite work, rejected/incomplete projection and resource propagation. Unit contact
is mocked;413contact is real. The first fixture omitted required before/after
fields; that test authoring error was corrected before numerical411.

Focused Ruff check/format and IDE diagnostics pass for all three new Python files;
complete code/diff reviewed. An initial protected-helper dependency was replaced
with the public bounded projection before411. Archive copies initially triggered
IDE duplicate warnings; preserving them as `.frozen` removes executable indexing
without changing source bytes or suppressing inspections. No full repository QA
or standalone type checker. No selected policy, builder, production or standards
changes. Selected160-file lock verifies unchanged.

Evidence: `artifacts/verification/ribbon_snap410`, `ribbon_snap411` (including412
diagnosis and rejected source snapshot), and `ribbon_snap413` (including414native
plan/result). Executed scripts: `tolerance410.py`, `snap411.py`, `diagnose412.py`,
`snap413.py`, `native414.py` under `artifacts/verification`. All five inputs and
unsuccessful outcomes remain in the denominator. No further experiment scheduled.

## User-requested seam inspection416–418

The user requests viewing the retained failure. No new route solve, body build,
fidelity-policy change or tolerance change runs. One retained gym configuration,
20recorded failed seams and two passing controls. The frozen418plan caps inspection/
display at60s/4GiB,3.8GiB launch headroom,33display samples per shared edge. It
compares the same planned patch corners with native BRep vertices and curve
evaluations at each bounded edge's returned parameter extents.

418 completes22records in5.181458s, sampled peak611840KiB. Body revision and
selected source lock remain unchanged. The20flags involve20distinct connected
shared edges but only four shared vertices exceed the1nmguard. Their errors are
1.138274,1.722393,4.586038 and6.071320nm. Two early passing control seams have zero
reported vertex/curve endpoint residual. These controls are not independent
complete-ribbon coverage or a new native validation pass.

Evaluated bounded-curve endpoints are not uniformly coincident with vertex
positions: maximum planned-corner error18.345084nm and curve-end-to-vertex distance
13.759046nm. Worst example is faces129/119, piece5 bend, left-top profile: the
flagged vertex differs4.586038nm while its evaluated curve endpoint differs
18.345084nm. These observations require investigating native trim-parameter and
endpoint representation before attributing all flags merely to harmless vertex
rounding or changing the guard to10nm. They do not demonstrate visible cracks or
continuous surface error along the edge.

The original body is now deliberately visible and framed at display x980cm.
Red polylines locate flagged shared edges, green marks the two controls; flags
concern endpoints, not a claim that entire red edges are displaced. Nanometre
errors are not visually exaggerated into gaps. Three original frozen guides and
both fixed cap profiles are retained as hidden native sketches. A failed-fidelity
caption remains visible. Overview capture reviewed; no appearance or body geometry
changed. Previous bodies/visibility outside this owned result are preserved.

Setup failures remain recorded: the first MCP wrapper rejected a future import
before execution; corrected416then stopped before measurements because MCP has no
`__file__`.417retains partial read-only records after a display parameter rounded
outside its native bounds.418reuses exact cached endpoint evaluations and clamps
interior display parameters. None of these starts a solver/native build or alters
the body. Executed source copies are `.frozen` to avoid IDE duplicate indexing.

Maintained adapter: `inspect_native.py`; focused Ruff check/format, IDE diagnostics
and complete source/diff review pass. No application tests/full suite are run for
this inspection-only adapter. Evidence and prior failed setup responses remain
under ignored `ribbon_seam416`, `ribbon_seam417`, `ribbon_seam418` and adjacent
transport records. No native acceptance or production promotion follows.

## User review: routing quality takes priority — 2026-11-02

The user identifies the displayed long out-and-back excursion and concentrated
late turning as worse than the earlier result. They also clarify that bounded
seam precision findings should be warnings when they cause no functional problem;
welding/clamping is acceptable in principle. This is not evidence that arbitrary
open topology, material mismatch or downstream failures may be ignored. The
observed seams already share edges; another weld does not address route placement.
No blanket warning threshold or new native repair is implemented in this review.

Read-only comparison confirms identical targets/profile/radius for saved381final
and displayed413.381has first-pass optimization12updates/12contacts, smoothing off;
407/413uses4joint updates/4contacts and excludes that optimizer. Budgets/stages
differ, so no matched speed comparison or causal ablation follows. Nevertheless,
the displayed experiment does not improve on the saved refined route:

| Same layout variant | Material mm | Longest flat mm | Guide RMS mm | Guide maximum mm |
| --- | ---: | ---: | ---: | ---: |
| saved381 after working first-pass optimizer |37.130034|14.264242|9.423004|16.188198|
| displayed413 guide-joint experiment plus zero snap |51.343310|21.267580|13.508696|23.550185|

The earlier reported percentage shortening was against the72.876677mm coarse
initialization, not the saved37.130034mm route. This distinction should have led
the presentation. Snapping itself moves corresponding left/center/right material
stations by at most5.933e-6mm on257fixed samples; it did not create the macroscopic
excursion. These are sampled comparisons, not continuous displacement bounds.

Source inspection identifies two retained limitations relevant to distribution:
407scores bend-center position, without directed heading/history alignment; its
inner closure still enumerates only basic allocations with at most three positive
straight/radius-growth coordinates. Ranking that set by quadratic guide error
does not minimize guide placement over interior feasible allocations. A better
bend-center score therefore does not establish distributed navigational activity.
Treat this experiment as insufficient for the user's placement goal. Repair the
first construction formulation; do not use aesthetic smoothing to mask the run
and concentrated correction or enlarge the candidate bank to chase this specimen.
No solver change, new solve or native build occurs in this review.

The user asks whether the other layouts worked. Read-only comparison of all five
with saved381final confirms identical targets/profile contracts. Against those
working refined outputs, none of the four changed407routes is shorter; gym-one
is identical. Partial improvements remain and should not be reported as universal
failure or as an overall improvement:

| Layout | Saved381 → experiment material mm | Saved381 → experiment longest flat mm | Additional finding |
| --- | --- | --- | --- |
| new-excursion |37.130 →51.343|14.264 →21.268|Guide position/direction worse; built, strict seam flags retained|
| trigger |35.647 →36.686|13.889 →13.440|Slight flat reduction, guide measures worse;408named native fidelity pass|
| gym-recent |17.310 →18.640|2.342 →1.643|Flat reduction, guide position/direction worse; native unattempted|
| gym-one |11.871 →11.871|6.213 →6.213|Identical; native unattempted|
| gym-six |153.666 →154.113|88.853 →88.524|Guide RMS6.346 →6.241mm improves, direction loss worsens; native unattempted|

These are outcomes under different refinement/contact budgets, not an equal-budget
algorithm comparison. No new solve/build is run. One new variant has a named native
pass, one is built with retained strict seam failure, three are unbuilt. No clear
overall routing win over the working baseline is established.

Static419diagnosis refines the earlier sparse-allocation explanation: the hairpin
is already shortest among all6recorded basic closures at its final selected frame.
Its14.851/21.074mm runs are164.777degrees apart; a5.534mm transverse closure demand
with.262572leverage forces the21.074mm return leg. Existing angles/banks/placement
must change to remove the long detour. Total flat travel is91.29%, including flat
leads inside banked folds. Endpoint tangents require180degrees reversal, but do
not establish this large excursion as necessary. See
`../experiment_ribbon_guide_joints/NOTES.md` for all-five-case evidence, limits and
the selected equal/opposite-bank factorization restriction.0new solves/builds.
