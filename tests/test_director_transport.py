"""
Check material-frame transport using independent quadrature and pose invariance.

Only development fields are evaluated here;reserved validation fixtures stay
unexamined until the live method/source fingerprint freezes.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.coupled_motion import rotate
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField, development
from experiments.experiment_ribbon_cap_transition.director_transport import integrate


def _checkpoint() -> None:
    """
    Keep unit-level geometry independent of live host budgets.
    """


def _planar_oracle(field: DirectorField, u: float) -> Vector3:
    """
    Integrate exact planar angles with independent composite Simpson quadrature.
    """
    a, b, c, d = field.bending
    totals = [0.0, 0.0]
    count = 1024
    for i in range(count + 1):
        t = u * i / count
        angle = (
            a * t
            + b * math.sin(2 * math.pi * t) / (2 * math.pi)
            + c * (1 - math.cos(2 * math.pi * t)) / (2 * math.pi)
            + d * (1 - math.cos(4 * math.pi * t)) / (4 * math.pi)
        )
        weight = 1 if i in (0, count) else 4 if i % 2 else 2
        totals[0] += weight * math.cos(angle)
        totals[1] -= weight * math.sin(angle)
    scale = field.length_mm * u / (3 * count)
    return Vector3(totals[0] * scale, 0, totals[1] * scale)


@pytest.mark.parametrize("field", development()[:4], ids=lambda f: f.name)
def test_planar_fields_match_independent_angle_oracle(field: DirectorField) -> None:
    """
    Preserve straight/arc/return/reversal positions and permanent material width.
    """
    path = integrate(field, 256, _checkpoint)
    for u in (0.173, 0.5, 1.0):
        assert magnitude(difference(path.lane(u, 0)[0], _planar_oracle(field, u))) < 2e-6
        state, _ = path.pose(u)
        assert state[6:9] == pytest.approx((0, 1, 0), abs=1e-12)


@pytest.mark.parametrize("field", development()[4:], ids=lambda f: f.name)
def test_spatial_transport_converges_without_frame_repair(field: DirectorField) -> None:
    """
    Verify grid convergence,orthonormal directors and differentiated dense output.
    """
    coarse, fine = integrate(field, 128, _checkpoint), integrate(field, 256, _checkpoint)
    for u in (0.173, 0.499, 0.823, 1.0):
        state, _ = fine.pose(u)
        tangent, width = Vector3(*state[3:6]), Vector3(*state[6:9])
        assert abs(dot(tangent, tangent) - 1) < 1e-6
        assert abs(dot(width, width) - 1) < 1e-6
        assert abs(dot(tangent, width)) < 1e-6
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            assert magnitude(difference(coarse.lane(u, q)[0], fine.lane(u, q)[0])) < 1e-4
        if u < 1:
            q, step = field.half_width_mm, 1e-6
            delta = difference(fine.lane(u + step, q)[0], fine.lane(u - step, q)[0])
            numerical = Vector3(delta.x / (2 * step), delta.y / (2 * step), delta.z / (2 * step))
            assert magnitude(difference(numerical, fine.lane(u, q)[1])) < 1e-5


@pytest.mark.parametrize(
    "axis,angle",
    [(Vector3(0, 0, 1), 0.73), (Vector3(1, 0, 0), -1.2), (unit(Vector3(1, 2, 3)), math.pi)],
)
def test_rigid_pose_change_preserves_all_material_lanes(axis: Vector3, angle: float) -> None:
    """
    Compare an independently transported rotated pose with transformed outputs.
    """
    field = development()[5]
    offset = Vector3(7, -11, 13)
    t, w = rotate(Vector3(1, 0, 0), axis, angle), rotate(Vector3(0, 1, 0), axis, angle)
    initial = (offset.x, offset.y, offset.z, t.x, t.y, t.z, w.x, w.y, w.z)
    base = integrate(field, 128, _checkpoint)
    moved = integrate(field, 128, _checkpoint, initial=initial)
    for u in (0, 0.37, 1):
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            point, velocity = base.lane(u, q)
            expected = offset.translated(rotate(point, axis, angle), 1)
            actual, actual_velocity = moved.lane(u, q)
            assert magnitude(difference(actual, expected)) < 1e-10
            assert magnitude(difference(actual_velocity, rotate(velocity, axis, angle))) < 1e-9


@pytest.mark.parametrize("scale", [0.1, 2.5, 10.0])
def test_uniform_scaling_preserves_dimensionless_motion(scale: float) -> None:
    """
    Expose hidden unit/width constants without counting scaled copies as coverage.
    """
    field = development()[4]
    changed = replace(
        field, length_mm=field.length_mm * scale, diameter_mm=field.diameter_mm * scale
    )
    original = integrate(field, 128, _checkpoint)
    scaled = integrate(changed, 128, _checkpoint)
    for u in (0.1, 0.413, 1.0):
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            p, v = original.lane(u, q)
            actual, velocity = scaled.lane(u, q * scale)
            expected = Vector3(p.x * scale, p.y * scale, p.z * scale)
            expected_velocity = Vector3(v.x * scale, v.y * scale, v.z * scale)
            assert magnitude(difference(actual, expected)) < 1e-9 * max(1, scale)
            assert magnitude(difference(velocity, expected_velocity)) < 1e-8 * max(1, scale)


@pytest.mark.parametrize("steps", [True, 0, 129, 256.0])
def test_unregistered_grids_reject(steps: object) -> None:
    """
    Bound work before integration instead of accepting arbitrary refinement.
    """
    with pytest.raises(ValueError):
        integrate(development()[0], steps, _checkpoint)  # type: ignore[arg-type]


def test_malformed_directors_reject_without_normalizing() -> None:
    """
    Reject a nonorthogonal frame rather than silently repairing user geometry.
    """
    with pytest.raises(ValueError, match="perpendicular"):
        integrate(development()[0], 64, _checkpoint, initial=(0, 0, 0, 1, 0, 0, 1, 0, 0))
