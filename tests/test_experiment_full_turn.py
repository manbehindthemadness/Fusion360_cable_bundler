"""
Protect prescribed winding and unchanged bank defaults without whole-ribbon solves.
"""

from __future__ import annotations

import math
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, dot, magnitude, unit
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_cap_transition.fixtures import (
    close_full_turn_case,
    full_turn_case,
    reversal_case,
)
from experiments.experiment_ribbon_cap_transition.full_turn import FullTurnDiagnostic
from experiments.experiment_ribbon_cap_transition.master_frames import master_scaffold, sampled_roll


def test_full_turn_fixture_retains_u_turn_geometry_and_returns_endpoint_roll() -> None:
    """
    Change only the declared endpoint roll/identity, not material, route or sphere.
    """
    parent, case = reversal_case(), full_turn_case()
    assert case.route.curves == parent.route.curves
    assert case.lines == parent.lines and case.diameter_mm == parent.diameter_mm
    assert case.end_boundary == parent.end_boundary
    assert case.end_width == case.start_width == Vector3(0, 1, 0)
    assert case.name != parent.name


def test_close_fixture_changes_gap_without_changing_material_sphere_or_directions() -> None:
    """
    Freeze the new R20 route while preserving full-turn boundary orientations.
    """
    parent, case = full_turn_case(), close_full_turn_case()
    curves = case.route.curves
    assert magnitude(difference(curves[0].start, Vector3(0, 0, -20))) <= 1e-12
    assert magnitude(difference(curves[-1].end, Vector3(0, 0, 20))) <= 1e-12
    assert case.lines == parent.lines and case.diameter_mm == parent.diameter_mm
    assert case.end_boundary == parent.end_boundary
    assert case.start_width == parent.start_width and case.end_width == parent.end_width
    assert case.name == "sphere4_reversal180_twist360_gap40"
    for curve, original, t in (
        (curves[0], parent.route.curves[0], 0),
        (curves[-1], parent.route.curves[-1], 1),
    ):
        assert dot(unit(curve.derivative(t)), unit(original.derivative(t))) == pytest.approx(1)


def test_prescription_retains_one_full_turn_on_nonuniform_distances() -> None:
    """
    Keep unwrapped winding and global distance easing rather than principal roll.
    """
    angles = FullTurnDiagnostic().angles((0, 1, 5, 9, 10), 0)
    assert angles[0] == 0 and angles[-1] == 2 * math.pi
    assert angles[2] == pytest.approx(math.pi)
    assert angles[1] == pytest.approx(2 * math.pi * (10 * 0.1**3 - 15 * 0.1**4 + 6 * 0.1**5))
    assert all(a < b for a, b in zip(angles, angles[1:]))


@pytest.mark.parametrize("distances", ((1, 2, 3), (0, 1, 1), (0, float("nan"), 2), (0, 1)))
def test_prescription_rejects_malformed_distance_coordinates(distances: tuple[float, ...]) -> None:
    """
    Refuse missing, nonfinite, repeated or nonzero-origin distance coordinates.
    """
    with pytest.raises(ValueError, match="distances"):
        FullTurnDiagnostic().angles(distances, 0)


def test_full_turn_refuses_a_half_twist_target_instead_of_adding_540_degrees() -> None:
    """
    Require a transported matching endpoint roll, not an arbitrary added revolution.
    """
    with pytest.raises(ValueError, match="endpoint width"):
        FullTurnDiagnostic().angles((0, 5, 10), math.pi)


def test_master_scaffold_default_zero_roll_is_unchanged_and_diagnostic_is_not_rate_pass() -> None:
    """
    Exercise a small straight scaffold, not a complete ribbon solve or native build.
    """
    curve = CubicBezier(Vector3(0, 0, 0), Vector3(10, 0, 0), Vector3(20, 0, 0), Vector3(30, 0, 0))
    route = RoutePreview(UUID(int=1), "unit full-turn scaffold", (curve.start, curve.end), (curve,))
    width = Vector3(0, 1, 0)
    ordinary = master_scaffold(route, width, width, 28.5)
    diagnostic = master_scaffold(route, width, width, 28.5, twist=FullTurnDiagnostic())
    assert all(angle == 0 for angle in ordinary.bank_angles_radians)
    assert diagnostic.bank_angles_radians[-1] == 2 * math.pi
    assert sampled_roll(ordinary.frames)["net_roll_degrees"] == 0
    assert sampled_roll(diagnostic.frames)["net_roll_degrees"] == pytest.approx(360)
    assert diagnostic.frames[0].width == diagnostic.frames[-1].width == width
    assert diagnostic.distances_mm == ordinary.distances_mm
    assert diagnostic.bank_rate_limit_radians_per_mm == ordinary.bank_rate_limit_radians_per_mm
    maximum_average = max(
        abs(b - a) / (s2 - s1)
        for a, b, s1, s2 in zip(
            diagnostic.bank_angles_radians,
            diagnostic.bank_angles_radians[1:],
            diagnostic.distances_mm,
            diagnostic.distances_mm[1:],
        )
    )
    assert maximum_average > diagnostic.bank_rate_limit_radians_per_mm
