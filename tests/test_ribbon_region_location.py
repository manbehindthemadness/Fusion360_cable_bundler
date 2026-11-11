"""
Resolve stable material regions without traversing unused terminal-frame computations.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, cast
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import (
    Region,
    TopologyChanged,
    locate,
    regions,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from tests.test_ribbon_terminal_protection import _two_folds


@pytest.mark.parametrize("lead", (0.0, 2.0))
@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
def test_occupied_and_internal_absent_regions_need_no_terminal_frame_reads(
    monkeypatch: pytest.MonkeyPatch, lead: float, scale: float
) -> None:
    """
    Preserve actual occupied identity and absent leading-slab pose at every independently authored scale.
    """
    source = _two_folds(scale, -1.0, lead)
    end = Mock(side_effect=AssertionError("Region lookup does not need previous terminal frames"))
    monkeypatch.setattr(PlacedPiece, "end_pose", end)
    for piece, tag in zip(source.pieces, regions(source)):
        assert locate(source, source.pieces, tag) is piece
    if lead == 0:
        missing = locate(source, source.pieces, Region(0, True))
        assert missing.pose is source.pieces[0].pose
        assert missing.geometry == Straight(1e-12) and missing.label == "Absent-slot bound"
    end.assert_not_called()


def test_absent_trailing_slot_reads_only_actual_last_piece_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the exact final frame and conservative slab with one endpoint access after ordered lookup.
    """
    source = _two_folds(1.0, 1.0, 0.0)
    original = cast(Callable[[PlacedPiece], Pose], PlacedPiece.end_pose)
    expected = original(source.pieces[-1])
    visited: list[PlacedPiece] = []

    def measured(piece: PlacedPiece) -> Pose:
        """
        Count terminal accesses while retaining the unchanged actual endpoint evaluation.
        """
        visited.append(piece)
        return original(piece)

    monkeypatch.setattr(PlacedPiece, "end_pose", measured)
    missing = locate(source, source.pieces, Region(2, True))
    assert missing.pose is expected and missing.geometry == Straight(1e-12)
    assert missing.label == "Absent terminal-slot bound"
    assert visited == [source.pieces[-1]]


def test_empty_source_uses_start_frame_and_missing_fold_rejects_before_endpoint_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Empty material has its original start frame; changed fold identity remains a hard lookup error.
    """
    source = _two_folds(1.0, 1.0, 0.0)
    end = Mock(side_effect=AssertionError("Invalid or empty material has no terminal read"))
    monkeypatch.setattr(PlacedPiece, "end_pose", end)
    with pytest.raises(TopologyChanged, match="original ordered folds"):
        locate(source, source.pieces[:-1], Region(0, False))
    empty = replace(
        source,
        pieces=(PlacedPiece(source.pieces[0].pose, Straight(2), "Straight-only source"),),
    )
    missing = locate(empty, (), Region(0, True))
    assert missing.pose == Pose(
        empty.targets.start, empty.targets.start_tangent, empty.targets.start_width
    )
    with pytest.raises(TopologyChanged, match="unavailable"):
        locate(empty, (), Region(0, False))
    end.assert_not_called()
