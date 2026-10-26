"""
Validate unit-rotation transport independently of endpoint-search outcomes.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.director_fields import DirectorField, development
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_transport import integrate


def _checkpoint() -> None:
    """
    Leave host-resource enforcement to live experiments.
    """


@pytest.mark.parametrize("angle", [-2.0, 0.0, math.pi])
def test_rotation_transport_matches_exact_circular_motion(angle: float) -> None:
    """
    Compare all terminal positions/directors with closed-form planar motion.
    """
    field = DirectorField("analytic_rotation", 90, (angle, 0, 0, 0), (0, 0, 0, 0))
    path = integrate_rotation(field, 256, _checkpoint)
    for u in (0.173, 0.5, 1.0):
        theta = angle * u
        expected = Vector3(
            90 * math.sin(theta) / angle if angle else 90 * u,
            0,
            90 * (math.cos(theta) - 1) / angle if angle else 0,
        )
        assert magnitude(difference(path.lane(u, 0)[0], expected)) < 1e-7
        state, _ = path.pose(u)
        assert (
            magnitude(
                difference(Vector3(*state[3:6]), Vector3(math.cos(theta), 0, -math.sin(theta)))
            )
            < 1e-8
        )


@pytest.mark.parametrize("field", development()[4:], ids=lambda f: f.name)
def test_structural_rotation_matches_independent_axis_transport(field: DirectorField) -> None:
    """
    Require grid convergence against a different integrator and unit node axes.
    """
    path = integrate_rotation(field, 256, _checkpoint)
    reference = integrate(field, 512, _checkpoint)
    for i in range(0, 257, 17):
        state = path.states[i]
        t, w = Vector3(*state[3:6]), Vector3(*state[6:9])
        assert abs(dot(t, t) - 1) < 2e-14
        assert abs(dot(w, w) - 1) < 2e-14
        assert abs(dot(t, w)) < 2e-14
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            assert (
                magnitude(difference(path.lane(i / 256, q)[0], reference.lane(i / 256, q)[0]))
                < 5e-6
            )
