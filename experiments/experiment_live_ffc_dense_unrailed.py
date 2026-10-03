"""
Add one dense, unrailed control to the open live-FFC scratch design.

Run with ``Python.Run`` while the scratch ``Untitled`` design from
``experiment_live_ffc_correspondence.py`` is active. The design stays open.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts import ribbon_builder
from experiments.experiment_live_ffc_correspondence import _live_plan, _loft_case


def run(_context: object) -> None:
    """
    Test whether dense-section failure persists without perimeter rails.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if (
        scratch is None
        or scratch.name != "Untitled"
        or str(application.userInterface.activeCommand) != "SelectCommand"
    ):
        raise RuntimeError("Activate the open Untitled FFC scratch design first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or design.rootComponent.occurrences.count != 3:
        raise RuntimeError("The active scratch does not contain the three prior probe cases.")
    source = next(
        (
            application.documents.item(index)
            for index in range(application.documents.count)
            if application.documents.item(index).name == "Wire creation tester v109"
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The original FFC source design is no longer open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The FFC source is not a Fusion design.")
    output = (
        Path(ribbon_builder.__file__).resolve().parents[3]
        / "artifacts/verification/live_ffc_correspondence.json"
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    if not report.get("scratch_open") or report.get("source") != source.name:
        raise RuntimeError("The existing report does not match the open scratch and source.")
    plan, thickness_mm, dimensions, group_id = _live_plan(source_design)
    if group_id != report["group_id"] or len(plan.sections) != report["stations"]:
        raise RuntimeError("The source FFC plan changed since the prior comparison.")
    report["cases"]["all_stations_no_rails"] = _loft_case(
        design,
        plan,
        tuple(range(len(plan.sections))),
        thickness_mm,
        dimensions,
        False,
        application.pointTolerance * 10.0,
    )
    report["source_modified_after"] = source.isModified
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "LIVE_FFC_DENSE_UNRAILED="
        + json.dumps(
            {"result": report["cases"]["all_stations_no_rails"]["result"], "scratch_open": True},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
