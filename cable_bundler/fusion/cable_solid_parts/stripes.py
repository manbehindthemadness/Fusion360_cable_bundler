"""Create and replace Custom Graphics stripe decorations for generated cables."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import (
    CableStripe,
)
from ...routing import (
    RoutePreview,
    StripeContinuation,
    StripeMeshResult,
    build_continuous_stripe_mesh,
)
from .constants import GENERATED_STRIPE_GROUP_ID
from .materials import cable_appearance
from .sweep_geometry import RouteSweepSegment, prepare_group_sweep_segments


def generated_stripe_graphics_groups(
    graphics_owner: adsk.fusion.Component,
) -> tuple[adsk.fusion.CustomGraphicsGroup, ...]:
    """
    Return every current or legacy stripe group owned by one component.
    """
    groups = graphics_owner.customGraphicsGroups
    return tuple(
        group
        for group_index in range(groups.count)
        if (group := groups.item(group_index)) is not None
        and (
            group.id == GENERATED_STRIPE_GROUP_ID
            or group.id.startswith(f"{GENERATED_STRIPE_GROUP_ID}:")
            or group.name.endswith(" Solid Stripes")
        )
    )


def _delete_stripe_graphics_group(group: adsk.fusion.CustomGraphicsGroup) -> None:
    """
    Delete one stripe group and all children with checked Fusion results.
    """
    for child_index in range(group.count - 1, -1, -1):
        child = group.item(child_index)
        if child is not None and child.deleteMe() is False:
            raise RuntimeError("Fusion could not delete an obsolete cable-group stripe.")
    if group.deleteMe() is False:
        raise RuntimeError("Fusion could not delete obsolete cable-group stripe graphics.")


def clear_group_stripe_graphics(
    graphics_owner: adsk.fusion.Component,
    cable_group_id: UUID,
    *,
    include_legacy: bool = False,
) -> None:
    """
    Delete the stable overlay for one group and optional child-owned legacy data.
    """
    target_id = f"{GENERATED_STRIPE_GROUP_ID}:{cable_group_id}"
    for group in reversed(generated_stripe_graphics_groups(graphics_owner)):
        if group.id != target_id and not include_legacy:
            continue
        _delete_stripe_graphics_group(group)


def clear_all_stripe_graphics(graphics_owner: adsk.fusion.Component) -> None:
    """
    Delete every managed stripe overlay from a harness component.
    """
    for group in reversed(generated_stripe_graphics_groups(graphics_owner)):
        _delete_stripe_graphics_group(group)


def replace_group_stripe_graphics(
    graphics_owner: adsk.fusion.Component,
    routes: tuple[RoutePreview, ...],
    stripes: tuple[CableStripe, ...],
    cable_radius_mm: float,
    cable_group_id: UUID,
    *,
    is_visible: bool = True,
) -> int:
    """
    Replace all leg-owned stripe meshes for one multi-body cable group.
    """
    clear_group_stripe_graphics(graphics_owner, cable_group_id)
    groups = graphics_owner.customGraphicsGroups
    if not stripes:
        return 0
    group = groups.add()
    if group is None:
        raise RuntimeError("Fusion did not create stripe graphics for a cable group.")
    group.id = f"{GENERATED_STRIPE_GROUP_ID}:{cable_group_id}"
    group.name = "Cable Group Solid Stripes"
    group.isVisible = is_visible
    segments, start_junctions, end_junctions = prepare_group_sweep_segments(routes)
    created = 0
    for stripe_index, stripe in enumerate(stripes):
        decorated_segments = build_continuous_segment_stripes(
            segments,
            start_junctions,
            end_junctions,
            stripe,
            cable_radius_mm,
        )
        for segment, result in decorated_segments:
            if not result.vertices or not result.triangle_indices:
                continue
            coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
                [
                    coordinate / 10.0
                    for point in result.vertices
                    for coordinate in (point.x, point.y, point.z)
                ]
            )
            if coordinates is None:
                raise RuntimeError("Fusion did not create cable-group stripe coordinates.")
            stripe_mesh = group.addMesh(coordinates, list(result.triangle_indices), [], [])
            if stripe_mesh is None:
                raise RuntimeError("Fusion did not draw a cable-group stripe.")
            stripe_mesh.name = (
                f"Cable Group Leg {segment.source_route_index + 1}"
                + (f" Segment {segment.segment_index + 1}" if segment.segment_count > 1 else "")
                + f" Stripe {stripe_index + 1}"
            )
            stripe_mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
            stripe_color = adsk.core.Color.create(
                stripe.color.red,
                stripe.color.green,
                stripe.color.blue,
                255,
            )
            stripe_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(stripe_color)
            if stripe_effect is None:
                raise RuntimeError("Fusion did not create a cable-group stripe color.")
            stripe_mesh.color = stripe_effect
            created += 1
    return created


def replace_group_stripe_bodies(
    component: adsk.fusion.Component,
    routes: tuple[RoutePreview, ...],
    stripes: tuple[CableStripe, ...],
    cable_radius_mm: float,
    design: adsk.fusion.Design,
) -> int:
    """
    Replace transient stripe presentation with persistent renderable mesh bodies.

    Stripe coordinates are authored in millimeters while Fusion mesh-body input
    uses the design's internal centimeter units.
    """
    mesh_bodies = component.meshBodies
    for body_index in range(mesh_bodies.count - 1, -1, -1):
        body = mesh_bodies.item(body_index)
        if body is not None and body.deleteMe() is False:
            raise RuntimeError("Fusion could not delete an obsolete cable stripe body.")
    if not stripes:
        return 0
    segments, start_junctions, end_junctions = prepare_group_sweep_segments(routes)
    created = 0
    for stripe_index, stripe in enumerate(stripes):
        appearance = cable_appearance(design, stripe.color)
        decorated_segments = build_continuous_segment_stripes(
            segments,
            start_junctions,
            end_junctions,
            stripe,
            cable_radius_mm,
        )
        for segment, result in decorated_segments:
            if not result.vertices or not result.triangle_indices:
                continue
            coordinates = [
                coordinate / 10.0
                for point in result.vertices
                for coordinate in (point.x, point.y, point.z)
            ]
            body = mesh_bodies.addByTriangleMeshData(
                coordinates,
                list(result.triangle_indices),
                [],
                [],
            )
            if body is None:
                raise RuntimeError("Fusion did not create a renderable cable stripe body.")
            body.name = (
                f"Cable Group Leg {segment.source_route_index + 1}"
                + (f" Segment {segment.segment_index + 1}" if segment.segment_count > 1 else "")
                + f" Stripe {stripe_index + 1}"
            )
            body.appearance = appearance
            created += 1
    return created


def build_continuous_segment_stripes(
    segments: tuple[RouteSweepSegment, ...],
    start_junctions: tuple[Optional[int], ...],
    end_junctions: tuple[Optional[int], ...],
    stripe: CableStripe,
    cable_radius_mm: float,
) -> tuple[tuple[RouteSweepSegment, StripeMeshResult], ...]:
    """
    Propagate one stripe's boundary state through an oriented segment tree.
    """
    if not (len(segments) == len(start_junctions) == len(end_junctions)):
        raise RuntimeError("Cable-group stripe topology is inconsistent.")
    roots = {
        junction
        for junction in start_junctions
        if junction is not None and junction not in end_junctions
    }
    if len(segments) > 1 and len(roots) != 1:
        raise RuntimeError("Cable-group stripe segments do not have one root junction.")
    root_junction = next(iter(roots), None)
    junction_states: dict[int, StripeContinuation] = {}
    decorated: list[tuple[RouteSweepSegment, StripeMeshResult]] = []
    pending = list(range(len(segments)))
    while pending:
        progressed = False
        for segment_index in pending:
            start_junction = start_junctions[segment_index]
            if (
                start_junction is not None
                and start_junction != root_junction
                and start_junction not in junction_states
            ):
                continue
            continuation = None if start_junction is None else junction_states.get(start_junction)
            result = build_continuous_stripe_mesh(
                segments[segment_index].route,
                stripe,
                cable_radius_mm,
                continuation,
            )
            if result.start is None or result.end is None:
                raise RuntimeError("Cable-group stripe segment has no continuation state.")
            if start_junction is not None:
                junction_states.setdefault(start_junction, result.start)
            end_junction = end_junctions[segment_index]
            if end_junction is not None:
                junction_states[end_junction] = result.end
            decorated.append((segments[segment_index], result))
            pending.remove(segment_index)
            progressed = True
            break
        if not progressed:
            raise RuntimeError("Cable-group stripe segments do not form one connected tree.")
    return tuple(decorated)
