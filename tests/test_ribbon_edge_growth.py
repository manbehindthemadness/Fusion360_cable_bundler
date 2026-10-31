"""
Verify shared geometric growth with fixed attachments and no length constraint.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import experiments.experiment_ribbon_edge_pair.growth as pair_growth
from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import boundary, frame
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_edge_pair.geometry import EdgeChart, elevate
from experiments.experiment_ribbon_edge_pair.growth import grow, normalize, within_limit
from experiments.experiment_ribbon_edge_pair.measure import PairMeasure


def _chart() -> EdgeChart:
    """
    Supply fixed spatial target poses without any prior fitted coordinates.
    """
    case = EndpointCase(
        "growth control",
        Vector3(0, 0, 0),
        Vector3(45, 12, 8),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        3,
        1.5,
    )
    return EdgeChart(case, boundary(case))


@pytest.mark.parametrize("factor", (1.0, 2.0, 16.0))
def test_growth_preserves_caps_and_scales_all_endpoint_derivatives_together(factor: float) -> None:
    """
    Keep endpoint positions fixed while geometrically lengthening the shared curve.
    """
    chart = _chart()
    original = chart.original
    grown = grow(original, factor)
    for u in (0.0, 1.0):
        before, after = original.jet(u), grown.jet(u)
        assert before[0] == after[0]
        for expected, actual in zip(before[1:4], after[1:4]):
            assert (
                magnitude(
                    difference(
                        actual,
                        Vector3(expected.x * factor, expected.y * factor, expected.z * factor),
                    )
                )
                < 1e-7
            )
        first, last = frame(original, u), frame(grown, u)
        assert magnitude(difference(last.tangent, first.tangent)) < 1e-10
        assert magnitude(difference(last.width, first.width)) < 1e-10
        assert abs(last.slope) < 1e-10
        assert last.curvature == pytest.approx(first.curvature / factor, rel=1e-9)
    if factor > 1:
        assert magnitude(difference(grown.jet(0.25)[0], original.jet(0.25)[0])) > 1


def test_growth_commutes_with_exact_degree_elevation() -> None:
    """
    Shared growth changes geometry, not its polynomial representation or parameterization.
    """
    original = _chart().original
    first = elevate(grow(original, 3))
    second = grow(elevate(original), 3)
    for i in range(33):
        assert magnitude(difference(first.jet(i / 32)[0], second.jet(i / 32)[0])) < 1e-10


def test_both_opposing_attachments_stay_on_their_ordered_sides_after_growth() -> None:
    """
    Recomputing B from the grown frame preserves A/B endpoint identity without snapping.
    """
    chart = _chart()
    grown = grow(chart.original, 8)
    half = 2.4
    for u, center, width in (
        (0, chart.case.start, chart.case.start_width),
        (1, chart.case.end, chart.case.end_width),
    ):
        observed = frame(grown, u)
        for offset, sign in ((0, 1), (-2 * half, -1)):
            expected = center.translated(width, sign * half)
            assert magnitude(difference(observed.lane(offset)[0], expected)) < 1e-9


@pytest.mark.parametrize("factor", (0, 0.5, True, float("inf"), float("nan")))
def test_invalid_growth_cannot_change_the_original_curve(factor: float) -> None:
    """
    Reject malformed factors rather than shrinking or silently repairing a curve.
    """
    original = _chart().original
    with pytest.raises(ValueError):
        grow(original, factor)


def test_a_folded_pair_cannot_pass_a_small_deficit_tolerance() -> None:
    """
    Require actual positive progress and defined safe utilization on both edges.
    """
    folded = PairMeasure((), (), 0, 0, None, 0, ())
    assert not within_limit(folded, PinchLimit())
    safe = replace(folded, minimum_j=0.1, peak_b=0.995)
    assert within_limit(safe, PinchLimit())
    assert not within_limit(replace(safe, peak_a=0.997), PinchLimit())


def test_normalization_resets_to_supplied_geometry_and_propagates_resource_stops() -> None:
    """
    Record the original pair first and never continue after the external limit stops work.
    """
    seen = []
    checkpoints = 0

    def checkpoint() -> None:
        """
        Permit one measurement, then stop before another curve can be evaluated.
        """
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints > 1:
            raise RuntimeError("Time cap")

    def observe(_curve: object, _measured: PairMeasure, factor: float, stage: str) -> None:
        """
        Retain the first callback's exact reset factor and stage.
        """
        seen.append((factor, stage))

    with pytest.raises(RuntimeError, match="Time cap"):
        normalize(_chart(), checkpoint, observe)
    assert seen == [(1.0, "reset-original")]


def test_normalization_grows_real_distance_and_cures_the_spatial_fold() -> None:
    """
    A common geometric growth must make both sampled material edges regular.
    """
    chart = _chart()
    result = normalize(chart, lambda: None, lambda *_args: None)
    assert result.factor > 1
    assert result.disposition == "sampled limits satisfied"
    assert within_limit(result.measured, PinchLimit())
    assert len(result.measured.frames) == 4097
    before = [chart.original.jet(i / 64)[0] for i in range(65)]
    after = [result.curve.jet(i / 64)[0] for i in range(65)]
    old_distance = sum(magnitude(difference(b, a)) for a, b in zip(before, before[1:]))
    new_distance = sum(magnitude(difference(b, a)) for a, b in zip(after, after[1:]))
    assert new_distance > old_distance


def test_valid_planar_pair_is_preserved_without_growth() -> None:
    """
    Keep an already regular input unchanged instead of forcing extra material distance.
    """
    case = replace(
        _chart().case,
        end=Vector3(20, 20, 0),
        end_tangent=Vector3(0, 1, 0),
        start_width=Vector3(0, 0, 1),
    )
    chart = EdgeChart(case, boundary(case))
    result = normalize(chart, lambda: None, lambda *_args: None)
    assert result.factor == 1 and result.curve is chart.original
    assert result.evaluations == 2 and result.measured.failed == 0


def test_dense_failure_makes_the_next_growth_use_the_dense_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A coarse pass cannot keep shrinking the growth bracket after dense rejection.
    """
    grids: list[int] = []
    safe = PairMeasure((), (), 1, 0.1, 0.1, 0, ())

    def observe_grid(
        _chart: EdgeChart,
        _curve: object,
        stations: int,
        _limit: PinchLimit,
    ) -> PairMeasure:
        """
        Reject only the first dense observation to expose the following grid choice.
        """
        grids.append(stations)
        return replace(safe, failed=1) if len(grids) == 2 else safe

    monkeypatch.setitem(vars(pair_growth), "measure", observe_grid)
    result = normalize(_chart(), lambda: None, lambda *_args: None, doublings=1, refinements=0)
    assert result.factor == 2 and result.disposition == "sampled limits satisfied"
    assert grids == [513, 4097, 4097, 4097]
