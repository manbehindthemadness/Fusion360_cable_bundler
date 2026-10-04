"""
Exercise the production one-face FFC builder on the saved live route in scratch.

Only an unsaved scratch is modified; the saved source remains read-only.
"""

from __future__ import annotations

import json
import math
from importlib import reload
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion import solid_ribbon
from cable_bundler.fusion.cable_solid_parts import one_face_ffc
from experiments import experiment_live_ffc_correspondence

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_production_sweep.json"


def run(_context: object) -> None:
    """
    Build the complete conditioned route without touching the saved source.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("Open the saved FFC source design first.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The source is not a Fusion design.")
    modified_before = source.isModified
    reload(solid_ribbon)
    plan, thickness_mm, dimensions, _group_id = reload(
        experiment_live_ffc_correspondence
    )._live_plan(source_design)
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate an unsaved FFC scratch before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    component = design.rootComponent.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    ).component
    component.name = "Production one-face FFC trial"
    row: dict[str, object] = {
        "station_indices": one_face_ffc.sweep_station_indices(plan),
        "source_modified_before": modified_before,
        "contact_offsets_mm": [
            [
                math.dist(
                    (center.x, center.y, center.z),
                    (target.x, target.y, target.z),
                )
                for center, target in zip(station.centers, targets)
            ]
            for station, targets in zip((plan.sections[0], plan.sections[-1]), plan.contact_centers)
        ],
    }
    try:
        feature = reload(one_face_ffc).build_one_face_ffc_sweep(
            component, plan, dimensions, thickness_mm, adsk.core.Matrix3D.create()
        )
        body = feature.bodies.item(0)
        row.update(
            {
                "result": "solid",
                "body_faces": body.faces.count,
                "side_faces": feature.sideFaces.count,
                "volume_cm3": body.volume,
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    if source.isModified != modified_before:
        raise RuntimeError("The saved FFC source changed during the experiment.")
    row["source_modified_after"] = source.isModified
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.fit()
    print(
        "FFC_PRODUCTION_SWEEP="
        + json.dumps({"result": row["result"], "error": row.get("error"), "report": str(OUTPUT)})
    )


if __name__ == "__main__":
    run(None)
