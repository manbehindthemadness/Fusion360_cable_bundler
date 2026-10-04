"""
Measure whether a newly built FFC exposes rendered UVs before texture mapping.

Creates one component in the active empty, unsaved scratch. The saved route
source is read only, and the scratch is left open for inspection.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.one_face_ffc import build_one_face_ffc_sweep
from experiments.experiment_live_ffc_correspondence import _live_plan

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_uv_readiness.json"


def _uv_span(mesh: adsk.fusion.TriangleMesh | None) -> tuple[float, float] | None:
    """
    Return the transverse UV range from a mesh, when available.
    """
    if mesh is None or not mesh.textureCoordinates:
        return None
    values = tuple(float(point.x) for point in mesh.textureCoordinates)
    return min(values), max(values)


def run(_context: object) -> None:
    """
    Record calculated versus display UVs before and after viewport refresh.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled" or scratch.isModified:
        raise RuntimeError("Activate a fresh empty unsaved FFC scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or design.rootComponent.occurrences.count:
        raise RuntimeError("The active scratch is not an empty Fusion design.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source must be open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved FFC source is not a design.")
    source_modified = source.isModified
    plan, thickness_mm, dimensions, _group_id = _live_plan(source_design)
    component = design.rootComponent.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    ).component
    component.name = "FFC UV readiness trial"
    feature = build_one_face_ffc_sweep(
        component, plan, dimensions, thickness_mm, adsk.core.Matrix3D.create()
    )
    side = feature.sideFaces.item(0)
    calculated = side.meshManager.createMeshCalculator().calculate()
    before = side.meshManager.displayMeshes
    row: dict[str, object] = {
        "calculated_uv": _uv_span(calculated),
        "before_display_count": before.count,
        "before_display_uv": _uv_span(before.item(0)) if before.count else None,
    }
    application.activeViewport.refresh()
    after = side.meshManager.displayMeshes
    row["after_display_count"] = after.count
    row["after_display_uv"] = _uv_span(after.item(0)) if after.count else None
    row["source_modified_after"] = source.isModified
    if source.isModified != source_modified:
        raise RuntimeError("The saved FFC source changed during UV readiness testing.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    print("FFC_UV_READINESS=" + json.dumps(row))


if __name__ == "__main__":
    run(None)
