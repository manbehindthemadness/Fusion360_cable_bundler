"""
Test occupied-width guidance,refresh semantics and bounded nonlinear fitting.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.edge_clearance import NearPair, Ruling, screen
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery.active_clearance import linearize, sample
from experiments.experiment_ribbon_route_discovery.active_fit import refine_active
from experiments.experiment_ribbon_route_discovery.solver import screen_seeds


def test_width_crossing_survives_center_clearance_and_refresh_releases_stale_plane() -> None:
    """
    Regress a center-clear but occupied-span collision and its later rotated escape.
    """
    a = Ruling(0, Vector3(-20, 0, 0), Vector3(0, 0, 0), Vector3(0, -10, 0), Vector3(0, 10, 0))
    b = Ruling(
        1, Vector3(-1, -10, 0.25), Vector3(-1, 10, 0.25), Vector3(40, -10, 0), Vector3(40, 10, 0)
    )
    ca = a.start.translated(difference(a.end, a.start), 0.5)
    cb = b.start.translated(difference(b.end, b.start), 0.5)
    assert magnitude(difference(ca, cb)) > 9
    pairs: list[NearPair] = []
    result = screen((a, b), 1, lambda: None, pair_observer=pairs.append)
    assert result["contact_detected"] and len(pairs) == 1
    planes, deficits, ambiguous = linearize(tuple(pairs), 1)
    assert len(planes) == len(deficits) == 8 and ambiguous == 0
    assert deficits[0] == pytest.approx((1.05 - 0.25) / 1.05)
    plane = planes[0]
    assert plane is not None
    assert plane.margin((a.start, a.end), (b.start, b.end)) == pytest.approx(-0.8)
    moved = replace(b, start=Vector3(-20, 5, 0), end=Vector3(0, 5, 0))
    assert plane.margin((a.start, a.end), (moved.start, moved.end)) < 0
    pairs.clear()
    clear = screen((a, moved), 1, lambda: None, pair_observer=pairs.append)
    assert not clear["contact_detected"] and not pairs
    fresh, deficits, ambiguous = linearize(tuple(pairs), 1)
    assert fresh == (None,) * 8 and deficits == (0.0,) * 8 and ambiguous == 0


def test_exact_parallel_ambiguity_keeps_a_deficit_without_inventing_a_direction() -> None:
    """
    Disclose an unresolved intersecting pair even when its model has zero derivative.
    """
    a = Ruling(0, Vector3(-1, 0, 0), Vector3(1, 0, 0), Vector3(0, -1, 0), Vector3(0, 1, 0))
    b = replace(a, fraction=1, flat_start=Vector3(10, -1, 0), flat_end=Vector3(10, 1, 0))
    pairs: list[NearPair] = []
    screen((a, b), 1, lambda: None, pair_observer=pairs.append)
    planes, deficits, ambiguous = linearize(tuple(pairs), 1)
    assert planes[0] is None and deficits[0] == 1 and ambiguous == 1


def test_active_fit_preserves_oblique_control_and_monotone_actual_merit() -> None:
    """
    Verify closure and recorded work on actual integrated geometry,without host APIs.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("active-oblique", Vector3(0, 0, 0), Vector3(80, 0, 12), x, x, y, y)
    _, selected, _ = screen_seeds(case, lambda: None)
    path, metrics = refine_active(case, selected[0], lambda: None)
    final = sample(case, path, lambda: None)
    assert metrics["strict_endpoint_gate"] and not final.contacts["contact_detected"]
    assert metrics["evaluations"] <= 254 and 2 <= metrics["contact_audits"] <= 44
    assert len(path.states) == 513
    for stage in metrics["stages"]:
        assert all(b <= a for a, b in zip(stage["history"], stage["history"][1:]))
        assert all(t["accepted"] == (t["after"] < t["before"]) for t in stage["trials"])


@pytest.mark.parametrize("thickness", [0, -1, float("nan"), float("inf")])
def test_invalid_guidance_thickness_rejects(thickness: float) -> None:
    """
    Refuse malformed dimensions before normalizing any proximity penalty.
    """
    with pytest.raises(ValueError):
        linearize((), thickness)
