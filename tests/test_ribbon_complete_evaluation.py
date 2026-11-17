"""
Keep complete numerical testing separate from native and physical acceptance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_complete.evaluation import evaluate
from experiments.experiment_ribbon_complete.material_witnesses import WitnessWork
from experiments.experiment_ribbon_locked_solver.solver import Result
from tests.test_ribbon_complete_execution import checkpoint, targets, trunk


def test_trunk_exhaustion_leaves_all_endings_unattempted_without_measuring_or_retrying() -> None:
    """
    A complete case cannot pass by retaining the trunk's unsuccessful empty output.
    """
    calls = []

    def unresolved(
        t: Targets, _check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Return the original finite unsuccessful result once.
        """
        calls.append(t)
        return Result(None, None, {"status": "unresolved"}, None)

    source = targets()
    work = WitnessWork(32, checkpoint)
    result = evaluate(source, unresolved, work, 1, lambda event: None)
    assert calls == [source.trunk] and result.status == "trunk_unresolved"
    assert result.material is None and len(result.plan.unattempted_route_ids) == 4
    assert work.calls == 0


def test_absent_violation_witness_keeps_whole_ribbon_unqualified() -> None:
    """
    Prepared native-ready geometry with small ending bounds still has missing physical checks.
    """
    events = []
    source = targets()
    expected_calls = 2 * sum(len(branch.controls) + 1 for branch in source.branches)
    work = WitnessWork(expected_calls, checkpoint)
    result = evaluate(source, trunk, work, 1, events.append)
    assert result.status == "unqualified" and result.material is not None
    assert result.material.status == "not_witnessed" and work.calls == expected_calls
    assert (
        "native_fidelity" in result.outstanding and "trunk_material_metrics" in result.outstanding
    )
    assert "native_junctions" in result.outstanding and "contact" in result.outstanding
    assert events[-1]["stage"] == "complete_material_witness"
    assert len(events[-1]["findings"]) == 4 and result.audit_cpu_seconds >= 0


def test_witness_exhaustion_cannot_be_reported_as_a_physical_unqualified_result() -> None:
    """
    A resource stop propagates with its measured count and never emits a completed audit event.
    """
    events = []
    work = WitnessWork(1, checkpoint)
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        evaluate(targets(), trunk, work, 1, events.append)
    assert work.calls == 1 and not any(
        event["stage"] == "complete_material_witness" for event in events
    )


def test_bad_partition_stops_before_spending_a_trunk_solve() -> None:
    """
    Malformed measurement policy is not permitted to launch geometry first.
    """

    def forbidden(
        _targets: Targets, _check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Detect an unauthorized numerical constructor call.
        """
        raise AssertionError("Constructor must not run")

    with pytest.raises(ValueError, match="Freeze"):
        evaluate(targets(), forbidden, WitnessWork(2, checkpoint), 0, lambda event: None)
