# Isolated ribbon diagnosis

## Unified end-rule preflight (audit 10)

Spatial mode now checks the solved trunk and all 38 authored endings before the
first native loft. It writes `preflight.json` before construction, including for
cases whose trunk later fails. Every reverse-loft branch reuses its checked route;
a changed center, direction, radius, or identity is rejected rather than replanned.
The sole construction exception is reverse lofting for the split geometry, not an
exception to curvature, length, pitch, or cap-approach rules.

Checks include initial trunk and individual branch curvature, sampled fitted-end
radius and neighbor pitch, internal end-region and branch six-percent limits,
cap endpoint coincidence and approach-normal agreement, and conductor lengths
including both branches. A known violation yields `reject`; otherwise the verdict
is `unresolved`, never a predicted kernel pass. Continuous final-path curvature,
material strain, global clearance, shortest routing, and native interpolation are
not certified by these finite checks. The sampled end-radius comparison retains
the copied solver's trial minimum of three conductor diameters, not a new proof.

This is an audit/ordering revision, not a new route solver. The four-width input
matrix, fixed test connection targets, copied shape solver, internal blend, and
reverse-loft implementation remain unchanged for a controlled comparison.
Diagnostic observation still attempts rejected geometry and reports construction
separately; it must not be interpreted as accepting the candidate. The harness
still does not construct an individual branch if its existing curvature check
rejects it. Current spatial branches pass that check.

The six audit-10 reruns completed with the same matrix fingerprint as audit 9:
all six preflight verdicts reject; four construct 39 solids and two reproduce
the prior main-loft kernel failures. All 228 planned endings have cap-approach
misalignment: 5.625 degrees in the oblique cases and 3.299 degrees in the S cases.
The branch routes use sampled frame tangents while the physical guides use exact
endpoint tangents. All constructed branches reuse their planned routes; the 152
constructed branches still pass the older finite section/rim checks. Those checks
therefore do not establish smooth, rule-compliant end junctions. The S complete
sampled lane spreads, including both endings, are 9.53% and 19.85%.

The visible end-region curling is not repaired by this audit revision. Reverse
loft starts on the actual cap plane but subsequent sections follow the separately
authored branch route; the internal trunk blend is another separate calculation.
The tangent mismatch is established, but its contribution to the visible shape
has not been isolated from the blend/folding and native interpolation effects.
Focused verification: 66 distinct tests passed, changed-code Ruff lint/format and
IDE inspections passed. Reports and native archives were retained one case at a
time; the final S scratch remains open. Production code and design are untouched.

## Current four-width rerun (matrix 8, audit 9)

`--mode spatial --case-index 0` through `5` now uses a sphere of **four cable
widths in diameter**: 114 mm for the unchanged 19 × 1.5 mm material profile.
All previous spatial route coordinates are uniformly multiplied by 0.8 around
the sphere center. Width, thickness, end directions, and prescribed twist stay
unchanged. This is an explicitly changed input matrix, not a same-input repeat.
The legacy five-width inputs remain available through `spatial_cases(5)` for
local comparison; the live spatial mode enforces the current four-width contract.

Both complete end-guide lines must fit the tighter sphere. Interior sweeps are
still unconfined. The 1% length limits, 6% maximum per split end, 15° connection
turns, native topology audit, and curvature policy are unchanged. Compression
makes the four oblique bend inputs fail the existing curvature certificate;
they are labeled curvature controls before execution. Observation mode still
attempts construction, but rejected input cannot become an overall pass merely
because Fusion constructs a solid. Both S inputs retain curvature certification.
The five-width results below are historical comparisons.

### Four-width results (2026-10-04)

All six invocations completed. Four fixtures built a trunk and 38 split exits
each; all 152 constructed exits passed their finite section/connection audits.
No fixture passed all rules. Construction was attempted for all four rejected
curvature controls, rather than treating an input rejection as a kernel result.

| Fixture | Input curvature | Native side spread | Sampled lane spread | Construction |
|---|---|---:|---:|---|
| Oblique quarter, untwisted | Rejected | Numerical zero | Numerical zero | 39 solids |
| Oblique quarter, +45° | Rejected | 3.125% | 41.60% | 39 solids |
| Oblique half, −90° | Rejected | Unavailable | 33.06% | Kernel rejection |
| Oblique half, 180° | Rejected | Unavailable | 46.14% | Kernel rejection |
| Nonplanar S, +45° | Accepted | 0.151% | 10.52% | 39 solids |
| Nonplanar S, −90° | Accepted | 0.586% | 21.65% | 39 solids |

