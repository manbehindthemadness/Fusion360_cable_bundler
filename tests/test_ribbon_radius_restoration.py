"""
Restore a terminal return within unused work without losing material identity or widening physical rules.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import radius_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_contact import JointMode
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import jacobian
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.radius_model import RadiusJoints
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def source() -> FoldRoute:
    """
    Keep a two-fold analytical control with different radius anchors and turn signs.
    """
    return _route((fold(2, 1.2, 1, 0.2, 0), Straight(3), fold(3, 1.2, -1, -0.3, 0), Straight(4)))


def _radii(route: FoldRoute) -> tuple[float, ...]:
    """
    Read actual ordered construction radii independently of the model's parameter slots.
    """
    return tuple(
        piece.geometry.radius_mm
        for piece in route.pieces
        if isinstance(piece.geometry, CylindricalFold)
    )


@pytest.mark.parametrize("selected", (0, 1))
def test_only_selected_radius_can_grow_without_changing_material_floor(
    source: FoldRoute, selected: int
) -> None:
    """
    Keep every other radius, profile and sign while exposing one additional physical coordinate.
    """
    model = RadiusJoints(source, selected)
    radius = next(i for i, full in enumerate(model.indices) if full % 4 == 3)
    values = list(model.initial)
    assert model.bounds(radius)[0] == _radii(source)[selected] / model.scale
    values[radius] += 0.25 / model.scale
    result = model.route(tuple(values))
    assert result is not None
    expected = list(_radii(source))
    expected[selected] += 0.25
    assert _radii(result) == pytest.approx(expected)
    assert result.radius_mm == source.radius_mm and result.targets is source.targets
    assert model.preserves(result) and model.admissible(tuple(values))
    assert len(model.initial) == len(SignedJoints(source).initial) + 1
    other = RadiusJoints(source, 1 - selected)
    changed = list(other.initial)
    other_radius = next(i for i, full in enumerate(other.indices) if full % 4 == 3)
    changed[other_radius] += 0.25 / other.scale
    incompatible = other.route(tuple(changed))
    assert incompatible is not None and not model.preserves(incompatible)
    values[radius] = model.initial[radius] - 0.25 / model.scale
    assert not model.admissible(tuple(values))


@pytest.mark.parametrize("selected", (-1, 2, True))
def test_radius_joint_requires_an_existing_fold(source: FoldRoute, selected: int) -> None:
    """
    Reject malformed event selection instead of silently releasing another radius.
    """
    with pytest.raises(ValueError, match="existing incident fold"):
        RadiusJoints(source, selected)


def test_domain_aware_derivative_uses_one_valid_side_without_more_equation_calls(
    source: FoldRoute,
) -> None:
    """
    Keep a near-zero surviving fold out of an invalid zero-angle probe.
    """
    model = SignedJoints(source)
    angle = next(i for i, full in enumerate(model.indices) if full % 4 == 1)
    values = list(model.initial)
    values[angle] = 1e-6
    current = tuple(values)
    calls: list[tuple[float, ...]] = []

    def equations(probe: tuple[float, ...]) -> tuple[float, ...]:
        """
        Fail if a derivative tries to measure a vanished original material region.
        """
        assert model.admissible(probe)
        calls.append(probe)
        return (probe[angle] ** 2,)

    result = jacobian(
        model,
        current,
        equations,
        1,
        set(range(len(values))) - {angle},
        lambda: None,
        admissible=model.admissible,
    )
    assert len(calls) == 2 and calls[0] == current
    assert calls[1][angle] == pytest.approx(1.1e-5)
    assert result[0][angle] == pytest.approx(1.2e-5)
    invalid = list(current)
    invalid[angle] = 0.0
    assert not model.admissible(tuple(invalid))
    with pytest.raises(ArithmeticError, match="base is outside"):
        jacobian(
            model, tuple(invalid), equations, 1, set(), lambda: None, admissible=model.admissible
        )


def _previous(source: FoldRoute, **changes: Any) -> Result:
    """
    Describe completed, unsuccessful work without granting another allocation.
    """
    detail = {
        "status": "unresolved",
        "stop_reason": "fold_boundary",
        "iterations": 3,
        "newton_steps": 9,
        "contacts": 1,
        "contact_pairs": 100,
        "contact_seconds": 0.01,
        **changes,
    }
    return Result(source, None, detail)


def _continue(
    source: FoldRoute,
    previous: Result,
    checkpoint: Callable[[], None] = lambda: None,
    *,
    trigger: radius_recovery.RadiusTrigger = radius_recovery.RadiusTrigger.FOLD_DOMAIN,
) -> Result | None:
    """
    Supply one original allocation and unchanged source/evidence to the continuation boundary.
    """
    evidence = Report("blocked", 1, Witness("start", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)))
    return radius_recovery.continue_after_boundary(
        source,
        evidence,
        Mock(spec=Gate),
        checkpoint,
        lambda event: None,
        previous,
        maximum_length_mm=20,
        minimum_straight_mm=1e-5,
        remaining_pairs=600,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        cpu_started=10,
        started=20,
        trigger=trigger,
    )


@pytest.mark.parametrize("trigger", tuple(radius_recovery.RadiusTrigger))
def test_boundary_continuation_deducts_and_combines_all_work(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    trigger: radius_recovery.RadiusTrigger,
) -> None:
    """
    Give three completed updates only one remaining update and preserve every previous counter.
    """
    monkeypatch.setitem(vars(radius_recovery), "process_time", lambda: 10.1)
    monkeypatch.setitem(vars(radius_recovery), "perf_counter", lambda: 20.4)
    answer = Result(
        source,
        ContactResult("separated", 5),
        {
            "status": "separated",
            "iterations": 1,
            "newton_steps": 4,
            "contacts": 1,
            "contact_pairs": 5,
            "contact_seconds": 0.02,
        },
    )
    called = Mock(return_value=answer)
    monkeypatch.setitem(vars(radius_recovery), "recover", called)
    quality_fields = (
        {
            "method": "constrained_straight_feature",
            "length_ceiling_released": True,
            "fixed_reversal_declined": {"stop_reason": "linear_trust_budget"},
        }
        if trigger is radius_recovery.RadiusTrigger.RELEASED_QUALITY
        else {}
    )
    previous = _previous(source, stop_reason=trigger.value, **quality_fields)
    result = _continue(source, previous, trigger=trigger)
    assert result is not None and result.contact is answer.contact
    options = called.call_args.kwargs
    assert options["maximum_updates"] == 1 and options["remaining_pairs"] == 500
    assert options["maximum_cpu_seconds"] == pytest.approx(0.25)
    assert options["maximum_seconds"] == pytest.approx(1.6)
    assert options["mode"] is JointMode.RADIUS_RESTORATION
    assert result.detail["iterations"] == 4 and result.detail["newton_steps"] == 13
    assert result.detail["contact_pairs"] == 105 and result.detail["contacts"] == 2
    assert result.detail["before_radius"] == previous.detail
    assert previous.detail["iterations"] == 3


@pytest.mark.parametrize(
    "changes",
    (
        {"length_ceiling_released": False},
        {"length_ceiling_released": None},
        {"fixed_reversal_declined": None},
        {"fixed_reversal_declined": {"stop_reason": "phase_budget"}},
        {"method": "coupled_feature_planes"},
    ),
)
def test_radius_quality_handoff_requires_both_actual_failed_actions(
    source: FoldRoute, monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    """
    A generic stall or malformed history cannot release an incident radius through this trigger.
    """
    forbidden = Mock(side_effect=AssertionError("Missing actual released-quality history"))
    monkeypatch.setitem(vars(radius_recovery), "recover", forbidden)
    detail = {
        "stop_reason": "joint_no_descent",
        "method": "constrained_straight_feature",
        "length_ceiling_released": True,
        "fixed_reversal_declined": {"stop_reason": "linear_trust_budget"},
        **changes,
    }
    assert (
        _continue(
            source,
            _previous(source, **detail),
            trigger=radius_recovery.RadiusTrigger.RELEASED_QUALITY,
        )
        is None
    )
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    (
        {"status": "separated"},
        {"stop_reason": "phase_budget"},
        {"stop_reason": "joint_no_descent"},
        {"stop_reason": "linear_closure_infeasible"},
        {"iterations": 4},
        {"iterations": True},
        {"contact_pairs": 600},
    ),
)
def test_unsupported_or_exhausted_work_cannot_start_radius_recovery(
    source: FoldRoute, monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    """
    Do not turn another failure, malformed counters or spent work into a fresh solver phase.
    """
    forbidden = Mock(side_effect=AssertionError("No allocation remains"))
    monkeypatch.setitem(vars(radius_recovery), "recover", forbidden)
    assert _continue(source, _previous(source, **changes)) is None
    forbidden.assert_not_called()


def test_hard_caller_stop_still_propagates(source: FoldRoute) -> None:
    """
    Preserve cancellation and outer resource errors instead of treating them as optional failure.
    """

    def stopped() -> None:
        """
        Represent the caller's hard scheduling boundary.
        """
        raise TimeoutError("caller stop")

    with pytest.raises(TimeoutError, match="caller stop"):
        _continue(source, _previous(source), stopped)


def test_proof_completion_cannot_accept_after_the_shared_cpu_deadline(
    source: FoldRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Retain measured work but decline a nominally clear child that finishes after the original allocation.
    """
    clock = iter((10.1, 10.36))
    monkeypatch.setitem(vars(radius_recovery), "process_time", lambda: next(clock))
    monkeypatch.setitem(vars(radius_recovery), "perf_counter", lambda: 20.4)
    answer = Result(
        source,
        ContactResult("separated", 5),
        {
            "status": "separated",
            "iterations": 1,
            "newton_steps": 4,
            "contacts": 1,
            "contact_pairs": 5,
            "contact_seconds": 0.02,
        },
    )
    monkeypatch.setitem(vars(radius_recovery), "recover", Mock(return_value=answer))
    result = _continue(source, _previous(source))
    assert result is not None and result.contact is None and result.route is source
    assert result.detail["status"] == "unresolved"
    assert result.detail["stop_reason"] == "phase_budget"
    assert result.detail["contact_pairs"] == 105


