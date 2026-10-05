# Isolated Discrete/Split ribbon experiment

## Current route requirement: shortest feasible deviation

Both complete cable-end guides must remain inside a shared sphere of diameter
five nominal cable widths. Subject to the existing macaroni rules, prescribed
end positions/orientations, required connection transitions, and clearance,
minimize total route arc length. Leaving the sphere is permitted only as part
of the shortest feasible route; it is neither required nor a license for an
arbitrarily large return. Do not relax rules or move the specified ends to
shorten a route. Negative controls remain deliberately invalid and labeled.

The current matrix-version-4 fixture does **not** implement this requirement:
its preserved stress core, fixed eight-width terminal turns, and two-cubic
return with a twenty-width scale allowance were authored without length
minimization. Existing runs remain historical diagnostic evidence, not evidence
of compliance with this revised requirement. Merely reducing that allowance
or selecting the shortest of a few candidates does not prove shortest feasible
deviation. A replacement must report its feasibility checks, length objective,
and optimality evidence or explicitly identify an unresolved optimality gap.
Do not rerun the old matrix as a test of the new requirement.

Status: **stress-test harness, not a universally certified solver**. Production
is unchanged. No result-dependent fixture repair, endpoint relocation, or
geometric fallback is used. Do not promote this experiment into production yet.

The snapshot originates at production commit `09d9e60`. Copies retain the
production frame transport, bank lattice, lane fitting/folding, guide measurement,
main fitted loft, and split-exit loft. Imports and formatting are adapted for
isolation. General changes reject an infeasible bank, prohibit fitted-loft-to-sweep
fallback, and require a cap parallel to its guide containing every ordered lane.
Domain models, vector primitives, profile/material helpers, and Fusion remain shared
dependencies. This is not yet a duplicate of the complete harness routing workflow.

`contract.py` certifies a continuous cubic curvature upper bound using derivative
Bernstein hulls and bounded de Casteljau subdivision. The full discrete profile
envelope includes side caps and thickness, irrespective of bank. The maximum
permitted curvature × reach ratio is 0.8. Singular, discontinuous, nonfinite,
or uncertifiable inputs fail before construction. Cable-end branch cubics receive
the same contract, with an enclosing lobe reach rather than only the exit radius.

`cases.py` crosses nine deterministic families with 3/5/19 lanes: straight,
spatial S, broad hairpin, 180-degree roll, rising 360-degree helix, close return,
tight-radius policy rejection, nonlocal crossing, and an undersized end guide.
These are exact C1 cubic fixtures inspired by the spaghetti stress dimensions;
they do not replace the PH quintic corpus or claim identical kernel outcomes.
Geometry, case identities, numbered lane order, and expected classifications are fixed before
execution. The nonlocal controls visit the same interior point twice with
different tangents. If the guard admits them, the harness reports a guard gap
and does not construct their unsafe solids. A tight-radius policy rejection
tests the conservative guard; it does not prove the bank-aware ribbon is illegal.

`transitions.py` applies the same terminal-transition fixture to **every** family,
including negative controls. Two added tangent-continuous quarter turns bend the
trunk in its thickness plane right up to its fitted caps. Every ordered lane
then turns 90 degrees between its cap and an actual round connection sketch
profile, normal to the connection tangent. Both turns use radius eight times
the ribbon width; original interior stress curves remain intact. No result is
used to choose geometry. This changes the matrix inputs, not the solver, and
must not be compared against the old straight-terminal/fan-out fixtures as a
same-input improvement. The connection profiles are explicit planar test
geometry, not a complete production connector or branch-planner workflow.

Matrix version 4 additionally puts both **complete cable-end guide lines** in
one shared sphere whose **diameter is five nominal ribbon widths** (`lanes ×
conductor diameter`). `end_boundary.py` preserves the incoming cap turn and
original interior stress cubics, authors a uniform two-cubic return, and places
the outgoing cap two widths from the incoming cap. Its terminal quarter turn
retains the same radius. The sphere is centered halfway between the two caps.
These inputs are fixed before solving; no solver result chooses their geometry.
The boundary neither requires nor prohibits sweep excursions. Existing stress
fixtures extend outside it, but a wholly internal sweep is also acceptable.
Split connection profiles are not confined. Both authored guide extents and
actual Fusion sketch-line extents are checked; curvature, bank, cap, branch,
and interference policies remain unchanged. Each result records the sphere
and largest guide radius. This is a new input matrix, not a same-input repair.

