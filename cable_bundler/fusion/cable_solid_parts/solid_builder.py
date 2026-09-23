"""Build persistent Fusion sweep bodies for one routed cable group."""

from __future__ import annotations

import json
import math
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import (
    CableGroupDefinition,
    CableMaterialSettings,
)
from ...routing import (
    RoutePreview,
    Vector3,
    tightest_bend,
)
from ..harness_gateway import ATTRIBUTE_GROUP
from .constants import (
    FINALIZED_OUTPUT_MODE,
    GENERATED_CABLE_GROUP_ATTRIBUTE,
    GENERATED_OUTPUT_MODE_KEY,
    SOLID_OUTPUT_MODE,
)
from .materials import cable_appearance, material_metadata
from .metadata import fusion_point, route_in_component_space, route_metadata
from .stripes import (
    clear_group_stripe_graphics,
    replace_group_stripe_bodies,
    replace_group_stripe_graphics,
)
from .sweep_geometry import (
    is_straight,
    prepare_group_sweep_segments,
    split_route_endpoint_pullbacks,
    split_route_for_pullback,
)


def _optional_uuid_text(value: Optional[UUID]) -> Optional[str]:
    """
    Convert optional generated-owner identity to JSON-compatible text.
    """
    return None if value is None else str(value)


def _route_endpoint_pullback_options(
    point: Vector3,
    route: RoutePreview,
    start_distance_mm: float,
    end_distance_mm: float,
    start_materials: Optional[CableMaterialSettings],
    end_materials: Optional[CableMaterialSettings],
    start_attachment_id: Optional[UUID],
    end_attachment_id: Optional[UUID],
    start_diameter_mm: float,
    end_diameter_mm: float,
) -> tuple[float, Optional[CableMaterialSettings], Optional[UUID], float]:
    """
    Match an oriented construction-segment boundary to its logical route end.
    """
    if point == route.curves[0].start:
        return start_distance_mm, start_materials, start_attachment_id, start_diameter_mm
    if point == route.curves[-1].end:
        return end_distance_mm, end_materials, end_attachment_id, end_diameter_mm
    return 0.0, None, None, 0.0


