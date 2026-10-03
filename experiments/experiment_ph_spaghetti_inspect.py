"""
Read path control-point coordinates in the open PH spaghetti scratch design.

Run via Fusion ``Python.Run``. This inspection does not change the design.
"""

from __future__ import annotations

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion


def run(_context: object) -> None:
    """
    Compare world-space Z controls of planar and intended lateral paths.
    """
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    samples: list[dict[str, object]] = []
    for name in (
        "radius_h20_ribbon_10x0p5mm",
        "lateral_h20_d5_a0",
        "lateral_h20_d15_a0",
    ):
        sketch = root.sketches.itemByName(f"{name} PH path")
        if sketch is None or sketch.sketchCurves.sketchControlPointSplines.count != 1:
            samples.append({"name": name, "error": "Missing expected control-point spline."})
            continue
        spline = sketch.sketchCurves.sketchControlPointSplines.item(0)
        controls = spline.controlPoints
        samples.append(
            {
                "name": name,
                "sketch_control_z_cm": [point.geometry.z for point in controls],
                "world_control_z_cm": [point.worldGeometry.z for point in controls],
                "spline_world_control_count": spline.worldGeometry.controlPointCount,
            }
        )
    print("PH_SPAGHETTI_INSPECT=" + json.dumps(samples, sort_keys=True))


if __name__ == "__main__":
    run(None)
