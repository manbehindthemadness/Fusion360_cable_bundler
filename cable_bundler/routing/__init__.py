"""
Host-independent routing geometry and parallel-cable solvers.
"""

from .avoidance import RouteCollision, route_collisions, separate_route_collisions
from .geometry import CubicBezier
from .parallel import (
    CableRouteInput,
    GateCapacityError,
    GateCapacityPolicy,
    GateFrame,
    RefineFrame,
    RoutePreview,
    Vector3,
    assign_route_crossings,
    place_route_crossings,
    solve_parallel_routes,
)
from .ribbon import RibbonFrame, ribbon_frames, ribbon_has_hard_axis_bend, ribbon_lane_points
from .smooth import (
    CIRCULAR_SWEEP_BEND_FACTOR,
    BendRadius,
    TransitionAdjustment,
    TransitionLengths,
    TransitionLimits,
    fair_route,
    minimum_circular_bend_radius,
    sample_centerline,
    straight_route,
    tightest_bend,
    transition_limits,
)
from .stripe_geometry import (
    StripeContinuation,
    StripeMeshResult,
    build_continuous_stripe_mesh,
    build_stripe_mesh,
)

__all__ = [
    "CubicBezier",
    "BendRadius",
    "CIRCULAR_SWEEP_BEND_FACTOR",
    "GateCapacityError",
    "GateCapacityPolicy",
    "GateFrame",
    "RefineFrame",
    "RoutePreview",
    "RibbonFrame",
    "RouteCollision",
    "StripeContinuation",
    "StripeMeshResult",
    "Vector3",
    "CableRouteInput",
    "assign_route_crossings",
    "place_route_crossings",
    "build_continuous_stripe_mesh",
    "build_stripe_mesh",
    "solve_parallel_routes",
    "route_collisions",
    "ribbon_frames",
    "ribbon_has_hard_axis_bend",
    "ribbon_lane_points",
    "separate_route_collisions",
    "TransitionLengths",
    "TransitionAdjustment",
    "TransitionLimits",
    "fair_route",
    "minimum_circular_bend_radius",
    "sample_centerline",
    "straight_route",
    "tightest_bend",
    "transition_limits",
]
