"""
Check crossing-side hypotheses without weakening width or endpoint acceptance.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, dot
from experiments.experiment_ribbon_cap_transition.edge_clearance import NearPair, Ruling
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import coherent_clearance
from experiments.experiment_ribbon_route_discovery.coherent_contacts import build
from experiments.experiment_ribbon_route_discovery.families import Seed


def _pair(index: int, height: float) -> NearPair:
    """
    Author two perpendicular width rulings with a known signed vertical crossing.
    """
    first = Ruling(
        index / 128, Vector3(-10, 0, 0), Vector3(10, 0, 0), Vector3(0, 0, 0), Vector3(0, 20, 0)
    )
    second = Ruling(
        (100 + index) / 128,
        Vector3(0, -10, height),
        Vector3(0, 10, height),
        Vector3(50, 0, 0),
        Vector3(50, 20, 0),
    )
    return NearPair(first, second, abs(height), 50, Vector3(0, 0, 0), Vector3(0, 0, height))


def test_connected_crossing_keeps_one_side_and_covers_its_extents() -> None:
    """
    Alternating closest-point normals must not force opposite local escape sides.
    """
    pairs = tuple(_pair(i, 0.1 if i % 2 else -0.1) for i in range(12))
    model = build(pairs, 1)
    assert model.components == 1 and model.flipped == 6 and model.ambiguous == 0
    assert len(model.planes) == 8
    assert min(p.first_u for p in model.planes) == 0
    assert max(p.first_u for p in model.planes) == 11 / 128
    anchor = model.planes[0].normal
    assert all(dot(anchor, p.normal) == pytest.approx(1) for p in model.planes)
    # Both sides are explicit hypotheses; neither may erase the thickness margin.
    plane = model.planes[0]
    flipped = replace(plane, normal=Vector3(0, 0, 0).translated(plane.normal, -1))
    pair = pairs[0]
    assert plane.margin(
        (pair.first.start, pair.first.end), (pair.second.start, pair.second.end)
    ) == pytest.approx(-0.95)
    assert flipped.margin(
        (pair.first.start, pair.first.end), (pair.second.start, pair.second.end)
    ) == pytest.approx(-1.15)
    assert build(tuple(reversed(pairs)), 1) == model


def test_disconnected_regions_and_parallel_ambiguity_remain_explicit() -> None:
    """
    Separate events keep independent seeds; undefined normals stay unmodeled.
    """
    pair = _pair(0, 0)
    coincident = replace(pair.second, start=pair.first.start, end=pair.first.end)
    ambiguous = replace(pair, second=coincident)
    model = build((ambiguous, _pair(10, 0.1)), 1)
    assert model.components == 2 and model.ambiguous == 1
    assert len(model.planes) == 1
    assert build((), 1).planes == ()


@pytest.mark.parametrize("thickness", [0, -1, float("nan"), float("inf")])
def test_invalid_thickness_is_not_hidden_as_direction_ambiguity(thickness: float) -> None:
    """
    Reject malformed inputs before building escape hypotheses.
    """
    with pytest.raises(ValueError):
        build((), thickness)


def test_clear_control_preserves_exact_endpoints_and_records_both_hypotheses() -> None:
    """
    Actual transport with no contact must not introduce an escape or extra bending.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("neutral", Vector3(0, 0, 0), Vector3(100, 0, 0), x, x, y, y)
    seed = Seed(0, (0.0,) * 9 + (1.0,), 0, ())
    results = tuple(coherent_clearance.candidates(case, seed, lambda: None))
    assert [metrics["escape_sign"] for _, metrics in results] == [1, -1]
    for path, metrics in results:
        assert metrics["strict_endpoint_gate"] and metrics["evaluations"] <= 303
        assert metrics["coherent_model"]["planes"] == ()
        assert path.states[-1][:3] == pytest.approx((100, 0, 0))
        assert metrics["coordinates"] == seed.coordinates
