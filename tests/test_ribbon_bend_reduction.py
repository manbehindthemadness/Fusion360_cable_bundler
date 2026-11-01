"""
Check algebraic fold reduction, nonnegative closure and fail-closed contact handling.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_bend_reduction.closure import close_lengths
from experiments.experiment_ribbon_bend_reduction.reduce import Trial, reduce_bends
from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count, reclose, rewrites
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import (
    FoldRoute,
    PlacedPiece,
    Pose,
    Straight,
    extend,
)
from experiments.experiment_ribbon_fold_route.primitives import Piece, fold


def _route(geometries: tuple[Piece, ...]) -> FoldRoute:
    """
    Author analytical boundary conditions for unit checks, not native-case coverage.
    """
    start = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    pose = start
    pieces = []
    for index, geometry in enumerate(geometries):
        piece = PlacedPiece(pose, geometry, str(index))
        pieces.append(piece)
        pose = piece.end_pose()
    targets = Targets(
        "analytical fold rewrite",
        start.origin,
        pose.origin,
        start.tangent,
        pose.tangent,
        start.width,
        pose.width,
        1,
        1.0,
    )
    return FoldRoute(targets, tuple(pieces), 1.0)


@pytest.mark.parametrize(
    "directions,delta,reference,expected",
    [
        ((Vector3(1, 0, 0),), Vector3(4, 0, 0), (10,), (4,)),
        ((Vector3(1, 0, 0),), Vector3(-4, 0, 0), (10,), None),
        ((Vector3(1, 0, 0),), Vector3(4, 1, 0), (10,), None),
        ((Vector3(1, 0, 0), Vector3(1, 0, 0)), Vector3(4, 0, 0), (0, 10), (0, 4)),
        ((Vector3(1, 0, 0), Vector3(-1, 0, 0)), Vector3(4, 0, 0), (2, 2), (4, 0)),
        ((), Vector3(0, 0, 0), (), ()),
        ((), Vector3(0, 1, 0), (), None),
    ],
)
def test_nonnegative_exact_closure(
    directions: tuple[Vector3, ...],
    delta: Vector3,
    reference: tuple[float, ...],
    expected: tuple[float, ...] | None,
) -> None:
    """
    Find the closest legal straight lengths without inventing backwards material.
    """
    result = close_lengths(directions, delta, reference)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("bank", [0.0, 0.35, -0.6])
def test_same_crease_rotation_preserves_frame_and_checks_positional_closure(bank: float) -> None:
    """
    Preserve diagonal rotation identity while refusing incompatible flat-lead offsets.
    """
    route = _route(
        (
            Straight(12),
            fold(1, 1.2, math.pi / 4, bank, 0),
            fold(1, 1.2, math.pi / 4, bank, 0),
            Straight(8),
        )
    )
    proposals = rewrites(route)
    assert len(proposals) == 1
    replacement = proposals[0].replacement
    assert replacement is not None
    expected = route.pieces[-1].end_pose()
    actual = extend(route.pieces[0].pose, (replacement,))
    assert magnitude(difference(expected.tangent, actual.tangent)) < 1e-12
    assert magnitude(difference(expected.width, actual.width)) < 1e-12
    candidate = reclose(route, proposals[0])
    if bank != 0:
        # Diagonal folds require intermediate flat leads; the two remaining
        # directions cannot reproduce that offset in this analytical fixture.
        assert candidate is None
        return
    assert candidate is not None
    assert fold_count(candidate) == 1
    assert cap_error(candidate) < 1e-10
    assert material_error(candidate) < 1e-12
    assert candidate.targets == route.targets


def test_cancelling_detour_can_be_removed_and_adjacent_straights_merge() -> None:
    """
    Delete a full solver-authored return and close with one forward straight.
    """
    route = _route(
        (
            Straight(10),
            fold(1, 1.2, math.pi, 0, 0),
            Straight(5),
            fold(1, 1.2, math.pi, 0, 0),
            Straight(8),
        )
    )
    candidate = reclose(route, rewrites(route)[0])
    assert candidate is not None
    assert fold_count(candidate) == 0
    assert len(candidate.pieces) == 1
    assert candidate.material_length_mm == pytest.approx(13)
    assert cap_error(candidate) < 1e-12


def test_different_crease_directions_are_not_merged() -> None:
    """
    Refuse the commuting-rotation assumption when crease directions differ.
    """
    route = _route((fold(1, 1.2, math.pi / 3, 0.2, 0), fold(1, 1.2, math.pi / 3, -0.2, 0)))
    assert rewrites(route) == ()


@pytest.mark.parametrize("status", ["separated", "penetration", "unresolved"])
def test_only_contact_separation_accepts_bend_reduction(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Retain the baseline for both nonpassing contact dispositions.
    """
    route = _route(
        (
            Straight(10),
            fold(1, 1.2, math.pi, 0, 0),
            Straight(5),
            fold(1, 1.2, math.pi, 0, 0),
            Straight(8),
        )
    )

    def inspect(
        candidate: FoldRoute, *, checkpoint: Callable[[], None] | None = None
    ) -> ContactResult:
        """
        Supply an explicitly mocked contact boundary for rewrite-control checks.
        """
        del candidate, checkpoint
        return ContactResult(status, 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_bend_reduction.reduce.inspect_contact", inspect
    )
    trials: list[Trial] = []
    result, reason = reduce_bends(route, record=trials.append)
    assert trials
    if status == "separated":
        assert fold_count(result) == 0
        assert all(t.accepted for t in trials)
    else:
        assert result is route
        assert not any(t.accepted for t in trials)
    assert reason == "no_accepted_rewrite"


