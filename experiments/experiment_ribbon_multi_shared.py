"""
Build two independent ribbon instances in one open Fusion trial document.

Run through Fusion Text Commands ``Python.Run`` with ``Wire creation tester
v107`` active and no command open. The source design is read-only. The new,
unsaved design deliberately remains open for visual inspection.
"""

from __future__ import annotations

import json
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ribbon_lobe_exit import _trial
from experiments.experiment_ribbon_reverse_loft import (
    _pairwise_overlaps,
    _source_cases,
    _SourceCase,
)

_RIBBON_OFFSET_CM = 15.0


def _build_ribbon_instance(
    root: adsk.fusion.Component,
    cases: tuple[_SourceCase, ...],
    label: str,
    offset_cm: float,
) -> dict[str, object]:
    """
    Build one independently owned, inspectable ribbon and all its exits.
    """
    transform = adsk.core.Matrix3D.create()
    transform.setCell(0, 3, offset_cm)
    occurrence = root.occurrences.addNewComponent(transform)
    if occurrence is None:
        raise RuntimeError(f"Fusion could not create ribbon component {label}.")
    component = occurrence.component
    component.name = label
    manager = adsk.fusion.TemporaryBRepManager.get()
    results: list[dict[str, object]] = []
    transient_branches: list[tuple[str, adsk.fusion.BRepBody]] = []
    for case in cases:
        try:
            result, transient, trial_ribbon, branch = _trial(component, case)
            trial_ribbon.isVisible = False
            trial_ribbon.name = f"Validation copy {case.route_id[:8]}"
            branch.name = f"Lane {case.line_index + 1:02d} exit {case.route_id[:8]}"
            results.append(result)
            if (
                result["branch_valid"]
                and result["union_ok"]
                and result["union_lumps"] == 1
                and result["overlap_ok"]
                and result["overlap_volume_cm3"] > 0
            ):
                transient_branches.append((case.route_id, transient))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            results.append({"route_id": case.route_id, "error": f"{type(error).__name__}: {error}"})
    ribbon_copy = manager.copy(cases[0].body)
    if ribbon_copy is None:
        raise RuntimeError(f"Fusion could not copy the ribbon for {label}.")
    visible_ribbon = component.bRepBodies.add(ribbon_copy)
    if visible_ribbon is None:
        raise RuntimeError(f"Fusion could not import the ribbon for {label}.")
    visible_ribbon.name = "Ribbon reference"
    for sketch in component.sketches:
        sketch.isVisible = False
    for plane in component.constructionPlanes:
        plane.isLightBulbOn = False
    pairwise = _pairwise_overlaps(transient_branches, cases[0].body)
    return {
        "component": component.name,
        "offset_cm": offset_cm,
        "root_count": len(cases),
        "passed": len(transient_branches),
        "errors": [result for result in results if "error" in result],
        "pairwise_overlap_count": pairwise["overlap_count"],
        "pairwise_failure_count": pairwise["failure_count"],
        "pairwise_failures": pairwise["failures"],
    }


def run(_context: object) -> None:
    """
    Complete an open trial or create one, leaving its solids for inspection.
    """
    application = adsk.core.Application.get()
    active_document = application.activeDocument
    document = next(
        (item for item in application.documents if item.name == "Wire creation tester v107"),
        None,
    )
    if document is None:
        raise RuntimeError("Keep Wire creation tester v107 open before this trial.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this trial.")
    scratch = None if active_document == document else active_document
    if scratch is not None:
        trial_design = adsk.fusion.Design.cast(application.activeProduct)
        if trial_design is None:
            raise RuntimeError("The active trial document is not a Fusion design.")
        components = [
            occurrence.component.name for occurrence in trial_design.rootComponent.occurrences
        ]
        if components != ["Ribbon A - Group 5"]:
            raise RuntimeError("The active design is not the partial two-ribbon trial.")
    document.activate()
    source_modified_before = document.isModified
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    started = perf_counter()
    cases = _source_cases(design)
    if scratch is None:
        scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    else:
        scratch.activate()
    if scratch is None:
        raise RuntimeError("Fusion could not open the inspectable trial design.")
    trial_design = adsk.fusion.Design.cast(application.activeProduct)
    if trial_design is None:
        raise RuntimeError("The new document is not a Fusion design.")
    trial_design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = trial_design.rootComponent
    if root.occurrences.count == 0:
        ribbons = [_build_ribbon_instance(root, cases, "Ribbon A - Group 5", 0.0)]
    else:
        existing = root.occurrences.item(0).component
        branches = [body for body in existing.bRepBodies if body.name.startswith("Lane ")]
        if not branches or not all(
            body.isValid and body.isSolid and body.volume > 0 for body in branches
        ):
            raise RuntimeError("The retained first ribbon is incomplete or invalid.")
        for plane in existing.constructionPlanes:
            plane.isLightBulbOn = False
        ribbons = [
            {
                "component": existing.name,
                "root_count": len(cases),
                "solid_count": len(branches),
                "missing_route_ids": [
                    case.route_id
                    for case in cases
                    if not any(case.route_id[:8] in body.name for body in branches)
                ],
                "resumed": True,
            }
        ]
    ribbons.append(
        _build_ribbon_instance(root, cases, "Ribbon B - Group 5 offset", _RIBBON_OFFSET_CM)
    )
    print(
        "RIBBON_MULTI_SHARED="
        + json.dumps(
            {
                "source_document": document.name,
                "source_modified_before": source_modified_before,
                "source_modified_after": document.isModified,
                "trial_document": scratch.name,
                "trial_open": scratch.isValid,
                "ribbons": ribbons,
                "wall_ms": round((perf_counter() - started) * 1000.0, 1),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
