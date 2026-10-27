"""
Check exact neutral routing across dimensions and exclude superficially straight twists.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery.broad_search import SearchLedger
from experiments.experiment_ribbon_route_discovery.generalization_cases import fresh
from experiments.experiment_ribbon_route_discovery.generalized import neutral_boundary, solve


@pytest.mark.parametrize("scale,lines", [(0.1, 3), (1.0, 7), (20.0, 32)])
def test_neutral_route_scales_rotates_and_does_no_search(scale: float, lines: int) -> None:
    """
    Route arbitrary translated frames with zero intrinsic bend and preserved endpoints.
    """
    factor = math.sqrt(0.5)
    tangent = Vector3(factor, 0, factor)
    width = Vector3(0, 1, 0)
    start = Vector3(12 * scale, -3 * scale, 7 * scale)
    case = EndpointCase(
        "neutral arbitrary frame",
        start,
        start.translated(tangent, 80 * scale),
        tangent,
        tangent,
        width,
        width,
        lines,
        scale,
    )
    ledger = SearchLedger()
    handoff = solve(case, lambda: None, ledger)
    assert handoff is not None and handoff.method == "neutral"
    assert ledger.seed_bank == () and ledger.trials == []
    assert handoff.metrics["evaluations"] == 1 and handoff.metrics["strict_endpoint_gate"]
    assert not handoff.contact["contact_detected"]
    assert handoff.path.field.sample(0.5) == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="one-use"):
        solve(case, lambda: None, ledger)


def test_reverse_sideways_and_rolled_boundaries_are_not_neutral() -> None:
    """
    A straight chord alone must not discard endpoint orientation or material order.
    """
    case = fresh()[0]
    assert neutral_boundary(case)
    for other in (
        replace(case, end=Vector3(-80, 0, 0)),
        replace(case, end=Vector3(80, 1, 0)),
        replace(case, end_width=Vector3(0, -1, 0)),
        replace(case, end_tangent=Vector3(-1, 0, 0)),
    ):
        assert not neutral_boundary(other)
    assert all(not neutral_boundary(other) for other in fresh()[1:])


def test_neutral_dispatch_rejects_invalid_frames_before_transport() -> None:
    """
    Do not treat a matching but nonunit pair of frames as a valid straight solution.
    """
    case = replace(fresh()[0], start_tangent=Vector3(2, 0, 0), end_tangent=Vector3(2, 0, 0))
    with pytest.raises(ValueError, match="unit"):
        solve(case, lambda: None, SearchLedger())
