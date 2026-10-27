"""
Check fixed boundary coverage without solving or constructing validation fixtures.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_route_discovery.breadth_cases import cases
from experiments.experiment_ribbon_route_discovery.generalization_cases import fresh, reserved


def test_boundary_matrix_is_fixed_valid_and_distinct() -> None:
    """
    Preserve48 unique named inputs and valid frames across all six boundary families.
    """
    matrix = cases()
    assert matrix == cases()
    assert len(matrix) == len({case.name for case in matrix}) == 48
    assert (
        len(
            {
                (case.end, case.end_tangent, case.end_width, case.lines, case.diameter_mm)
                for case in matrix
            }
        )
        == 48
    )
    previous = {
        (case.end, case.end_tangent, case.end_width, case.lines, case.diameter_mm)
        for case in fresh() + reserved()
    }
    for case in matrix:
        Targets.capture(case)
        assert (
            case.end,
            case.end_tangent,
            case.end_width,
            case.lines,
            case.diameter_mm,
        ) not in previous
    assert {case.lines for case in matrix} == {5, 7, 9, 13, 16, 19, 24, 32}


@pytest.mark.parametrize("index", range(8))
def test_planar_u_preserves_material_width_and_reverses_tangent(index: int) -> None:
    """
    Simple U boundary controls require an out-of-plane return,not a wide-axis bend.
    """
    case = cases()[index]
    width = case.lines * case.diameter_mm
    assert case.end.x == case.end.y == 0
    assert case.end.z >= 1.6 * width
    assert case.end_tangent.x == pytest.approx(-1)
    assert case.end_tangent.y == pytest.approx(0, abs=1e-12)
    assert case.end_width.x == pytest.approx(0, abs=1e-12)
    assert case.end_width.y == pytest.approx(1)
    assert case.start_width == Vector3(0, 1, 0)
