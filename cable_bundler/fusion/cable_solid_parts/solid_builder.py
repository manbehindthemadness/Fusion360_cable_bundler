"""Build persistent Fusion sweep bodies for one routed cable group."""

from __future__ import annotations

import json
import math
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
from .sweep_geometry import is_straight, prepare_group_sweep_segments


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
) -> None:
    """
    Sweep every deterministic group leg from its own path-normal profile.
    """
    if not routes:
        raise ValueError("A cable group requires at least one routed leg.")
    if output_mode not in {SOLID_OUTPUT_MODE, FINALIZED_OUTPUT_MODE}:
        raise ValueError(f"Unsupported cable output mode: {output_mode}")
    construction_segments, _start_junctions, _end_junctions = prepare_group_sweep_segments(routes)
    local_routes = tuple(route_in_component_space(route, transform) for route in routes)
    bodies: list[adsk.fusion.BRepBody] = []
    leg_lengths = [0.0] * len(routes)
    for segment in construction_segments:
        route = segment.route
        leg_number = segment.source_route_index + 1
        section_name = f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Diameter"
        body, length_mm = _build_route_sweep(
            component,
            route,
            group.diameter_mm,
            transform,
            f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Centerline",
            section_name,
            f"Cable Group Leg {leg_number} Segment {segment.segment_index + 1} Sweep",
        )
        body.name = f"Cable Group {group_index + 1} Leg {leg_number}"
        if segment.segment_count > 1:
            body.name += f" Segment {segment.segment_index + 1}"
        bodies.append(body)
        leg_lengths[segment.source_route_index] += length_mm
    if component.bRepBodies.count != len(construction_segments):
        raise RuntimeError("Fusion did not retain one solid body per cable-group segment.")
    total_length_mm = sum(leg_lengths)
    component.name = f"Cable Group {group_index + 1}_{total_length_mm:.2f}mm"
    appearance = cable_appearance(design, materials.main_color, materials.appearance)
    for body in bodies:
        body.appearance = appearance
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
                for route, length_mm in zip(local_routes, leg_lengths)
            ],
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
            local_routes,
            materials.stripes,
            group.diameter_mm / 2.0,
            design,
        )
    else:
        replace_group_stripe_graphics(
            stripe_graphics_owner,
            local_routes,
            materials.stripes,
            group.diameter_mm / 2.0,
            group.cable_group_id,
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
