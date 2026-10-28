# Reproducible ribbon case generation

Use `devtools.ribbon_analysis.case_generation` before a generalization run. It
creates fixed boundary inputs and scenario metadata;it runs no solver,Fusion
graphics,native construction or feasibility filtering. Existing experiment budgets
still govern later execution. Keep native sweep bodies hidden in their respective
experiment Bodies folders and informative diagnostics visible by default.

## Allocation and inventory

The default64cases contain16normal,16stress and32random challenges,in that order.
Sizes48..4096in multiples of4preserve exact25/25/50allocation. The lower bound
reserves space for every mandatory normal solo and combination;the upper bound is
a generator workload limit,not a geometric restriction or native batch allowance.

Every normal quarter starts with these stable solos:U180,S(two opposing45degree
bend intents),lateral45/90/180,and twist45/90/180. Four fixed compounds follow:
U+twist90,S+lateral45,lateral90+twist45,lateral45+twist180+S. Additional normal
slots use reversed compound orders and dimensional/reference-scale variations.
Normal controls express a regression expectation;they are not newly certified
feasible geometry. Never change them to rescue an ongoing solver test.

Stress starts with all exact entries in the tracked
`devtools/ribbon_analysis/case_generation/stress_inventory.json`:legacy07/08/11/
12/13,G07/G08,and B02's practical-versus-strict target-closure case. Historical
source paths/digests and interpretation travel with every case. Ignored reports
are not runtime dependencies. Extra slots compact those boundary chords with
fixed lineage;their feasibility is unknown. Do not infer physical impossibility
from a historical solver failure. To promote a new failure,save its exact targets,
identity and evidence source,revise the inventory/generator version between runs,
and preserve old manifests. Increase batch size if the stress quarter cannot fit
the full inventory;never silently drop a known case.

## Choose a generation mode

Both modes use the same solver/diagnostic handoff and retain the exact normal and
stress quarters. Select `mode="random"` or `mode="installation"` in `generate`,or
`--mode random|installation` in the CLI. The original `random` mode remains the
default. The `random` stratum name means the dynamic half in either mode;case IDs
use `R...` for arbitrary poses and `I...` for installations.

### Arbitrary poses (`random`)

This half does not combine a small set of successful fitted shapes. It
independently samples both full3Dendpoint frames using uniform unit quaternions,
chord direction uniformly on the sphere,conductor count uniformly1..64,diameter
log-uniform.5..1.5mm,and chord length log-uniform.25..12nominal widths. Start
positions occupy a box of+/-3nominal widths. `RandomBounds` configures conductor,
diameter and chord ranges within the analyzer's1..128conductor support. No sphere
limiter,curvature rule,solver score or successful output influences generation.
These inputs have unknown feasibility. Keep that distinct from positive-control
expectations and known-invalid controls;a search failure is not an infeasibility
proof. The generator currently provides no known-invalid oracle.

### Connector installations (`installation`)

The dynamic half cycles evenly through five generic engineering families:
same-board,parallel-boards,perpendicular-boards,reversed-connector,and
board-to-panel. Board relationships couple the two connector poses;they are not
independent full-space rotations. Dimensions,spacing,lateral offsets,connector
heading and assembly yaw vary within those relationships. Yaw turns the whole
assembly together;rigid rotations do not count as extra family coverage.

Default chords span2..12nominal widths. Diameter retains the log-uniform.5..1.5mm
range. Conductor counts are drawn from6,8,10,14,16,20,26,34,40,50,60,64within
the bounds. Explicit `RandomBounds` overrides the scale ranges;when its conductor
range contains none of that preferred inventory,counts are uniform within the
supplied range. Mount standoffs span0.2..0.5widths and the declared room extends
1.5..3widths beyond endpoint coordinate bounds. These are test assumptions,not
manufacturer limits or a real-world prevalence distribution.

Each `case.installation` freezes the mounting family,two connectors and an
axis-aligned inspection room. Each connector records its cable exit point,
outward departure,ordered width,mount point/normal,board-or-panel kind and mating
direction. The path leaves the start along its departure and arrives **opposite**
the end connector's departure. Width points from first conductor toward last;
never flip it to eliminate a required twist. Mating and cable exit can differ:
the same-board family includes cable exits parallel to the board with mating
normal to it.

Mount planes and room are contextual metadata,not enforced solver obstacles or
containment rules. Housing keepouts,required straight leads and mechanical contact
are unmodeled. The existing geometry uses `width=lines*diameter_mm`;this does not
independently represent an IDC pitch,insulation thickness or a calibrated cable
SKU. A realistic-looking assembly is not an independently known-feasible route.
All new installations explicitly retain `feasibility="unknown"`,without solve
filtering. Do not relabel exhaustion as physical impossibility. Establish any
future positive feasibility oracle from independent physical/reference geometry,
withhold that route from solver initialization,and version the contract first.

