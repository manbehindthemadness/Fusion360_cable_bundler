"""
Compare production FFC and Discrete loft profiles on identical route stations.

Run through the local Fusion script runner with no command active. The open
saved harness supplies only routing/contact data. Both lofts are generated in
one new unsaved scratch, placed side by side, and measured from rendered UVs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import RibbonBodyType, RibbonGeometryType, loads
from cable_bundler.domain.ffc import resolve_ffc_dimensions
from cable_bundler.fusion.cable_solid_parts.ribbon_builder import _build_solid_loft
from cable_bundler.fusion.cable_solids import _solve_complete_group_routes
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
from cable_bundler.fusion.solid_ribbon import SolidRibbonPlan, SolidRibbonSection, solid_ribbon_plan
from cable_bundler.routing import Vector3
from cable_bundler.routing.geometry import difference, magnitude

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "artifacts/verification/production_loft_uv_comparison.json"
)
CONTROL_OUTPUT = OUTPUT.with_name("production_loft_uv_control.json")
CAP_PLANE_TOLERANCE_MM = 0.025


def _midpoint(section: SolidRibbonSection) -> adsk.core.Point3D:
    """
    Convert the middle of a numbered contact bank into Fusion centimeters.
    """
    first, last = section.centers[0], section.centers[-1]
    return adsk.core.Point3D.create(
        (first.x + last.x) / 20.0,
        (first.y + last.y) / 20.0,
        (first.z + last.z) / 20.0,
    )


def _on_plane(node: adsk.core.Point3D, section: SolidRibbonSection) -> bool:
    """
    Test a mesh node against one numbered Interface contact plane.
    """
    origin = _midpoint(section)
    dx = (node.x - origin.x) * 10.0
    dy = (node.y - origin.y) * 10.0
    dz = (node.z - origin.z) * 10.0
    separation = abs(dx * section.normal.x + dy * section.normal.y + dz * section.normal.z)
    return separation <= CAP_PLANE_TOLERANCE_MM


def _face_uv_report(
    face: adsk.fusion.BRepFace,
    plan: SolidRibbonPlan,
) -> dict[str, object]:
    """
    Measure one loft side face using rendered, never calculated, UVs.
    """
    meshes = face.meshManager.displayMeshes
    if not meshes.count:
        return {"rendered": False}
    mesh = meshes.item(0)
    coordinates = mesh.nodeCoordinates
    texture = mesh.textureCoordinates
    if len(coordinates) != len(texture) or not texture:
        raise RuntimeError("Fusion returned unpaired loft display-mesh UVs.")
    u = tuple(float(point.x) for point in texture)
    v = tuple(float(point.y) for point in texture)
    if not all(math.isfinite(value) for value in (*u, *v)):
        raise RuntimeError("Fusion returned nonfinite loft display-mesh UVs.")
    first = tuple(value for node, value in zip(coordinates, u) if _on_plane(node, plan.sections[0]))
    last = tuple(value for node, value in zip(coordinates, u) if _on_plane(node, plan.sections[-1]))
    return {
        "rendered": True,
        "nodes": len(u),
        "u_range": [min(u), max(u)],
        "v_range": [min(v), max(v)],
        "start_nodes": len(first),
        "end_nodes": len(last),
        "start_u_range": [min(first), max(first)] if first else None,
        "end_u_range": [min(last), max(last)] if last else None,
    }


def _loft_report(
    feature: adsk.fusion.LoftFeature,
    plan: SolidRibbonPlan,
) -> dict[str, object]:
    """
    Summarize the production loft's topology and per-face UV domains.
    """
    body = feature.bodies.item(0)
    faces = tuple(feature.sideFaces.item(index) for index in range(feature.sideFaces.count))
    rows = tuple(_face_uv_report(face, plan) for face in faces)
    rendered = tuple(row for row in rows if row["rendered"])
    both_ends = tuple(row for row in rendered if row["start_nodes"] and row["end_nodes"])
    return {
        "solid": body.isSolid,
        "volume_cm3": body.volume,
        "body_faces": body.faces.count,
        "side_faces": len(faces),
        "rendered_side_faces": len(rendered),
        "both_contact_planes": len(both_ends),
        "face_uv": rows,
    }


def _source_plan(
    design: adsk.fusion.Design,
) -> tuple[SolidRibbonPlan, float, str]:
    """
    Resolve the displayed Solid Discrete group's authoritative station plan.
    """
    stored = FusionHarnessGateway(design).list_stored_harnesses()
    if not stored:
        raise RuntimeError("The saved source has no harness definition.")
    definition = loads(stored[0].serialized_definition)
    matches = tuple(
        group
        for group in definition.cable_groups
        if group.ribbon_body_type is RibbonBodyType.SOLID
        and group.ribbon_geometry is RibbonGeometryType.DISCRETE
    )
    if len(matches) != 1:
        raise RuntimeError("The source must have exactly one Solid Discrete ribbon group.")
    group = matches[0]
    _preview, legs, routes_by_id = _solve_complete_group_routes(design, definition, None)
    group_legs = tuple(
        (leg, routes_by_id[leg.route_id])
        for leg in legs
        if leg.cable_group_id == group.cable_group_id
    )
    main = tuple(item for item in group_legs if not item[0].is_connection_branch)
    if len(main) != 1:
        raise RuntimeError("The ribbon group needs exactly one main route.")
    leg, route = main[0]
    fitted = ribbon_route_shape(
        design, definition, leg, route, group.ribbon_lines, group.diameter_mm
    )
    plan = solid_ribbon_plan(
        design,
        definition,
        group,
        leg,
        tuple(item for item in group_legs if item[0].is_connection_branch),
        fitted.shape,
    )
    return plan, group.diameter_mm, str(group.cable_group_id)


def run(_context: object) -> None:
    """
    Build both section styles in one unsaved scratch and save a UV audit.
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
    if source is None or not source.isSaved:
        raise RuntimeError("Open the saved harness source before this experiment.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    modified_before = source.isModified
    plan, diameter_mm, group_id = _source_plan(source_design)
    lines = len(plan.sections[0].centers)
    pitch_mm = (
        magnitude(difference(plan.sections[0].centers[-1], plan.sections[0].centers[0]))
        / (lines - 1)
        if lines > 1
        else diameter_mm
    )
    ffc = resolve_ffc_dimensions(pitch_mm, (None,) * lines, None, None)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the loft comparison scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent
    cases: list[dict[str, object]] = []
    built: list[tuple[str, adsk.fusion.LoftFeature]] = []
    for label, offset_cm in (("Discrete", 0.0), ("FFC", 10.0)):
        placement = adsk.core.Matrix3D.create()
        placement.translation = adsk.core.Vector3D.create(offset_cm, 0.0, 0.0)
        component = root.occurrences.addNewComponent(placement).component
        component.name = f"Production loft · {label} · {lines} lines"
        row: dict[str, object] = {"profile": label, "offset_cm": offset_cm}
        try:
            feature = _build_solid_loft(
                component,
                plan,
                diameter_mm,
                adsk.core.Matrix3D.create(),
                ffc if label == "FFC" else None,
            )
            feature.name = f"Production {label} profile loft"
            built.append((label, feature))
            row["result"] = "solid"
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row.update({"result": "failed", "error": str(error)})
        cases.append(row)
    viewport = application.activeViewport
    viewport.fit()
    viewport.refresh()
    for row in cases:
        matching = next((feature for label, feature in built if label == row["profile"]), None)
        if matching is not None:
            row.update(_loft_report(matching, plan))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    capture = OUTPUT.with_suffix(".png")
    captured = viewport.saveAsImageFile(str(capture), 0, 0)
    if source.isModified != modified_before:
        raise RuntimeError("The saved source changed during the loft comparison.")
    report = {
        "source": source.name,
        "source_modified_before": modified_before,
        "source_modified_after": source.isModified,
        "scratch": scratch.name,
        "group_id": group_id,
        "lines": lines,
        "pitch_mm": pitch_mm,
        "thickness_mm": diameter_mm,
        "ffc_trace_width_mm": ffc.trace_width_mm,
        "ffc_spacing_mm": ffc.spacing_mm,
        "same_plan": True,
        "capture": str(capture) if captured else None,
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "PRODUCTION_LOFT_UV_COMPARISON="
        + json.dumps(
            {
                "report": str(OUTPUT),
                "results": [(row["profile"], row["result"]) for row in cases],
                "capture": str(capture) if captured else None,
            }
        )
    )


def _controlled_plan(lines: int, pitch_mm: float, diameter_mm: float) -> SolidRibbonPlan:
    """
    Hold the route valid while changing only the production section style.

    Twelve parallel planes span 110 mm; the bank turns 30 degrees total, so
    no neighboring selected loft sections present a severe angular step.
    """
    sections: list[SolidRibbonSection] = []
    for station_index in range(12):
        angle = math.radians(30.0 * station_index / 11.0)
        width = Vector3(0.0, math.cos(angle), math.sin(angle))
        centers = tuple(
            Vector3(10.0 * station_index, 0.0, 0.0).translated(
                width, (line - (lines - 1) / 2.0) * pitch_mm
            )
            for line in range(lines)
        )
        sections.append(SolidRibbonSection(centers, Vector3(1.0, 0.0, 0.0), width, diameter_mm))
    ordered = tuple(sections)
    lanes = tuple(tuple(section.centers[line] for section in ordered) for line in range(lines))
    contact_ids = tuple(str(line + 1) for line in range(lines))
    return SolidRibbonPlan(
        ordered,
        lanes,
        (contact_ids, contact_ids),
        (contact_ids, contact_ids),
        (),
        (ordered[0].centers, ordered[-1].centers),
    )


def run_control(_context: object, lines: int = 5) -> None:
    """
    Compare two production loft profiles on identical valid control stations.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = application.activeDocument
    if source is None:
        raise RuntimeError("Fusion has no active source document.")
    source_modified_before = source.isModified
    if lines not in (5, 19):
        raise ValueError("The controlled loft comparison supports 5 or 19 lines.")
    pitch_mm = 2.5 if lines == 5 else 2.5066666666666664
    diameter_mm = 1.5
    output = (
        CONTROL_OUTPUT
        if lines == 5
        else CONTROL_OUTPUT.with_name("production_loft_uv_control_19.json")
    )
    plan = _controlled_plan(lines, pitch_mm, diameter_mm)
    ffc = resolve_ffc_dimensions(pitch_mm, (None,) * lines, None, None)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the controlled loft scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The controlled loft scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    cases: list[dict[str, object]] = []
    built: list[tuple[str, adsk.fusion.LoftFeature]] = []
    for label, offset_cm in (("Discrete", 0.0), ("FFC", 4.0)):
        placement = adsk.core.Matrix3D.create()
        placement.translation = adsk.core.Vector3D.create(0.0, offset_cm, 0.0)
        component = design.rootComponent.occurrences.addNewComponent(placement).component
        component.name = f"Production loft · {label} · valid control"
        row: dict[str, object] = {"profile": label, "offset_cm": offset_cm}
        try:
            feature = _build_solid_loft(
                component,
                plan,
                diameter_mm,
                adsk.core.Matrix3D.create(),
                ffc if label == "FFC" else None,
            )
            feature.name = f"Production {label} profile loft"
            built.append((label, feature))
            row["result"] = "solid"
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row.update({"result": "failed", "error": str(error)})
        cases.append(row)
    viewport = application.activeViewport
    viewport.fit()
    viewport.refresh()
    for row in cases:
        matching = next((feature for label, feature in built if label == row["profile"]), None)
        if matching is not None:
            row.update(_loft_report(matching, plan))
    camera = viewport.camera
    camera.target = adsk.core.Point3D.create(5.5, 2.0, 0.0)
    camera.eye = adsk.core.Point3D.create(5.5, 2.0, 30.0)
    camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
    camera.viewExtents = 16.0
    viewport.camera = camera
    viewport.refresh()
    output.parent.mkdir(parents=True, exist_ok=True)
    capture = output.with_suffix(".png")
    captured = viewport.saveAsImageFile(str(capture), 0, 0)
    if source.isModified != source_modified_before:
        raise RuntimeError("The source changed during the controlled loft comparison.")
    report = {
        "source": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "scratch": scratch.name,
        "lines": lines,
        "pitch_mm": pitch_mm,
        "thickness_mm": diameter_mm,
        "total_bank_rotation_degrees": 30.0,
        "same_plan": True,
        "capture": str(capture) if captured else None,
        "cases": cases,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "PRODUCTION_LOFT_UV_CONTROL="
        + json.dumps(
            {
                "report": str(output),
                "results": [(row["profile"], row["result"]) for row in cases],
                "capture": str(capture) if captured else None,
            }
        )
    )


if __name__ == "__main__":
    run(None)
