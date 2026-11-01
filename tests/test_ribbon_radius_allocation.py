"""
Check affine radius allocation, straight controls and conservative contact acceptance.
"""

from __future__ import annotations

import math
from typing import Callable

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold
from experiments.experiment_ribbon_radius_allocation.model import Model
from experiments.experiment_ribbon_radius_allocation.program import allocate
from experiments.experiment_ribbon_radius_allocation.solve import Trial, solve


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Author analytical boundary conditions without counting them as native coverage.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = start
    pieces = []
    for index, geometry in enumerate(geometries):
        piece = PlacedPiece(pose, geometry, str(index))
        pieces.append(piece)
        pose = piece.end_pose()
    target = Targets(
        "analytical radius allocation",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(target, tuple(pieces), 1.0)


def test_linear_allocation_rounds_a_corner_without_length_growth() -> None:
    """
    Solve a degenerate four-row program at its known minimum-straight optimum.
    """
    result = allocate(
        ((1, 0, 0), (0, 1, 0), (1, 1, 0)), (10, 12, 0), (1, 1, math.pi / 2), (0, 1), 22
    )
    assert result is not None
    assert result.values == pytest.approx((0, 2, 10))
    assert result.straight_length == pytest.approx(2)
    assert result.variable_material_length < 22


def test_material_budget_excludes_a_point_that_only_closes_position() -> None:
    """
    Keep the no-length-growth constraint authoritative in the linear solve.
    """
    assert allocate(((1, 0, 0),), (10, 0, 0), (1,), (0,), 5) is None


def test_affine_model_matches_independent_recomposition() -> None:
    """
    Verify growth coefficients across planar and diagonal fixed-crease folds.
    """
    source = _route(
        (
            Straight(10),
            fold(1, 1.2, math.pi / 3, 0.35, 0),
            Straight(6),
            fold(1, 1.2, -math.pi / 4, -0.2, 0),
            Straight(8),
        )
    )
    model = Model(source)
    columns, _, _ = model.equations()
    origin = model.endpoint((0.0,) * len(source.pieces)).origin
    values = tuple(
        value * 0.7 if i in model.straight_indices else 2.3 for i, value in enumerate(model.initial)
    )
    expected = origin
    for column, value in zip(columns, values):
        expected = expected.translated(Vector3(*column), value * source.targets.diameter_mm)
    actual = model.endpoint(values)
    assert magnitude(difference(actual.origin, expected)) < 1e-11
    assert magnitude(difference(actual.tangent, source.targets.end_tangent)) < 1e-12
    assert magnitude(difference(actual.width, source.targets.end_width)) < 1e-12


def test_gentler_quarter_turn_absorbs_straights_with_actual_contact_gate() -> None:
    """
    Grow a fillet to its exact endpoint-limited radius and remove one straight.
    """
    source = _route((Straight(10), fold(1, 1.2, math.pi / 2, 0, 0), Straight(12)))
    result, optimum, fraction, reason = solve(source)
    assert optimum is not None
    assert fraction == 1 and reason == "allocated"
    assert cap_error(result) < 1e-10
    assert material_error(result) < 1e-12
    assert result.material_length_mm < source.material_length_mm
    bends = [p.geometry for p in result.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(bends) == 1
    assert bends[0].radius_mm == pytest.approx(11)
    assert bends[0].angle_radians == math.pi / 2
    assert len(result.pieces) == 2
    assert sum(
        p.geometry.material_length_mm for p in result.pieces if isinstance(p.geometry, Straight)
    ) == pytest.approx(2)


def test_direct_straight_control_remains_direct_and_straight() -> None:
    """
    Avoid replacing a correct straight connection with unnecessary curved travel.
    """
    source = _route((Straight(10),))
    result, optimum, fraction, reason = solve(source)
    assert result is source
    assert optimum is not None
    assert fraction == 0 and reason == "no_straight_reduction"


@pytest.mark.parametrize("status", ["penetration", "unresolved"])
def test_unaccepted_contact_retains_original_and_records_all_fractions(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Never turn contact-budget exhaustion into a radius-allocation success.
    """

    def inspect(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Supply an explicitly mocked nonpassing contact decision.
        """
        del route, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_radius_allocation.solve.inspect_contact", inspect
    )
    source = _route((Straight(10), fold(1, 1.2, math.pi / 2, 0, 0), Straight(12)))
    trials: list[Trial] = []
    result, optimum, fraction, reason = solve(source, record=trials.append)
    assert result is source and optimum is not None
    assert fraction == 0 and reason == "contact_fraction_budget"
    assert [t.fraction for t in trials] == [2.0 ** (-i) for i in range(8)]
    assert all(t.contact.status == status for t in trials)


def test_resource_stop_propagates_from_linear_enumeration() -> None:
    """
    Preserve budget interruptions as errors rather than reporting an allocation.
    """

    def stop() -> None:
        """
        Model the experiment runner's independent resource checkpoint.
        """
        raise TimeoutError("unit budget")

    with pytest.raises(TimeoutError, match="unit budget"):
        allocate(((1, 0, 0),), (10, 0, 0), (1,), (0,), 10, stop)
