"""
Keep adaptive-to-fixed correction inside one original allocation and exact current ownership.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_continuation as continuation,
)
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window, reidentify
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.ribbon_adaptive_controls import (
    negative_discovery_boundary as negative_discovery_boundary,
)
from tests.test_ribbon_adaptive_continuation import moved, reply
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source

pytestmark = pytest.mark.usefixtures(negative_discovery_boundary.__name__)


@dataclass
class Prepared:
    """
    Retain authored geometry and explicit protocol clocks/checker boundaries for one recovery invocation.
    """

    source: FoldRoute
    evidence: Report
    terminal: Mock
    clock: list[float]
    visited: list[FoldRoute]


@pytest.fixture
def prepared(monkeypatch: pytest.MonkeyPatch) -> Prepared:
    """
    Spend eight fits on two real closed modules while the actual occupied first straight survives exactly.
    """
    source, hardware, evidence = _source()
    clock = [0.0]
    for module in (runner, continuation):
        for name in ("process_time", "perf_counter"):
            monkeypatch.setitem(vars(module), name, lambda: clock[0])
    visited: list[FoldRoute] = []

    def plan(route: FoldRoute, *args: Any, **kwargs: Any) -> Proposal:
        """
        Select two disjoint analytical straight intervals without moving the occupied leading member.
        """
        del args, kwargs
        index = 2 if visited else len(route.pieces) - 1
        visited.append(route)
        return _proposal(Window(route, index, index + 1))

    def construct(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Model fitted-choice costs and one started correction while using genuine closed material geometry.
        """
        del minimum, args
        roots.attempted += 4
        if roots.attempted == 4:
            roots.newton_steps += min(1, roots.newton_limit)
        clock[0] += 0.04
        return _bump(proposal.window)

    monkeypatch.setitem(vars(runner), "plan", plan)
    monkeypatch.setitem(vars(runner), "construct", construct)
    terminal = Mock(
        spec=Gate,
        hardware=hardware,
        certify=Mock(side_effect=(evidence, evidence, Report("clear", 1))),
    )
    return Prepared(source, evidence, terminal, clock, visited)


def run(prepared: Prepared, *, work: Work | None = None, record: Any = None) -> Result | None:
    """
    Invoke the controller once with its original budget; no fixture represents fresh geometry qualification.
    """
    return runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        record or Mock(),
        work=work or Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )


@pytest.mark.parametrize("accepted,late", ((True, False), (False, False), (True, True)))
def test_one_handoff_uses_only_residual_work_and_never_restarts_after_failure(
    prepared: Prepared,
    monkeypatch: pytest.MonkeyPatch,
    accepted: bool,
    late: bool,
) -> None:
    """
    Preserve actual caps and counters across dynamic primitive count; clearance and child solver are explicit doubles.
    """
    captured: list[Work] = []

    def child(source: FoldRoute, evidence: Report, *args: Any, **kwargs: Any) -> Result:
        """
        Inspect the true residual allocation and return independently constructed cap-preserving material motion.
        """
        del args
        assert source.pieces[0] is prepared.source.pieces[0] and evidence is prepared.evidence
        captured.append(kwargs["work"])
        return reply(moved(source), accepted)

    monkeypatch.setitem(vars(continuation), "recover_sequence", child)

    def record(event: dict[str, Any]) -> None:
        """
        Charge preparation and optionally a late result receipt to the same original phase.
        """
        if event.get("stage") == "adaptive_continuation":
            prepared.clock[0] += 0.01 if event["status"] == "started" else 0.3 if late else 0

    result = run(prepared, record=record)
    assert result is not None and len(captured) == 1 and len(prepared.visited) == 2
    left = captured[0]
    assert (left.updates, left.pairs, left.newton_steps) == (2, 2048, 23)
    assert left.cpu_seconds == pytest.approx(0.26) and left.wall_seconds == pytest.approx(1.91)
    assert result.detail["iterations"] == 3 and result.detail["newton_steps"] == 3
    assert result.detail["roots_attempted"] == 8 and result.detail["contact_pairs"] == 7
    assert (result.contact is not None) is (accepted and not late)
    if accepted and not late:
        assert result.detail["pruning_unavailable"] == 2 and result.detail["pruning_attempted"] == 0
    else:
        assert result.route is prepared.source
        assert result.detail["stop_reason"] == ("phase_budget" if late else "projection_failed")


@pytest.mark.parametrize("work", (Work(1, 23, 0.35, 2), Work(2, 23, 0.35, 2), Work(4, 23, 0.03, 2)))
def test_exhausted_original_work_cannot_start_the_child(
    prepared: Prepared,
    monkeypatch: pytest.MonkeyPatch,
    work: Work,
) -> None:
    """
    Neither available Newton steps nor exhausted root fitting can renew updates or phase time.
    """
    child = Mock(side_effect=AssertionError("No genuinely remaining original allocation"))
    monkeypatch.setitem(vars(runner), "continue_fixed", child)
    result = run(prepared, work=work)
    assert result is not None and result.contact is None
    child.assert_not_called()


