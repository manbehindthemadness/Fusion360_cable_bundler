"""
Run precomputed variable-twist profile sweeps in the bank-extreme scratch.

Use Fusion ``Python.Run`` after the fixed-bank experiment. This appends
isolated geometry to that unsaved scratch and leaves it open.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_banked_profile_sweeps import _sweep


def run(_context: object) -> None:
    """
    Compare the two twist-distribution predictions with actual Fusion sweeps.
    """
    application = adsk.core.Application.get()
    active_command = str(application.userInterface.activeCommand)
    if active_command != "SelectCommand":
        raise RuntimeError(f"Finish the active Fusion command before this probe: {active_command}.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or design.rootComponent.features.sweepFeatures.count != 20:
        raise RuntimeError("Open the 20-solid bank-extreme scratch before running twist controls.")
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    plan_path = root_path / "artifacts/verification/banked_profile_extremes_math.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    planned = plan.get("twist_cases") if isinstance(plan, dict) else None
    if not isinstance(planned, list) or len(planned) != 18:
        raise ValueError("Expected the 18-case preregistered twist plan.")
    results: list[dict[str, object]] = []
    for index, planned_case in enumerate(planned):
        if not isinstance(planned_case, dict):
            raise ValueError("The twist plan contains a malformed case.")
        entry: dict[str, object] = dict(planned_case)
        results.append(entry)
        try:
            entry.update(_sweep(design.rootComponent, entry, (36 + index) * 8.0))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            entry["result"] = "failed"
            entry["error"] = str(error)
    application.activeViewport.fit()
    report = {"scratch_document": application.activeDocument.name, "cases": results}
    output = root_path / "artifacts/verification/banked_profile_twist_fusion.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "BANKED_PROFILE_TWIST="
        + json.dumps(
            {"cases": len(results), "solids": sum(row["result"] == "solid" for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
