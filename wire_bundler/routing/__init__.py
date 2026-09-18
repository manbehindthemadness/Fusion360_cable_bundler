"""
Host-independent routing geometry and parallel-wire solvers.
"""

from .avoidance import RouteCollision, route_collisions, separate_route_collisions
from .geometry import CubicBezier
from .parallel import (
    GateCapacityError,
    GateFrame,
    RefineFrame,
    RoutePreview,
    Vector3,
    WireRouteInput,
    place_route_crossings,
    solve_parallel_routes,
)
from .smooth import (
    CIRCULAR_SWEEP_BEND_FACTOR,
    BendRadius,
    TransitionAdjustment,
    TransitionLengths,
    TransitionLimits,
    fair_route,
    minimum_circular_bend_radius,
    sample_centerline,
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
    "GateFrame",
    "RefineFrame",
    "RoutePreview",
    "RouteCollision",
    "StripeContinuation",
    "StripeMeshResult",
    "Vector3",
    "WireRouteInput",
    "place_route_crossings",
    "build_continuous_stripe_mesh",
    "build_stripe_mesh",
    "solve_parallel_routes",
    "route_collisions",
    "separate_route_collisions",
    "TransitionLengths",
    "TransitionAdjustment",
    "TransitionLimits",
    "fair_route",
    "minimum_circular_bend_radius",
    "sample_centerline",
    "tightest_bend",
    "transition_limits",
]