@pytest.mark.skip(
    reason="Historical layout retired; geometry qualification uses fresh unique inputs"
)
def test_solver_restores_the_boundary_case_with_original_total_work() -> None:
    """
    Grow the implicated tight bend rather than erase a fold, flip another sign or move a cap.
    """
    scene = Scene(
        Config(4080537969, 2, 0.75, 300, 300),
        Goal.from_degrees(19, 8, 32),
        Goal.from_degrees(6, 4, 32),
    )
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda event: None
    )
    assert result.route is not None
    route = result.route
    recovery = result.detail["construction"]["recovery"]
    assert recovery["radius_restoration"]
    assert recovery["before_radius"]["stop_reason"] == "fold_boundary"
    assert recovery["iterations"] == 4 and recovery["newton_steps"] == 13
    assert recovery["before_radius"]["iterations"] == 3
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert cap_error(route) < 1e-10 and material_error(route) < 1e-10
    assert _radii(route)[0] > route.radius_mm
    assert all(radius == route.radius_mm for radius in _radii(route)[1:])
    assert route.material_length_mm == pytest.approx(18.052209020594397, abs=1e-7)
    assert result.detail["quality"]["first_pass_outcome"] == "feasibility_repaired"
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    assert inspect(route, hardware).status == "clear"


