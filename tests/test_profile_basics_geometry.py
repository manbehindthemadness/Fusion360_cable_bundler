"""
Verify authored calibration geometry without counting it as an endpoint-routing solve.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_profile_basics.geometry import (
    Arc,
    Helix,
    ReferenceCurve,
    Straight,
    compound_s,
)


def test_compound_s_keeps_shared_positions_and_tangents_then_turns_laterally() -> None:
    """
    The authored circular fixture has two opposite planar turns and one lateral turn.
    """
    arcs = compound_s(2.0)
    for left, right in zip(arcs, arcs[1:]):
        p, t, _ = left.jet(1)
        q, v, _ = right.jet(0)
        assert magnitude(difference(p, q)) < 1e-12
        assert magnitude(difference(unit(t), unit(v))) < 1e-12
    assert magnitude(difference(arcs[-1].jet(1)[0], Vector3(6.0, 4.0, 2.0))) < 1e-12
    assert magnitude(difference(unit(arcs[-1].jet(1)[1]), Vector3(0, 0, 1))) < 1e-12
    assert dot(unit(arcs[0].jet(1)[2]), unit(arcs[1].jet(0)[2])) == pytest.approx(-1.0)


@pytest.mark.parametrize(
    "curve", (Straight(), Helix(1, 3), Arc(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), 2))
)
def test_reference_jet_matches_independent_position_differences(curve: ReferenceCurve) -> None:
    """
    Independent symmetric differences check analytical derivatives of each authored primitive.
    """
    u, step = 0.4, 1e-4
    center, velocity, acceleration = curve.jet(u)
    left = curve.jet(u - step)[0]
    right = curve.jet(u + step)[0]
    for axis in ("x", "y", "z"):
        assert (getattr(right, axis) - getattr(left, axis)) / (2 * step) == pytest.approx(
            getattr(velocity, axis), rel=1e-7, abs=1e-7
        )
        assert (
            getattr(right, axis) - 2 * getattr(center, axis) + getattr(left, axis)
        ) / step**2 == pytest.approx(getattr(acceleration, axis), rel=1e-5, abs=1e-5)


def test_arc_turns_exactly_ninety_degrees() -> None:
    """
    Preserve the requested primitive angle without numerical target fitting.
    """
    arc = Arc(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), 2, math.pi / 2)
    assert magnitude(difference(arc.jet(1)[0], Vector3(2, 2, 0))) < 1e-12
