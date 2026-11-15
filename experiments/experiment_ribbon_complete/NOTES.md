# Complete-ribbon input capture

This host-independent experimental adapter requires the project Python environment;
it does not require Fusion, perform a solve, or build geometry. Run its focused checks
with `uv run pytest tests/test_ribbon_complete_capture.py` after verifying the SDK.

`capture.capture` accepts a saved harness group, fixed trunk targets, two explicit
ordered cap ports, and an already resolved route and endpoint pair for every root
and descendant attachment. It preserves attachment and association UUIDs, numbered
root conductor identity, route objects, and control order. Missing targets or branch
coverage are incomplete input, not solver infeasibility. The current topology is
one trunk between two connections; other topologies are explicitly rejected.

Point comparisons use the authorized inclusive 0.01 mm dimensional policy without
snapping inputs. Unit-frame identity uses a tighter dimensionless check to keep
cap and route material frames consistent. Duplicate nominal diameter inputs must
agree exactly because they describe the same input, rather than measured geometry.

This is an input contract only. Integrating native cap data into branch construction,
continuous material-coordinate and path audits, contact and junction checks, complete
conductor lengths, and the six-percent complete-path ending allowance remain
outstanding. No input test counts as independent geometry coverage.

Checkpoint 3229 adds the separate read-only entry
`experiments/experiment_ribbon_complete_native_capture.py`. It inspected one retained
N10 trunk with explicit one-to-one face provenance: all 696 lateral faces produced
a sampled physical inverse and round trip, and both registered native cap planes
were captured without nearest-cap fitting. Its frozen input, per-face observations,
resource measurements and receipt audit are under `artifacts/verification/resume3229/`.
This establishes sampled native trunk coordinate recovery and identifies actual cap
geometry for a subsequent branch plan. It does not provide final termination targets,
continuous material compatibility, branch geometry or complete-ribbon compliance.

Checkpoint 3230 adds planned branch length enclosures and the complete-path ending
allowance audit. `curve_lengths.iter_branch_lengths` reads each unchanged frozen cubic
route under one explicit `LengthWork` allocation and the caller's resource checkpoint.
It yields each result so a caller can persist a prefix before a later stop. It defaults
to 0.01 mm enclosure width; a tighter requested measurement must have a documented
need in the caller's frozen scope. This does not change physical acceptance accuracy.
Initialization and subdivision cells are charged without refunds or automatic renewal.

The length enclosure follows two independent geometric inequalities: a cubic's chord
is no longer than its arc, and its control polygon is no shorter. Exact de Casteljau
subdivision preserves those inequalities. Integer square roots bound distance arithmetic,
and outward conversion preserves the final enclosure. Work exhaustion can leave a wide
bound; a small quadrature difference is never treated as an error enclosure.

`lengths.audit_end_allowance` requires a receipt for every branch, every trunk lane,
and both internal end regions. It follows each terminal leaf through explicit parent
links to its root pin. Siblings are alternative paths, not serial material. For each
end it tests the worst opposite termination against
`end_region <= 0.06 * (trunk + start_chain + end_chain)`, including the current end
chain in both numerator and denominator. Internal fitted regions increase the end
region but are already included in the trunk. A single inclusive 0.01 mm dimensional
allowance applies to the full end check. Persistent route UUIDs alone do not permit
stale receipts: the stored source route must also equal the frozen route geometry.

Length ranges with established error bounds can resolve the named allowance; estimates
and ranges crossing the threshold stay unresolved. Trunk length enclosures and their
referenced provenance must be established by the caller's measurement stage. None of
these values certify native loft interpolation or equal material increments. The
current capture contract consumes already resolved branch routes; producing physically
valid branches from boundary targets remains part of the unfinished generalized solver.

Focused verification: 33 tests across capture, allowance accounting, and curve lengths,
plus Ruff and full IDE diagnostics. These include exact analytical length controls,
uncertainty and resource stops, descendant/sibling paths, and stale-source rejection.
They add no independent geometry coverage or native complete-output qualification.

Checkpoints 3231–3234 add `root_profiles.partition` and `bind_frame`. The partition
retains every original exterior arc and closes adjacent conductor roots with opposite
internal seams. Actual native cap planes determine section placement; ordered width
and the material thickness sign remain consistent at both ends. This supplies root
geometry for subsequent reverse lofting, with no nearest-cap selection or overlap.

Three stopped inspection scopes remain recorded: 3231 rejected a component-local
measurement argument, 3232 completed 119/420 samples before its 20-second deadline,
and 3233 rejected a recreated path object during scoped strategy setup. The corrected
3234 callback preserves the guards and original alias identities. It checked all
420 samples against the same retained N10 native caps in 4.17 seconds, with no CAD
changes. Root geometry was identical in all scopes; no tolerance or budget increased.

