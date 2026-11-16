"""
Verify complete orchestration preserves fixed inputs, both ends and one shared stop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_complete import native_execution
from experiments.experiment_ribbon_complete.branch_plan import SpatialBranchPlan
from experiments.experiment_ribbon_complete.contracts import IncompleteRibbonInput
from experiments.experiment_ribbon_complete.execution import RibbonTargets, prepare
from experiments.experiment_ribbon_complete.native_branch_body import NativeBranchBody
from experiments.experiment_ribbon_complete.native_execution import NativeTrunkBody
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_locked_solver.solver import Result
from tests.test_ribbon_complete_branch_construction import data
from tests.test_ribbon_complete_branch_targets import boundaries
from tests.test_ribbon_complete_capture import inputs


def targets(child: bool = False) -> RibbonTargets:
    """
    Supply analytical complete targets and explicit roots before any trunk invocation.
    """
    definition, group, trunk_targets, caps, _ = inputs(2, child)
    _, roots = data(2, child)
    return RibbonTargets(definition, group, trunk_targets, caps, boundaries(2, child), roots)


def checkpoint() -> None:
    """
    Permit bounded analytical contract work without native or recovery allocation.
    """


def trunk(
    source: Targets,
    check: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Result:
    """
    Supply an exact straight analytical trunk, not a replacement endpoint solver.
    """
    check()
    record({"stage": "analytical_trunk"})
    route = FoldRoute(
        source,
        (
            PlacedPiece(
                Pose(source.start, source.start_tangent, source.start_width),
                Straight(10),
                "analytical",
            ),
        ),
        1,
    )
    return Result(route, route, {"status": "analytical_trunk"}, None)


@pytest.mark.parametrize("child", (False, True))
def test_complete_execution_retains_both_endings_descendants_and_original_inputs(
    child: bool,
) -> None:
    """
    Every frozen branch survives one trunk invocation without acquiring physical acceptance.
    """
    source = targets(child)
    calls = []
    events = []

    def selected(
        t: Targets, check: Callable[[], None], record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Observe one original input without altering the analytical constructor.
        """
        calls.append(t)
        return trunk(t, check, record)

    result = prepare(source, selected, checkpoint, events.append)
    assert calls == [source.trunk]
    assert (
        result.source is source
        and result.captured.associations is source.definition.attachment_associations
    )
    assert len(result.branches) == 4 + int(child) and result.unattempted_route_ids == ()
    assert tuple(p.source for p in result.branches) == result.captured.branches
    assert all("native_junctions" in p.outstanding for p in result.branches)
    assert result.wall_seconds >= 0 and result.cpu_seconds >= 0


def test_missing_targets_or_roots_stop_before_spending_a_trunk_solve() -> None:
    """
    Incomplete input cannot consume work and later receive fabricated endpoint coverage.
    """
    source = targets()
    calls = []

    def forbidden(
        t: Targets, _check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Fail if incomplete input reaches the external constructor.
        """
        calls.append(t)
        raise AssertionError("Unexpected trunk call")

    for changed in (
        replace(source, branches=source.branches[:-1]),
        replace(source, roots=source.roots[:-1]),
    ):
        with pytest.raises(IncompleteRibbonInput):
            prepare(changed, forbidden, checkpoint, lambda event: None)
    assert calls == []


def test_unresolved_trunk_retains_every_branch_as_unattempted_and_blocks_native() -> None:
    """
    Constructor exhaustion never becomes empty complete geometry or a native fallback.
    """
    source = targets()

    def unresolved(
        _t: Targets, _check: Callable[[], None], _record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Return the original unsuccessful outcome without geometry.
        """
        return Result(None, None, {"status": "unresolved"}, None)

    plan = prepare(source, unresolved, checkpoint, lambda event: None)
    assert len(plan.unattempted_route_ids) == 4 and plan.branches == ()
    with pytest.raises(IncompleteRibbonInput, match="every prepared"):
        next(native_execution.iter_bodies(plan, checkpoint, lambda event: None))


def test_foreign_trunk_targets_cannot_borrow_complete_input_identity() -> None:
    """
    Matching object shape cannot substitute a differently targeted trunk.
    """
    source = targets()

    def foreign(
        t: Targets, check: Callable[[], None], record: Callable[[dict[str, Any]], None]
    ) -> Result:
        """
        Deliberately return an unrelated target pose to exercise provenance rejection.
        """
        return trunk(replace(t, end=Vector3(11, 0, 0)), check, record)

    with pytest.raises(IncompleteRibbonInput, match="frozen complete"):
        prepare(source, foreign, checkpoint, lambda event: None)


def test_shared_stop_preserves_completed_branch_event_without_retrying_trunk() -> None:
    """
    One caller stop prevents subsequent branches rather than renewing their allocation.
    """
    stopped = False
    events = []

    def check() -> None:
        """
        Propagate a latched stop from the existing caller.
        """
        if stopped:
            raise TimeoutError("shared stop")

    def record(event: dict[str, Any]) -> None:
        """
        Stop after the first actual branch has been reported.
        """
        nonlocal stopped
        events.append(event)
        if event["stage"] == "complete_branch":
            stopped = True

    with pytest.raises(TimeoutError, match="shared stop"):
        prepare(targets(), trunk, check, record)
    assert sum(e["stage"] == "complete_trunk" for e in events) == 1
    assert sum(e["stage"] == "complete_branch" for e in events) == 1


@pytest.mark.parametrize("refuse", (False, True))
def test_native_sequence_retains_exact_sources_and_prefix_after_kernel_refusal(
    monkeypatch: pytest.MonkeyPatch, refuse: bool
) -> None:
    """
    External-boundary doubles show no retry, alternate geometry or loss of completed parts.
    """
    plan = prepare(targets(), trunk, checkpoint, lambda event: None)
    assert plan.trunk.route is not None
    body = type("Body", (), {"isSolid": True, "volume": 1})()
    calls = []

    def native_trunk(route: FoldRoute, check: Callable[[], None]) -> NativeTrunkBody:
        """
        Retain the original trunk source without importing Fusion in unit tests.
        """
        check()
        calls.append(route)
        return NativeTrunkBody(route, body, ())

    def native_branch(branch: SpatialBranchPlan, check: Callable[[], None]) -> NativeBranchBody:
        """
        Refuse the second ending once, preserving the first completed branch.
        """
        check()
        calls.append(branch)
        if refuse and branch is plan.branches[1]:
            raise RuntimeError("kernel refusal")
        return NativeBranchBody(branch, body, ())

    monkeypatch.setattr(native_execution, "build_trunk", native_trunk)
    monkeypatch.setattr(native_execution, "build_branch", native_branch)
    stream = native_execution.iter_bodies(plan, checkpoint, lambda event: None)
    first, second = next(stream), next(stream)
    assert first.source is plan.trunk.route and second.source is plan.branches[0]
    if refuse:
        with pytest.raises(RuntimeError, match="kernel refusal"):
            next(stream)
        assert calls == [plan.trunk.route, plan.branches[0], plan.branches[1]]
    else:
        remaining = tuple(stream)
        assert tuple(part.source for part in remaining) == plan.branches[1:]
        assert calls == [plan.trunk.route, *plan.branches]
