"""
Probe single- and multi-trace FFC lofts in an unsaved Fusion scratch design.

Run through Fusion Text Commands ``Python.Run`` with ``Wire creation tester
v109`` open and no command in progress. The source is read only. The report
is written under ignored ``artifacts/verification/``.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from importlib import reload
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler.fusion.cable_solid_parts.ribbon_builder as ribbon_builder_module
from cable_bundler.domain import CableGroupType, RibbonBodyType, RibbonGeometryType, loads
from cable_bundler.fusion.cable_solids import _solve_complete_group_routes
from cable_bundler.fusion.ffc_dimensions import ffc_dimensions
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
from cable_bundler.fusion.solid_ribbon import SOLID_RIBBON_LEAD_FRACTIONS, solid_ribbon_plan


def run(_context: object) -> None:
    """
    Probe the symmetric V-notched FFC profile through full and paired lofts.
    """
    application = adsk.core.Application.get()
    original = application.activeDocument
    if original is None or str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the loft probe.")
    source = next(
        (
            application.documents.item(index)
            for index in range(application.documents.count)
            if application.documents.item(index).name == "Wire creation tester v109"
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The open Wire creation tester v109 design is required.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The FFC source document is not a Fusion design.")
    source_modified_before = source.isModified
    selected = None
    discrete_solid = None
    for stored in FusionHarnessGateway(source_design).list_stored_harnesses():
        definition = loads(stored.serialized_definition)
        for group in definition.cable_groups:
            if group.ribbon_geometry is RibbonGeometryType.FFC:
                selected = (definition, group)
                break
            if (
                group.group_type is CableGroupType.RIBBON
                and group.ribbon_body_type is RibbonBodyType.SOLID
            ):
                discrete_solid = (definition, group)
        if selected is not None:
            break
    if selected is None and discrete_solid is not None:
        definition, existing = discrete_solid
        group = replace(
            existing,
            ribbon_geometry=RibbonGeometryType.FFC,
            ribbon_body_type=RibbonBodyType.SOLID,
            trace_width_mm=None,
            trace_spacing_mm=None,
        )
        definition = replace(
            definition,
            cable_groups=tuple(
                group if item.cable_group_id == group.cable_group_id else item
                for item in definition.cable_groups
            ),
        )
        selected = (definition, group)
    if selected is None:
        raise RuntimeError("The FFC source has no saved FFC or Solid ribbon cable group.")
    definition, group = selected
    _routes, legs, routes_by_id = _solve_complete_group_routes(source_design, definition, None)
    group_legs = tuple(
        (leg, routes_by_id[leg.route_id])
        for leg in legs
        if leg.cable_group_id == group.cable_group_id
    )
    main = tuple(item for item in group_legs if not item[0].is_connection_branch)
    if len(main) != 1:
        raise RuntimeError("FFC must have one main route for the loft probe.")
    leg, route = main[0]
    dimensions = ffc_dimensions(source_design, definition, group)
    shape = ribbon_route_shape(
        source_design, definition, leg, route, group.ribbon_lines, dimensions.pitch_mm
    ).shape
    plan = solid_ribbon_plan(
        source_design,
        definition,
        group,
        leg,
        tuple(item for item in group_legs if item[0].is_connection_branch),
        shape,
        dimensions.pitch_mm,
    )
    builder = reload(ribbon_builder_module)
    variants: dict[str, dict[str, object]] = {}
    report: dict[str, object] = {
        "source": source.name,
        "source_modified_before": source_modified_before,
        "group_id": str(group.cable_group_id),
        "lines": group.ribbon_lines,
        "pitch_mm": dimensions.pitch_mm,
        "width_mm": dimensions.trace_width_mm,
        "spacing_mm": dimensions.spacing_mm,
        "stations": len(plan.sections),
        "variants": variants,
    }
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not open a scratch design.")
    try:
        scratch_design = adsk.fusion.Design.cast(application.activeProduct)
        if scratch_design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        lead_count = len(SOLID_RIBBON_LEAD_FRACTIONS)
        first_main = lead_count
        last_main = len(plan.sections) - lead_count - 1
        guides = tuple(
            first_main + math.ceil(fraction * (last_main - first_main))
            for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
        )
        indices = tuple(dict.fromkeys((0, *guides, len(plan.sections) - 1)))
        middle_lane = group.ribbon_lines // 2
        single_trace = tuple(
            replace(station, centers=(station.centers[middle_lane],)) for station in plan.sections
        )
        section_sets = (
            (("ffc_full", plan.sections), ("ffc_single_trace", single_trace))
            + tuple(
                (f"ffc_pair_{start}_{end}", (plan.sections[start], plan.sections[end]))
                for start, end in zip(indices, indices[1:])
            )
            + tuple(
                (f"ffc_single_pair_{start}_{end}", (single_trace[start], single_trace[end]))
                for start, end in zip(indices, indices[1:])
            )
        )
        for name, stations in section_sets:
            transform = adsk.core.Matrix3D.create()
            component = scratch_design.rootComponent.occurrences.addNewComponent(
                transform
            ).component
            try:
                loft = builder._build_solid_loft(
                    component,
                    replace(plan, sections=stations),
                    group.diameter_mm,
                    transform,
                    dimensions,
                )
                variants[name] = {
                    "result": "success",
                    "feature_bodies": loft.bodies.count,
                    "component_bodies": component.bRepBodies.count,
                    "solid": loft.bodies.item(0).isSolid,
                    "volume_cm3": loft.bodies.item(0).volume,
                    "side_faces": loft.sideFaces.count,
                }
                if name == "ffc_full":
                    lane_faces = [0] * group.ribbon_lines
                    for face_index in range(loft.sideFaces.count):
                        face = loft.sideFaces.item(face_index)
                        if face is None:
                            raise RuntimeError("The FFC loft has a missing side face.")
                        lane = builder._face_lane(face, shape.frames, transform, group, plan)
                        lane_faces[lane] += 1
                    variants[name]["lane_face_counts"] = lane_faces
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                variants[name] = {
                    "result": "failed",
                    "error": str(error),
                }
    finally:
        if not scratch.close(False):
            raise RuntimeError("Fusion could not close the scratch design.")
        if not original.activate():
            raise RuntimeError("Fusion could not restore the original design.")
    report["source_modified_after"] = source.isModified
    output = (
        Path(builder.__file__).resolve().parents[3] / "artifacts/verification/ffc_loft_probe.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("FFC_LOFT_PROBE=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
