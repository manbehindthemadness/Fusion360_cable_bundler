# Endpoint gym and solver diagnostics

The user-directed Rubik gym starts from its environment and two connection faces.
It does not author a reference cable, supply a witness route, run a solver or add
physical validity rules. The planar second gym is deferred.

The gym can also be linked to the diagnostic solver palette. Choose **Create/edit
gym layout** in diagnostics, author the endpoints, then choose **Open in solver
diagnostics** in the gym. Select optional procedures/settings and press **Run
selected**. Use **View result**, the recorded-result selector and search playback
to inspect the transported paths. Handoff does not run a solver automatically.

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
source-pinned plan; each later Run selected freezes its own bounded plan, exact
inputs and gym identity. Worker results retain the context, and imports reject
missing or mismatched layouts. Pure helpers in `gym.handoff` provide write-once
input manifests and validated replay without importing Fusion.

Per edit: 10 seconds, 4 GiB sampled Fusion RSS, 3.8 GiB launch headroom. No native
cable attempts or automatic numerical experiments. The outer grid is visual
context; whether routing is confined to the central void/approaches or uses the
surrounding space remains undecided. Rendering is not a feasibility judgment.
