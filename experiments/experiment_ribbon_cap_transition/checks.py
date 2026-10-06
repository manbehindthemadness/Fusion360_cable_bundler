"""
Audit finite complete-path samples without claiming native or continuous compliance.
"""

from __future__ import annotations

from cable_bundler.routing.geometry import cross, difference, magnitude
from experiments.experiment_ribbon_diagnosis.preflight import EndPlan
from experiments.experiment_secure_discrete_ribbon.shape import RibbonShape


def inspect_samples(shape: RibbonShape, plan: EndPlan) -> tuple[dict[str, object], list[str]]:
    """
    Check full guides, occupied samples and whole-lane three-point bend radii.

    Branch control hulls plus enclosing profile radius conservatively bound
    branch containment. Trunk containment and lane curvature remain sampled;
    these checks do not prove native loft skin or continuous final-lane behavior.
    """
    case = plan.case
    failures = []
    boundary = case.end_boundary
    radius = boundary.diameter_mm / 2
    guide_points = tuple(
        origin.translated(width, sign * case.lines * case.diameter_mm / 2)
        for origin, width in (
            (case.route.curves[0].start, case.start_width),
            (case.route.curves[-1].end, case.end_width),
        )
        for sign in (-1, 1)
    )
    guide_maximum = max(magnitude(difference(point, boundary.center)) for point in guide_points)
    occupied_maximum = max(
        magnitude(difference(point, boundary.center)) + case.diameter_mm / 2
        for lane in shape.lanes
        for point in lane
    )
    branch_maximum = max(
        magnitude(difference(point, boundary.center)) + case.diameter_mm
        for route in plan.routes.values()
        for curve in route.curves
        for point in (curve.start, curve.control_a, curve.control_b, curve.end)
    )
    if max(guide_maximum, occupied_maximum, branch_maximum) > radius + 1e-8:
        failures.append("occupied_sphere_containment")
    minimum = None
    for lane in shape.lanes:
        for a, b, c in zip(lane, lane[1:], lane[2:]):
            ab, bc, ac = difference(b, a), difference(c, b), difference(c, a)
            twice_area = magnitude(cross(ab, ac))
            if twice_area <= 1e-10:
                continue
            bend_radius = magnitude(ab) * magnitude(bc) * magnitude(ac) / (2 * twice_area)
            minimum = bend_radius if minimum is None else min(minimum, bend_radius)
    if minimum is not None and minimum < 3 * case.diameter_mm - 1e-6:
        failures.append("sampled_whole_lane_bend_radius")
    return {
        "sphere_diameter_widths": boundary.diameter_mm / (case.lines * case.diameter_mm),
        "sphere_radius_mm": radius,
        "full_guide_maximum_radius_mm": guide_maximum,
        "sampled_trunk_occupied_radius_mm": occupied_maximum,
        "branch_control_hull_occupied_radius_mm": branch_maximum,
        "sampled_whole_lane_minimum_radius_mm": minimum,
        "minimum_required_lane_radius_mm": 3 * case.diameter_mm,
        "scope": "Finite trunk samples; full guides and conservative branch control hulls. Native skin and continuous final-lane audit unmeasured.",
    }, failures