Every row registers both ends and every lane before a guard runs. Safety
rejections record `not_reached` and a reason; they are not fabricated passes.
Once a trunk exists, independent audit failures are accumulated rather than
short-circuiting its cap/connection checks. A missing cap blocks only that end;
an exit construction failure does not skip other lanes. Each built exit receives
independent section and eight-point connection-rim audits even if one fails.
The connection check requires a unique planar end cap matching the authored
profile center and normal, with all rim landmarks on that cap.
These landmarks do not prove continuous tangent or curvature continuity of
the generated skin across the cap seam.

`live.py` creates actual cable-end sketch lines at both ends, reads their fitted
lane centers, builds the copied fitted main loft, and constructs every numbered
split exit. This exercises the copied ribbon solve/build path, not the full
harness centerline/branch route planner: root cubics are explicit test inputs.
Main sections require one identifiable local contour with exactly
`2 * lanes + 2` edges. Remote return-leg contours are recorded separately.
The local contour locator follows the solved median lane so intended folding
is not mistaken for a missing route-axis contour. Every cubic is intersected
at 39 interior parameters. Additional checks require numbered lobe midpoints
on the trunk skin, both fitted caps, the complete output body count, and no
split-exit pair intersection. Trunk/exit interference permits the builder's
intentional 0.02 mm cap seam through a conservative volume allowance.
Frame bend-plus-roll, lane-length spread, pitch, and face transitions are recorded
as diagnostics, not arbitrary repair thresholds. A failed case removes its
entire scratch occurrence. These sampled
audits do **not** certify global surface injectivity, continuous section fidelity,
bank/twist effects, folded lane geometry, or nonlocal clearance. The input
curvature certificate alone does not certify the Fusion loft. These are blocking
requirements for the requested durable solver, not optional fallbacks.

Reports separate `built_and_audited`, `expected_rejection`, `guard_gap`,
`audit_failure`, `unexpected_rejection`, and `unexpected_failure`. Expected
rejections are not counted as built ribbons. Any unexpected output or unresolved
audit prevents promotion. A second temporary scratch repeats a representative
of every observed status/stage and a 19-lane failure if present, then closes;
the final full-matrix scratch remains open. Stable failures remain failures.
Each case checkpoints the ignored report. Exact input fingerprints and audit
versions prevent comparing changed experiments as though they were repeats.

Run `uv run python -m experiments.experiment_secure_ribbon_runner` with Fusion,
the add-in, and the local development MCP server running and no command active.
The runner replaces only the scratch named
`Secure ribbon experiment — Discrete Split`. Other documents are inventoried
without changing them. Reports are generated under ignored
`artifacts/verification/secure_discrete_ribbon_bounded/`. Earlier reports under
`secure_discrete_ribbon/` are preserved. Unit regressions live in
`tests/test_experiment_secure_ribbon.py`.
Matrix/reporting regressions and folded-section locator checks are in
`tests/test_experiment_ribbon_stress_cases.py` and
`tests/test_experiment_ribbon_audits.py`. `--inventory` only inventories documents;
`--close-unmodified` closes unchanged documents while preserving modified designs.

## Earlier straight-terminal run (2026-10-04)

All 27 primary cases completed: 14 built and passed the finite audits, six
controls were rejected as expected, three self-crossing controls exposed the
nonlocal guard gap, and four output audits failed. The retained positive cases
contain 246 solids and passed 10,296 section intersections. Six representative
cases repeated in a separate scratch with unchanged classifications; that scratch
was closed. Repeatability does not turn the recorded failures into successes.

The three-/five-lane near-return exit inputs produced measured branch overlaps
of 0.454811 and 4.86887 mm3. The 19-lane spatial case missed the first lobe
landmark at gate 9. The 19-lane near-return case did not yield an identifiable
local contour at sampled station 21/40, even using the solved median-lane
reference. That last result remains an unresolved section-fidelity finding,
not a proven diagnosis of Fusion's internal failure. The authored branch inputs
do not establish what the complete production branch planner would produce.
No geometry repair or solver change was made to remove these findings.

