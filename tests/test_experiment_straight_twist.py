"""
Check fixed authoring inputs independently of Fusion construction.
"""

import math

import pytest

from experiments.experiment_ribbon_cap_transition.straight_twist import (
    rate_metrics,
    section_arcs,
    twist_frames,
)


@pytest.mark.parametrize("degrees", (0.0, 180.0, 360.0))
def test_fixed_path_and_perpendicular_frames(degrees: float) -> None:
    """
    Roll alone changes; centerline and section-plane normals stay fixed.
    """
    frames = twist_frames(degrees)
    assert len(frames) == 32
    assert frames[0].origin.z == 0
    assert frames[-1].origin.z == 57
    for frame in frames:
        assert frame.origin.x == frame.origin.y == 0
        assert frame.width.z == frame.thickness.z == 0
        assert math.hypot(frame.width.x, frame.width.y) == pytest.approx(1)
        assert frame.width.x * frame.thickness.x + frame.width.y * frame.thickness.y == 0
    metrics = rate_metrics(degrees)
    assert metrics["analytic_peak_degrees_per_mm"] == pytest.approx(degrees * 1.875 / 57)
    assert metrics["maximum_station_rate_degrees_per_mm"] <= metrics["analytic_peak_degrees_per_mm"]
    assert metrics["maximum_station_increment_degrees"] < 180


def test_contour_is_single_closed_cycle() -> None:
    """
    Every endpoint has exactly two incident arcs; no geometry is added or removed.
    """
    arcs = section_arcs()
    assert len(arcs) == 40
    incidences: dict[tuple[float, float], int] = {}
    for arc in arcs:
        for point in (arc[0], arc[-1]):
            incidences[point] = incidences.get(point, 0) + 1
    assert len(incidences) == 40
    assert set(incidences.values()) == {2}
    assert max(point[0] for arc in arcs for point in arc) == 14.4


def test_nonfinite_twist_rejected() -> None:
    """
    Malformed prescribed roll cannot reach native authoring.
    """
    with pytest.raises(ValueError, match="finite"):
        twist_frames(float("nan"))