def test_rewrite_commutes_with_rigid_world_coordinate_changes() -> None:
    """
    Preserve the same simplification under rotated and translated endpoint frames.
    """
    original = _route(
        (
            Straight(12),
            fold(1, 1.2, math.pi / 4, 0, 0),
            fold(1, 1.2, math.pi / 4, 0, 0),
            Straight(8),
        )
    )

    def rotate(value: Vector3) -> Vector3:
        """
        Apply an exact proper rotation that permutes all three world axes.
        """
        return Vector3(value.z, value.x, value.y)

    shift = Vector3(101, -24, 7)
    target = original.targets
    moved_target = replace(
        target,
        start=rotate(target.start).translated(shift, 1),
        end=rotate(target.end).translated(shift, 1),
        start_tangent=rotate(target.start_tangent),
        end_tangent=rotate(target.end_tangent),
        start_width=rotate(target.start_width),
        end_width=rotate(target.end_width),
    )
    moved = FoldRoute(
        moved_target,
        tuple(
            PlacedPiece(
                Pose(
                    rotate(piece.pose.origin).translated(shift, 1),
                    rotate(piece.pose.tangent),
                    rotate(piece.pose.width),
                ),
                piece.geometry,
                piece.label,
            )
            for piece in original.pieces
        ),
        original.radius_mm,
    )
    baseline = reclose(original, rewrites(original)[0])
    result = reclose(moved, rewrites(moved)[0])
    assert baseline is not None and result is not None
    assert fold_count(result) == fold_count(baseline)
    assert result.material_length_mm == pytest.approx(baseline.material_length_mm)
    for u in (0.0, 0.17, 0.53, 0.91, 1.0):
        for q in (-baseline.half_width_mm, 0.0, baseline.half_width_mm):
            expected = rotate(baseline.surface(u, q)[0]).translated(shift, 1)
            assert magnitude(difference(result.surface(u, q)[0], expected)) < 1e-10


@pytest.mark.parametrize("scale", [0.1, 10.0])
def test_nonnegative_closure_scales_with_physical_dimensions(scale: float) -> None:
    """
    Keep the same length allocation at different conductor dimension scales.
    """
    directions = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0))
    result = close_lengths(
        directions,
        Vector3(4 * scale, 3 * scale, 2 * scale),
        (2 * scale, 7 * scale, 5 * scale, 2 * scale),
    )
    assert result == pytest.approx((4 * scale, 3 * scale, 2 * scale, 0.0), abs=1e-10)