def build_cable_group_solid(
    component: adsk.fusion.Component,
    stripe_graphics_owner: adsk.fusion.Component,
    group: CableGroupDefinition,
    group_index: int,
    routes: tuple[RoutePreview, ...],
    transform: adsk.core.Matrix3D,
    harness_id: UUID,
    materials: CableMaterialSettings,
    design: adsk.fusion.Design,
    output_mode: str = SOLID_OUTPUT_MODE,
    *,
    is_visible: bool = True,
    route_diameters_mm: tuple[float, ...] = (),
    connection_branch_indices: frozenset[int] = frozenset(),
    route_materials: tuple[CableMaterialSettings, ...] = (),
    route_attachment_ids: tuple[Optional[UUID], ...] = (),
    route_pullbacks_mm: tuple[float, ...] = (),
    route_end_pullbacks_mm: tuple[float, ...] = (),
    route_pullback_materials: tuple[Optional[CableMaterialSettings], ...] = (),
    route_end_pullback_materials: tuple[Optional[CableMaterialSettings], ...] = (),
    route_pullback_attachment_ids: tuple[Optional[UUID], ...] = (),
    route_end_pullback_attachment_ids: tuple[Optional[UUID], ...] = (),
    route_pullback_diameters_mm: tuple[float, ...] = (),
    route_end_pullback_diameters_mm: tuple[float, ...] = (),
) -> None:
    """
    Sweep every deterministic group leg from its own path-normal profile.
    """
    if not routes:
        raise ValueError("A cable group requires at least one routed leg.")
    if output_mode not in {SOLID_OUTPUT_MODE, FINALIZED_OUTPUT_MODE}:
        raise ValueError(f"Unsupported cable output mode: {output_mode}")
    diameters = route_diameters_mm or (group.diameter_mm,) * len(routes)
    if len(diameters) != len(routes):
        raise ValueError("Every cable-group route requires one sweep diameter.")
    if any(index < 0 or index >= len(routes) for index in connection_branch_indices):
        raise ValueError("Cable-end branch route indices are invalid.")
    materials_by_route = route_materials or (materials,) * len(routes)
    if len(materials_by_route) != len(routes):
        raise ValueError("Every cable-group route requires material settings.")
    attachment_ids = route_attachment_ids or (None,) * len(routes)
    if len(attachment_ids) != len(routes):
        raise ValueError("Every cable-group route requires attachment identity metadata.")
    pullbacks_mm = route_pullbacks_mm or (0.0,) * len(routes)
    end_pullbacks_mm = route_end_pullbacks_mm or (0.0,) * len(routes)
    if len(pullbacks_mm) != len(routes) or len(end_pullbacks_mm) != len(routes):
        raise ValueError("Every cable-group route requires two endpoint pullback distances.")
    if any(
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or distance < 0.0
        for distance in (*pullbacks_mm, *end_pullbacks_mm)
    ):
        raise ValueError("Cable pullback distances must be finite and nonnegative.")
    pullback_materials: tuple[Optional[CableMaterialSettings], ...] = (
        route_pullback_materials if route_pullback_materials else (None,) * len(routes)
    )
    end_pullback_materials: tuple[Optional[CableMaterialSettings], ...] = (
        route_end_pullback_materials if route_end_pullback_materials else (None,) * len(routes)
    )
    pullback_attachment_ids: tuple[Optional[UUID], ...] = (
        route_pullback_attachment_ids if route_pullback_attachment_ids else (None,) * len(routes)
    )
    end_pullback_attachment_ids: tuple[Optional[UUID], ...] = (
        route_end_pullback_attachment_ids
        if route_end_pullback_attachment_ids
        else (None,) * len(routes)
    )
    if not all(
        len(values) == len(routes)
        for values in (
            pullback_materials,
            end_pullback_materials,
            pullback_attachment_ids,
            end_pullback_attachment_ids,
        )
    ):
        raise ValueError("Every cable-group route requires complete pullback endpoint data.")
    pullback_diameters_mm = route_pullback_diameters_mm or tuple(
        diameter * 0.75 for diameter in diameters
    )
    end_pullback_diameters_mm = route_end_pullback_diameters_mm or tuple(
        diameter * 0.75 for diameter in diameters
    )
    if (
        len(pullback_diameters_mm) != len(routes)
        or len(end_pullback_diameters_mm) != len(routes)
        or any(
            isinstance(pullback_diameter, bool)
            or not isinstance(pullback_diameter, (int, float))
            or not math.isfinite(pullback_diameter)
            or pullback_diameter < 0.0
            or pullback_diameter > diameter
            or (distance > 0.0 and pullback_diameter <= 0.0)
            for pullback_diameter, diameter, distance in (
                *zip(pullback_diameters_mm, diameters, pullbacks_mm),
                *zip(end_pullback_diameters_mm, diameters, end_pullbacks_mm),
            )
        )
    ):
        raise ValueError(
            "Active pullback diameters must be positive and no larger than their routes."
        )
    main_route_indices = tuple(
        index for index in range(len(routes)) if index not in connection_branch_indices
    )
    main_routes = tuple(routes[index] for index in main_route_indices)
    construction_segments, _start_junctions, _end_junctions = prepare_group_sweep_segments(
        main_routes
    )
    local_routes = tuple(route_in_component_space(route, transform) for route in routes)
    bodies: list[adsk.fusion.BRepBody] = []
    leg_lengths = [0.0] * len(routes)
    branch_body_layout: dict[int, tuple[int, int, float]] = {}
    branch_insulation_routes: dict[int, RoutePreview] = {}
    main_insulation_body_count = 0
    main_pullbacks: list[
        tuple[RoutePreview, int, Optional[UUID], CableMaterialSettings, float, float, str, float]
    ] = []
    for segment in construction_segments:
        route_index = main_route_indices[segment.source_route_index]
        source_route = routes[route_index]
        route = segment.route
        start_options = _route_endpoint_pullback_options(
            route.curves[0].start,
            source_route,
            pullbacks_mm[route_index],
            end_pullbacks_mm[route_index],
            pullback_materials[route_index],
            end_pullback_materials[route_index],
            pullback_attachment_ids[route_index],
            end_pullback_attachment_ids[route_index],
            pullback_diameters_mm[route_index],
            end_pullback_diameters_mm[route_index],
        )
        end_options = _route_endpoint_pullback_options(
            route.curves[-1].end,
            source_route,
            pullbacks_mm[route_index],
            end_pullbacks_mm[route_index],
            pullback_materials[route_index],
            end_pullback_materials[route_index],
            pullback_attachment_ids[route_index],
            end_pullback_attachment_ids[route_index],
            pullback_diameters_mm[route_index],
            end_pullback_diameters_mm[route_index],
        )
        split = split_route_endpoint_pullbacks(
            route,
            start_options[0] if output_mode == FINALIZED_OUTPUT_MODE else 0.0,
            end_options[0] if output_mode == FINALIZED_OUTPUT_MODE else 0.0,
        )
        leg_number = route_index + 1
        if split.insulation is not None:
            section_name = (
                f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Diameter"
            )
            body, length_mm = _build_route_sweep(
                component,
                split.insulation,
                diameters[route_index],
                transform,
                f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Centerline",
                section_name,
                f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Sweep",
            )
            body.name = f"Cable Group {group_index + 1} Leg {leg_number}"
            if segment.segment_count > 1:
                body.name += f" Segment {segment.segment_index + 1}"
            bodies.append(body)
            body.appearance = cable_appearance(
                design,
                materials_by_route[route_index].main_color,
                materials_by_route[route_index].appearance,
            )
            leg_lengths[route_index] += length_mm
            main_insulation_body_count += 1
        for pullback_route, options, applied_length in (
            (split.start_pullback, start_options, split.start_length_mm),
            (split.end_pullback, end_options, split.end_length_mm),
        ):
            pullback_material = options[1]
            if pullback_route is None or pullback_material is None:
                continue
            main_pullbacks.append(
                (
                    pullback_route,
                    route_index,
                    options[2],
                    pullback_material,
                    float(applied_length),
                    float(options[0]),
                    (
                        "start"
                        if source_route.curves[0].start
                        in (pullback_route.curves[0].start, pullback_route.curves[-1].end)
                        else "end"
                    ),
                    float(options[3]),
                )
            )
    applied_main_pullbacks: dict[int, dict[str, float]] = {}
    for (
        _pullback_route,
        route_index,
        _attachment_id,
        _pullback_material,
        applied_length,
        _requested_length,
        boundary,
        _pullback_diameter_mm,
    ) in main_pullbacks:
        applied_main_pullbacks.setdefault(route_index, {})[boundary] = applied_length
    main_insulation_routes: list[RoutePreview] = []
    for index in main_route_indices:
        applied = applied_main_pullbacks.get(index, {})
        insulation = split_route_endpoint_pullbacks(
            routes[index],
            applied.get("start", 0.0),
            applied.get("end", 0.0),
        ).insulation
        if insulation is not None:
            main_insulation_routes.append(route_in_component_space(insulation, transform))
    main_pullback_metadata: list[dict[str, object]] = []
    for pullback_number, (
        pullback_route,
        route_index,
        attachment_id,
        pullback_material,
        applied_length,
        requested_length,
        boundary,
        pullback_diameter_mm,
    ) in enumerate(main_pullbacks, start=1):
        body, length_mm = _build_route_sweep(
            component,
            pullback_route,
            pullback_diameter_mm,
            transform,
            f"Cable Group Pullback {pullback_number} Centerline",
            f"Cable Group Pullback {pullback_number} Diameter",
            f"Cable Group Pullback {pullback_number} Sweep",
        )
        body.name = f"Cable Group {group_index + 1} Pullback {pullback_number}"
        bodies.append(body)
        body.appearance = cable_appearance(
            design,
            pullback_material.pullback.color,
            pullback_material.pullback.appearance,
        )
        leg_lengths[route_index] += length_mm
        main_pullback_metadata.append(
            {
                "attachment_id": _optional_uuid_text(attachment_id),
                "route_id": str(routes[route_index].cable_id),
                "length_mm": applied_length,
                "requested_mm": requested_length,
                "boundary": boundary,
                "diameter_mm": pullback_diameter_mm,
            }
        )
    for route_index in sorted(connection_branch_indices):
        branch_number = route_index + 1
        split = split_route_for_pullback(
            routes[route_index],
            pullbacks_mm[route_index] if output_mode == FINALIZED_OUTPUT_MODE else 0.0,
        )
        branch_materials = materials_by_route[route_index]
        insulation_body_count = 0
        pullback_body_count = 0
        if split.insulation is not None:
            body, length_mm = _build_route_sweep(
                component,
                split.insulation,
                diameters[route_index],
                transform,
                f"Cable Connection Branch {branch_number} Centerline",
                f"Cable Connection Branch {branch_number} Diameter",
                f"Cable Connection Branch {branch_number} Sweep",
            )
            body.name = f"Cable Group {group_index + 1} Connection Branch {branch_number}"
            bodies.append(body)
            body.appearance = cable_appearance(
                design,
                branch_materials.main_color,
                branch_materials.appearance,
            )
            leg_lengths[route_index] += length_mm
            insulation_body_count = 1
            branch_insulation_routes[route_index] = route_in_component_space(
                split.insulation, transform
            )
        if split.pullback is not None:
            body, length_mm = _build_route_sweep(
                component,
                split.pullback,
                pullback_diameters_mm[route_index],
                transform,
                f"Cable Connection Branch {branch_number} Pullback Centerline",
                f"Cable Connection Branch {branch_number} Pullback Diameter",
                f"Cable Connection Branch {branch_number} Pullback Sweep",
            )
            body.name = f"Cable Group {group_index + 1} Connection Branch {branch_number} Pullback"
            bodies.append(body)
            body.appearance = cable_appearance(
                design,
                branch_materials.pullback.color,
                branch_materials.pullback.appearance,
            )
            leg_lengths[route_index] += length_mm
            pullback_body_count = 1
        branch_body_layout[route_index] = (
            insulation_body_count,
            pullback_body_count,
            split.pullback_length_mm,
        )
    expected_body_count = (
        main_insulation_body_count
        + len(main_pullbacks)
        + sum(
            insulation_count + pullback_count
            for insulation_count, pullback_count, _length_mm in branch_body_layout.values()
        )
    )
    if component.bRepBodies.count != expected_body_count:
        raise RuntimeError("Fusion did not retain one solid body per cable-group segment.")
    total_length_mm = sum(leg_lengths)
    component.name = f"Cable Group {group_index + 1}_{total_length_mm:.2f}mm"
    metadata = json.dumps(
        {
            "harness_id": str(harness_id),
            "cable_group_id": str(group.cable_group_id),
            GENERATED_OUTPUT_MODE_KEY: output_mode,
            "diameter_mm": group.diameter_mm,
            "length_mm": total_length_mm,
            "route_legs": [
                {
                    "route_id": str(route.cable_id),
                    "label": route.cable_number,
                    "length_mm": length_mm,
                    "route_curves_mm": route_metadata(route),
                }
                for index, (route, length_mm) in enumerate(zip(local_routes, leg_lengths))
                if index not in connection_branch_indices
            ],
            "connection_branches": [
                {
                    "route_id": str(local_routes[index].cable_id),
                    "label": local_routes[index].cable_number,
                    "diameter_mm": diameters[index],
                    "attachment_id": _optional_uuid_text(attachment_ids[index]),
                    "length_mm": leg_lengths[index],
                    "pullback_mm": branch_body_layout[index][2],
                    "pullback_requested_mm": (
                        pullbacks_mm[index] if output_mode == FINALIZED_OUTPUT_MODE else 0.0
                    ),
                    "pullback_diameter_mm": pullback_diameters_mm[index],
                    "insulation_body_count": branch_body_layout[index][0],
                    "pullback_body_count": branch_body_layout[index][1],
                    "route_curves_mm": route_metadata(local_routes[index]),
                }
                for index in sorted(connection_branch_indices)
            ],
            "main_insulation_body_count": main_insulation_body_count,
            "main_pullbacks": main_pullback_metadata,
            **material_metadata(materials),
        },
        sort_keys=True,
    )
    if (
        component.attributes.add(
            ATTRIBUTE_GROUP,
            GENERATED_CABLE_GROUP_ATTRIBUTE,
            metadata,
        )
        is None
    ):
        raise RuntimeError("Fusion could not store the generated cable-group identity.")
    if output_mode == FINALIZED_OUTPUT_MODE:
        clear_group_stripe_graphics(stripe_graphics_owner, group.cable_group_id)
        replace_group_stripe_bodies(
            component,
            tuple(main_insulation_routes),
            materials.stripes,
            group.diameter_mm / 2.0,
            design,
            branch_decorations=tuple(
                (
                    branch_insulation_routes[index],
                    materials_by_route[index].stripes,
                    diameters[index] / 2.0,
                )
                for index in sorted(connection_branch_indices)
                if index in branch_insulation_routes
            ),
        )
    else:
        replace_group_stripe_graphics(
            stripe_graphics_owner,
            tuple(local_routes[index] for index in main_route_indices),
            materials.stripes,
            group.diameter_mm / 2.0,
            group.cable_group_id,
            is_visible=is_visible,
            branch_decorations=tuple(
                (
                    local_routes[index],
                    materials_by_route[index].stripes,
                    diameters[index] / 2.0,
                )
                for index in sorted(connection_branch_indices)
            ),
        )


