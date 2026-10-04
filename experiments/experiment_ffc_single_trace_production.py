"""
Exercise the production one-face sweep and UV renderer for an antenna trace.

This creates a new unsaved Fusion scratch and leaves it open. No saved design
or existing scratch is modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import CableColor
from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.fusion.cable_solid_parts.one_face_ffc import build_one_face_ffc_sweep
from cable_bundler.fusion.cable_solid_parts.one_face_texture import apply_ffc_trace_texture
from cable_bundler.fusion.solid_ribbon import SolidRibbonPlan, SolidRibbonSection
from cable_bundler.routing import Vector3

OUTPUT = (
    Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_single_trace_production.json"
)


def run(_context: object) -> None:
    """
    Build and color one straight, contact-to-contact 0.2 mm antenna ribbon.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the single-trace scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    component = design.rootComponent.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    ).component
    component.name = "Production single-trace FFC trial"
    centers = tuple(Vector3(0.0, 0.0, z) for z in (0.0, 15.0, 30.0))
    sections = tuple(
        SolidRibbonSection((center,), Vector3(0.0, 0.0, 1.0), Vector3(1.0, 0.0, 0.0), 1.0)
        for center in centers
    )
    plan = SolidRibbonPlan(
        sections,
        (centers,),
        (("antenna-start",), ("antenna-end",)),
        (("attachment-start",), ("attachment-end",)),
        (),
        ((centers[0],), (centers[-1],)),
    )
    dimensions = FfcDimensions(1.25, 1.0, 0.25)
    row: dict[str, object] = {"scratch": scratch.name}
    try:
        feature = build_one_face_ffc_sweep(
            component, plan, dimensions, 0.2, adsk.core.Matrix3D.create()
        )
        apply_ffc_trace_texture(
            design,
            feature,
            sections[0],
            sections[-1],
            dimensions,
            (CableColor("Antenna", 255, 140, 0),),
            CableColor("Web", 40, 40, 40),
            UUID(int=1),
            adsk.core.Matrix3D.create(),
        )
        row.update(
            {
                "result": "textured",
                "body_faces": feature.bodies.item(0).faces.count,
                "side_faces": feature.sideFaces.count,
                "appearance": feature.sideFaces.item(0).appearance.name,
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.fit()
    print("FFC_SINGLE_TRACE_PRODUCTION=" + json.dumps(row))


if __name__ == "__main__":
    run(None)
