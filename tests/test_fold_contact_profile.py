"""
Preserve occupied profile volume while pruning empty rectangular-envelope corners.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height
from experiments.experiment_ribbon_fold_route.contact_profile import clip_profile
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from tests.test_fold_route import CASES


@pytest.mark.parametrize("lines", (1, 3, 8, 12))
@pytest.mark.parametrize("diameter", (0.075, 0.75, 7.5))
def test_clipped_cells_enclose_each_occupied_profile_interval(lines: int, diameter: float) -> None:
    """
    Keep lobes, valleys, apices and side arcs at multiple profile sizes and counts.
    """
    half = lines * diameter / 2 + diameter / 10
    for index in range(31):
        low = -half + 2 * half * index / 31
        high = -half + 2 * half * (index + 1) / 31
        cell = Cell(2, Span(0.1, 0.9), Span(low, high), Span(-diameter, diameter), 5)
        clipped = clip_profile(cell, lines, diameter)
        assert clipped is not None
        assert replace(clipped, height=cell.height) == cell
        assert cell.height.low <= clipped.height.low <= clipped.height.high <= cell.height.high
        for sample in range(33):
            q = low + (high - low) * sample / 32
            height = profile_height(q, lines, diameter)
            assert clipped.height.low <= -height <= height <= clipped.height.high


@pytest.mark.parametrize(
    "q,height",
    (
        (Span(1.1537109375, 1.1542968750000002), Span(-0.28125, -0.280517578125)),
        (Span(-1.194140625, -1.1935546874999998), Span(-0.375, -0.374267578125)),
    ),
)
def test_depth_stalled_boxes_contain_no_joined_profile_material(q: Span, height: Span) -> None:
    """
    Discard the two empty cells recorded at the user's original depth-limit stop.
    """
    assert clip_profile(Cell(0, Span(0.25, 0.251), q, height, 36), 3, 0.75) is None


def test_full_profile_and_interior_boxes_preserve_the_original_envelope() -> None:
    """
    Leave unchanged cells intact when clipping cannot tighten their occupied extent.
    """
    for q, height in ((Span(-1.2, 1.2), Span(-0.375, 0.375)), (Span(0, 0), Span(-0.1, 0.1))):
        cell = Cell(0, Span(0, 1), q, height)
        assert clip_profile(cell, 3, 0.75) is cell


@pytest.mark.parametrize("gap,status", ((1.1, "separated"), (0.1, "penetration")))
def test_profile_tips_separate_without_waiving_real_overlap(gap: float, status: str) -> None:
    """
    Resolve overlapping outer rectangles using actual material, with fixed work limits.
    """
    first = PlacedPiece(
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(0.2), "a"
    )
    second = replace(first, pose=replace(first.pose, origin=Vector3(0, 4.7, gap)), label="b")
    route = FoldRoute(CASES[1], (first, second), 0.75 / 0.996)
    result = inspect_contact(route, maximum_pairs=1024, maximum_depth=36)
    assert result.status == status
    if status == "penetration":
        assert result.witness is not None
