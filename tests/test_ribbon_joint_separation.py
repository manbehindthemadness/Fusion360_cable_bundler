"""
Recover closed intersecting material plans only through bounded, independently certified joint motion.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion import contact_recovery
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import (
    Region,
    Separation,
    Side,
    TopologyChanged,
)
from experiments.experiment_ribbon_feature_insertion.separation_step import InitialStep, plan_step
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings


@pytest.fixture(scope="module")
def rejected() -> tuple[Branch, ContactResult]:
    """
    Recreate the fixed gym failure without depending on saved experiment artifacts.
    """
    scene = Scene(Config(1483650491, 6, 0.75, 300, 300), Goal(15, 1, 1), Goal(22, 3, 1))
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, lambda e: None
    )
    assert result.route is None and len(result.rejected) == 4
    assert all(contact.status == "penetration" for _, contact in result.rejected)
    return min(result.rejected, key=lambda item: item[0].priority)


def test_solver_recovers_with_original_caps_profile_radii_and_pair_pool(
    rejected: tuple[Branch, ContactResult],
) -> None:
    """
    Separate the failed material geometry without adding folds or accepting its original collision.
    """
    branch, _ = rejected
    rows: list[dict[str, Any]] = []
    result = solver_v2.solve(
        branch.route.targets, Settings(0, False, False), lambda: None, rows.append
    )
    assert result.route is not None and result.detail["contact"] == "separated"
    recovery = result.detail["construction"]["recovery"]
    assert recovery["status"] == "separated" and 1 <= recovery["iterations"] <= 4
    assert 0 < recovery["pairs"] <= 821 and recovery["contacts"] == 1
    assert result.detail["construction"]["contact_pairs"] == 1227 + recovery["pairs"] <= 2048
    assert result.detail["construction"]["contacts"] == 5
    selection = recovery["selection"]
    assert selection["status"] == "selected" and selection["roots"] != branch.roots
    assert recovery["cpu_seconds"] <= 0.35 and recovery["elapsed_seconds"] <= 2
    before = [p.geometry for p in branch.route.pieces if isinstance(p.geometry, CylindricalFold)]
    after = [p.geometry for p in result.route.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(before) == len(after) == 4
    assert [(f.radius_mm, f.width_mm) for f in after] == [(f.radius_mm, f.width_mm) for f in before]
    assert result.route.targets == branch.route.targets
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    assert any(
        r["stage"] == "joint_separation_recovery" and r["status"] == "separated" for r in rows
    )


def test_incomplete_contact_never_returns_the_rejected_baseline(
    rejected: tuple[Branch, ContactResult], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve pair-limit uncertainty even after a local separation constraint improves.
    """
    branch, measurement = rejected
    monkeypatch.setitem(
        vars(contact_recovery),
        "inspect_contact",
        Mock(return_value=ContactResult("unresolved", 821, limit="pairs")),
    )
    result = contact_recovery.recover(
        branch.route, measurement, 821, 1e-5, lambda: None, lambda e: None
    )
    assert result.route is None and result.contact is None
    assert result.pairs == 821 and result.contacts == 1


def test_only_local_budget_exhaustion_is_fail_soft(
    rejected: tuple[Branch, ContactResult], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain a numerical rejection on local exhaustion and propagate hard caller stops.
    """
    branch, measurement = rejected
    clock = iter((0.0, 0.4, 0.4))
    monkeypatch.setitem(vars(contact_recovery), "process_time", lambda: next(clock))
    result = contact_recovery.recover(
        branch.route, measurement, 821, 1e-5, lambda: None, lambda e: None
    )
    assert result.route is None and result.detail["stop_reason"] == "local_budget"
    assert result.contacts == result.pairs == 0


def test_hard_caller_stop_is_not_hidden(rejected: tuple[Branch, ContactResult]) -> None:
    """
    Stop immediately on source/resource/cancellation errors instead of treating them as recovery failure.
    """
    branch, measurement = rejected

    def stopped() -> None:
        """
        Model an outer hard deadline or cancellation guard.
        """
        raise TimeoutError("hard caller stop")

    with pytest.raises(TimeoutError, match="hard caller stop"):
        contact_recovery.recover(branch.route, measurement, 821, 1e-5, stopped, lambda e: None)


def test_absent_slot_bounds_never_add_geometry_or_rebind_a_vanished_fold(
    rejected: tuple[Branch, ContactResult],
) -> None:
    """
    Keep analysis-only zero-slot bounds distinct from the actual material topology.
    """
    branch, _ = rejected
    model = MovableBends(branch.route)
    original = model.pieces(model.initial)
    bound = Separation(model, (Region(1, True), Region(1, False)), original[0].pose.tangent)
    assert bound.gap(model.initial, Side.BEFORE) <= 0
    assert bound.gap(model.initial, Side.AFTER) <= 0
    assert model.pieces(model.initial) == original
    values = list(model.initial)
    values[1] = 0
    with pytest.raises(TopologyChanged):
        bound.gap(tuple(values), Side.BEFORE)


def test_cached_first_motion_reuses_exact_math_and_rejects_different_evidence(
    rejected: tuple[Branch, ContactResult], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Avoid repeating prediction derivatives without transferring them to any other source or witness.
    """
    branch, measurement = rejected
    model = MovableBends(branch.route)
    bound = Separation.from_measurement(model, branch.route, measurement)
    assert bound is not None
    planned = plan_step(model, model.initial, bound, None, lambda: None)
    assert planned is not None
    cached = InitialStep(branch.route, measurement, planned)
    baseline: list[dict[str, Any]] = []
    contact_recovery.recover(
        branch.route, measurement, 821, 1e-5, lambda: None, baseline.append, maximum_updates=1
    )
    forbidden = Mock(side_effect=AssertionError("First derivatives must not be recomputed"))
    monkeypatch.setitem(vars(contact_recovery), "plan_step", forbidden)
    events: list[dict[str, Any]] = []
    contact_recovery.recover(
        branch.route,
        measurement,
        821,
        1e-5,
        lambda: None,
        events.append,
        maximum_updates=1,
        initial_step=cached,
    )
    assert [row for row in events if "route" in row] == [row for row in baseline if "route" in row]
    assert any("route" in row for row in events)
    forbidden.assert_not_called()
    for route, evidence in (
        (replace(branch.route), measurement),
        (branch.route, replace(measurement)),
    ):
        with pytest.raises(ValueError, match="identical source and measurement"):
            contact_recovery.recover(
                route, evidence, 821, 1e-5, lambda: None, events.append, initial_step=cached
            )
