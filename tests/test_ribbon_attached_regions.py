"""
Keep attached-feature constraints tied to actual material intersections and stable region identities.
"""

from __future__ import annotations

from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_contraction.runner import restore
from experiments.experiment_ribbon_feature_insertion.attached_regions import (
    continues_feature,
    with_attached_straights,
)
from experiments.experiment_ribbon_feature_insertion.separation import Region, Separation
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.straight_witness import straight_witness
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from tests.test_fold_contact import _route


def test_straight_witness_is_a_shared_actual_material_interior_point() -> None:
    """
    Verify one oblique midplane crossing without interpreting parallel or separated sheets as clearance.
    """
    a = PlacedPiece(Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(10), "a")
    b = PlacedPiece(Pose(Vector3(5, 0, -5), Vector3(0, 0, 1), Vector3(0, 1, 0)), Straight(10), "b")
    route = _route(a, b)
    witness = straight_witness(route, 0, 1)
    assert witness is not None and witness.pieces == (0, 1)
    assert all(
        occupied_coordinates(p, witness.point, route.targets.lines, route.targets.diameter_mm)
        is not None
        for p in route.pieces
    )
    parallel = PlacedPiece(
        Pose(Vector3(0, 0, 0.5), a.pose.tangent, a.pose.width), Straight(10), "parallel"
    )
    assert straight_witness(_route(a, parallel), 0, 1) is None
    with pytest.raises(ValueError, match="distinct ordered"):
        straight_witness(route, 0, 0)


@pytest.mark.skip(reason="Archived gym layout retired under fresh-input validation policy")
def test_confirmed_attached_straight_changes_the_whole_feature_correction() -> None:
    """
    Clear the fold and its crossing attached runway under original contact/cap/material limits.
    """
    scene = Scene(
        Config(2945237171, 8, 0.75, 300, 300),
        Goal(2, 3, roll_degrees=12),
        Goal(15, 1, roll_degrees=53),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(scene.targets, Settings(0), lambda: None, events.append)
    assert result.route is not None and result.detail["contact"] == "separated"
    assert result.route.material_length_mm < 120
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    recovery = result.detail["construction"]["recovery"]
    assert recovery["accepted_improvement"] is True and recovery["iterations"] <= 4
    assert result.detail["construction"]["contact_pairs"] <= 2048
    branch_event = next(
        e
        for e in events
        if e.get("stage") == "feature_contact"
        and e.get("status") == "penetration"
        and e["roots"] == (0, 1)
    )
    route = restore(branch_event["route"])
    measurement = inspect_contact(route, maximum_pairs=1024)
    bound = Separation.from_measurement(MovableBends(route), route, measurement)
    assert bound is not None
    expanded = with_attached_straights(bound, route, measurement)
    assert expanded.extra_regions and expanded.pair == bound.pair
    assert expanded.model.original is route


@pytest.mark.parametrize("side", (0, 1))
@pytest.mark.parametrize("slot", (2, 3))
def test_fold_contact_can_continue_to_either_attached_slot(side: int, slot: int) -> None:
    """
    Match stable material regions in either contact order without changing the opposing identity.
    """
    before = (Region(2, False), Region(5, True))
    after = (Region(slot, True), before[1])
    if side:
        before, after = (before[1], before[0]), (after[1], after[0])
    assert continues_feature(before, after) and continues_feature(after, before)


@pytest.mark.parametrize(
    "after",
    (
        (Region(4, True), Region(5, True)),
        (Region(2, True), Region(6, True)),
        (Region(3, False), Region(5, True)),
    ),
)
def test_unrelated_contact_regions_still_require_handoff(after: tuple[Region, Region]) -> None:
    """
    Reject separate straight slots, distinct folds and changes to both interacting material sides.
    """
    before = (Region(2, False), Region(5, True))
    assert not continues_feature(before, after)
    assert continues_feature(before, before)