Those figures describe matrix/audit version 2, not the new curved-terminal
matrix. The latest report is
`artifacts/verification/secure_discrete_ribbon/report.json`.
The solver is **not** cleared for production promotion.

## Curved-terminal run (2026-10-04)

Matrix version 3 / audit version 4 completed all 27 cases: 14 passed the finite
audits, six controls were rejected, three exposed the nonlocal guard gap, and
four failed trunk-section audits. All 324 constructed split exits, including
those belonging to failed trunk cases, passed their section and connection-cap
checks (2,592 connection-rim landmarks). The 162 transitions belonging to the
nine negative controls explicitly record why construction was not reached.
The retained 14 cases contain 214 solids. Six representative repeats had
unchanged classifications; their temporary scratch was closed.

| Failed trunk | Cubic / total | Station | Fixture region |
|---|---|---|---|
| `near_return_5x1` | 3 / 6 | 2 / 40 | Interior return bend |
| `broad_hairpin_19x0.5` | 1 / 6 | 2 / 40 | Incoming cap turn |
| `helix_360_19x0.5` | 1 / 6 | 8 / 40 | Incoming cap turn |
| `near_return_19x0.5` | 2 / 6 | 37 / 40 | Interior approach leg |

Each finding is an unresolved failure to identify a local sampled contour,
not a proven diagnosis of the kernel or a certificate of physical self-contact.
No solver repair was made. Successful connection correspondence does not
cancel a failed trunk audit or prove continuous skin behavior through the seam.
Focused matrix/coverage/audit tests (64 total), changed-code Ruff checks,
format checks, and IDE inspections passed. No repository-wide suite was run.

The final full-matrix scratch is active. Existing user documents remain open,
including modified `Wire creation tester v112`; no user work was saved or
discarded to enforce a single-document review state.

## Endpoint-bounded run (2026-10-04)

Matrix version 4 / audit version 4 completed all 27 cases. Both full guide lines
are inside the five-width-diameter sphere in every case. None of the 18 positive
cases passed all geometry audits: 13 have trunk-audit findings and five failed
main-loft construction. All 194 exits constructed for the 13 audited trunks
passed their independent section and connection-cap checks. The six expected
negative rejections and three nonlocal guard gaps remain separate outcomes.
Six representative repeats had unchanged classifications.

The five construction failures are the 3-/5-/19-lane near-return lofts and the
19-lane straight/spatial section profiles. Trunk findings occur on the incoming
cap cubic; the 19-lane helix additionally has a lobe landmark with two face hits.
These findings do not by themselves diagnose physical self-contact or the
kernel. No solver or audit repair was made. No solids are retained under the
existing failed-case cleanup policy. The new report is
`artifacts/verification/secure_discrete_ribbon_bounded/report.json`.

All 110 focused experiment tests passed, alongside changed-code Ruff lint,
format checks, and IDE inspections. The boundary tests accept both wholly
internal and externally deviating sweeps; neither trajectory is required.
No full application or repository-wide suite was run.

Source SHA-256 values:

| Production source | SHA-256 |
|---|---|
| `routing/ribbon.py` | `33135930a99ed0e2e8552418db851c61a4b752cacb0d48a4927d8ad4d1e9910a` |
| `routing/ribbon_bank.py` | `3aec42126af61b00b3a88204348b8a92949691838e4346b88de669cdb57e6986` |
| `routing/ribbon_shape.py` | `661cc2c4848e860b809f429295d9ae917f6041049535e1e3dba869238c31bf05` |
| `fusion/ribbon_geometry.py` | `0d507d5d5dfd46b01f671753a94604b09c821055a3edc82a3a2784717589cbc7` |
| `fusion/cable_solid_parts/ribbon_builder.py` | `21b412cdc226649696555d0faec60a981eff0b0c65a92c1a0575b04c7c41a673` |
| `fusion/cable_solid_parts/ribbon_exit_loft.py` | `d43ce7011ef6ef0c5b438dd53b3875a4b1444a7adc3fad636ee489ce328c777b` |
