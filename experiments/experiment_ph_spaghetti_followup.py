"""
Probe gentle 3D controls in the already-open PH spaghetti scratch design.

Run with Fusion ``Python.Run`` after experiment_ph_spaghetti_sweep.py. It
appends only experiment geometry and leaves the scratch design open.
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
    Check whether mild 3D paths work independently of tight hairpin geometry.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    cases = (
        ("straight_d5_circle", 80 + 0j, 80 + 0j, 80 + 0j, None, 0.0, 5.0),
        ("straight_d5_ribbon", 80 + 0j, 80 + 0j, 80 + 0j, 10.0, 0.0, 5.0),
        ("wide_h60_d75_circle", 60j, 75 + 0j, -75 + 0j, None, 0.0, 5.0),
        ("wide_h60_d75_ribbon", 60j, 75 + 0j, -75 + 0j, 10.0, 0.0, 5.0),
        ("wide_h60_d75_roll180", 60j, 75 + 0j, -75 + 0j, 10.0, 180.0, 0.0),
        ("h20_d25_lateral1", 20j, 25 + 0j, -25 + 0j, 10.0, 0.0, 1.0),
        ("h60_d25_lateral5", 60j, 25 + 0j, -25 + 0j, 10.0, 0.0, 5.0),
        ("h60_d25_lateral15", 60j, 25 + 0j, -25 + 0j, 10.0, 0.0, 15.0),
    )
    report: dict[str, object] = {"document": application.activeDocument.name, "cases": []}
    for index, (name, end, first, last, width, roll, lateral) in enumerate(cases):
        entry: dict[str, object] = {
            "name": name,
            "profile": "circle_3mm" if width is None else "ribbon_10x0p5mm",
            "twist_degrees": roll,
            "lateral_displacement_mm": lateral,
        }
        report["cases"].append(entry)
        try:
            curve = ph_hermite_candidates(HermiteCase(name, end, first, last))[0]
            entry.update(
                _sweep_case(
                    root,
                    name,
                    curve.controls,
                    700.0 + index * 10.0,
                    1.5,
                    width,
                    roll,
                    lateral,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            entry["result"] = "failed"
            entry["error"] = str(error)
    application.activeViewport.fit()
    output = (
        Path(cable_bundler.__file__).resolve().parents[1]
        / "artifacts/verification/ph_spaghetti_followup.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_SPAGHETTI_FOLLOWUP="
        + json.dumps(
            {"results": {entry["name"]: entry["result"] for entry in report["cases"]}},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
