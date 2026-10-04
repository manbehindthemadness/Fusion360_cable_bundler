"""
Apply the production UV stripe renderer to the retained live-route sweep trial.

Only the unsaved scratch's test appearance is changed. The saved source is
read to recover the same ordered route plan and remains unmodified.
"""

from __future__ import annotations

import colorsys
import json
from importlib import reload
from pathlib import Path
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableColor
from cable_bundler.fusion.cable_solid_parts import one_face_texture
from experiments.experiment_live_ffc_correspondence import _live_plan

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_production_texture.json"


def run(_context: object) -> None:
    """
    Color the scratch trial's one side face and retain it for visual review.
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
        raise RuntimeError("The saved FFC source design is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The source is not a Fusion design.")
    modified_before = source.isModified
    plan, _thickness, dimensions, group_id = _live_plan(source_design)
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC sweep scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    matches = [
        occurrence.component
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name == "Production one-face FFC trial"
    ]
    if len(matches) != 1 or matches[0].features.sweepFeatures.count != 1:
        raise RuntimeError("The production FFC sweep trial is unavailable.")
    feature = matches[0].features.sweepFeatures.item(0)
    colors = []
    for index in range(len(plan.sections[0].centers)):
        hue = index * 0.618033988749895 % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
        colors.append(CableColor(f"Trace {index + 1}", *(round(channel * 255) for channel in rgb)))
    base = CableColor("FFC web", 38, 42, 48)
    row: dict[str, object] = {"source_modified_before": modified_before}
    try:
        texture = reload(one_face_texture)
        samples = texture._section_uv_samples(
            feature.sideFaces.item(0), plan.sections[0], dimensions, adsk.core.Matrix3D.create()
        )
        row["uv_range"] = (samples[0][0], samples[-1][0])
        row["uv_samples"] = len(samples)
        texture.apply_ffc_trace_texture(
            design,
            feature,
            plan.sections[0],
            plan.sections[-1],
            dimensions,
            tuple(colors),
            base,
            UUID(group_id),
            adsk.core.Matrix3D.create(),
        )
        side = feature.sideFaces.item(0)
        row.update(
            {
                "result": "textured",
                "appearance": side.appearance.name if side.appearance else None,
                "side_faces": feature.sideFaces.count,
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    if source.isModified != modified_before:
        raise RuntimeError("The saved FFC source changed during the texture experiment.")
    row["source_modified_after"] = source.isModified
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.refresh()
    print("FFC_PRODUCTION_TEXTURE=" + json.dumps(row))


if __name__ == "__main__":
    run(None)
