"""
Verify bounded recovery may improve a poor accepted fallback without losing its certificate.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, Policy
from experiments.experiment_ribbon_feature_insertion.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import branch_recovery, solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve
from tests.test_ribbon_aesthetic import _route


def _construction() -> tuple[Result, Frames, Branch]:
    """
    Keep exact shared caps while supplying controlled prior contact dispositions to the policy.
    """
    compact = _route((Straight(5), Straight(5)))
    angle = 0.5
    longer = _route(
        (
            fold(1, 1.2, angle, 0, 0),
            fold(1, 1.2, -angle, 0, 0),
            fold(1, 1.2, -angle, 0, 0),
            fold(1, 1.2, angle, 0, 0),
            Straight(10 - 4 * math.sin(angle)),
        )
    )
    longer = replace(longer, targets=compact.targets)
    frames = Frames.create(compact.targets)
    branch = Branch.measure((1, 1), compact, frames.guide)
    prior_failure = ContactResult(
        "penetration",
        224,
        witness=Penetration((0, 1), (0.5, 0, 0), (0.5, 0, 0), Vector3(5, 0, 0)),
    )
    result = Result(
        longer,
        None,
        "separated",
        3,
        0.01,
        3,
        0,
        ContactResult("separated", 904),
        1391,
        ((branch, prior_failure),),
    )
    return result, frames, branch


@pytest.mark.parametrize("outcome", ("shorter", "failed", "not_better"))
def test_recovery_uses_only_remaining_pool_and_rechecks_preferences(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Retain the safe fallback on failure or worsening while counting all spent work.
    """
    original, frames, branch = _construction()
    route = (
        branch.route
        if outcome == "shorter"
        else original.route
        if outcome == "not_better"
        else None
    )
    contact = ContactResult("separated", 123) if route is not None else None
    recovery = Recovery(
        route, contact, 123, 1, 0.02, {"status": "separated" if route else "unresolved"}
    )
    attempt = Mock(return_value=recovery)
    monkeypatch.setitem(vars(branch_recovery), "recover", attempt)
    events: list[dict[str, Any]] = []
    result, detail = branch_recovery.recover_construction(
        original,
        frames,
        1e-5,
        lambda: None,
        events.append,
        selection_policy=Policy.MONOTONIC,
    )
    assert attempt.call_args.args[0] is branch.route
    assert attempt.call_args.args[2] == 657
    assert attempt.call_args.kwargs["cap_policy"] is CapPolicy.ANALYTIC_SUPPORT
    assert 0 < attempt.call_args.kwargs["maximum_cpu_seconds"] <= 0.35
    assert 0 < attempt.call_args.kwargs["maximum_seconds"] <= 2.0
    assert result.contact_pairs == 1514 and result.contacts == 4
    assert result.contact_seconds == pytest.approx(0.03)
    assert detail is not None and detail["accepted_improvement"] is (outcome == "shorter")
    assert detail["cap_support_policy"] == "analytic_support"
    if outcome == "shorter":
        assert result.route is branch.route and result.contact is contact
        assert events[-1]["status"] == "improved"
    else:
        assert result.route is original.route and result.contact is original.contact
        assert events[-1]["status"] == "baseline_retained"


@pytest.mark.parametrize("condition", ("disabled", "unmeasured", "exhausted", "worse_guide"))
def test_successful_routes_without_a_permitted_improvement_do_no_recovery_work(
    monkeypatch: pytest.MonkeyPatch, condition: str
) -> None:
    """
    Respect optimization controls, certificate provenance, guide ordering and the shared pool.
    """
    source, frames, branch = _construction()
    policy = Policy.MIDPOINT if condition == "disabled" else Policy.MONOTONIC
    if condition == "unmeasured":
        source = replace(source, contact=ContactResult("unresolved", 1024, limit="pairs"))
    elif condition == "exhausted":
        source = replace(source, contact_pairs=2048)
    elif condition == "worse_guide":
        branch = replace(branch, guide=replace(branch.guide, rms_mm=1e6))
        source = replace(source, rejected=((branch, source.rejected[0][1]),))
    attempt = Mock(side_effect=AssertionError("No permitted recovery"))
    monkeypatch.setitem(vars(branch_recovery), "recover", attempt)
    result, detail = branch_recovery.recover_construction(
        source,
        frames,
        1e-5,
        lambda: None,
        lambda event: None,
        selection_policy=policy,
    )
    assert result is source and detail is None
    attempt.assert_not_called()


