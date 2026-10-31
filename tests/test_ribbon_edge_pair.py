"""
Check fixed target correspondence and coupled pinch measurements without seed discovery.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

import experiments.experiment_ribbon_edge_pair.measure as pair_measure
from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import (
    BoundaryCurve,
    BoundaryFrame,
    boundary,
    frame,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_edge_pair.geometry import EdgeChart, elevate
from experiments.experiment_ribbon_edge_pair.measure import measure
from experiments.experiment_ribbon_edge_pair.projection import correct


def _case(spatial: bool = True) -> EndpointCase:
    """
    Supply distinct spatial and planar fixed-pose cases independent of any fitted result.
    """
    x, y, z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)
    if spatial:
        return EndpointCase("spatial", Vector3(0, 0, 0), Vector3(45, 12, 8), x, x, y, z, 3, 1.5)
    return EndpointCase("quarter", Vector3(0, 0, 0), Vector3(20, 20, 0), x, y, z, z, 3, 1.5)


def test_zero_deviation_preserves_the_supplied_edge_and_its_derivatives() -> None:
    """
    Degree elevation adds freedom without selecting a different initial path.
    """
    case = _case()
    original = boundary(case)
    chart = EdgeChart(case, original)
    changed = chart.curve((0.0,) * 16)
    assert len(changed.points) == len(elevate(original).points)
    for i in range(17):
        for expected, actual in zip(original.jet(i / 16), changed.jet(i / 16)):
            assert magnitude(difference(actual, expected)) <= 1e-6


@pytest.mark.parametrize("sign", (-1, 1))
def test_deviations_keep_both_material_sides_on_their_original_targets(sign: int) -> None:
    """
    Interior changes and cap speed/curvature scales cannot move or swap target attachments.
    """
    case = _case()
    chart = EdgeChart(case, boundary(case))
    values = tuple(sign * (i % 3 - 1) * 0.02 for i in range(16))
    changed = chart.curve(values)
    half = 2.4
    for u, center, tangent, width in (
        (0, case.start, case.start_tangent, case.start_width),
        (1, case.end, case.end_tangent, case.end_width),
    ):
        observed = frame(changed, u)
        arrival_errors = {
            "position": magnitude(difference(observed.position, center.translated(width, half))),
            "tangent": magnitude(difference(observed.tangent, tangent)),
            "width": magnitude(difference(observed.width, width)),
        }
        assert arrival_errors == pytest.approx(dict.fromkeys(arrival_errors, 0.0), abs=1e-10)
        assert abs(observed.slope) < 1e-10
        assert (
            magnitude(difference(observed.lane(-2 * half)[0], center.translated(width, -half)))
            < 1e-9
        )


def test_cached_measurements_match_independently_evaluated_derivatives() -> None:
    """
    Compare the fast evaluator to the retained de Casteljau/Frenet implementation.
    """
    case = _case()
    chart = EdgeChart(case, boundary(case))
    curve = chart.curve((0.0,) * 16)
    measured = measure(chart, curve, 65, PinchLimit())
    for i, actual in enumerate(measured.frames):
        expected = frame(curve, i / 64)
        assert actual is not None
        assert actual.curvature == pytest.approx(expected.curvature, rel=1e-8)
        assert actual.slope == pytest.approx(expected.slope, rel=1e-8, abs=1e-10)
        assert actual.slope_rate == pytest.approx(expected.slope_rate, rel=1e-7, abs=1e-9)


def test_planar_turn_shares_the_same_limit_and_keeps_both_edges_regular() -> None:
    """
    A constant bend plane gives equal A/B pinch without invented width-dependent radii.
    """
    case = _case(False)
    chart = EdgeChart(case, boundary(case))
    measured = measure(chart, chart.curve((0.0,) * 16), 129, PinchLimit())
    assert measured.failed == 0 and measured.minimum_j == pytest.approx(1)
    assert measured.peak_b == pytest.approx(measured.peak_a)
    assert measured.peak_a < 0.996
    for sample in measured.frames:
        assert sample is not None
        assert sample.slope == pytest.approx(0, abs=1e-10)


def test_folded_opposing_edge_cannot_report_a_safe_negative_utilization() -> None:
    """
    A reversed material map remains failed rather than dividing by negative progress.
    """
    case = _case()
    chart = EdgeChart(case, boundary(case))
    measured = measure(chart, chart.curve((0.0,) * 16), 129, PinchLimit())
    assert measured.minimum_j < 0
    assert measured.failed > 0
    assert measured.peak_b is None
    assert {"A", "B"} <= set(measured.governing)


def test_zero_material_progress_rejects_even_below_the_numerical_pinch_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A collapsed almost-straight map must fail even when its pinch deficit is tiny.
    """
    case = _case(False)
    chart = EdgeChart(case, boundary(case))
    collapsed = BoundaryFrame(
        Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1), 0, 10 / 4.8, 10, 1e-14
    )
    monkeypatch.setitem(vars(pair_measure), "_frame", lambda *_args: collapsed)
    measured = measure(chart, chart.curve((0.0,) * 16), 65, PinchLimit())
    assert measured.minimum_j == 0
    assert measured.failed == 65 and measured.peak_b is None


