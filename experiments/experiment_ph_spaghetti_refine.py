"""
Refine observed PH sweep failure transitions in the open Fusion scratch.

Run through Fusion ``Python.Run`` after the broad spaghetti probe. This
appends only experiment geometry and leaves the design open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_ph_fusion_sweep import _sweep_case
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates


@dataclass(frozen=True)
class RefineCase:
    """
    Define an endpoint, profile, roll, and lateral-displacement probe.
    """

    name: str
    separation_mm: float
    derivative_mm: float
    ribbon: bool
    roll_degrees: float = 0.0
    lateral_mm: float = 0.0


def refine_cases() -> tuple[RefineCase, ...]:
    """
    Concentrate samples around observed solid/failure boundaries.
    """
    cases = [
        RefineCase(f"circle_h{height:g}", height, 25.0, False) for height in (5.2, 5.4, 5.6, 5.8)
    ]
    cases.extend(
        RefineCase(f"ribbon_h5_roll{angle:g}", 5.0, 25.0, True, angle)
        for angle in (5, 10, 15, 20, 30, 40)
    )
    cases.extend(
        RefineCase(f"ribbon_h10_roll{angle:g}", 10.0, 25.0, True, angle)
        for angle in (100, 110, 120, 130)
    )
    cases.extend(
        RefineCase(f"ribbon_h20_lateral{lateral:g}", 20.0, 25.0, True, 0.0, lateral)
        for lateral in (1.5, 2, 3, 4)
    )
    cases.extend(
        RefineCase(
            f"wide_h60_d75_lateral{lateral:g}_roll{roll:g}",
            60.0,
            75.0,
            True,
            roll,
            lateral,
        )
        for lateral in (5, 10, 15, 20, 30)
        for roll in (0, 90, 180)
    )
    return tuple(cases)


def run(_context: object) -> None:
    """
    Sweep the refinements into the existing scratch and record kernel outcomes.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before refinement.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    report: dict[str, object] = {"document": application.activeDocument.name, "cases": []}
    for index, probe in enumerate(refine_cases()):
        entry: dict[str, object] = {
            "name": probe.name,
            "separation_mm": probe.separation_mm,
            "derivative_mm": probe.derivative_mm,
            "profile": "ribbon_10x0p5mm" if probe.ribbon else "circle_3mm",
            "twist_degrees": probe.roll_degrees,
            "lateral_displacement_mm": probe.lateral_mm,
        }
        report["cases"].append(entry)
        try:
            hermite = HermiteCase(
                probe.name,
                complex(0.0, probe.separation_mm),
                complex(probe.derivative_mm, 0.0),
                complex(-probe.derivative_mm, 0.0),
            )
            curve = ph_hermite_candidates(hermite)[0]
            entry.update(
                _sweep_case(
                    root,
                    probe.name,
                    curve.controls,
                    800.0 + index * 10.0,
                    1.5,
                    10.0 if probe.ribbon else None,
                    probe.roll_degrees,
                    probe.lateral_mm,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            entry["result"] = "failed"
            entry["error"] = str(error)
    application.activeViewport.fit()
    output = (
        Path(cable_bundler.__file__).resolve().parents[1]
        / "artifacts/verification/ph_spaghetti_refine.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_SPAGHETTI_REFINE="
        + json.dumps(
            {
                "cases": len(report["cases"]),
                "solids": sum(entry["result"] == "solid" for entry in report["cases"]),
                "report": str(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
