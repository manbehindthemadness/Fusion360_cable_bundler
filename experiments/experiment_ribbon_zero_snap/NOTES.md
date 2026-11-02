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
