"""
Preserve original strict construction evidence when optional shortening loses hardware eligibility.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_feature_insertion.solve import Result as Construction
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.construction_fallback import retain_original
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from tests.test_ribbon_aesthetic import _route


def _result(
    route: FoldRoute | None, contact: ContactResult | None, status: str = "separated"
) -> Construction:
    """
    Bind a route to its own contact evidence without implying native coverage.
    """
    return Construction(
        route=route,
        allocation=None,
        status=status,
        contacts=1,
        contact_seconds=0.01,
        closed_branches=1,
        unattempted_contacts=0,
        contact=contact,
        contact_pairs=7,
    )


def test_restoration_returns_only_original_objects_without_changing_spent_work() -> None:
    """
    Keep route/certificate identity and measure actual baseline eligibility under the shared gate.
    """
    route = _route((Straight(2),))
    current_route = replace(_route((Straight(3),)), targets=route.targets)
    contact = ContactResult("separated", 7)
    original, current = (
        _result(route, contact),
        _result(current_route, ContactResult("separated", 11)),
    )
    terminal = Mock(spec=Gate)
    terminal.permits.return_value = True
    restored = retain_original(original, current, terminal)
    assert restored is not None and restored[0] is route and restored[1] is contact
    assert original.contact_pairs == current.contact_pairs == 7
    terminal.permits.assert_called_once_with(route, "original_construction_fallback")


@pytest.mark.parametrize(
    ("contact", "status"),
    (
        (None, "separated"),
        (ContactResult("unresolved", 1), "separated"),
        (ContactResult("penetration", 1), "separated"),
        (ContactResult("separated", 1), "unresolved"),
    ),
)
def test_incomplete_original_evidence_never_grants_hardware_or_contact_success(
    contact: ContactResult | None,
    status: str,
) -> None:
    """
    An actual strict separated construction is required before measuring or selecting a fallback.
    """
    route = _route((Straight(2),))
    current = replace(_route((Straight(3),)), targets=route.targets)
    terminal = Mock(spec=Gate)
    assert (
        retain_original(_result(route, contact, status), _result(current, contact), terminal)
        is None
    )
    terminal.permits.assert_not_called()


def test_missing_or_unchanged_original_route_does_not_repeat_existing_work() -> None:
    """
    A failed initial construction or identical current baseline cannot create another fallback action.
    """
    route = _route((Straight(2),))
    contact = ContactResult("separated", 7)
    terminal = Mock(spec=Gate)
    assert retain_original(_result(None, contact), _result(route, contact), terminal) is None
    assert retain_original(_result(route, contact), _result(route, contact), terminal) is None
    terminal.permits.assert_not_called()


def test_hardware_rejection_and_caller_resource_errors_remain_authoritative() -> None:
    """
    No retained certificate can override blocked hardware or a hard checkpoint failure.
    """
    route = _route((Straight(2),))
    current = replace(_route((Straight(3),)), targets=route.targets)
    original, changed = _result(route, ContactResult("separated", 7)), _result(current, None)
    terminal = Mock(spec=Gate)
    terminal.permits.return_value = False
    assert retain_original(original, changed, terminal) is None
    terminal.permits.side_effect = TimeoutError("resource")
    with pytest.raises(TimeoutError, match="resource"):
        retain_original(original, changed, terminal)
    with pytest.raises(ValueError, match="same fixed targets"):
        retain_original(original, _result(_route((Straight(3),)), None), terminal)


def test_unsafe_optional_recovery_retains_original_physical_baseline_and_own_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Restore a hardware-clear initial construction after all optional updates were already spent.
    """
    scene = Scene(
        Config(3187744133, 1, 0.75, 300, 300),
        Goal.from_degrees(5, 8, 47),
        Goal.from_degrees(3, 9, 295),
    )
    captured: list[Construction] = []
    construct = solver_v2.construct

    def recorded(*args: Any, **kwargs: Any) -> Construction:
        """
        Retain the real initial immutable result without replacing any physical operation.
        """
        result = construct(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setitem(vars(solver_v2), "construct", recorded)
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda e: None
    )
    assert len(captured) == 1
    original = captured[0]
    assert result.route is original.route and result.route is not None
    assert result.first_pass is original.route and original.contact is not None
    assert result.detail["contact_measurement"] == asdict(original.contact)
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    assert result.detail["construction"]["recovery"]["iterations"] == 4
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert result.detail["construction"]["optional_selection"] == "declined_for_terminal_clearance"
    assert result.detail["final_contact_source"] == "hardware_safe_original_construction"
    quality = result.detail["quality"]
    assert quality["construction_length_mm"] == quality["final_length_mm"]
    assert quality["first_pass_outcome"] == "original_construction_retained"
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
