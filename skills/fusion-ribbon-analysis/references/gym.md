# Endpoint gym preview

The user-directed Rubik gym starts from its environment and two connection faces.
It does not author a reference cable, supply a witness route, run a solver or add
physical validity rules. The planar second gym is deferred.

`devtools.ribbon_analysis.gym.generate(Config(...))` produces a seeded, immutable
layout. The central empty cube has side `void_widths * lines * diameter_mm`, with
`void_widths >= 3`. Its 26 surrounding cells form a 3×3×3 arrangement. Two distinct
zones receive virtual axis-aligned boxes wholly inside their cells. Zone choice,
box size/position, face and quarter-turn connector orientation depend only on the
seed and dimensions. No solve, fitted route or success filtering enters generation.

This first preview uses nominal width `lines * diameter_mm`; it introduces no
new bonded contour or profile-padding policy. Virtual boxes are shared graphics,
not native cable solids. Each selected face hosts ordered conductor-circle markers
at its center. Arrows show outward face normals; a future route departs A along
its normal and arrives at B opposite its outward normal. The exposed `Targets`
retain these signs and conductor order.

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

Per edit: 10 seconds, 4 GiB sampled Fusion RSS, 3.8 GiB launch headroom. No native
cable attempts or automatic numerical experiments. The outer grid is visual
context; whether routing is confined to the central void/approaches or uses the
surrounding space remains undecided. Rendering is not a feasibility judgment.
