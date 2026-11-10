"""
Keep contraction proposals compatible with actual ordered mating accuracy across length scales.
"""

from __future__ import annotations

from typing import Any

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import contract
from experiments.experiment_ribbon_contraction.runner import restore
from experiments.experiment_ribbon_fold_route.geometry import Pose, Straight, pose_error
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("scale", (1.0, 10.0, 1000.0))
def test_shortening_proposals_keep_actual_ordered_caps_at_mating_accuracy(scale: float) -> None:
    """
    Reject normalized-only stopping that lets physical position error grow with material length.
    """
    original = _route(
        (
            Straight(5 * scale),
            fold(2 * scale, 1.2, 1.0, 0.0, 0.0),
            Straight(3 * scale),
            fold(2 * scale, 1.2, -1.0, 0.0, 0.0),
            Straight(5 * scale),
        )
    )
    events: list[dict[str, Any]] = []
    result = contract(original, lambda: None, events.append)
    assert result.detail["status"] == "shortened"
    assert result.route.targets is original.targets
    assert result.route.material_length_mm < original.material_length_mm
    assert result.detail["iterations"] <= 4 and result.detail["contacts"] <= 2
    proposals = [restore(event["route"]) for event in events if event.get("route") is not None]
    assert proposals
    for proposal in proposals:
        target = original.targets
        errors = pose_error(
            proposal.pieces[0].pose, Pose(target.start, target.start_tangent, target.start_width)
        ) + pose_error(
            proposal.pieces[-1].end_pose(), Pose(target.end, target.end_tangent, target.end_width)
        )
        assert max(errors) < 1e-10
        assert proposal.targets == original.targets
