"""
Compare ribbon anomalies with rotation-invariant circular Fusion sweeps.

Run through Fusion ``Python.Run`` in the open PH scratch. The test appends
separated control geometry and leaves the unsaved document open.
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

HOLDOUT_NAMES = (
    "h5_w10_roll32p5",
    "h5_w10_roll35",
    "h5_w10_roll37p5",
    "h5_w8_roll40",
    "h5_w12_roll25",
    "h5_w12_roll30",
)
RETROSPECTIVE_NAME = "roll_h10_a360"
CONTROL_RADII_MM = (0.25, 1.0, 1.5)


def _read_cases(root: Path) -> list[dict[str, object]]:
    """
    Select fixed anomalous and failed ribbon cases from prior Fusion reports.
    """
    holdout_path = root / "artifacts/verification/ph_macaroni_holdout_fusion.json"
    historical_path = root / "artifacts/verification/ph_macaroni_limit.json"
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    holdout_cases = holdout.get("cases") if isinstance(holdout, dict) else None
    historical_cases = historical.get("cases") if isinstance(historical, dict) else None
    if not isinstance(holdout_cases, list) or not isinstance(historical_cases, list):
        raise ValueError("The prerequisite Fusion reports have no case lists.")
    selected: list[dict[str, object]] = []
    for name in HOLDOUT_NAMES:
        matches = [
            case for case in holdout_cases if isinstance(case, dict) and case.get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one prior holdout case named {name}.")
        selected.append(matches[0])
    matches = [
        case
        for case in historical_cases
        if isinstance(case, dict) and case.get("name") == RETROSPECTIVE_NAME
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one prior case named {RETROSPECTIVE_NAME}.")
    selected.append(matches[0])
    return selected


def run(_context: object) -> None:
    """
    Sweep three circular radii with zero and inherited twist per source path.
    """
    application = adsk.core.Application.get()
    active_command = str(application.userInterface.activeCommand)
    if active_command != "SelectCommand":
        raise RuntimeError(f"Finish the active Fusion command before this probe: {active_command}.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    project_root = Path(cable_bundler.__file__).resolve().parents[1]
    source_cases = _read_cases(project_root)
    results: list[dict[str, object]] = []
    for source_index, source in enumerate(source_cases):
        name = source.get("name")
        separation = source.get("separation_mm")
        derivative = source.get("derivative_mm")
        roll = source.get("twist_degrees", source.get("roll_degrees"))
        ribbon_result = source.get("result", source.get("fusion_result"))
        if (
            not isinstance(name, str)
            or not all(isinstance(value, (int, float)) for value in (separation, derivative, roll))
            or ribbon_result not in ("solid", "failed")
        ):
            raise ValueError(f"The prior case {name!r} has incomplete geometry or outcome data.")
        hermite = HermiteCase(
            name,
            complex(0.0, separation),
            complex(derivative, 0.0),
            complex(-derivative, 0.0),
        )
        curve = ph_hermite_candidates(hermite)[0]
        maximum_curvature = max(abs(curve.curvature_at(index / 4096)) for index in range(4097))
        for radius_index, radius in enumerate(CONTROL_RADII_MM):
            for variant_index, twist in enumerate((0.0, float(roll))):
                control_name = f"{name}_circle_r{radius:g}_twist{twist:g}"
                entry: dict[str, object] = {
                    "source_name": name,
                    "source_ribbon_result": ribbon_result,
                    "separation_mm": float(separation),
                    "derivative_mm": float(derivative),
                    "source_roll_degrees": float(roll),
                    "circle_radius_mm": radius,
                    "circle_curvature_reach": maximum_curvature * radius,
                    "control_twist_degrees": twist,
                }
                results.append(entry)
                offset_index = source_index * 6 + radius_index * 2 + variant_index
                try:
                    entry.update(
                        _sweep_case(
                            design.rootComponent,
                            control_name,
                            curve.controls,
                            1800.0 + offset_index * 10.0,
                            radius,
                            twist_degrees=twist,
                        )
                    )
                except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                    entry["result"] = "failed"
                    entry["error"] = str(error)
    report = {"document": application.activeDocument.name, "cases": results}
    output = project_root / "artifacts/verification/ph_circular_pivot_controls.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_CIRCULAR_PIVOT_CONTROLS="
        + json.dumps(
            {"cases": len(results), "solids": sum(row["result"] == "solid" for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
