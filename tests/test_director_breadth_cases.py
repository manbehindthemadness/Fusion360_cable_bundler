"""
Check fixture contracts without integrating or solving reserved target witnesses.
"""

from __future__ import annotations

import math

import pytest

from experiments.experiment_ribbon_cap_transition.director_breadth_cases import (
    BreadthField,
    registered,
)


def test_higher_harmonic_witness_derivative_and_caps() -> None:
    """
    Check an unrelated synthetic field against finite differences and cap values.
    """
    field = BreadthField("synthetic", 80, (1, 0, 0, 0), (0.1, -0.1, 0.2, 0), 13, 1, 0.4, 0.03)
    for u in (0.0, 1.0):
        assert abs(field.sample(u)[1]) < 1e-12
    for u in (0.17, 0.43, 0.81):
        step = 1e-6
        numerical = (field.sample(u + step)[1] - field.sample(u - step)[1]) / (2 * step * 80)
        assert field.sample(u)[2] == pytest.approx(numerical, rel=1e-8)
    with pytest.raises(ValueError):
        BreadthField("invalid", 80, (1, 0, 0, 0), (0, 0, 0, 0), third_bending=math.inf)


def test_registered_phases_and_initial_frames_are_frozen() -> None:
    """
    Require balanced families and proper initial axes without consuming outcomes.
    """
    specs = registered()
    assert len({s.field.name for s in specs}) == len(specs) == 24
    assert sum(s.phase == "validation" for s in specs) == 12
    for family in {s.family for s in specs}:
        assert sum(s.family == family and s.phase == "validation" for s in specs) == 2
    for spec in specs:
        values = spec.initial_pose()
        t, w = values[3:6], values[6:9]
        assert sum(v * v for v in t) == pytest.approx(1)
        assert sum(v * v for v in w) == pytest.approx(1)
        assert abs(sum(a * b for a, b in zip(t, w))) < 1e-14