The half-bend failures occurred at the main loft: −90° returned
`ASM_LOFT_SURFACE_SELF_INTERSECTS`, and 180° returned `ASM_BAD_UV_SKIN_DIR`.
Their original exception chains and section evidence are retained even where
the final row error reports the subsequent lane-length audit. The S fixtures
pass curvature and paired-side checks, but still fail interior lane lengths.
These outcomes do not prove shortest-route feasibility or universal prediction.

Matrix fingerprint: `5a91a75e3969b681a53f886bd3c752d76eacec9d24804dc5e49cb2e993455505`.
Reports and F3D archives are in the unique `spatial-00-*` through `spatial-05-*`
artifact directories with matrix version 8 and audit version 9. Previous scratch
documents were archived before closing; the final −90° S fixture remains open.
Production code and solver copies were unchanged. Focused verification passed:
155 tests, changed-code Ruff lint/format checks, and IDE inspections.

## Spatial bend/twist exploration (matrix version 7, audit version 8)

Use `--mode spatial --case-index 0` through `5`, one invocation at a time.
All six fixed fixtures use the inspected production example's 19 × 1.5 mm
proportions, but do not copy or modify its Solid-body design: construction still
tests the experimental Discrete/Split path. Four oblique quarter/half bends use
end-width rotations of 0°, +45°, −90°, and 180°. Two genuinely nonplanar S curves
use +45° and −90° end-width rotations. These prescribed guide rotations do not
guarantee the solver chooses the same accumulated roll. Both full end guides
are checked against the shared five-width-diameter sphere before construction.

Each new connection fixture turns 15°, with the same 6% maximum path length and
unchanged curvature certification. The angle is authored before execution, not
chosen in response to a failed build. Existing compact cases retain 90° turns.
The branch geometry is therefore a new comparison, not a same-input improvement.

The spatial side audit identifies four native longitudinal seams by matching
their endpoints to observed side/lobe junctions at both caps. It does not assume
a world width axis or planar route. Audit v8 follows a unique native edge chain
between a fixed adjacent-face pair, allowing harmless edge segmentation. Missing,
branched, duplicated, disconnected, or ambiguous chains cannot pass; there is no
substitute shortest path, proximity-based stitching, or geometry repair. Both
paired native seam lengths and sampled conductor-lane lengths must meet 1%.
This still does not prove full surface developability or continuous clearance.

All inputs are exploratory build candidates, not guaranteed-success predictions.
Length lower bounds and unresolved optimality gaps are reported. The nonplanar
S fixtures are stress inputs, not certified shortest routes. This first positive
matrix does not replace deliberately invalid controls or prove universal behavior.
No output failure changes a fixture, a copied solver, or an audit threshold.

### First spatial run (2026-10-04)

All six inputs built a trunk and 38 split exits; all 228 exits passed the existing
section/connection audits. Only the untwisted oblique control passed all measured
trunk checks. No case is globally shortest-route or cloth-metric certified.

| Fixture | Native paired-side spread | Sampled lane spread |
|---|---:|---:|
| Oblique quarter, untwisted | Numerical zero | Numerical zero |
| Oblique quarter, +45° | 2.85% | 34.43% |
| Oblique half, −90° | 2.64% | 26.69% |
| Oblique half, 180° | 5.02% | 39.12% |
| Nonplanar S, +45° | Unmeasured | 7.61% |
| Nonplanar S, −90° | Unmeasured | 16.58% |

The −90° half bend also reported 42 local section edges where 40 were expected;
this is an audit finding, not proof of physical self-intersection. Both S cases
returned zero matching direct seam candidates at all four cap landmarks. Their
native side-length measurements remain unresolved, not silently accepted. The
fixed fixtures do not establish whether alternate inextensible routes exist for
those boundary conditions. No result-dependent geometry changes were made.

Reports and native archives are in unique `spatial-00-*` through `spatial-05-*`
directories under the diagnostic artifact directory. Each previous scratch was
archived and closed; the final −90° S case was left open. Focused verification:
74 tests, changed-code lint/format checks, and IDE inspections passed.

### Resolution of the S-case measurements (audit version 8)

