"""
Compare the real FFC route's sparse and complete loft gates in Fusion.

Run with ``Python.Run`` while ``Wire creation tester v109`` is active and no
command is open. Only an unsaved scratch design receives geometry; it remains
open for inspection after writing an ignored report under ``artifacts/verification``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import RibbonGeometryType, loads
from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.fusion.cable_solid_parts import ribbon_builder
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point
from cable_bundler.fusion.cable_solids import _solve_complete_group_routes
from cable_bundler.fusion.ffc_dimensions import ffc_dimensions
from cable_bundler.fusion.harness_gateway import FusionHarnessGateway
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
from cable_bundler.fusion.solid_ribbon import (
    SOLID_RIBBON_LEAD_FRACTIONS,
    SolidRibbonPlan,
    SolidRibbonSection,
    solid_ribbon_plan,
)
from cable_bundler.routing import Vector3
from cable_bundler.routing.geometry import cross, dot
from experiments.experiment_loft_seam_rail import _add_vertex_rail


def _live_plan(
    design: adsk.fusion.Design,
) -> tuple[SolidRibbonPlan, float, FfcDimensions, str]:
    """
    Resolve the saved FFC group through the product's normal planning path.
    """
    for stored in FusionHarnessGateway(design).list_stored_harnesses():
        definition = loads(stored.serialized_definition)
        for group in definition.cable_groups:
            if group.ribbon_geometry is not RibbonGeometryType.FFC:
                continue
            _, legs, routes_by_id = _solve_complete_group_routes(design, definition, None)
            group_legs = tuple(
                (leg, routes_by_id[leg.route_id])
                for leg in legs
                if leg.cable_group_id == group.cable_group_id
            )
            main = tuple(item for item in group_legs if not item[0].is_connection_branch)
            if len(main) != 1:
                raise RuntimeError("The live FFC group needs exactly one main route.")
            leg, route = main[0]
            dimensions = ffc_dimensions(design, definition, group)
            shape = ribbon_route_shape(
                design, definition, leg, route, group.ribbon_lines, dimensions.pitch_mm
            ).shape
            plan = solid_ribbon_plan(
                design,
                definition,
                group,
                leg,
                tuple(item for item in group_legs if item[0].is_connection_branch),
                shape,
                dimensions.pitch_mm,
            )
            return plan, group.diameter_mm, dimensions, str(group.cable_group_id)
    raise RuntimeError("The active design has no saved FFC group.")


def _sparse_indices(station_count: int) -> tuple[int, ...]:
    """
    Mirror the station selection in the current production loft builder.
    """
    lead_count = len(SOLID_RIBBON_LEAD_FRACTIONS)
    first_main = lead_count
    last_main = station_count - lead_count - 1
    main = (
        tuple(
            first_main + math.ceil(fraction * (last_main - first_main))
            for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
        )
        if first_main <= last_main
        else ()
    )
    return tuple(dict.fromkeys((0, *main, station_count - 1)))


def _angle_degrees(first: Vector3, second: Vector3) -> float:
    """
    Measure a section-axis change without treating reversed axes as equal.
    """
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(first, second)))))


def _frame_steps(plan: SolidRibbonPlan, indices: tuple[int, ...]) -> list[dict[str, float | int]]:
    """
    Record both tangent and width rotation across every chosen gate interval.
    """
    return [
        {
            "from": start,
            "to": end,
            "normal_degrees": _angle_degrees(
                plan.sections[start].normal, plan.sections[end].normal
            ),
            "width_degrees": _angle_degrees(plan.sections[start].width, plan.sections[end].width),
        }
        for start, end in zip(indices, indices[1:])
    ]


def _land_point(
    station: SolidRibbonSection,
    lane: int,
    top: bool,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.core.Point3D:
    """
    Locate the center of a trace's colorable top or bottom flat land.
    """
    height_axis = cross(station.normal, station.width)
    height = thickness_mm / 2.0 if top else -thickness_mm / 2.0
    return fusion_point(station.centers[lane].translated(height_axis, height), transform)


def _rail_corners(
    station: SolidRibbonSection,
    pitch_mm: float,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.core.Point3D, ...]:
    """
    Label two opposite perimeter corners of the exact FFC profile.
    """
    height_axis = cross(station.normal, station.width)
    left = station.centers[0].translated(station.width, -pitch_mm / 2.0)
    right = station.centers[-1].translated(station.width, pitch_mm / 2.0)
    return (
        fusion_point(left.translated(height_axis, thickness_mm / 2.0), transform),
        fusion_point(right.translated(height_axis, -thickness_mm / 2.0), transform),
    )


def _inspect_lands(
    loft: adsk.fusion.LoftFeature,
    plan: SolidRibbonPlan,
    indices: tuple[int, ...],
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
    tolerance_cm: float,
) -> dict[str, object]:
    """
    Check that each logical trace land remains on one side face at every gate.
    """
    faces = loft.sideFaces
    lane_count = len(plan.sections[0].centers)
    expected = 12 * lane_count + 4
    failures: list[dict[str, object]] = []
    tested = 0
    for lane in range(lane_count):
        for top in (True, False):
            initial = _land_point(plan.sections[indices[0]], lane, top, thickness_mm, transform)
            hits = [
                face_index
                for face_index in range(faces.count)
                if faces.item(face_index).isPointOnFace(initial, tolerance_cm)
            ]
            if len(hits) != 1:
                failures.append({"lane": lane, "top": top, "station": indices[0], "hits": hits})
                continue
            face = faces.item(hits[0])
            for station_index in indices[1:]:
                tested += 1
                point = _land_point(
                    plan.sections[station_index], lane, top, thickness_mm, transform
                )
                if not face.isPointOnFace(point, tolerance_cm):
                    failures.append(
                        {"lane": lane, "top": top, "station": station_index, "face": hits[0]}
                    )
    return {
        "side_faces": faces.count,
        "expected_unsplit_side_faces": expected,
        "land_samples": tested,
        "land_misses": len(failures),
        "first_misses": failures[:24],
        "clean": faces.count == expected and not failures,
    }


def _loft_case(
    design: adsk.fusion.Design,
    plan: SolidRibbonPlan,
    indices: tuple[int, ...],
    thickness_mm: float,
    dimensions: FfcDimensions,
    rails: bool,
    tolerance_cm: float,
) -> dict[str, object]:
    """
    Loft the product's own FFC sections with optional opposite-corner rails.
    """
    transform = adsk.core.Matrix3D.create()
    component = design.rootComponent.occurrences.addNewComponent(transform).component
    sections: list[adsk.fusion.Sketch] = []
    case: dict[str, object] = {
        "indices": list(indices),
        "rails": rails,
        "frame_steps": _frame_steps(plan, indices),
    }
    try:
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        for station_index in indices:
            sketch, _plane = ribbon_builder._add_solid_section(
                component, plan.sections[station_index], thickness_mm, transform, dimensions
            )
            sections.append(sketch)
            loft_input.loftSections.add(sketch.profiles.item(0))
        if rails:
            corners = [
                _rail_corners(plan.sections[index], dimensions.pitch_mm, thickness_mm, transform)
                for index in indices
            ]
            for vertex in (0, 1):
                rail, gap_cm = _add_vertex_rail(component, "live FFC", corners, vertex)
                case[f"rail_{vertex}_gate_gap_cm"] = gap_cm
                if gap_cm > 0.001:
                    raise RuntimeError(f"Rail {vertex} missed a gate by {gap_cm:g} cm.")
                if loft_input.centerLineOrRails.addRail(rail) is None:
                    raise RuntimeError(f"Fusion rejected rail {vertex}.")
        loft_input.isSolid = True
        loft_input.isTangentEdgesMerged = True
        loft = component.features.loftFeatures.add(loft_input)
        if loft is None:
            code, detail = adsk.core.Application.get().getLastError()
            raise RuntimeError(f"Fusion rejected the loft ({code}: {detail}).")
        case["body_count"] = loft.bodies.count
        if loft.bodies.count != 1 or not loft.bodies.item(0).isSolid:
            case["result"] = "invalid_body"
        else:
            case["volume_cm3"] = loft.bodies.item(0).volume
            case["inspection"] = _inspect_lands(
                loft, plan, indices, thickness_mm, transform, tolerance_cm
            )
            case["result"] = "clean" if case["inspection"]["clean"] else "deviation"
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        case["result"] = "failed"
        case["error"] = str(error)
    return case


def run(_context: object) -> None:
    """
    Compare actual-source loft outcomes without modifying its saved design.
    """
    application = adsk.core.Application.get()
    source = application.activeDocument
    if (
        source is None
        or source.name != "Wire creation tester v109"
        or str(application.userInterface.activeCommand) != "SelectCommand"
    ):
        raise RuntimeError("Activate Wire creation tester v109 and finish the active command.")
    design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if design is None:
        raise RuntimeError("The source document is not a Fusion design.")
    source_modified_before = source.isModified
    plan, thickness_mm, dimensions, group_id = _live_plan(design)
    sparse = _sparse_indices(len(plan.sections))
    all_stations = tuple(range(len(plan.sections)))
    report: dict[str, object] = {
        "source": source.name,
        "source_modified_before": source_modified_before,
        "group_id": group_id,
        "traces": len(plan.sections[0].centers),
        "stations": len(plan.sections),
        "thickness_mm": thickness_mm,
        "pitch_mm": dimensions.pitch_mm,
        "trace_width_mm": dimensions.trace_width_mm,
        "spacing_mm": dimensions.spacing_mm,
        "start_contact_ids": list(plan.contact_ids[0]),
        "end_contact_ids": list(plan.contact_ids[1]),
        "cases": {},
    }
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create an unsaved scratch design.")
    try:
        scratch_design = adsk.fusion.Design.cast(application.activeProduct)
        if scratch_design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        scratch_design.designType = adsk.fusion.DesignTypes.DirectDesignType
        for name, indices, rails in (
            ("production_sparse", sparse, False),
            ("sparse_two_rails", sparse, True),
            ("all_stations_two_rails", all_stations, True),
        ):
            report["cases"][name] = _loft_case(
                scratch_design,
                plan,
                indices,
                thickness_mm,
                dimensions,
                rails,
                application.pointTolerance * 10.0,
            )
    finally:
        report["scratch_open"] = scratch.isValid
        report["source_modified_after"] = source.isModified
        output = (
            Path(ribbon_builder.__file__).resolve().parents[3]
            / "artifacts/verification/live_ffc_correspondence.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "LIVE_FFC_CORRESPONDENCE="
            + json.dumps(
                {
                    "source": report["source"],
                    "traces": report["traces"],
                    "stations": report["stations"],
                    "results": {name: case["result"] for name, case in report["cases"].items()},
                    "scratch_open": report["scratch_open"],
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    run(None)
