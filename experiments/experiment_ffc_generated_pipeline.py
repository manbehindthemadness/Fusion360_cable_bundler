"""
Exercise the product FFC body/material builder in an unsaved Fusion scratch.

The saved source supplies persistent group, route, and contact identity but
receives no geometry or metadata changes.
"""

from __future__ import annotations

import json
from importlib import reload
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import RibbonGeometryType, loads
from cable_bundler.fusion import solid_ribbon
from cable_bundler.fusion.cable_solid_parts import ribbon_builder
from cable_bundler.fusion.cable_solids import _solve_complete_group_routes
from cable_bundler.fusion.ffc_dimensions import ffc_dimensions
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_generated_pipeline.json"


def run(_context: object) -> None:
    """
    Build one generated FFC component using the normal product entry point.
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
    stored = FusionHarnessGateway(source_design).list_stored_harnesses()
    if not stored:
        raise RuntimeError("The source has no stored harness.")
    definition = loads(stored[0].serialized_definition)
    group_index, group = next(
        (index, group)
        for index, group in enumerate(definition.cable_groups)
        if group.ribbon_geometry is RibbonGeometryType.FFC
    )
    _preview, legs, routes_by_id = _solve_complete_group_routes(source_design, definition, None)
    group_legs = tuple(
        (leg, routes_by_id[leg.route_id])
        for leg in legs
        if leg.cable_group_id == group.cable_group_id
    )
    main = tuple(item for item in group_legs if not item[0].is_connection_branch)
    if len(main) != 1:
        raise RuntimeError("The live FFC group needs one main route.")
    leg, route = main[0]
    dimensions = ffc_dimensions(source_design, definition, group)
    fitted = ribbon_route_shape(
        source_design, definition, leg, route, group.ribbon_lines, dimensions.pitch_mm
    )
    plan = reload(solid_ribbon).solid_ribbon_plan(
        source_design,
        definition,
        group,
        leg,
        tuple(item for item in group_legs if item[0].is_connection_branch),
        fitted.shape,
        dimensions.pitch_mm,
    )
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate an unsaved FFC scratch before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    component = design.rootComponent.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    ).component
    component.name = "Generated FFC product trial"
    notices: list[str] = []
    row: dict[str, object] = {"source_modified_before": modified_before}
    try:
        body = reload(ribbon_builder).build_discrete_ribbon_solid(
            component,
            group,
            group_index,
            route,
            fitted.shape,
            fitted.guide_planes,
            adsk.core.Matrix3D.create(),
            definition.harness_id,
            definition.cable_group_materials(group),
            design,
            "solid",
            notices,
            plan,
            dimensions,
        )
        sides = [
            body.faces.item(index)
            for index in range(body.faces.count)
            if body.faces.item(index).appearance is not None
            and body.faces.item(index).appearance.hasTexture
        ]
        row.update(
            {
                "result": "generated",
                "body_faces": body.faces.count,
                "textured_faces": len(sides),
                "component_attributes": component.attributes.count,
                "notices": notices,
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    if source.isModified != modified_before:
        raise RuntimeError("The saved source changed during generated-output QA.")
    row["source_modified_after"] = source.isModified
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.fit()
    print("FFC_GENERATED_PIPELINE=" + json.dumps(row))


if __name__ == "__main__":
    run(None)
