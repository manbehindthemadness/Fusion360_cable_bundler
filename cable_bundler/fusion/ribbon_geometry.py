"""
Resolve open end guides into a banked frame shared by ribbon preview and output.
"""

from __future__ import annotations

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import HarnessDefinition
from ..routing import RibbonFrame, RoutePreview, ribbon_frames
from .route_preview_parts.frames import ProfileFrame, connection_profile_frames


def ribbon_route_frames(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    leg: CableGroupRouteLeg,
    route: RoutePreview,
    *,
    maximum_sections: int = 32,
) -> tuple[RibbonFrame, ...]:
    """
    Carry each end's curve direction through one two-ended discrete ribbon leg.
    """
    if leg.start_connection_id is None or leg.end_connection_id is None:
        raise ValueError("A discrete ribbon requires two physical open ends.")
    connections = {connection.connection_id: connection for connection in definition.connections}
    start = connections[leg.start_connection_id]
    end = connections[leg.end_connection_id]
    cache: dict[str, ProfileFrame] = {}
    start_width = connection_profile_frames(design, start, cache)[0].u_direction
    end_width = connection_profile_frames(design, end, cache)[0].u_direction
    return ribbon_frames(route, start_width, end_width, maximum_sections=maximum_sections)
