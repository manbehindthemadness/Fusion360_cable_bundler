"""
Check the persisted 19-line Solid ribbon in a disposable Fusion design.

Run through Fusion Text Commands ``Python.Run`` with no command active. The
active design is not edited; the experiment closes its unsaved scratch design.
Requires Fusion with the cable bundler importable from the add-in directory.
"""

from __future__ import annotations

import json
from importlib import reload
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler.fusion.cable_solid_parts.ribbon_builder as ribbon_builder_module
import cable_bundler.fusion.solid_ribbon as solid_ribbon_module
from cable_bundler.domain import loads
from cable_bundler.fusion.cable_solids import _solve_complete_group_routes
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
from cable_bundler.routing.geometry import difference, magnitude


def run(_context: object) -> None:
    """
    Verify one uniform-width contact-to-contact loft in the source geometry.
    """
    application = adsk.core.Application.get()
    solid_ribbon = reload(solid_ribbon_module)
    ribbon_builder = reload(ribbon_builder_module)
    original = application.activeDocument
    if original is None or str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Open a design and finish the active Fusion command first.")
    source = next(
        (
            document
            for document in application.documents
            if document.name == "Wire creation tester v107"
        ),
        None,
    )
    if source is None or not source.activate():
        raise RuntimeError("Keep Wire creation tester v107 open for this probe.")
    source_modified_before = source.isModified
    source_design = adsk.fusion.Design.cast(application.activeProduct)
    if source_design is None:
        raise RuntimeError("The source document is not a Fusion design.")
    actual_plan = None
    for stored in FusionHarnessGateway(source_design).list_stored_harnesses():
        definition = loads(stored.serialized_definition)
        for group in definition.cable_groups:
            if group.ribbon_lines != 19:
                continue
            _routes, legs, routes_by_id = _solve_complete_group_routes(
                source_design, definition, None
            )
            group_legs = tuple(
                (leg, routes_by_id[leg.route_id])
                for leg in legs
                if leg.cable_group_id == group.cable_group_id
            )
            main = tuple(item for item in group_legs if not item[0].is_connection_branch)
            if len(main) != 1:
                raise RuntimeError("The source Solid ribbon does not have one main leg.")
            leg, route = main[0]
            fitted = ribbon_route_shape(
                source_design, definition, leg, route, group.ribbon_lines, group.diameter_mm
            )
            plan = solid_ribbon.solid_ribbon_plan(
                source_design,
                definition,
                group,
                leg,
                tuple(item for item in group_legs if item[0].is_connection_branch),
                fitted.shape,
            )
            actual_plan = (plan, group.diameter_mm)
            break
        if actual_plan is not None:
            break
    if actual_plan is None:
        raise RuntimeError("No persisted 19-line ribbon was found in the source design.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not open a scratch design.")
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        transform = adsk.core.Matrix3D.create()
        plan, diameter_mm = actual_plan
        line_count = len(plan.sections[0].centers)
        start_span = magnitude(
            difference(plan.sections[0].centers[-1], plan.sections[0].centers[0])
        )
        end_span = magnitude(
            difference(plan.sections[-1].centers[-1], plan.sections[-1].centers[0])
        )
        component = design.rootComponent.occurrences.addNewComponent(transform).component
        started = perf_counter()
        loft = ribbon_builder._build_solid_loft(component, plan, diameter_mm, transform)
        elapsed_s = perf_counter() - started
        camera = application.activeViewport.camera
        camera.isFitView = True
        application.activeViewport.camera = camera
        application.activeViewport.refresh()
        image_path = "/private/tmp/cable-bundler-solid-ribbon-uniform.png"
        if not application.activeViewport.saveAsImageFile(image_path, 1600, 1200):
            raise RuntimeError("Fusion could not capture the uniform Solid ribbon.")
        result = {
            "lofts": component.features.loftFeatures.count,
            "bodies": component.bRepBodies.count,
            "solid": component.bRepBodies.item(0).isSolid,
            "volume_cm3": component.bRepBodies.item(0).volume,
            "side_faces": loft.sideFaces.count,
            "elapsed_s": elapsed_s,
            "station_count": len(plan.sections),
            "line_count": line_count,
            "start_span_mm": start_span,
            "end_span_mm": end_span,
            "middle_span_mm": magnitude(
                difference(plan.sections[20].centers[-1], plan.sections[20].centers[0])
            ),
            "lobe_width_mm": plan.sections[0].lobe_width_mm,
            "image_path": image_path,
        }
    finally:
        if not scratch.close(False):
            raise RuntimeError("Fusion could not close the scratch design.")
        if not original.activate():
            raise RuntimeError("Fusion could not restore the original active design.")
    print(
        "SOLID_RIBBON_SECTION="
        + json.dumps(
            {
                "source_document": source.name,
                "source_modified_before": source_modified_before,
                "source_modified_after": source.isModified,
                "result": result,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
