"""
Exercise production in-place ribbon exits beside the retained two-ribbon trial.

Run through Fusion Text Commands ``Python.Run`` with the unsaved two-ribbon
trial active. A third, offset component remains open for visual inspection;
the saved source design is only read. No document is created or closed.
"""

from __future__ import annotations

import json
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.ribbon_exit_loft import (
    RibbonExitEnd,
    build_ribbon_exit_loft,
)
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane
from experiments.experiment_ribbon_reverse_loft import _source_cases

_OFFSET_CM = 30.0


def run(_context: object) -> None:
    """
    Add one benchmark component without touching the two retained ribbons.
    """
    application = adsk.core.Application.get()
    trial = application.activeDocument
    if trial is None or trial.name != "Untitled":
        raise RuntimeError("Activate the unsaved two-ribbon trial first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this trial.")
    trial_design = adsk.fusion.Design.cast(application.activeProduct)
    if trial_design is None:
        raise RuntimeError("The active trial is not a Fusion design.")
    existing = [item.component.name for item in trial_design.rootComponent.occurrences]
    if existing != ["Ribbon A - Group 5", "Ribbon B - Group 5 offset"]:
        raise RuntimeError("The active design is not the retained two-ribbon trial.")
    source = next(
        (item for item in application.documents if item.name == "Wire creation tester v107"),
        None,
    )
    if source is None or not source.activate():
        raise RuntimeError("Keep Wire creation tester v107 open for the comparison.")
    source_modified_before = source.isModified
    source_design = adsk.fusion.Design.cast(application.activeProduct)
    if source_design is None:
        raise RuntimeError("The source document is not a Fusion design.")
    cases = _source_cases(source_design)
    if not trial.activate():
        raise RuntimeError("Fusion could not restore the two-ribbon trial.")
    started = perf_counter()
    transform = adsk.core.Matrix3D.create()
    transform.setCell(0, 3, _OFFSET_CM)
    occurrence = trial_design.rootComponent.occurrences.addNewComponent(transform)
    if occurrence is None:
        raise RuntimeError("Fusion could not create the in-place benchmark component.")
    component = occurrence.component
    component.name = "Ribbon C - in-place exits"
    manager = adsk.fusion.TemporaryBRepManager.get()
    ribbon_copy = manager.copy(cases[0].body)
    if ribbon_copy is None:
        raise RuntimeError("Fusion could not copy the source ribbon.")
    ribbon = component.bRepBodies.add(ribbon_copy)
    if ribbon is None:
        raise RuntimeError("Fusion could not import the in-place benchmark ribbon.")
    ribbon.name = "Ribbon reference"
    results: list[dict[str, object]] = []
    for case in cases:
        try:
            end = RibbonExitEnd(
                RibbonGuidePlane(
                    case.end_fit.centers[case.line_index],
                    case.end_fit.approach_normal or case.end_frame.tangent,
                ),
                case.end_frame,
                case.lane_centers,
                case.end_fit,
            )
            body = build_ribbon_exit_loft(
                component,
                ribbon,
                case.route,
                end,
                case.line_index,
                case.ribbon_diameter_mm,
                case.cap_diameter_mm,
                case.transform,
            )
            body.name = f"Lane {case.line_index + 1:02d} exit {case.route_id[:8]}"
            results.append({"route_id": case.route_id, "volume_cm3": round(body.volume, 9)})
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            results.append({"route_id": case.route_id, "error": f"{type(error).__name__}: {error}"})
    for sketch in component.sketches:
        sketch.isLightBulbOn = False
    for plane in component.constructionPlanes:
        plane.isLightBulbOn = False
    print(
        "RIBBON_IN_PLACE="
        + json.dumps(
            {
                "trial_document": trial.name,
                "trial_open": trial.isValid,
                "source_modified_before": source_modified_before,
                "source_modified_after": source.isModified,
                "root_count": len(cases),
                "passed": sum("error" not in result for result in results),
                "errors": [result for result in results if "error" in result],
                "wall_ms": round((perf_counter() - started) * 1000.0, 1),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