@pytest.mark.parametrize("status", ("penetration", "unresolved"))
@pytest.mark.skip(
    reason="Historical layout retired; geometry qualification uses fresh unique inputs"
)
def test_radius_restoration_cannot_bypass_full_self_contact(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Decline the otherwise successful radius change when the unchanged whole-volume certificate fails.
    """
    from experiments.experiment_ribbon_terminal_hardware import joint_contact

    contact = Mock(return_value=ContactResult(status, 1))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", contact)
    scene = Scene(
        Config(4080537969, 2, 0.75, 300, 300),
        Goal.from_degrees(19, 8, 32),
        Goal.from_degrees(6, 4, 32),
    )
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda event: None
    )
    assert result.route is None
    contact.assert_called_once()


@pytest.mark.skip(
    reason="Historical layout retired; geometry qualification uses fresh unique inputs"
)
def test_infeasible_fixed_reflection_can_grow_only_its_incident_radius_with_unused_work() -> None:
    """
    Preserve case103 caps/material/contact while extending the existing restoration to its explicit limit.
    """
    scene = Scene(
        Config(2433123344, 5, 0.75, 300, 300),
        Goal.from_degrees(23, 8, 1),
        Goal.from_degrees(9, 3, 30),
    )
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda event: None
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    detail = result.detail["construction"]["recovery"]
    assert detail["radius_restoration"]
    assert detail["before_radius"]["stop_reason"] == "linear_closure_infeasible"
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["cpu_seconds"] < 0.35 and detail["contact_pairs"] <= 2048
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    radii = [
        piece.geometry.radius_mm
        for piece in result.route.pieces
        if isinstance(piece.geometry, CylindricalFold)
    ]
    assert all(radius >= result.route.radius_mm for radius in radii)
    assert sum(radius > result.route.radius_mm for radius in radii) == 1


def _second_feature_targets() -> Targets:
    """
    Replay exact Fusion-authored N1/4056488310 poses, A4/9/311 and B19/2/2.
    """
    return Targets(
        name="Rubik gym preview",
        start=Vector3(-1.6051988706373195, -0.00609697964386321, -0.5975880092851172),
        end=Vector3(2.046971344925264, -2.7141160774438755, 1.6346532248133048),
        start_tangent=Vector3(0.5257311121191336, -3.051817141297008e-17, -0.8506508083520399),
        end_tangent=Vector3(0.0, 0.8506508083520399, 0.5257311121191337),
        start_width=Vector3(-0.43811755475431635, 0.8571673007021122, -0.27077153990616054),
        end_width=Vector3(0.5591929034707469, -0.43585084500790916, 0.7052214812481591),
        lines=1,
        diameter_mm=0.75,
    )


@pytest.mark.skip(
    reason="Historical layout retired; geometry qualification uses fresh unique inputs"
)
def test_radius_restoration_retains_a_second_measured_hardware_feature() -> None:
    """
    Keep both actual intrusions active without renewing work or releasing another radius.
    """
    targets = _second_feature_targets()
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(targets, Settings(1, False, True, True), lambda: None, events.append)
    assert result.route is not None and result.route.targets == targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    recovery = result.detail["construction"]["recovery"]
    assert recovery["radius_restoration"] and recovery["selected_fold"] == 0
    assert recovery["before_radius"]["stop_reason"] == "linear_closure_infeasible"
    assert recovery["iterations"] <= 4 and recovery["newton_steps"] <= 24
    assert recovery["cpu_seconds"] < 0.35 and recovery["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert recovery["length_goal_excess_mm"] > 0
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
    assert _radii(result.route)[0] > result.route.radius_mm
    assert all(radius == result.route.radius_mm for radius in _radii(result.route)[1:])
    added = [event for event in events if event.get("status") == "hardware_constraint_added"]
    assert len(added) == 1 and added[0]["reference"]["straight"]
    hardware_reports = [
        event
        for event in events
        if event.get("stage") == "terminal_hardware"
        and event.get("phase") == "joint_flat_contact_final"
    ]
    assert [event["status"] for event in hardware_reports] == ["blocked", "clear"]
    hardware = Hardware.create(targets, Dimensions.scaled(targets))
    assert inspect(result.route, hardware).status == "clear"