`native_distance.trimmed_distance_mm` transforms a copied point and proxies its face
in the same assembly context. `native_membership.witness_distance_mm` first uses a
positive native trim-membership query and the actual evaluated native point as a
distance witness; only membership/inverse misses invoke the expensive minimum search.
The witness value bounds distance from above and is not an exact minimum. See the
[Autodesk proxy documentation](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ComponentsProxies_UM.htm)
for the coordinate-context requirement. The frozen 3234 callback is an executed
inspection scope, not an entry to rerun or a renewed allocation.

Root correspondence and 18 additional focused tests do not establish continuous
transition geometry, valid material mapping through an ending, native junction flow,
contact/curvature compliance, or a complete branch build. Those remain required.

Checkpoint 3235 adds `profile_transition.build`: each root edge becomes a rational
quintic/quadratic tensor boundary with the exact root at one end and the prescribed
round conductor section at the other. The first and last three homogeneous rows
repeat, so first and second longitudinal *shape* derivatives vanish at both ends.
Shared material-chart endpoints remain shared throughout the transition. Rational
weights vary along both parameters; existing builders that assume separable weights
cannot consume this plan without an explicit extension and verification.

`transition_certificate.certify` reuses the exact Bernstein polynomial operations
from checkpoint 3204. Positive weights and clockwise boundary determinant bounds
hold over the full parameter rectangle. A separate polynomial residual bounds the
terminal radius error against the actual stored coefficients to 0.01 mm. Mixed
coefficient signs stay unresolved; there is no automatic refinement or point-grid
substitution. Exact source vertices, canonical endpoint weights and repeated control
rows protect coordinate continuity and the proof premise, rather than imposing a
tighter physical dimensional acceptance goal.

Eight focused tests pass. A frozen host-only scope certified all 84 edge transitions
from the 20 root profiles in the native-root receipt, in 0.356 seconds, under a
five-second review deadline. Exact nets and certificate fields are preserved under
`artifacts/verification/resume3235/`. These are coefficient/property checks, not 84
independent layouts or new native geometry. The terminal radius comes from the
fixed conductor diameter; no termination position or branch length was chosen.

This defines continuous transverse boundaries only. It supplies no interior volume
map or spatial centerline/frame. A spatial composition must preserve the actual cap
frame and material signs, derive valid three-dimensional coordinates, and pass the
local and complete material-length, curvature, contact, junction and ending-allowance
audits. Its native construction must reproduce the same frozen plan. Endpoint shape
derivatives being zero does not establish that the full spatial junction is smooth.

Checkpoint 3236 adds exact spatial composition. `FrameSpan` stores explicit polynomial
center, width and thickness fields on an exact interval of global branch parameter.
Controls remain raw; normalization cannot hide a collapsing or scaled frame. The
root's signed material orientation must be retained on every span. `compose` restricts
the original section morph to that interval, then forms complete homogeneous world
controls using exact Bernstein products and degree elevation. Weights remain a full
matrix. World longitudinal degree can reach ten; the native builder must explicitly
support that representation and preserve it through translation.

`SpatialPatch.jet` reports world geometry derivatives in the original global parameter,
including span scaling. `bind_root` checks source placement and material axes against
the actual cap, and bounds the whole root boundary's approach direction. Matching a
center tangent alone is insufficient when moving frame axes add lateral motion.

The coordinate certificate requires both a valid section certificate and a positive
signed ambient frame Jacobian over the full span and conservative transverse envelope.
It verifies actual world controls against the original composition before transferring
that argument. This establishes sufficient *local* boundary-coordinate regularity;
it does not establish global injectivity or physical compliance. Nine focused tests
include valid coordinate charts with extra boundary-path length, singular frames,
incorrect cap approach and tampered geometry, so those distinctions are exercised.

Checkpoint 3237 adds `branch_plan.assemble`, which retains the captured branch identity,
ordered complete spans and original material orientation. It checks source chart closure,
records first/second jet continuity, bounds full-curve centerline correspondence against
the reversed frozen route, and checks the whole prescribed terminal circle and boundary
approach. Missing physical and native checks remain explicitly listed.

Checkpoints 3238–3240 add `material_paths` and `material_traces`. Exact rational speed
residuals bound the integral of absolute longitudinal speed differences. Accumulating
those bounds once across spans covers every corresponding local interval and complete
path, without allowing stretching and compression to cancel. A separate chord versus
control-polygon witness can prove local extension; absence of a witness proves nothing.
Full-boundary uniformity is a diagnostic, not an additional physical equality rule:
through-thickness path lengths can legitimately differ in a bend.

