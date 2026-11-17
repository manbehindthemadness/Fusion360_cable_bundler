"""
Keep partial saved-plan audits distinct from geometry solving and complete acceptance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from experiments.experiment_ribbon_complete import qualification
from experiments.experiment_ribbon_complete.execution import prepare
from experiments.experiment_ribbon_locked_solver.solver import Result
from tests.test_ribbon_complete_execution import checkpoint, targets, trunk


def test_unresolved_trunk_cannot_become_a_measured_branch_result() -> None:
    """
    Missing complete geometry emits a reason without running downstream audits.
    """

    def unresolved(
        _targets: Any, _check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Retain an unsuccessful constructor result for the boundary test.
        """
        return Result(None, None, {"status": "unresolved"}, None)

    plan = prepare(targets(), unresolved, checkpoint, lambda row: None)
    rows = []
    qualification.inspect(plan, checkpoint, rows.append)
    assert rows == [
        {"gate": "branch_audits", "status": "not_attempted", "reason": "incomplete_plan"}
    ]


def test_failed_audit_retains_started_prefix_and_does_not_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A measurement interruption cannot turn the unattempted suffix into successful coverage.
    """
    plan = prepare(targets(), trunk, checkpoint, lambda row: None)
    rows = []

    def stop(*_args: Any) -> None:
        """
        Represent a caller-owned resource stop during the first audit.
        """
        raise RuntimeError("audit allocation exhausted")

    monkeypatch.setattr(qualification, "audit_bends", stop)
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        qualification.inspect(plan, checkpoint, rows.append)
    assert len(rows) == 1 and rows[0]["status"] == "started"
    assert rows[0]["route_id"] == str(plan.branches[0].source.source.leg.route_id)
