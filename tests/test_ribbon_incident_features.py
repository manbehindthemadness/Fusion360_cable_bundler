"""
Verify complete actual feature coverage and unused-work incident continuation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_feature_insertion.separation import Region
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import feature_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    FeatureEvidence,
    IncidentGuidance,
    RetainedFeatures,
    member_planes,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import (
    FeatureCoverage,
    FeaturePlane,
    SignedJoints,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("occupied", (False, True))
def test_complete_internal_feature_keeps_both_actual_adjoining_runways(occupied: bool) -> None:
    """
    Cover occupied neighboring material without inventing absent slabs or mating terminal straights.
    """
    source = _route(
        (
            Straight(2),
            fold(2, 1.2, 0.8, 0.2, 0),
            *((Straight(3),) if occupied else ()),
            fold(2, 1.2, -0.9, -0.3, 0),
            *((Straight(4),) if occupied else ()),
            fold(2, 1.2, 0.6, 0.1, 0),
            Straight(5),
        )
    )
    model = SignedJoints(source)
    report = Report(
        "blocked",
        1,
        Witness("start", 3 if occupied else 2, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0)),
    )
    plane = FeaturePlane.create(
        model,
        source,
        report,
        Hardware.create(source.targets, Dimensions.scaled(source.targets)),
        model.initial,
        coverage=FeatureCoverage.ADJOINING_INTERNAL,
    )
    assert plane is not None
    assert set(plane.members) == (
        {Region(1, False), Region(1, True), Region(2, True)} if occupied else {Region(1, False)}
    )
    parts = member_planes([plane, plane], model, model.initial)
    assert {p.reference for p in parts} == set(plane.members)
    assert len(parts) == len(plane.members)
    assert all(p.members == (p.reference,) and p.model is model for p in parts)


@pytest.mark.parametrize("status", ("clear", "unresolved"))
def test_incident_guidance_requires_actual_intrusion(status: str) -> None:
    """
    Incomplete or cleared measurement does not authorize a reflected action.
    """
    source = _route((Straight(2),))
    with pytest.raises(ValueError, match="actual intrusion"):
        IncidentGuidance(0, (FeatureEvidence(source, Report(status, 1)),))


@pytest.mark.parametrize("status", ("clear", "unresolved"))
def test_retained_features_require_actual_intrusion(status: str) -> None:
    """
    Continuing without reflection still requires immutable demonstrated hardware evidence.
    """
    source = _route((Straight(2),))
    with pytest.raises(ValueError, match="actual intrusion"):
        RetainedFeatures((FeatureEvidence(source, Report(status, 1)),))


def test_successful_original_action_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve every already accepted legacy feature result without adding incident work.
    """
    source = _route((Straight(2),))
    answer = Result(source, ContactResult("separated", 1), {})
    monkeypatch.setitem(vars(feature_recovery), "recover_fold", Mock(return_value=answer))
    child = Mock(side_effect=AssertionError("No renewed work"))
    monkeypatch.setitem(vars(feature_recovery), "recover_joints", child)
    result = feature_recovery.recover(
        source,
        Report("unresolved", 1),
        Mock(spec=Gate),
        lambda: None,
        lambda e: None,
        maximum_length_mm=3,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is answer
    child.assert_not_called()


def test_retained_case_uses_one_fresh_witness_and_only_unused_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The signed-preset case2 correction keeps caps, all earlier reports and the original shared limits.
    """
    scene = Scene(
        Config(871963558, 2, 0.75, 300, 300),
        Goal.from_degrees(9, 0, 284),
        Goal.from_degrees(23, 8, 322),
    )
    calls: list[dict[str, Any]] = []
    original = feature_recovery.recover_joints

    def recorded(route: FoldRoute, *args: Any, **kwargs: Any) -> Result | None:
        """
        Observe real child allocation without substituting any physical certificate.
        """
        calls.append(kwargs)
        return original(route, *args, **kwargs)

    monkeypatch.setitem(vars(feature_recovery), "recover_joints", recorded)
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda e: None
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    detail = result.detail["construction"]["recovery"]
    before = detail["before_coupled_incident"]
    assert before["iterations"] == 2 and before["newton_steps"] == 12
    assert len(calls) == 1 and calls[0]["maximum_updates"] == 2
    guidance = calls[0]["mode"]
    assert isinstance(guidance, IncidentGuidance) and guidance.selected_fold == 2
    assert len(guidance.evidence) == 3
    assert all(
        e.report.status == "blocked" and e.route.targets == scene.targets for e in guidance.evidence
    )
    assert 0 < calls[0]["maximum_cpu_seconds"] < 0.35
    assert 0 < calls[0]["maximum_seconds"] < 2
    assert calls[0]["remaining_pairs"] + before["contact_pairs"] == 1739
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["contact_pairs"] <= 1739 and detail["cpu_seconds"] <= 0.35
    assert result.route.material_length_mm < detail["maximum_length_mm"]
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10


def test_failed_unmoved_reflection_can_retain_three_features_without_renewing_work() -> None:
    """
    Preserve the case116 mating caps while continuing only after measured linear reflection failure.
    """
    scene = Scene(
        Config(2993953655, 10, 0.75, 300, 300),
        Goal.from_degrees(7, 7, 75),
        Goal.from_degrees(10, 2, 50),
    )
    records: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, records.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    detail = result.detail["construction"]["recovery"]
    unmoved = detail["before_unmoved_incident"]
    assert unmoved["stop_reason"] == "linear_projection_infeasible"
    assert unmoved["iterations"] == unmoved["newton_steps"] == 0
    assert detail["before_coupled_incident"]["iterations"] == 2
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["cpu_seconds"] < 0.35 and detail["contact_pairs"] <= 2048
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    handoffs = [event for event in records if event.get("stage") == "coupled_retained_handoff"]
    assert len(handoffs) == 1 and handoffs[0]["remaining_updates"] == 2
    assert handoffs[0]["feature_reports"] == 3