## Scenario semantics

Recipe events compose local endpoint poses with neutral spacing. They are mental
scenario intents,not geometric segments,intermediate routing controls or witness
curves. A lateral pose construction is not an allowed planar wide-axis bend,and
a twist's axial endpoint displacement does not require a straight centerline.
The solver discovers its own corkscrew/developable path. Ordered width axes remain
fixed. Endpoint frames cannot encode extra full winding or prove a particular
interior S/event sequence. Report interior-event coverage as unmeasured until a
separate event detector/control contract exists;do not call pose closure proof
that the requested event sequence occurred.

## Generate,freeze and replay

Consult the configured Python SDK before toolchain commands. From this repository:

```sh
uv run .venv/bin/python -m devtools.ribbon_analysis.case_generation generate --mode random --count 64 --seed 20261027 --output artifacts/verification/generated-cases/random-01.json
uv run .venv/bin/python -m devtools.ribbon_analysis.case_generation generate --mode installation --count 64 --seed 20261027 --output artifacts/verification/generated-cases/installation-01.json
uv run .venv/bin/python -m devtools.ribbon_analysis.case_generation inspect artifacts/verification/generated-cases/installation-01.json
```

Omit `--seed` for a fresh64-bit system seed. The manifest stores that seed AND all
complete floating-point poses/dimensions,events,lineage,strata,generator-source
digest and content fingerprint. Installation manifests also store the selected
mode and complete connector/context data. Each mode has per-case substreams,so changing
batch size does not shift an existing random prefix. Normal/stress inputs do not
change with seed. Files are write-once;choose a new filename for each batch.

For exact replay,load saved JSON with `read(Path(...))`,not just its seed:Python
versions and future generator changes can alter recomputed draws. Reading verifies
version,shape,frames,quarter allocation,required normal events,identities and digest.
The content digest detects accidental edits;it is not a signature or physical
certificate. Pin solver sources/policies/budgets separately before execution.
Original arbitrary-pose manifests retain version1's exact serialized shape and
fingerprint rules;installation manifests use version2. Both remain readable.
Adding generator source changes its source digest,even when legacy seeded poses
stay identical. Replay the saved original manifest to retain historical identity.

## Connect a solved path to the existing diagnostics

```python
from pathlib import Path
from devtools.ribbon_analysis.case_generation import candidate_for, read
from devtools.ribbon_analysis.api import analyze

manifest = read(Path("artifacts/verification/generated-cases/run-01.json"))
case = manifest.cases[0]
# Supply case.targets to the selected solver with its own bounded ledger.
# Keep unsuccessful/no-path outcomes;never replace or remove their case entries.
candidate = candidate_for(manifest, case, solved_path, solver_source=solver_source_pin)
evidence = analyze(candidate, checkpoint, intervals=512)
# Render this frozen Evidence with the existing owned-component diagnostic API.
```

`case.targets` implements the existing `TargetPose` protocol. If a solver insists
on its own input class,copy these fields without changing values. `candidate_for`
accepts both solved and partially solved paths of the original dimensions,retains
the exact targets,and attaches batch/case/source identity. It does not gate away
bad endpoints. When no path exists,retain a no-path/exhausted/error disposition;
never invent a successful ribbon or reduce the denominator to rendered results.
Inspect the same immutable evidence and failure regions the user sees. Generator
tests are not solved/native geometry coverage. Existing solve,analysis,actual
BRep construction,audit and graphic timings remain separate.

## Research basis

- Fixed examples plus generated cases and replayable failures follow the
  [Hypothesis replay workflow](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html);
  no Hypothesis dependency or hidden shrinking is introduced.
- The full-frame sampler uses Shoemake's uniform unit-quaternion construction,
  [Graphics Gems III reference code](https://github.com/erich666/GraphicsGems/blob/master/gemsiii/urot.c).
- Save full inputs because seeded helper algorithms can change across versions:
  [Python reproducibility notes](https://docs.python.org/3/library/random.html#notes-on-reproducibility).
- Boundary-pose planning and finite-width clearance remain separate from mechanical
  certification:[Patil et al.](https://people.eecs.berkeley.edu/~pabbeel/papers/2015-TASE-ribbons.pdf).
- Generic board-to-board relationships and distinct header/strain-relief options
  are informed by [TE's AMP-LATCH interconnect guide](https://www.te.com/content/dam/te-com/documents/consumer-devices/global/amp-latch-ribbon-cable-interconnect-solutions.pdf).
  It does not establish the normalized dimensions or route feasibility above.