Both S-case side seams comprise three native edges between the same two skin
faces. Audit v7 incorrectly required a single edge spanning both caps. The new
topological audit measures the entire unique chain and records its edge/face
identities. Unchanged input fingerprints were confirmed on both reruns.

| Fixture | Native paired-side spread | Sampled lane spread | Overall |
|---|---:|---:|---|
| Nonplanar S, +45° | 0.131% (pass) | 7.61% (fail) | Fail |
| Nonplanar S, −90° | 0.462% (pass) | 16.58% (fail) | Fail |

This resolves the native measurement gap, not the interior lane-length failures.
No solver, fixture, geometry tolerance, or production code changed. Rerun archives
and reports remain separate from audit-v7 evidence. Both builds retained all 38
exits, and the final −90° scratch remains open after archived cleanup. Focused
verification: 76 tests plus changed-code lint/format and IDE inspections passed.

The revised fixture requirement is **shortest feasible deviation**, measured by
total route arc length with fixed prescribed ends and all existing geometry
rules preserved. Both complete end guides still share a sphere of diameter
five cable widths. See the shared experiment README for the full contract.
Legacy matrix-version-4 modes retain the historical oversized return and do
not implement this requirement. Their archived results must not be presented
as shortest-route tests; their saved scratches are historical evidence only.

The default `compact` mode is matrix/audit version 6: six planar 90/180-degree
bends across 3/5/19 lanes, with exact endpoint normals and sampled-frame section
planes. It does not preserve the old oversized stress cores or compare identical
inputs. Constant-width translated input sides have equal lengths. Radius is
1.001 times the existing curvature-policy minimum; subdivided cubic chord/control
polygons bound route length. Tangent rotation divided by maximum curvature gives
an independent lower bound, with a reported gap of approximately 0.10004%.
This is a near-minimum trunk fixture, not an exact global shortest-route proof
or a minimization of the complete split-connection network. Each split-end lane
is capped at **6% of the central trunk route arc length**, excluding both end
regions. This is a maximum per end, not a 6% combined allowance or a minimum.
The authored quarter-turn radius is uniformly capped using a branch-length upper
bound and trunk-length lower bound. Existing curvature certification is unchanged:
a 90-degree transition that cannot fit legally is rejected, not enlarged, flattened,
or given a relaxed bend limit. This cap measures authored paths, not every native
skin fiber. Version-5 runs retained eight-width end turns and are historical only.

The 1% sampled lane target is mandatory in this mode. Native paired longitudinal
side/lobe seam edges are independently compared at both thickness levels; missing
or ambiguous rails cannot pass. This boundary-length check is not a complete
surface-strain/developability test and does not measure every material fiber.
Native edge sampling preserves the exact API parameter endpoints and clamps
interior samples to their finite bounds. This prevents floating-point endpoint
overshoot without changing geometry or widening the 1% tolerance.
Even when all measured audits pass, status remains
`audited_with_unresolved_optimality_gap`, not unconditional rule certification.

Requires Fusion, the local MCP server, and no active command. Production source snapshots
are hash-verified; production files are never modified. Output audits may fail while
geometry construction is still attempted. A constructed solid is not a rule-valid pass.

Run `experiments.experiment_ribbon_diagnosis_runner` with `--mode` and `--case-index`.
Each invocation executes exactly one indexed case, including for smoke mode. Baseline
uses historical inputs; planes changes only interior section planes; caps additionally
authors analytic endpoint normals; dense additionally uses 128 sections. These are
controlled experimental comparisons, not production fixes or proven durable solutions.

Each invocation creates a unique directory under
`artifacts/verification/ribbon_failure_diagnosis/`, containing `report.json` and
`geometry.f3d`. Reports identify the next index and explicitly distinguish completion
of one case from the full matrix. Historical reports are not overwritten. The previous
scratch named `Ribbon failure diagnosis` is exported and verified nonempty before it
is closed. Export failure leaves that document open and stops the next build. Other
documents are untouched. The final diagnostic document remains open for review.

The earlier retained-matrix run exhausted memory (approximately 60 GB reported by the
user) and its unsaved document was lost on force-quit. Its partial baseline and smoke
JSON reports survived. One-case execution limits accumulation, not peak kernel memory;
closing documents may not release all host memory. Restart between extended sessions.
Stopping the local client does not cancel an in-flight Fusion kernel operation.
