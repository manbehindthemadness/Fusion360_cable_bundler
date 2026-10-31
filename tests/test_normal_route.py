"""
Check continuous polynomial certificates and shared-profile endpoint construction.
"""

from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.polynomial_certificate import certify_curvature
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_normal_route.solver import solve

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


@pytest.mark.parametrize("maximum,status", [(Fraction(3), "certified"), (Fraction(1), "violated")])
def test_parabola_curvature_certificate(maximum: Fraction, status: str) -> None:
    """
    Bound the exact parabola (u,u²,0), whose maximum curvature is two.
    """
    points = (Vector3(0, 0, 0), Vector3(0.5, 0, 0), Vector3(1, 1, 0))
    result = certify_curvature(points, maximum)
    assert result.status == status


def test_interior_violation_and_budget_never_pass() -> None:
    """
    Reject a hidden interior peak even though both endpoint curvatures are small.
    """
    points = (Vector3(-1, 1, 0), Vector3(0, -1, 0), Vector3(1, 1, 0))
    assert certify_curvature(points, Fraction(1)).status == "violated"
    for maximum_nodes in (1, 2):
        bounded = certify_curvature(points, Fraction(3), maximum_nodes=maximum_nodes)
        assert bounded.status == "unresolved"
        assert bounded.nodes <= maximum_nodes


def test_straight_needs_no_frenet_frame_and_singular_speed_rejects() -> None:
    """
    Allow zero curvature for a constant frame while refusing stationary motion.
    """
    points = (Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(2, 0, 0))
    assert certify_curvature(points, Fraction(1), require_frame=False).status == "certified"
    assert certify_curvature(points, Fraction(1)).condition == "frame"
    stationary = (Vector3(0, 0, 0),) * 3
    assert certify_curvature(stationary, Fraction(1), require_frame=False).condition == "speed"


def test_straight_endpoint_control_stays_straight() -> None:
    """
    Preserve fixed endpoints and profile order without inserting a gratuitous loop.
    """
    case = EndpointCase("straight", Vector3(0, 0, 0), Vector3(60, 0, 0), X, X, Y, Y, 3)
    result = solve(case)
    assert result.status == "certified"
    assert len(result.probes) == 1
    assert result.route is not None
    for i in range(9):
        point, velocity, width, rate = result.route.frame(i / 8)
        assert point.x == pytest.approx(60 * i / 8)
        assert point.y == point.z == 0
        assert width == Y and rate == Vector3(0, 0, 0)
        assert dot(velocity, X) > 0


def test_spatial_shared_guides_keep_poses_and_have_correct_derivatives() -> None:
    """
    Check fixed cap frames, constant width and analytic offset-guide velocities.
    """
    case = EndpointCase("roll", Vector3(0, 0, 0), Vector3(45, 12, 8), X, X, Y, Z, 3)
    result = solve(case, maximum_probes=3)
    assert result.status == "length_incompatible"
    assert result.certificate is not None and result.certificate.status == "certified"
    route = result.route
    assert route is not None
    for u, point, tangent, width in ((0, case.start, X, Y), (1, case.end, X, Z)):
        p, v, w, rate = route.frame(u)
        assert magnitude(difference(p, point)) < 1e-10
        assert magnitude(difference(unit(v), tangent)) < 1e-10
        assert magnitude(difference(w, width)) < 1e-10
        assert magnitude(rate) < 1e-9
    for u in (0.13, 0.41, 0.79):
        p, v, w, _ = route.frame(u)
        assert abs(dot(w, v)) < 1e-10
        assert abs(dot(w, cross(cross(v, route.curve.jet(u)[2]), v))) < 1e-8
        a, av = route.lane(u, route.half_width_mm)
        b, _ = route.lane(u, -route.half_width_mm)
        assert magnitude(difference(a, b)) == pytest.approx(2 * route.half_width_mm)
        before, _ = route.lane(u - 1e-6, route.half_width_mm)
        after, _ = route.lane(u + 1e-6, route.half_width_mm)
        fd = difference(after, before)
        assert magnitude(difference(Vector3(fd.x / 2e-6, fd.y / 2e-6, fd.z / 2e-6), av)) < 1e-5


def test_coincident_targets_are_unimplemented_not_moved() -> None:
    """
    Expose unsupported input rather than inventing a different connection target.
    """
    case = EndpointCase("same", Vector3(0, 0, 0), Vector3(0, 0, 0), X, X, Y, Y, 1)
    with pytest.raises(ValueError, match="Coincident"):
        solve(case)
