# Gym range tester — 2026-11-03

The selected material-solver diagnostics expose **Gym range tester**. Set Min,
Max and Step for conductor count, diameter, central void percentage, zone depth,
and both endpoints' zone, face and roll. Zones/faces use the gym's one-based
labels; roll uses 0/90/180/270 degrees. Equal endpoint zones are excluded before
scheduling. Max is included only when reached by the step. Decimal stepping uses
exact fractions rather than cumulative floating addition.

Choose systematic or seeded random scheduling. Systematic mode visits the
Cartesian product with conductor count fastest, then repeats with continuing gym
seeds. Each case's gym seed is test seed plus zero-based index modulo 2^32.
Random mode samples reachable stepped values using an independent deterministic
per-case seed. Neither schedule depends on solver outcomes. A plan plus case
index reproduces inputs; runtime-limited solver outcomes need not be identical.

**Start new test** freezes the currently selected solver, first-pass optimization,
smoothing and optional UV settings. Case limit 0 explicitly means keep going until
a problem or Stop; a positive limit ends after that many attempts. A new test
starts a new journal rather than resuming or silently retrying a failed case.
Each range supports at most one million values, without allocating the Cartesian
product. Derived dimensions must be finite.

One case uses the normal numerical worker, native builder and named fidelity
audit. Failed/unresolved/cancelled work, missing native fidelity, unmeasured contact,
source drift, ownership/resource failures or logging failure stop scheduling.
Native dimensional accuracy warnings also stop by default; the checkbox permits
continuing through those warnings without altering any solver or audit tolerance.
Hard failures and unmeasured contact always stop. Full physical compliance and
visual route quality remain unmeasured: an accepted but unattractive route does
not automatically stop the tester.

Worker/native limits remain 120 seconds each, 4 GiB RSS and 3.8 GiB launch
headroom. The ordinary contact/search/accuracy rules remain unchanged. Stop
cancels numerical work or queues behind a synchronous native operation. A distinct
poll boundary after completion prevents another case from launching ahead of a
queued Stop. Cancellation collected after numerical exit skips native creation.
Manual run/layout controls are locked while active; closing the palette stops
scheduling. Reconnect reads the current state; interrupted application sessions
do not automatically restart testing.

Each run writes under the selected workspace's
`range-tests/range-<uuid>/`: immutable plan.json/source hashes, case-NNNNNN.json
complete inputs, append-only cases.jsonl and atomic status.json. Ordinary solver
job directories retain numerical trials, route/native results and build-progress
logs. Successful tester bodies are cleared before the next case; the initial
manual output is preserved hidden. Only the last test case is kept in active
scheduler memory; disk logs accumulate intentionally. Stopping selects the
frozen case and available path/history without clearing terminal status or logs.
**Inspect last case** can reopen it after a temporary host/display issue. There
is no disk resume, automatic retry or automatic visual-quality classification.

Implementation separates ranges, scheduling, journaling, and Fusion ownership.
The diagnostic viewer uses optional TesterControls, controller.inspect_layout
and viewer.open_results to preserve the stopped job; GymView.set_scene shares the
ordinary preview replacement path. The source lock includes all six tester
modules and the external palette JavaScript (192 files total).

## Verification and limits

Focused range/controller/gym/replay tests, scoped Ruff lint/format and a Node
harness executing the actual external and inline palette scripts pass. The client
harness verifies complete range/settings payloads, preserved form edits and queued
Stop ahead of the next poll while native work occupies the bridge. IDE inspection
is clean for new modules/JavaScript/tests; legacy duplicate-fragment weak warnings
remain. The large viewer HTML inspection returns no findings but times out, so
its IDE inspection is incomplete; the actual scripts and live bridge are exercised.

Live setup538 stopped on a stale run_contract import before geometry or palette
replacement; renewed539 reloads the missing dependency and installs idle. Smoke540
stopped before work because its setup guard compared tuple coordinates against
JSON lists. Renewed541 normalizes the same frozen input; no source, case or resource
budget is expanded. All stopped setup evidence remains under ignored artifacts.

541 exercises exactly one complete existing five-conductor configuration via the
actual palette bridge. Numerical acceptance/contact separation, native construction,
and named fidelity each pass separately. Job
`selected-b216ab0995294428bf14a20a0719c192` builds198 faces; 6860 surface samples
pass with maximum error7.954455e-10mm and no warnings. Seams, three material guides
and both caps pass. Generation1.441982s; audit21.994098s. The tester stops after
one attempt/one pass with reason “Configured case limit reached,” selects the case
and preserves logs. No second configuration, native retry, extended soak or full
physical audit was attempted. Failure/stop policies are covered by controlled
unit/client tests, not by claiming broad native geometry coverage.

UI-only542 repeats stopped-case inspection, confirms the same two replay methods,
job/status and native revision, then refreshes the palette for the final range-table
CSS. It launches0solves/builds and leaves the tester inactive with the completed
case/body visible. The smoke's case limit1 remains visible; set it to0 for the
requested until-problem operation. Native computer-use capture exposed only the
main Fusion viewport, so a complete palette screenshot review was unavailable.

Verification used the affected profile: focused pytest paths for range sequence/
tester, build progress, locked controller, diagnostic palette, gym handoff/model/
graphics and inspection consumers; scoped `uv run ruff check` and
`uv run ruff format --check`; changed-file IDE inspections; and
`node artifacts/verification/range_tester537-ui.cjs`. The final installer typing
edit also passes16gym-handoff/controller tests and scoped Ruff. Complete tracked
diff and new-file review pass. Full/repository-wide QA was outside this scope.
Pre-existing duplicate-fragment IDE weak warnings and the old Optional-job string
warning in test_ribbon_locked_controller.py remain; no introduced substantive
findings remain. Extended cycling/native cleanup across multiple configurations
is still unverified live; scheduling/cleanup boundaries are covered locally.

