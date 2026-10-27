"""
Verify occupied-width separation,scale/translation covariance and explicit ambiguity.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.edge_clearance import Ruling
from experiments.experiment_ribbon_route_discovery.guidance import (
    DistancePair,
    PlanePair,
    from_witness,
)


def test_full_width_margin_detects_overlap_hidden_by_center_distance() -> None:
    """
    Require separation of whole width segments,not merely their center points.
    """
    plane = PlanePair(0.1, 0.9, Vector3(1, 0, 0), 1)
    first = (Vector3(0, 0, 0), Vector3(20, 0, 0))
    second = (Vector3(-10, 0, 0), Vector3(1, 0, 0))
    assert plane.margin(first, second) == -2
    moved = tuple(p.translated(Vector3(1, 0, 0), 2) for p in first)
    assert plane.margin((moved[0], moved[1]), second) == 0


@pytest.mark.parametrize("scale", [0.1, 1.0, 100.0])
def test_margin_scales_with_geometry_and_ignores_common_translation(scale: float) -> None:
    """
    Keep dimensionless deficit independent of chosen geometry size and origin.
    """
    plane = PlanePair(0.1, 0.9, Vector3(0, 0, 1), scale)
    a = (Vector3(-10 * scale, 0, scale / 2), Vector3(10 * scale, 0, scale / 2))
    b = (Vector3(-10 * scale, 0, 0), Vector3(10 * scale, 0, 0))
    assert plane.margin(a, b) / scale == pytest.approx(-0.5)
    shift = Vector3(100, -25, 9)
    aa = tuple(p.translated(shift, 1) for p in a)
    bb = tuple(p.translated(shift, 1) for p in b)
    assert plane.margin((aa[0], aa[1]), (bb[0], bb[1])) == pytest.approx(plane.margin(a, b))


def test_exact_transverse_crossing_chooses_a_side_but_parallel_coincidence_rejects() -> None:
    """
    Supply a deterministic transverse hypothesis without inventing an ambiguous normal.
    """
    zero = Vector3(0, 0, 0)
    a = Ruling(0.1, Vector3(-1, 0, 0), Vector3(1, 0, 0), zero, zero)
    b = Ruling(0.9, Vector3(0, -1, 0), Vector3(0, 1, 0), zero, zero)
    plane = from_witness(a, b, (zero, zero), 1)
    assert plane.normal == Vector3(0, 0, 1)
    assert plane.margin((a.start, a.end), (b.start, b.end)) == -1
    with pytest.raises(ValueError, match="parallel"):
        from_witness(a, replace(a, fraction=0.9), (zero, zero), 1)


def test_actual_distance_releases_a_clear_pair_rejected_by_an_old_plane() -> None:
    """
    Regress stale separating directions that reject rotated but separated material.
    """
    a = (Vector3(-10, 0, 0), Vector3(10, 0, 0))
    b = (Vector3(-10, 5, 0), Vector3(10, 5, 0))
    assert PlanePair(0.1, 0.9, Vector3(1, 0, 0), 1).margin(a, b) == -21
    assert DistancePair(0.1, 0.9, 1).margin(a, b) == 4
