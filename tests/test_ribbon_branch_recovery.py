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
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, Policy
from experiments.experiment_ribbon_feature_insertion.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import branch_recovery
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
    assert result.contact_pairs == 1514 and result.contacts == 4
    assert result.contact_seconds == pytest.approx(0.03)
    assert detail is not None and detail["accepted_improvement"] is (outcome == "shorter")
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
