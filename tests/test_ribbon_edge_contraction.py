"""
Verify fixed-pose paired contraction and honest passing/failing boundary accounting.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve, boundary, frame
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_edge_pair.contraction import contract
from experiments.experiment_ribbon_edge_pair.geometry import EdgeChart
from experiments.experiment_ribbon_edge_pair.growth import rescale


def _chart() -> EdgeChart:
    """
    Supply a fixed planar quarter-turn with independently prescribed cap directions.
    """
    case = EndpointCase(
        "contraction",
        Vector3(0, 0, 0),
        Vector3(20, 20, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
        3,
        1.5,
    )
    return EdgeChart(case, boundary(case))


@pytest.mark.parametrize("factor", (0.9, 0.5, 0.1))
def test_contraction_preserves_both_ordered_attachments_and_tightens_caps(factor: float) -> None:
    """
    Scale actual geometry while fixing both edge positions and material cap frames.
    """
    chart = _chart()
    changed = rescale(chart.original, factor)
    for u in (0.0, 1.0):
        before, after = frame(chart.original, u), frame(changed, u)
        assert before.position == after.position
        assert magnitude(difference(after.tangent, before.tangent)) < 1e-10
        assert magnitude(difference(after.width, before.width)) < 1e-10
        assert magnitude(difference(after.lane(-4.8)[0], before.lane(-4.8)[0])) < 1e-9
        assert after.curvature == pytest.approx(before.curvature / factor, rel=1e-8)


def test_boundary_bracket_retains_a_valid_and_an_invalid_pair() -> None:
    """
    Stop with separate measured sides of the boundary, never accepting the failed trial.
    """
    stages: list[str] = []
    result = contract(
        _chart(), lambda: None, lambda _trial, stage: stages.append(stage), refinements=3
    )
    assert result.disposition == "observed constraint boundary bracketed"
    assert result.passing is not None and result.passing.passes
    assert result.failing is not None and not result.failing.passes
    assert result.failing.triggers
    assert result.passing.factor > result.failing.factor > 0
    assert stages[0] == "original" and stages[-1] == "boundary:2"
    assert result.evaluations == len(stages)


def test_contraction_exhaustion_is_not_reported_as_a_constraint_trigger() -> None:
    """
    A finite contraction budget without a failure is unresolved, not a physical boundary.
    """
    case = EndpointCase(
        "straight",
        Vector3(0, 0, 0),
        Vector3(60, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        3,
        1.5,
    )
    curve = BoundaryCurve(tuple(Vector3(60 * i / 7, 2.4, 0) for i in range(8)))
    result = contract(
        EdgeChart(case, curve), lambda: None, lambda *_args: None, steps=1, refinements=0
    )
    assert result.failing is None
    assert result.passing is not None and result.passing.passes
    assert result.disposition == "no trigger within contraction budget"


@pytest.mark.parametrize("factor", (0, -1, True, float("inf"), float("nan")))
def test_invalid_scaling_cannot_collapse_cap_directions(factor: float) -> None:
    """
    Reject invalid rescaling rather than returning a degenerate cap frame.
    """
    with pytest.raises(ValueError):
        rescale(_chart().original, factor)


def test_resource_stop_prevents_all_evaluations() -> None:
    """
    Propagate an external time/RSS stop without scheduling another trial.
    """

    def stop() -> None:
        """
        Simulate the caller's exhausted resource gate.
        """
        raise RuntimeError("resource stop")

    with pytest.raises(RuntimeError, match="resource stop"):
        contract(_chart(), stop, lambda *_args: None)
