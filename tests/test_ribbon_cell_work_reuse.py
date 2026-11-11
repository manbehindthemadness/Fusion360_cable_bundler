"""
Preserve complete contact outcomes while reusing only fixed-route material-cell work.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, cast
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route import contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


def _source(kind: str) -> FoldRoute:
    """
    Author independent thick-strip and banked-fold controls without saved geometry or solving.
    """
    if kind == "folds":
        return _route(
            (
                fold(1, 1.2, 2.5, 0.3, 0),
                Straight(3),
                fold(1, 1.2, -2, -0.2, 0),
                Straight(2),
                fold(1, 1.2, 1.5, 0.1, 0),
            )
        )
    source = _route((Straight(10),))
    first = source.pieces[0]
    gap = {"overlap": 0.2, "touch": 1.0, "clear": 1.2}[kind]
    return replace(
        source,
        pieces=(
            first,
            PlacedPiece(replace(first.pose, origin=Vector3(0, 0, gap)), Straight(10), "near"),
            PlacedPiece(replace(first.pose, origin=Vector3(100, 0, 0)), Straight(10), "far"),
        ),
    )


@pytest.mark.parametrize("kind", ("overlap", "touch", "clear", "folds"))
@pytest.mark.parametrize("policy", tuple(CapPolicy))
@pytest.mark.parametrize("maximum_pairs,depth", ((7, 36), (128, 36), (128, 1)))
def test_cell_reuse_preserves_every_result_field_and_original_allowance(
    kind: str, policy: CapPolicy, maximum_pairs: int, depth: int
) -> None:
    """
    Match strict witnesses, separation, pair/depth uncertainty and counters against uncached cell work.
    """
    source = _source(kind)
    arguments = dict(maximum_pairs=maximum_pairs, maximum_depth=depth, cap_policy=policy)
    expected = contact.inspect_contact(source, **arguments)
    measured = contact.inspect_contact(
        source, **arguments, projection_reuse=contact.ProjectionReuse.CELLS
    )
    assert measured == expected and measured.pairs_checked <= maximum_pairs


@pytest.mark.parametrize("kind", ("touch", "folds"))
def test_repeated_cells_avoid_actual_preparation_calls_without_omitting_pairs(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """
    Count actual cell and strict-point work independently of unchanged proof comparisons.
    """
    source = _source(kind)
    for placed in source.pieces:
        placed.end_pose()
    clip = Mock(wraps=contact.clip_profile)
    cap = Mock(wraps=contact.cap_region)
    inverse = Mock(wraps=contact.occupied_coordinates)
    profile = Mock(wraps=contact.profile_height)
    original_surface = cast(
        Callable[[PlacedPiece, float, float], tuple[Vector3, Vector3, Vector3, Vector3]],
        PlacedPiece.surface,
    )
    samples: list[tuple[PlacedPiece, float, float]] = []

    def surface(
        piece: PlacedPiece, u: float, q: float
    ) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Observe exact surface calls while leaving positions and derivatives unmodified.
        """
        samples.append((piece, u, q))
        return original_surface(piece, u, q)

    monkeypatch.setitem(vars(contact), "clip_profile", clip)
    monkeypatch.setitem(vars(contact), "cap_region", cap)
    monkeypatch.setitem(vars(contact), "occupied_coordinates", inverse)
    monkeypatch.setitem(vars(contact), "profile_height", profile)
    monkeypatch.setattr(PlacedPiece, "surface", surface)
    arguments = dict(maximum_pairs=512, cap_policy=CapPolicy.ANALYTIC_SUPPORT)
    expected = contact.inspect_contact(source, **arguments)
    original_counts = (clip.call_count, cap.call_count, len(samples))
    original_points = inverse.call_count, profile.call_count
    clip.reset_mock()
    cap.reset_mock()
    inverse.reset_mock()
    profile.reset_mock()
    samples.clear()
    measured = contact.inspect_contact(
        source, **arguments, projection_reuse=contact.ProjectionReuse.CELLS
    )
    counts = (clip.call_count, cap.call_count, len(samples))
    assert measured == expected
    assert counts[0] < original_counts[0] and counts[2] < original_counts[2]
    assert counts[1] <= original_counts[1]
    assert inverse.call_count < original_points[0] and profile.call_count < original_points[1]


def test_cache_hits_keep_cancellation_and_cannot_transfer_between_walks() -> None:
    """
    Check at resumed boundaries even when work is cached; another geometry owns a separate context.
    """
    interrupted = False

    def checkpoint() -> None:
        """
        Preserve hard caller cancellation at an already suspended material traversal.
        """
        if interrupted:
            raise InterruptedError("original cancellation")

    traversal = ContactTraversal(
        _source("touch"),
        maximum_pairs=128,
        checkpoint=checkpoint,
        projection_reuse=contact.ProjectionReuse.CELLS,
    )
    assert traversal.advance(1).limit == "pairs"
    interrupted = True
    with pytest.raises(InterruptedError, match="original cancellation"):
        traversal.advance(2)
    with pytest.raises(RuntimeError, match="cannot resume"):
        traversal.advance(128)
    clear = contact.inspect_contact(
        _source("clear"), maximum_pairs=128, projection_reuse=contact.ProjectionReuse.CELLS
    )
    overlap = contact.inspect_contact(
        _source("overlap"), maximum_pairs=128, projection_reuse=contact.ProjectionReuse.CELLS
    )
    assert clear.status == "separated" and overlap.status == "penetration"
