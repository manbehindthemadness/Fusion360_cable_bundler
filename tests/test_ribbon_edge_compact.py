"""
Verify local shortening retains ordered cap frames and both sampled edge limits.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import boundary, frame
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_edge_pair.compact import (
    LocalShape,
    distance,
    projected_step,
    shorten,
)
from experiments.experiment_ribbon_edge_pair.extrema import check_peaks
from experiments.experiment_ribbon_edge_pair.geometry import EdgeChart
from experiments.experiment_ribbon_edge_pair.growth import grow, within_limit
from experiments.experiment_ribbon_edge_pair.measure import frames_at, measure


def _chart() -> EdgeChart:
    """
    Supply a regular planar reference with fixed attachment positions and frames.
    """
    case = EndpointCase(
        "local quarter",
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


def test_local_deformation_preserves_both_ordered_target_sides() -> None:
    """
    Interior retraction and cap tightness changes cannot shift or swap attachments.
    """
    chart = _chart()
    changed = LocalShape(chart).curve(tuple((i % 3 - 1) * 0.01 for i in range(16)))
    for u, center, tangent, width in (
        (0, chart.case.start, chart.case.start_tangent, chart.case.start_width),
        (1, chart.case.end, chart.case.end_tangent, chart.case.end_width),
    ):
        observed = frame(changed, u)
        assert magnitude(difference(observed.tangent, tangent)) < 1e-10
        assert magnitude(difference(observed.width, width)) < 1e-10
        for offset, sign in ((0, 1), (-4.8, -1)):
            assert (
                magnitude(
                    difference(observed.lane(offset)[0], center.translated(width, sign * 2.4))
                )
                < 1e-9
            )


def test_projection_uses_slack_without_stepping_through_an_active_limit() -> None:
    """
    Respect a blocked direction while retaining an independent shortening component.
    """
    result = projected_step((1.0, -1.0), ((1.0, 0.0), (0.0, -1.0)), (0.0, -0.1), 0.25)
    assert result[0] <= 1e-12 and -0.1000001 <= result[1] < 0


def test_critical_samples_match_independent_evaluation_at_nonuniform_locations() -> None:
    """
    Cached critical-location derivatives must agree with the de Casteljau evaluator.
    """
    chart = _chart()
    fractions = (0.001, 0.07, 0.234567, 0.99)
    for u, observed in zip(fractions, frames_at(chart, chart.original, fractions)):
        expected = frame(chart.original, u)
        assert magnitude(difference(observed.position, expected.position)) < 1e-10
        assert observed.curvature == pytest.approx(expected.curvature, rel=1e-9)
        assert observed.slope_rate == pytest.approx(expected.slope_rate, abs=1e-10)


@pytest.mark.parametrize("fractions", ((), (-0.1,), (1.1,), (float("nan"),)))
def test_critical_sampling_rejects_invalid_domains(fractions: tuple[float, ...]) -> None:
    """
    Invalid external critical locations must fail before evaluating a curve.
    """
    chart = _chart()
    with pytest.raises(ValueError):
        frames_at(chart, chart.original, fractions)


def test_shortening_retains_a_densely_checked_shorter_pair() -> None:
    """
    A supplied expanded curve can retract without accepting a new fold or pinch failure.
    """
    chart = _chart()
    expanded = EdgeChart(chart.case, grow(chart.original, 2))
    initial = measure(expanded, expanded.original, 4097, PinchLimit())
    result = shorten(expanded, lambda: None, lambda *_args: None, rounds=2)
    assert result.accepted > 0
    assert within_limit(result.measured, PinchLimit())
    assert len(result.measured.frames) == 4097
    assert distance(result.measured) < distance(initial)


def test_invalid_input_is_retained_without_attempting_shortening() -> None:
    """
    A folded input cannot masquerade as a valid starting point for feasible retraction.
    """
    chart = _chart()
    spatial = EndpointCase(
        "folded",
        chart.case.start,
        Vector3(45, 12, 8),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        3,
        1.5,
    )
    result = shorten(EdgeChart(spatial, boundary(spatial)), lambda: None, lambda *_args: None)
    assert result.accepted == 0 and result.evaluations == 1
    assert result.disposition == "input not sampled-valid"


def test_straight_pair_at_chord_lower_bound_needs_no_singular_probe() -> None:
    """
    Preserve the exact shortest straight control without differentiating an undefined Frenet frame.
    """
    case = replace(_chart().case, end=Vector3(60, 0, 0), end_tangent=Vector3(1, 0, 0))
    from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

    curve = BoundaryCurve(tuple(Vector3(60 * i / 7, 0, 2.4) for i in range(8)))
    result = shorten(EdgeChart(case, curve), lambda: None, lambda *_args: None)
    assert result.accepted == 0 and result.evaluations == 1
    assert result.disposition == "already at chord lower bound"
    assert distance(result.measured) == pytest.approx(60)


def test_resource_stop_propagates_before_local_evaluation() -> None:
    """
    External resource exhaustion must halt without retries or an invented disposition.
    """

    def stop() -> None:
        """
        Simulate an exhausted numerical scheduling budget.
        """
        raise RuntimeError("budget exhausted")

    with pytest.raises(RuntimeError, match="budget exhausted"):
        shorten(_chart(), stop, lambda *_args: None)


def test_refined_peak_rejects_the_frozen_uniform_grid_false_acceptance() -> None:
    """
    Preserve run150's missed99.626percent peak as a regression, not physical coverage.
    """
    from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

    saved = json.loads(
        (Path(__file__).parent / "fixtures/ribbon_edge_compact_missed_peak.json").read_text()
    )
    case = EndpointCase(
        "run150 narrow peak",
        Vector3(11.147517077621664, -7.965443827033006, 13.114146501177316),
        Vector3(15.566152014003867, 14.152416300119217, 11.864943863944259),
        Vector3(0.0, 0.8506508083520399, 0.5257311121191336),
        Vector3(-0.85065080835204, -0.5257311121191335, 0.0),
        Vector3(0.8090169943749475, -0.3090169943749474, 0.5),
        Vector3(-0.42532540417602027, 0.6881909602355867, -0.587785252292473),
        3,
        1.5,
    )
    curve = BoundaryCurve(tuple(Vector3(**point) for point in saved["controls"]))
    chart = EdgeChart(case, curve)
    sampled = measure(chart, curve, 4097, PinchLimit())
    assert within_limit(sampled, PinchLimit())
    refined = check_peaks(chart, curve, sampled, lambda: None)
    assert not refined.within(PinchLimit())
    assert refined.peak_b is not None and refined.peak_b > 0.996
    result = shorten(chart, lambda: None, lambda *_args: None)
    assert result.accepted == 0 and result.disposition == "input fails refined peaks"


@pytest.mark.parametrize("count", (0, 1, 2))
def test_refined_peak_rejects_an_insufficient_uniform_grid(count: int) -> None:
    """
    Reject empty or underspecified samples instead of inventing a maximum bracket.
    """
    chart = _chart()
    observed = measure(chart, chart.original, 65, PinchLimit())
    with pytest.raises(ValueError, match="regular uniform sampled pair"):
        check_peaks(
            chart, chart.original, replace(observed, frames=observed.frames[:count]), lambda: None
        )


@pytest.mark.parametrize("rounds", (True, -1, 33, 0.5))
def test_malformed_round_budget_rejects(rounds: int) -> None:
    """
    Refuse unbounded or malformed iteration budgets before evaluating a curve.
    """
    with pytest.raises(ValueError):
        shorten(_chart(), lambda: None, lambda *_args: None, rounds=rounds)