def test_derived_opposing_velocity_matches_an_independent_position_difference() -> None:
    """
    Keep the opposing edge coupled through ruling motion instead of a naive normal offset.
    """
    case = _case()
    curve = boundary(case)
    u, delta = 0.23, 1e-6
    left = frame(curve, u - delta).lane(-4.8)[0]
    right = frame(curve, u + delta).lane(-4.8)[0]
    numerical = difference(right, left)
    numerical = Vector3(*(v / (2 * delta) for v in (numerical.x, numerical.y, numerical.z)))
    expected = frame(curve, u).lane(-4.8)[1]
    assert magnitude(difference(numerical, expected)) < 1e-5


def test_already_valid_geometry_needs_no_correction_and_is_checked_on_a_denser_grid() -> None:
    """
    Avoid unnecessary deviation once the existing pair satisfies the sampled limits.
    """
    case = _case(False)
    chart = EdgeChart(case, boundary(case))
    observations: list[str] = []
    result = correct(
        chart, lambda: None, lambda _curve, _measure, stage: observations.append(stage)
    )
    assert result.accepted == 0 and result.evaluations == 2
    assert result.disposition == "sampled limits satisfied"
    assert observations == ["original", "denser-check"]
    assert len(result.measured.frames) == 513


def test_checkpoint_failure_stops_before_any_proposal_and_is_not_a_feasibility_result() -> None:
    """
    Propagate scheduling failures instead of silently retrying or accepting geometry.
    """
    case = _case()
    chart = EdgeChart(case, boundary(case))
    observed: list[Any] = []

    def stop() -> None:
        """
        Simulate an exhausted external resource bound.
        """
        raise RuntimeError("Time cap")

    with pytest.raises(RuntimeError, match="Time cap"):
        correct(chart, stop, lambda *args: observed.append(args))
    assert observed == []


def test_exact_straight_control_does_not_require_an_invented_frenet_frame() -> None:
    """
    Retain the supplied constant width through an exactly zero-curvature edge.
    """
    case = replace(_case(), end=Vector3(60, 0, 0), end_width=Vector3(0, 1, 0))
    points = tuple(Vector3(60 * i / 7, 2.4, 0) for i in range(8))
    chart = EdgeChart(case, BoundaryCurve(points))
    measured = measure(chart, chart.curve((0.0,) * 16), 65, PinchLimit())
    assert measured.failed == 0 and measured.peak_a == 0 and measured.peak_b == 0
    for observed in measured.frames:
        assert observed is not None
        assert observed.width == case.start_width
        assert observed.tangent == case.start_tangent


@pytest.mark.parametrize("values", ((0.0,) * 15, (float("nan"),) * 16))
def test_malformed_deviations_reject(values: tuple[float, ...]) -> None:
    """
    Reject invalid external coordinates before evaluating or drawing a curve.
    """
    case = _case()
    with pytest.raises(ValueError):
        EdgeChart(case, boundary(case)).curve(values)


def test_wrong_side_cannot_be_used_as_the_primary_edge() -> None:
    """
    Reject material-side swaps before the opposing guide can be derived.
    """
    case = _case()
    wrong = boundary(replace(case, start_width=Vector3(0, -1, 0)))
    with pytest.raises(ValueError, match="ordered target side"):
        EdgeChart(case, wrong)


@pytest.mark.parametrize(
    "change", ({"end_tangent": Vector3(-1, 0, 0)}, {"end_width": Vector3(0, -1, 0)})
)
def test_intrinsic_limits_cannot_hide_wrong_terminal_frames(change: dict[str, Vector3]) -> None:
    """
    A geometrically straight pair cannot pass with reversed terminal order or arrival.
    """
    case = replace(_case(), end=Vector3(60, 0, 0), end_width=Vector3(0, 1, 0))
    points = tuple(Vector3(60 * i / 7, 2.4, 0) for i in range(8))
    with pytest.raises(ValueError):
        EdgeChart(replace(case, **change), BoundaryCurve(points))


def test_limit_driven_progress_is_not_misreported_as_a_fitted_pair() -> None:
    """
    Improve an existing violation while retaining unresolved status and fixed attachments.
    """
    case = _case()
    chart = EdgeChart(case, boundary(case))
    before = measure(chart, chart.curve((0.0,) * 16), 513, PinchLimit())
    result = correct(chart, lambda: None, lambda *_args: None, rounds=2)
    assert result.accepted > 0
    assert result.measured.score < before.score
    assert result.measured.failed > 0 and result.disposition == "unresolved"
    assert result.curve.points[0] == chart.original.points[0]
    assert result.curve.points[-1] == chart.original.points[-1]