The required comparison uses the original left/center/right mid-thickness traces.
`material_traces.audit` preserves exact source edge parameters at exterior tips and
internal seams, verifies midplane and side identity throughout the morph, and sums
the two center-relative bounds to cover all three comparisons. Unsupported crossings
are refused, not inferred from samples. All original root families N1/N2/N5/N10 are
covered analytically. The unchanged synthetic branch adapter has a certified bound
of 0.0074595872 mm, below the inclusive 0.01 mm gate. The earlier conservative bounds,
source snapshots, exact geometry and revised proof are retained under
`artifacts/verification/resume3238/` through `resume3240/`.

Fifteen focused tests cover these mechanisms, including nonuniform parameter speed,
local distortion concealed by equal totals, changed geometry, missing coverage, span
scaling and the distinction between thickness diagnostics and midline requirements.
Ruff and full IDE inspections pass. These are analytical mechanisms and adapter checks,
not independent complete-ribbon or native coverage. The 3240 audit used 0.314 seconds
wall time; this is a development proof, not an end-to-end solver or recovery benchmark.

Checkpoints 3241–3242 add `branch_lengths`, which measures the actual polynomial center
fields and uses the proven individual midline discrepancies to enclose each required
material path. Its receipt retains the same immutable spatial plan. Preview receipts,
missing bounds, stale plans and incomplete coverage cannot enter its allowance adapter.
`curve_lengths.enclose_segments` shares the existing exact chord/control-polygon
implementation across constant-through-quintic segments and cubic previews. Every
initialization/refinement cell remains charged to the caller's aggregate `LengthWork`.

`lengths.audit_ranges` contains the common interval accounting. The preview adapter
and actual-plan adapter validate their different provenance contracts before calling
it. Actual geometry lengths are never relabeled as preview measurements. A shared
source-chart validator also prevents patches within one span from referring to
different center fields when combining their material bounds.

The frozen 3242 packet measures three analytical complete-input controls, N2/N5/N10:
34 actual branch plans and 17 explicitly straight analytical trunk lanes, under one
51-cell allocation. Every authored candidate correctly fails the ending allowance:
its 3 mm endings are too long for its 10 mm trunk. This does not prove those boundary
inputs infeasible. The packet took 2.427 seconds under its 15-second review deadline,
with at least 54% sampled system memory free. An independent audit reconstructed the
geometry and verified all failures. The prior 3241 receipt and source snapshots remain
unchanged; its bridge was replaced to preserve distinct measurement provenance.

Sixty-one focused tests pass across the affected checks, including stale preview and
spatial-plan receipts, actual changed center geometry, aggregate resource stops,
complete coverage and shared arithmetic. Ruff and full IDE problem inspections pass.
These three analytical controls are not fresh solver layouts or native validation.

Checkpoint 3243 adds `ruled_support` and `branch_bends`. Exact tensor coefficient
bounds cover both principal curvatures of `C(u) + q W(u)` over the complete physical
width envelope, including saddle terms. Thickness scale and displacement from the
oriented unit support normal are measured separately; stored fields are never
normalized to obtain a pass. Positive local coordinates remain a separate result.

The center wide-axis comparison accounts for the original projected width and varying
parameter speed. A moving-frame comparison bounds center departure plus the rotation
effect at the full section reach, using one accumulated inclusive 0.01 mm allowance.
Tiny nonzero arithmetic residuals need not fail an exact-zero assertion. This comparison
does not author a replacement route or move targets. The existing 99.6% principal-reach
buffer retains its normal-offset regularity meaning; it does not establish that a
general raw thickness field is a valid physical normal-offset/material map.

Twelve focused tests pass, including planes, a parabolic cylinder under parameter
scaling, a saddle with a straight center, in-plane bending, section reach, degenerate
metrics and rounded axes. Ruff and full IDE inspections pass. The frozen 3243 packet
adds these named geometric checks to the same 34 analytical branch plans in 1.959
seconds, with at least 53% sampled system memory free. Independent planar-geometry
checks pass. The three complete candidates retain their ending-allowance failures;
there is no new native, fresh-layout or full-physical acceptance credit.

The modules still consume explicit frames and resolved routes rather than solving
branches from endpoint targets. Transverse/interior material validity, actual native
trunk length provenance, curvature, no lateral bending, contact, native fidelity and
junctions remain required. A longitudinal certificate or an allowance finding alone
clears none of those checks. No native or fresh complete-layout evidence was added.
