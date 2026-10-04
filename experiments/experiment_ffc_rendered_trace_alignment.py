"""
Render all numbered FFC lanes in an unsaved scratch, then restore its colors.

The live saved design supplies contact order and sizing only. The generated
scratch body is left open with its original production appearance restored.
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableColor, RibbonGeometryType, loads
from cable_bundler.fusion.cable_solid_parts.one_face_texture import apply_ffc_trace_texture
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from experiments.experiment_live_ffc_correspondence import _live_plan

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification"


def run(_context: object) -> None:
    """
    Expose every lane visually without altering the saved FFC definition.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved corrected FFC scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active scratch is not a Fusion design.")
    matches = [
        occurrence.component
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name.startswith("Cable Group 5_")
    ]
    if len(matches) != 1 or matches[0].features.sweepFeatures.count != 1:
        raise RuntimeError("The corrected generated FFC is not unique in this scratch.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    source_modified = source.isModified
    stored = FusionHarnessGateway(source_design).list_stored_harnesses()
    if not stored:
        raise RuntimeError("The source has no stored harness.")
    definition = loads(stored[0].serialized_definition)
    group = next(
        group
        for group in definition.cable_groups
        if group.ribbon_geometry is RibbonGeometryType.FFC
    )
    materials = definition.cable_group_materials(group)
    plan, _thickness, dimensions, group_id = _live_plan(source_design)
    feature = matches[0].features.sweepFeatures.item(0)
    rainbow = []
    for index in range(group.ribbon_lines):
        hue = index * 0.618033988749895 % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
        rainbow.append(CableColor(f"Trace {index + 1}", *(round(channel * 255) for channel in rgb)))
    transform = adsk.core.Matrix3D.create()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    capture = OUTPUT / "ffc_corrected_all_traces.png"
    apply_ffc_trace_texture(
        design,
        feature,
        plan.sections[0],
        plan.sections[-1],
        dimensions,
        tuple(rainbow),
        CableColor("Web", 38, 42, 48),
        UUID(group_id),
        transform,
    )
    application.activeViewport.refresh()
    if not application.activeViewport.saveAsImageFile(str(capture), 0, 0):
        raise RuntimeError("Fusion could not capture the rainbow FFC test.")
    apply_ffc_trace_texture(
        design,
        feature,
        plan.sections[0],
        plan.sections[-1],
        dimensions,
        group.resolved_ribbon_line_colors(materials.main_color),
        materials.main_color,
        group.cable_group_id,
        transform,
    )
    application.activeViewport.refresh()
    if source.isModified != source_modified:
        raise RuntimeError("The saved FFC source changed during the color test.")
    report = {
        "rainbow_trace_count": len(rainbow),
        "capture": str(capture),
        "source_modified_after": source.isModified,
        "restored_appearance": feature.sideFaces.item(0).appearance.name,
    }
    (OUTPUT / "ffc_rendered_trace_alignment.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("FFC_RENDERED_TRACE_ALIGNMENT=" + json.dumps(report))


if __name__ == "__main__":
    run(None)
