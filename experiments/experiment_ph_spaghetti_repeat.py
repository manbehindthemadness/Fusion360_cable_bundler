"""
Repeat the narrow Fusion sweep transitions in the open experiment scratch.

Run through Fusion ``Python.Run`` after the refinement probe. Each repetition
creates isolated geometry and leaves the unsaved design open.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_ph_fusion_sweep import _sweep_case
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates


def run(_context: object) -> None:
    """
    Repeat neighboring success/failure cases three times each.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before repeating the probe.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    cases = (
        ("circle_h5", 5.0, False, 0.0, 0.0),
        ("circle_h5.2", 5.2, False, 0.0, 0.0),
        ("ribbon_h5_roll30", 5.0, True, 30.0, 0.0),
        ("ribbon_h5_roll40", 5.0, True, 40.0, 0.0),
        ("ribbon_h20_lateral3", 20.0, True, 0.0, 3.0),
        ("ribbon_h20_lateral4", 20.0, True, 0.0, 4.0),
    )
    results: list[dict[str, object]] = []
    for repeat in range(3):
        for index, (name, separation, ribbon, roll, lateral) in enumerate(cases):
            unique_name = f"{name}_repeat{repeat + 1}"
            entry: dict[str, object] = {"name": name, "repeat": repeat + 1}
            results.append(entry)
            try:
                hermite = HermiteCase(
                    unique_name,
                    complex(0.0, separation),
                    25 + 0j,
                    -25 + 0j,
                )
                curve = ph_hermite_candidates(hermite)[0]
                entry.update(
                    _sweep_case(
                        root,
                        unique_name,
                        curve.controls,
                        1200.0 + (repeat * len(cases) + index) * 10.0,
                        1.5,
                        10.0 if ribbon else None,
                        roll,
                        lateral,
                    )
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                entry["result"] = "failed"
                entry["error"] = str(error)
    report = {"document": application.activeDocument.name, "cases": results}
    output = (
        Path(cable_bundler.__file__).resolve().parents[1]
        / "artifacts/verification/ph_spaghetti_repeat.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_SPAGHETTI_REPEAT="
        + json.dumps(
            {"cases": len(results), "solids": sum(row["result"] == "solid" for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
