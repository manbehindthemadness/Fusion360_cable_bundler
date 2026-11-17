"""
Separate sampled construction risk from numerical acceptance and operational errors.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from artifacts.verification.resume3148 import admission
from experiments.experiment_ribbon_complete_gym.readiness import ConstructionReadiness
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from tests.test_ribbon_complete_execution import checkpoint


@pytest.mark.parametrize("scope", list(admission.Scope))
@pytest.mark.parametrize("distance", [0.0, 9.401142965215215e-7, 1e-5, 2e-5])
def test_risk_is_measured_once_and_never_vetoes_a_proposal(
    monkeypatch: pytest.MonkeyPatch, scope: admission.Scope, distance: float
) -> None:
    """
    Every admission boundary retains raw near-support evidence without modifying a route.
    """
    route = cast(FoldRoute, object())
    calls = []
    witness = {"minimum_support_distance_mm": distance, "piece": 3, "profile": "top-1"}

    def exposure(source: FoldRoute, check: Callable[[], None]) -> list[dict[str, Any]]:
        """
        Record the exact caller-owned proposal and checkpoint at the diagnostic boundary.
        """
        calls.append((source, check))
        return [witness]

    monkeypatch.setitem(admission.__dict__, "exposure", exposure)
    events = []
    assert ConstructionReadiness(1e-5).accepts(route, checkpoint, events.append, scope)
    assert calls == [(route, checkpoint)]
    if distance > 1e-5:
        assert not events
    else:
        assert len(events) == 1
        event = events[0]
        assert event["status"] == "construction_warning"
        assert event["screen_status"] == "proposal_declined"
        assert event["witness"] is witness
        assert event["point_tolerance_mm"] == 1e-5 and event["scope"] == scope.value
        assert "unverified" in event["claim"]


@pytest.mark.parametrize("boundary", ["checkpoint", "measurement", "recorder"])
def test_advisory_policy_does_not_swallow_operational_failures(
    monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """
    Resource, measurement and recording errors still interrupt the caller unchanged.
    """
    failure = RuntimeError(boundary)

    def check() -> None:
        """
        Emulate the existing caller's resource stop without adding another budget.
        """
        if boundary == "checkpoint":
            raise failure

    def exposure(_source: FoldRoute, _check: Callable[[], None]) -> list[dict[str, Any]]:
        """
        Return one warning witness unless measurement itself failed.
        """
        if boundary == "measurement":
            raise failure
        return [{"minimum_support_distance_mm": 0.0}]

    def record(_event: dict[str, Any]) -> None:
        """
        Propagate a failed evidence write instead of accepting unrecorded risk.
        """
        if boundary == "recorder":
            raise failure

    monkeypatch.setitem(admission.__dict__, "exposure", exposure)
    with pytest.raises(RuntimeError) as caught:
        ConstructionReadiness(1e-5).accepts(
            cast(FoldRoute, object()), check, record, admission.Scope.FINAL
        )
    assert caught.value is failure
