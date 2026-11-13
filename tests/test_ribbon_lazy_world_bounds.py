"""
Avoid unused world-axis material bounds without changing contact proof decisions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_boundary import BoundaryCache
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("reuse", tuple(contact.ProjectionReuse))
@pytest.mark.parametrize("separating_axis", (0, 1, 2))
def test_world_bounds_stop_at_first_complete_separating_axis(
    reuse: contact.ProjectionReuse, separating_axis: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Use real thick material bounds and measure the original ordered broad-phase prefix.
    """
    source = _route((Straight(3), Straight(4)))
    origins = (Vector3(10, 0, 0), Vector3(0, 10, 0), Vector3(0, 0, 10))
    second = replace(
        source.pieces[1], pose=replace(source.pieces[1].pose, origin=origins[separating_axis])
    )
    source = replace(source, pieces=(source.pieces[0], second))
    axes = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    trace: list[tuple[int, Vector3]] = []

    def prepare(
        piece: PlacedPiece, direction: Vector3, *, boundary_cache: BoundaryCache | None = None
    ) -> Callable[[Cell], Span]:
        """
        Observe evaluations while leaving every physical enclosure unchanged.
        """
        original = prepare_projection(piece, direction, boundary_cache=boundary_cache)

        def evaluate(cell: Cell) -> Span:
            """
            Record the exact cell and axis whose full material bounds are used.
            """
            trace.append((cell.piece, direction))
            return original(cell)

        return evaluate

    monkeypatch.setitem(vars(contact), "prepare_projection", prepare)
    result = contact.inspect_contact(source, projection_reuse=reuse)
    assert result.status == "separated" and result.pairs_checked == 1
    assert result.witness is None and result.axis_tests == result.axis_separations == 0
    assert trace == [(piece, axis) for axis in axes[: separating_axis + 1] for piece in (0, 1)]


@pytest.mark.parametrize("reuse", tuple(contact.ProjectionReuse))
def test_partial_world_bounds_are_reused_only_for_identical_cells_and_axes(
    reuse: contact.ProjectionReuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Later pairs fill missing slots instead of accepting an unrelated axis or recomputing a slot.
    """
    source = _route((Straight(3), Straight(3), Straight(3)))
    origins = (Vector3(0, 0, 0), Vector3(0, 10, 0), Vector3(10, 0, 0))
    source = replace(
        source,
        pieces=tuple(
            replace(p, pose=replace(p.pose, origin=o)) for p, o in zip(source.pieces, origins)
        ),
    )
    trace: list[tuple[Cell, Vector3]] = []

    def prepare(
        piece: PlacedPiece, direction: Vector3, *, boundary_cache: BoundaryCache | None = None
    ) -> Callable[[Cell], Span]:
        """
        Retain real enclosure arithmetic with an independent invocation trace.
        """
        original = prepare_projection(piece, direction, boundary_cache=boundary_cache)

        def evaluate(cell: Cell) -> Span:
            """
            Count only actual mathematical projections, not cache lookups.
            """
            trace.append((cell, direction))
            return original(cell)

        return evaluate

    monkeypatch.setitem(vars(contact), "prepare_projection", prepare)
    result = contact.inspect_contact(source, projection_reuse=reuse)
    assert result.status == "separated" and result.pairs_checked == 3
    assert len(trace) == len(set(trace)) == 5
    assert [axis for cell, axis in trace if cell.piece == 2] == [Vector3(1, 0, 0)]
    assert all(axis != Vector3(0, 0, 1) for _, axis in trace)
