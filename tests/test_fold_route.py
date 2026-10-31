"""
Exercise algebraic pose closure and material compatibility of composed fold routes.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.material_lengths import measure_lengths
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.solver import connect


def _case(payload: dict[str, Any]) -> Targets:
    """
    Restore the five previously examined fixed endpoint inputs, without any paths.
    """
    return Targets(
        **{
            key: Vector3(**value) if isinstance(value, dict) else value
            for key, value in payload.items()
        }
    )


CASES = tuple(
    _case(item)
    for item in json.loads(
        Path(__file__).with_name("fixtures").joinpath("ribbon_fold_targets.json").read_text()
    )
)


def _check(route: FoldRoute) -> None:
    """
    Check all cap sides, shared-piece joins and local material differential identities.
    """
    case = route.targets
    half = route.half_width_mm
    for u, origin, tangent, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        for q in (-half, 0.0, half):
            point, velocity, across, _ = route.surface(u, q)
            assert magnitude(difference(point, origin.translated(width, q))) < 1e-8
            assert magnitude(difference(unit(velocity), tangent)) < 1e-8
            assert magnitude(difference(across, width)) < 1e-8
    for piece in route.pieces:
        length = piece.geometry.material_length_mm
        for q in (-half, -0.5 * half, 0.0, 0.5 * half, half):
            for u in (0.0, 0.13, 0.41, 0.79, 1.0):
                _, v, w, a = piece.surface(u, q)
                assert magnitude(v) == pytest.approx(length, rel=1e-12)
                assert magnitude(w) == pytest.approx(1.0, abs=1e-12)
                assert abs(dot(v, w)) / length < 1e-11
                assert abs(dot(a, w)) / length**2 < 1e-11
    for before, after in zip(route.pieces, route.pieces[1:]):
        for q in (-half, 0.0, half):
            p, v, w, _ = before.surface(1.0, q)
            point, velocity, across, _ = after.surface(0.0, q)
            assert magnitude(difference(p, point)) < 1e-8
            assert magnitude(difference(unit(v), unit(velocity))) < 1e-8
            assert magnitude(difference(w, across)) < 1e-8
    measured = measure_lengths(route, half, intervals=256)
    assert measured.lengths_mm == pytest.approx((route.material_length_mm,) * 3, rel=1e-12)
    assert measured.maximum_sampled_relative_speed_spread < 1e-11


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_fixed_targets_close_with_equal_material_paths(case: Targets) -> None:
    """
    Connect the same five development inputs using one unchanged direct construction.
    """
    route = connect(case)
    _check(route)
    assert route == connect(case)
    folds = [
        piece.geometry for piece in route.pieces if isinstance(piece.geometry, CylindricalFold)
    ]
    assert len(folds) <= 13
    assert all(case.diameter_mm / (2 * fold.radius_mm) < 0.996 for fold in folds)


def test_simple_inputs_do_not_receive_spatial_steering_loops() -> None:
    """
    Keep the straight control straight and use one tight bend for planar closure.
    """
    straight, quarter = connect(CASES[1]), connect(CASES[2])
    assert len(straight.pieces) == 1
    assert straight.material_length_mm == pytest.approx(60.0)
    assert len(quarter.pieces) == 3
    assert sum(isinstance(piece.geometry, CylindricalFold) for piece in quarter.pieces) == 1


def test_rotated_translated_input_carries_the_same_construction() -> None:
    """
    Preserve route identity under a rigid world-coordinate change.
    """
    case = CASES[0]

    def rotate(p: Vector3) -> Vector3:
        """
        Rotate90degrees about the world Z axis exactly in coordinates.
        """
        return Vector3(-p.y, p.x, p.z)

    shift = Vector3(100, -20, 7)
    moved = replace(
        case,
        start=rotate(case.start).translated(shift, 1),
        end=rotate(case.end).translated(shift, 1),
        start_tangent=rotate(case.start_tangent),
        end_tangent=rotate(case.end_tangent),
        start_width=rotate(case.start_width),
        end_width=rotate(case.end_width),
    )
    original, transformed = connect(case), connect(moved)
    _check(transformed)
    assert transformed.material_length_mm == pytest.approx(original.material_length_mm)
    for u in (0.0, 0.17, 0.53, 0.91, 1.0):
        for q in (-original.half_width_mm, 0.0, original.half_width_mm):
            expected = rotate(original.lane(u, q)[0]).translated(shift, 1)
            actual = transformed.lane(u, q)[0]
            assert magnitude(difference(actual, expected)) < 1e-8


def test_coincident_targets_do_not_trigger_an_invented_route() -> None:
    """
    Expose the omitted coincident-cap case instead of moving an endpoint.
    """
    case = replace(CASES[1], end=CASES[1].start)
    with pytest.raises(ValueError, match="Coincident"):
        connect(case)


@pytest.mark.parametrize(
    "tangent,width",
    [
        (Vector3(1, 0, 0), Vector3(0, -1, 0)),
        (Vector3(0.5, 0.5, -(2**-0.5)), Vector3(0.5, 0.5, 2**-0.5)),
        (Vector3(0, -1, 0), Vector3(-1, 0, 0)),
    ],
)
def test_half_turn_and_euler_pole_frames_close(tangent: Vector3, width: Vector3) -> None:
    """
    Resolve pure roll and proper-Euler poles without a longitudinal crease.
    """
    case = replace(CASES[1], end=Vector3(15, 8, -4), end_tangent=tangent, end_width=width)
    route = connect(case)
    _check(route)
    assert all(
        abs(piece.geometry.bank_radians) <= 0.786
        for piece in route.pieces
        if isinstance(piece.geometry, CylindricalFold)
    )


def test_negative_displacement_keeps_positive_material_progress() -> None:
    """
    Use rounded half-turns rather than negative-speed material for a backward target.
    """
    case = replace(CASES[1], end=Vector3(-10, 0, 0))
    route = connect(case)
    _check(route)
    assert len(route.pieces) == 3
    assert route.material_length_mm == pytest.approx(10 + 2 * 3.141592653589793 * route.radius_mm)


def test_nearly_parallel_planar_targets_do_not_divide_by_a_rounded_zero() -> None:
    """
    Resolve a tiny planar turn without subtracting nearly equal squared cosines.
    """
    angle = 1e-8
    case = replace(
        CASES[2], end=Vector3(20, 1e-7, 0), end_tangent=Vector3(math.cos(angle), math.sin(angle), 0)
    )
    route = connect(case)
    _check(route)
    assert len(route.pieces) == 3
