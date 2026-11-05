"""
Track confirmed crossing sheets through follow-up recovery without changing fold-contact rules.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from cable_bundler.routing.geometry import cross, unit
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, restore
from experiments.experiment_ribbon_feature_insertion.attached_regions import RegionPolicy
from experiments.experiment_ribbon_feature_insertion.contact_recovery import recover
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation, Side, regions
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.boundary import Boundary


@pytest.fixture(scope="module")
def crossing() -> tuple[Branch, ContactResult, FoldRoute, ContactResult]:
    """
    Reproduce the nine-conductor gym whose initial correction exposes a second straight crossing.
    """
    scene = Scene(
        Config(284829440, 9, 0.75, 300, 300),
        Goal.from_degrees(2, 7, 73),
        Goal.from_degrees(24, 1, 0),
    )
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    construction = construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, lambda e: None
    )
    branch, original = next(item for item in construction.rejected if item[0].roots == (1, 0))
    events: list[dict[str, Any]] = []
    recover(
        branch.route,
        original,
        1447,
        1e-5,
        lambda: None,
        events.append,
        maximum_updates=2,
        region_policy=RegionPolicy.ATTACHED_STRAIGHTS,
    )
    route = restore(next(e["route"] for e in events if e.get("iteration") == 1))
    measured = inspect_contact(route, maximum_pairs=1024)
    assert measured.status == "penetration" and measured.witness is not None
    assert measured.witness.pieces == (3, 7)
    return branch, original, route, measured


def test_crossing_plane_follows_material_while_explicit_axes_remain_fixed(
    crossing: tuple[Branch, ContactResult, FoldRoute, ContactResult],
) -> None:
    """
    Differentiate the complete moving plane rather than its frozen initial world normal.
    """
    _, _, route, measured = crossing
    model = MovableBends(route)
    initial = Separation.from_measurement(model, route, measured)
    assert initial is not None and initial.plane is None
    bound = Separation.following_measurement(model, route, measured)
    assert bound is not None and bound.plane == regions(route)[3]
    values = list(model.initial)
    values[1] -= 0.01
    changed = tuple(values)
    pieces = model.pieces(changed)
    normal = unit(cross(pieces[3].pose.tangent, pieces[3].pose.width))
    frozen_at_changed_pose = replace(bound, axis=normal, plane=None)
    frozen_at_original_pose = replace(bound, plane=None)
    for side in Side:
        assert bound.gap(changed, side) == pytest.approx(
            frozen_at_changed_pose.gap(changed, side), abs=1e-12
        )
    assert (
        abs(bound.gap(changed, Side.BEFORE) - frozen_at_original_pose.gap(changed, Side.BEFORE))
        > 1e-6
    )


def test_fold_contact_keeps_its_existing_world_axis(
    crossing: tuple[Branch, ContactResult, FoldRoute, ContactResult],
) -> None:
    """
    Preserve the established initial fold correction instead of broadening the new crossing rule.
    """
    branch, original, _, _ = crossing
    bound = Separation.following_measurement(MovableBends(branch.route), branch.route, original)
    assert bound is not None and bound.plane is None


def test_undecided_follow_up_never_invents_a_moving_crossing(
    crossing: tuple[Branch, ContactResult, FoldRoute, ContactResult],
) -> None:
    """
    Preserve unresolved depth and pair-limit evidence instead of claiming a confirmed crossing.
    """
    _, _, route, measured = crossing
    model = MovableBends(route)
    for limit in ("pairs", "depth"):
        undecided = replace(measured, status="unresolved", witness=None, limit=limit)
        assert Separation.following_measurement(model, route, undecided) is None


def test_follow_up_crossing_recovers_with_the_original_shared_allowance(
    crossing: tuple[Branch, ContactResult, FoldRoute, ContactResult],
) -> None:
    """
    Certify the compact branch only after both actual crossings clear within four updates.
    """
    branch, original, _, _ = crossing
    result = recover(
        branch.route,
        original,
        1447,
        1e-5,
        lambda: None,
        lambda e: None,
        region_policy=RegionPolicy.ATTACHED_STRAIGHTS,
    )
    assert result.route is not None and result.contact is not None
    assert result.contact.status == "separated" and result.route.material_length_mm < 100
    assert result.detail["iterations"] == 4 and result.contacts == 2
    assert 0 < result.pairs <= 1447 and result.detail["cpu_seconds"] <= 0.35
    assert result.route.targets == branch.route.targets
    assert result.route.radius_mm == branch.route.radius_mm
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