def test_missing_recovered_certificate_is_a_hard_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Never turn a returned shape into separation evidence without the completed certificate.
    """
    source, frames, branch = _construction()
    attempt = Mock(return_value=Recovery(branch.route, None, 0, 0, 0, {}))
    monkeypatch.setitem(vars(branch_recovery), "recover", attempt)
    with pytest.raises(ArithmeticError, match="certificate"):
        branch_recovery.recover_construction(
            source,
            frames,
            1e-5,
            lambda: None,
            lambda event: None,
            selection_policy=Policy.MONOTONIC,
        )


def test_pair_limited_straight_overlap_can_use_existing_fallback_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain raw uncertainty while a verified thickness witness enables one bounded compact correction.

    Explicitly retain legacy initial measurement to exercise this fallback;
    current v2's optional probe can establish the penetration earlier.
    """
    original = solver_v2.construct

    def without_probe(*args: Any, **kwargs: Any) -> Result:
        """
        Exercise the retained no-probe constructor policy without changing physical checks.
        """
        kwargs["probe_order"] = None
        return original(*args, **kwargs)

    monkeypatch.setitem(vars(solver_v2), "construct", without_probe)
    scene = Scene(
        Config(2976634137, 7, 0.75, 300, 300),
        Goal.from_degrees(8, 7, 65),
        Goal.from_degrees(12, 1, 81),
    )
    events: list[dict[str, Any]] = []
    result = solve(scene.targets, Settings(1, False, True), lambda: None, events.append)
    assert result.route is not None and result.detail["contact"] == "separated"
    assert result.route.material_length_mm < 90
    raw = next(
        event
        for event in events
        if event.get("stage") == "feature_contact"
        and event.get("roots") == (1, 0)
        and "contact" in event
    )
    assert raw["contact"]["status"] == "unresolved" and raw["contact"]["limit"] == "pairs"
    assert raw["contact"]["pairs_checked"] == 1024
    evidence = next(event for event in events if event.get("status") == "confirmed_straight_core")
    assert evidence["roots"] == (1, 0) and evidence["witness"]["pieces"] == (2, 6)
    construction = result.detail["construction"]
    recovery = construction["recovery"]
    assert recovery["accepted_improvement"] and recovery["roots"] == (1, 0)
    assert recovery["iterations"] == recovery["contacts"] == 1
    assert 0 < recovery["pairs"] <= 483 and construction["contact_pairs"] <= 2048
    assert construction["closed_branches"] == 3
    assert result.route.targets == scene.targets
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10


def test_missed_core_witness_preserves_unsupported_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Do not admit a pair-limited branch when the exact common interior point is unavailable.
    """
    source, frames, branch = _construction()
    unresolved = ContactResult("unresolved", 1024, unresolved_pieces=(0, 1), limit="pairs")
    source = replace(source, rejected=((branch, unresolved),))
    monkeypatch.setitem(vars(branch_recovery), "core_witness", lambda *_args: None)
    attempt = Mock(side_effect=AssertionError("Unconfirmed evidence must stay unresolved"))
    monkeypatch.setitem(vars(branch_recovery), "recover", attempt)
    result, detail = branch_recovery.recover_construction(
        source, frames, 1e-5, lambda: None, lambda event: None, selection_policy=Policy.MONOTONIC
    )
    assert result is source and detail is None and source.rejected[0][1] is unresolved
    attempt.assert_not_called()