@pytest.mark.parametrize("uncertain", (True, False))
def test_uncertain_candidate_or_exhausted_pairs_cannot_reuse_parent_evidence(
    prepared: Prepared,
    monkeypatch: pytest.MonkeyPatch,
    uncertain: bool,
) -> None:
    """
    A new candidate with no current strict witness cannot inherit its parent's hardware direction.
    """
    build = runner.construct

    def consume(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Exhaust the original root choices during the first complete candidate construction.
        """
        local = build(proposal, minimum, roots, *args)
        assert local is not None
        roots.attempted = 8
        return local

    monkeypatch.setitem(vars(runner), "construct", consume)
    prepared.terminal.certify.side_effect = None
    prepared.terminal.certify.return_value = Report("clear", 1)
    assert prepared.evidence.witness is not None
    proof = (
        ContactResult("unresolved", 3, limit="depth")
        if uncertain
        else ContactResult(
            "penetration",
            23,
            Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), prepared.evidence.witness.point),
        )
    )
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=proof))
    child = Mock(side_effect=AssertionError("No current witness or original pair allowance"))
    monkeypatch.setitem(vars(runner), "continue_fixed", child)
    result = run(prepared, work=Work(4, 23, 0.35, 2))
    assert result is not None and result.contact is None and len(prepared.visited) == 1
    child.assert_not_called()


def test_reidentification_preserves_only_exact_owned_objects_across_new_slots() -> None:
    """
    Equal copies lose undo ownership; exact surviving material keeps stable IDs despite a new piece count.
    """
    source, _, _ = _source()
    lineage = tuple((0, i) for i in range(len(source.pieces)))
    changed = replace(
        source, pieces=(replace(source.pieces[0], label="equal but recreated"),) + source.pieces[1:]
    )
    ids = reidentify(source, lineage, changed, 5)
    assert ids[0] == (5, 0) and ids[1:] == lineage[1:]
    rebuilt = moved(source)
    new_ids = reidentify(source, lineage, rebuilt, 5)
    assert len(new_ids) == len(rebuilt.pieces) and all(generation == 5 for generation, _ in new_ids)
    with pytest.raises(ValueError, match="unallocated"):
        reidentify(changed, ids, source, 5)


def test_zero_original_newton_pool_reaches_child_without_renewal(
    prepared: Prepared,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exhausted angular work may still allow exact preparation, never another set of corrections.
    """
    captured: list[Work] = []

    def child(source: FoldRoute, *args: Any, **kwargs: Any) -> Result:
        """
        Decline a protocol-only exact stage after observing zero remaining corrections.
        """
        del args
        captured.append(kwargs["work"])
        child_reply = reply(source, False)
        child_reply.detail.update(newton_steps=0, contacts=0, contact_pairs=0, contact_seconds=0.0)
        return child_reply

    monkeypatch.setitem(vars(continuation), "recover_sequence", child)
    result = run(prepared, work=Work(4, 23, 0.35, 2, 0))
    assert result is not None and result.contact is None and len(captured) == 1
    assert captured[0].newton_steps == result.detail["newton_steps"] == 0


@pytest.mark.parametrize("root_count", (1, 4, 8))
def test_failed_local_fits_can_correct_the_original_closed_topology_without_extra_events(
    prepared: Prepared,
    monkeypatch: pytest.MonkeyPatch,
    root_count: int,
) -> None:
    """
    An intact original route and current witness need no successful topology rewrite to use residual corrections.
    """
    captured: list[Work] = []

    def decline(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> None:
        """
        Spend the original local fit pool without constructing an open or accepted candidate.
        """
        del proposal, minimum, args
        roots.attempted = root_count
        prepared.clock[0] += 0.04

    def child(source: FoldRoute, evidence: Report, *args: Any, **kwargs: Any) -> Result:
        """
        Verify unchanged owned input and solve only a protocol-level fixed-topology boundary.
        """
        del args
        assert source is prepared.source and evidence is prepared.evidence
        captured.append(kwargs["work"])
        return reply(moved(source))

    monkeypatch.setitem(vars(runner), "construct", decline)
    monkeypatch.setitem(vars(continuation), "recover_sequence", child)
    prepared.terminal.certify.side_effect = None
    prepared.terminal.certify.return_value = Report("clear", 1)
    result = run(prepared)
    assert result is not None and result.contact is not None and len(captured) == 1
    assert captured[0].updates == 3 and captured[0].newton_steps == 24
    assert result.detail["rewrites"] == 0 and result.detail["iterations"] == 2
    assert (
        result.detail["roots_attempted"] == root_count and result.detail["pruning_attempted"] == 0
    )