def _build_route_sweep(
    component: adsk.fusion.Component,
    route: RoutePreview,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
    centerline_name: str,
    section_name: str,
    sweep_name: str,
) -> tuple[adsk.fusion.BRepBody, float]:
    """
    Create one route sweep from a path-normal circular profile.
    """
    if not route.curves:
        raise ValueError("The smooth route contains no curves.")
    stage = "create centerline sketch"
    try:
        sketch = component.sketches.add(component.xYConstructionPlane)
        if sketch is None:
            raise RuntimeError("Fusion did not create the cable centerline sketch.")
        sketch.name = centerline_name
        curves = adsk.core.ObjectCollection.create()
        length_mm = 0.0
        for index, curve in enumerate(route.curves):
            stage = f"create centerline segment {index + 1}"
            points = [
                sketch.modelToSketchSpace(fusion_point(point, transform))
                for point in (curve.start, curve.control_a, curve.control_b, curve.end)
            ]
            if is_straight(curve):
                entity = sketch.sketchCurves.sketchLines.addByTwoPoints(points[0], points[3])
            else:
                entity = sketch.sketchCurves.sketchControlPointSplines.add(
                    points, adsk.fusion.SplineDegrees.SplineDegreeThree
                )
            if entity is None or not curves.add(entity):
                raise RuntimeError("Fusion could not create a cable centerline segment.")
            length_mm += entity.length * 10
        stage = "join centerline path"
        path = component.features.createPath(curves, False)
        if path is None:
            raise RuntimeError("Fusion could not join the ordered centerline segments.")
        stage = "define cross-section plane"
        plane_input = component.constructionPlanes.createInput()
        if not plane_input.setByDistanceOnPath(
            curves.item(0), adsk.core.ValueInput.createByReal(0)
        ):
            raise RuntimeError("Fusion could not orient the cable cross-section.")
        stage = "create cross-section plane"
        plane = component.constructionPlanes.add(plane_input)
        if plane is None:
            raise RuntimeError("Fusion did not create the cable cross-section plane.")
        plane.name = section_name
        stage = "create diameter sketch"
        section = component.sketches.add(plane)
        if section is None:
            raise RuntimeError("Fusion did not create the cable cross-section sketch.")
        section.name = section_name
        center = section.modelToSketchSpace(fusion_point(route.curves[0].start, transform))
        circle = section.sketchCurves.sketchCircles.addByCenterRadius(center, diameter_mm / 20)
        if circle is None or section.profiles.count != 1:
            raise RuntimeError("Fusion could not create one circular sweep profile.")
        sweep_profile = section.profiles.item(0)
        if sweep_profile is None:
            raise RuntimeError("Fusion did not retain the circular sweep profile.")
        sweeps = component.features.sweepFeatures
        stage = "define sweep"
        sweep_input = sweeps.createInput(
            sweep_profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        stage = "create solid sweep"
        sweep = sweeps.add(sweep_input)
        if sweep is None or sweep.bodies.count != 1:
            raise RuntimeError("Fusion did not produce one cable solid.")
        body = sweep.bodies.item(0)
        if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Fusion produced an invalid or empty cable solid.")
        sweep.name = sweep_name
        sketch.isLightBulbOn = False
        section.isLightBulbOn = False
        plane.isLightBulbOn = False
        return body, length_mm
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        if stage == "create solid sweep":
            bend = tightest_bend(route)
            if bend is not None:
                diagnostic = (
                    f"tightest sampled bend radius {bend.radius_mm:.3f} mm on centerline "
                    f"curve {bend.curve_index + 1} at t={bend.parameter:.3f}; "
                    f"cable radius {diameter_mm / 2:.3f} mm"
                )
                raise RuntimeError(f"{stage}: {error}; route diagnostic: {diagnostic}") from error
        raise RuntimeError(f"{stage}: {error}") from error
