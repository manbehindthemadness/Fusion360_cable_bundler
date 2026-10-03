"""
Run preregistered local-fold holdouts in the open Fusion PH scratch.

Run through Fusion ``Python.Run`` after the local macaroni-limit script has
written its ignored holdout plan. Appends only isolated experiment geometry.
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
    Compare twelve precomputed predictions with fresh Fusion sweep outcomes.
    """
    application = adsk.core.Application.get()
    active_command = str(application.userInterface.activeCommand)
    if active_command != "SelectCommand":
        raise RuntimeError(
            f"Finish the active Fusion command before the holdout probe: {active_command}."
        )
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    project_root = Path(cable_bundler.__file__).resolve().parents[1]
    plan_path = project_root / "artifacts/verification/ph_macaroni_holdout_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    planned = plan.get("cases") if isinstance(plan, dict) else None
    if not isinstance(planned, list) or len(planned) != 12:
        raise ValueError("The expected twelve-case holdout plan is missing.")
    results: list[dict[str, object]] = []
    for index, planned_case in enumerate(planned):
        if not isinstance(planned_case, dict):
            raise ValueError("The holdout plan contains a malformed case.")
        name = planned_case.get("name")
        separation = planned_case.get("separation_mm")
        derivative = planned_case.get("derivative_mm")
        width = planned_case.get("ribbon_width_mm")
        roll = planned_case.get("twist_degrees")
        if not isinstance(name, str) or not all(
            isinstance(value, (int, float)) for value in (separation, derivative, width, roll)
        ):
            raise ValueError("The holdout plan has incomplete geometry parameters.")
        entry: dict[str, object] = dict(planned_case)
        results.append(entry)
        try:
            hermite = HermiteCase(
                name,
                complex(0.0, separation),
                complex(derivative, 0.0),
                complex(-derivative, 0.0),
            )
            curve = ph_hermite_candidates(hermite)[0]
            entry.update(
                _sweep_case(
                    root,
                    name,
                    curve.controls,
                    1500.0 + index * 10.0,
                    1.5,
                    width,
                    roll,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            entry["result"] = "failed"
            entry["error"] = str(error)
    report = {"document": application.activeDocument.name, "cases": results}
    output = project_root / "artifacts/verification/ph_macaroni_holdout_fusion.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_MACARONI_HOLDOUT="
        + json.dumps(
            {"cases": len(results), "solids": sum(row["result"] == "solid" for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
