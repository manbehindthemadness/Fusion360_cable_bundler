"""
Verify global derivative scaling, C4 joins and paired field measurements.
"""

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.distributed_bend import distributed_controls
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    EndpointCase,
    derivative,
    endpoint_cases,
    evaluate,
)
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.native_budget import NativeBudget
from experiments.experiment_ribbon_cap_transition.piecewise_bend import (
    BendPiece,
    PiecewiseBend,
    build_piecewise,
)
from experiments.experiment_ribbon_cap_transition.piecewise_paths import compare_paths, trace_paths


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1], reference_cases()[0]))
def test_three_regions_preserve_external_jets_and_c4_joins(case: EndpointCase) -> None:
    """
    Local derivatives scale into one smooth global curve with unchanged cap jets.
    """
    scaffold, _metadata = build_piecewise(case)
    previous, _old_metadata = distributed_controls(case)
    assert len(scaffold.pieces) == 3
    for piece, endpoint in ((scaffold.pieces[0], 0.0), (scaffold.pieces[-1], 1.0)):
        current, original = piece.controls, previous
        duration = piece.end_parameter - piece.start_parameter
        for order in range(5):
            expected, actual = evaluate(original, endpoint), evaluate(current, endpoint)
            assert (
                magnitude(
                    difference(Vector3(0, 0, 0).translated(actual, duration**-order), expected)
                )
                < 1e-4
            )
            if order < 4:
                current, original = derivative(current), derivative(original)
    for left, right in zip(scaffold.pieces, scaffold.pieces[1:]):
        a, b = left.controls, right.controls
        for order in range(5):
            actual_left = Vector3(0, 0, 0).translated(
                evaluate(a, 1), (left.end_parameter - left.start_parameter) ** -order
            )
            actual_right = Vector3(0, 0, 0).translated(
                evaluate(b, 0), (right.end_parameter - right.start_parameter) ** -order
            )
            assert magnitude(difference(actual_left, actual_right)) < 1e-4
            if order < 4:
                a, b = derivative(a), derivative(b)
        for offset in (-13.5, 0, 13.5):
            for left_jet, right_jet in zip(
                left.jet(left.end_parameter, offset), right.jet(right.start_parameter, offset)
            ):
                assert magnitude(difference(left_jet, right_jet)) < 1e-5


def test_straight_path_preserves_all_lanes_without_bend_fallback() -> None:
    """
    The exact straight branch has no internal regions or singular binormal calls.
    """
    case = endpoint_cases()[0]
    scaffold, _metadata = build_piecewise(case)
    paths = trace_paths(case, scaffold)
    assert len(scaffold.pieces) == 1
    assert len(paths) == case.lines
    for path in paths:
        assert len(path.curves) == 32
        assert magnitude(difference(unit(path.curves[0].derivative(0)), case.start_tangent)) < 1e-8


def test_paired_measurement_matches_exact_parabola() -> None:
    """
    Analytic and exact cubic parabola radii agree in global parameter units.
    """
    case = EndpointCase(
        "parabola",
        Vector3(0, 0, 0),
        Vector3(1, 1, 0),
        Vector3(1, 0, 0),
        unit(Vector3(1, 2, 0)),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
        lines=1,
        diameter_mm=0.01,
    )
    points = tuple(Vector3(i / 7, i * (i - 1) / 42, 0) for i in range(8))
    scaffold = PiecewiseBend((BendPiece(0, 1, points),))
    paths = trace_paths(case, scaffold)
    result = compare_paths(case, scaffold, paths, NativeBudget(memory=lambda: 1000))
    assert result["observations_per_field"] == 288
    assert result["analytic_smallest_observed"]["radius_mm"] == pytest.approx(0.5)
    assert result["cubic_smallest_observed"]["radius_mm"] == pytest.approx(0.5)
    assert result["max_position_error_mm"] < 1e-12
    assert result["cap_position_error_mm"] == 0
