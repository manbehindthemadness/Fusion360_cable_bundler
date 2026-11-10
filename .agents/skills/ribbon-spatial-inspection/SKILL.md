---
name: ribbon-spatial-inspection
description: Inspect ribbon material geometry in shared Fusion and four-view displays, commit a spatial-motion prediction, and measure one bounded closure-preserving probe. Use to investigate ribbon shapes and test spatial reasoning before proposing generalized solver improvements.
---

# Ribbon Spatial Inspection

Use the project's existing instrument in
`experiments/experiment_ribbon_spatial_inspection/`. Keep its numerical packet,
Fusion overlay and explanation aligned. This is an experimental diagnostic tool;
it grants no solver-repair, native-build or production-promotion permission.

## Start with the maintained contract

Read the project-root `AGENTS.md`, `experiment_testing_rules.txt` and
`rollback_end_loft_notes.txt` before planning, running or reporting an experiment.
Read [the instrument workflow and limitations](../../../experiments/experiment_ribbon_spatial_inspection/NOTES.md).
Use existing session authorization; the skill does not add an approval gate or
supersede the project's current user-directed exceptions.

Choose the mode that answers the request:

- **Inspect retained current-run evidence:** open its frozen `Ledger` and render
  it without solving or consuming another probe. Historical artifacts may explain
  a prior result; they never become fresh validation cases.
- **New diagnostic:** reserve one unique input with `preparation.author` and
  execute its original numerical worker once. Freeze a bounded plan first. Use
  the maintained fresh-input registry, not a manually chosen or outcome-filtered
  seed. The current author supports N5 only; do not imply broader population scope.
- **Prediction and probe:** use the frozen baseline and the single allowance
  described below. Do not run this mode merely to show an existing result.

## Run through stable entry points

Follow the linked workflow for authoring, original solve and capture. Obtain the
configured SDK using the available PyCharm `get_python_environment` tool before
each Python toolchain invocation. Run numerical work in that cold SDK subprocess.
Fusion's inherited `PYTHONHOME`/`PYTHONPATH` must be absent from its environment.
Do not reload cached solver modules holding live geometry.

- `preparation.freeze_job(directory)` or `worker capture DIRECTORY` captures the
  original accepted or explicitly retained rejected route without solving again.
- `host.Inspector(component, document_id, directory, python_executable).show()`
  owns only the explicitly supplied diagnostic component and palette in the same
  idle Fusion document. Retain the inspector. Do not infer ownership from an
  experiment's private global variables or delete unrelated geometry.
- `Ledger.state()` supplies the shared baseline, committed prediction and result.
  Use the palette's acknowledged native bridge for commit/probe when available;
  `Ledger.commit(...)` and cold `worker probe DIRECTORY` are underlying APIs.
  Host launch and ledger execution markers both prevent automatic repeat attempts.

Do not copy the implementation into skill scripts. Read the relevant module when
an entry-point contract is unclear, and fix the shared implementation if needed.
Missing Fusion permits packet inspection only; report live-display coverage absent.

## Explain, predict, then measure

Inspect top/front/side/isometric views, selected material sections and actual
witnesses. Read the same world coordinates, center frames, cap residuals and
contact/hardware status that the user sees. Bracket width-dependent fold entry
and exit and inspect the affected interval, not only the visible symptom.
Check the selected landmark's actual primitive/ordered-feature kind against the
explanation. A matched XYZ displacement does not validate an incorrect feature label.
When a recovery candidate remains unresolved, locate where certification actually
spent its work; that region can be at the opposite terminal from the original witness.
Distinguish an occupied-point witness from an inconclusive enclosure there.
Treat necessary A-to-B straight travel as spatial work area for distributing
required bend/orientation features, while retaining reasonable total length.
Measure the straight span and chord separately; straight percentage is not a
spare-material allowance. Test explicit feature motion and cap compensation,
without requiring uniform spacing or adding folds merely to fill empty travel.

Before executing geometry, commit exactly one prediction containing:

- `coordinate`, bounded nonzero `delta`, and `section` indices from the packet;
- `expected_displacement_mm`: world XYZ displacement of the selected center
  material point;
- `tolerance_mm`: a declared prediction-scoring tolerance;
- `explanation`: which material moves, how fixed-cap compensation acts, and
  which clearance or shape properties could worsen.

The baseline and prediction must be fingerprinted and sealed before execution.
Use ordered fold/straight-slot identity and normalized material fraction across
appearing or merged straight primitives. Do not substitute primitive indices,
nearest-point matching or a claim of fixed material distance when length changes.
An open-cap baseline is inspectable but cannot be repaired by this probe.
An earlier, already-recorded closed-cap stage of the current failed attempt may
be inspected separately. Preserve its stage, parentage and distinct fingerprint;
never silently substitute it for the original final candidate or award pass credit.

Consume at most one geometry attempt per diagnostic. Preserve blocked, stopped,
incomplete and unsuccessful attempts; do not edit the prediction or retry after
observing them. Preserve startup failures too. A startup failure is not evidence
that geometry ran; review launch/start markers and logs before any separately
recorded recovery within existing authorization.

Use the implemented limits: 4 GiB sampled RSS, 3.8 GiB launch headroom, 120 seconds
for the original solve, 10 seconds for capture, 0.35 CPU/2 wall seconds for probe
geometry, and a separate 10 seconds for post-probe analysis. Keep the existing
pair/cell, coordinate-motion and bounded retraction ceilings; no budget expansion
or search loop. Source drift stops execution. Display-only revisions must retain
the original source receipt and disclose their separate provenance.

## Report evidence and extract reusable rules

Compare the sealed prediction with observed displacement and error. Report cap
closure, bounded contact/hardware results, length change and separate timings.
Verify the retained proposal/result, native overlay and viewer controls without
reexecuting the probe. Use focused tests and IDE checks when implementation changes.

Count independent complete configurations, separately from sections and probes.
State native attempts and missing physical audits. Curved material sections are
not rigid cross-sections; sampled display chords and hardware proxies are not
continuous physical or native certificates. A missing witness is not clearance.
One matched prediction does not establish broad spatial comprehension or improved
solver reliability. Keep diagnostic cases outside fresh validation denominators.

Turn observations into mechanisms with falsifiable predictions and analytical
tests. A later solver change needs separately scoped validation on new unique
layouts, compared with historical aggregate statistics. Never encode a specimen's
seed, saved route, coordinates or desired outcome as a generalized repair.
