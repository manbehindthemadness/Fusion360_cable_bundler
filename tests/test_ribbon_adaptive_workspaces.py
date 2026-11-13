"""
Keep surviving material workspaces available without transferring stale ordinals or renewed work.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_construction as construction,
)
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_plan as planning
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import (
    Edit,
    EventId,
    Window,
    events,
    reopen,
)
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.ribbon_adaptive_controls import (
    negative_discovery_boundary as negative_discovery_boundary,
)
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source
from tests.test_ribbon_aesthetic import _route

pytestmark = pytest.mark.usefixtures(negative_discovery_boundary.__name__)

State = tuple[FoldRoute, tuple[EventId, ...], tuple[Edit, ...]]


@pytest.fixture
def modules() -> State:
    """
    Author three real closed modules with surviving straight gaps and explicit piece lineage.
    """
    route = _route((Straight(12), Straight(20), Straight(12), Straight(20), Straight(12)))
    lineage: tuple[EventId, ...] = tuple((0, i) for i in range(len(route.pieces)))
    history: list[Edit] = []
    for generation, index in enumerate((4, 2, 0), 1):
        window = Window(route, index, index + 1)
        local = _bump(window)
        children = tuple((generation, i) for i in range(len(local.pieces)))
        history.append(
            Edit(
                children, lineage[index : index + 1], route.pieces[index : index + 1], local.pieces
            )
        )
        route = window.splice(local)
        lineage = lineage[:index] + children + lineage[index + 1 :]
    return route, lineage, tuple(history)


@pytest.mark.parametrize(
    "selected,expected", (((1, 3), (0, 5)), ((5, 6), (5, 6)), ((4, 7), (0, 11)), ((4, 13), (0, 17)))
)
def test_nested_disjoint_and_bridging_domains_follow_whole_surviving_modules(
    modules: State,
    selected: tuple[int, int],
    expected: tuple[int, int],
) -> None:
    """
    A child interval reopens its full module; untouched gaps remain local and bridging covers both sides.
    """
    route, lineage, history = modules
    base = Window(route, *selected)
    expanded = reopen(base, lineage, history)
    assert (expanded.begin, expanded.end) == expected and expanded.source is route
    if selected == expected:
        assert expanded is base
    assert all(
        a is b for a, b in zip(expanded.route.pieces, route.pieces[expected[0] : expected[1]])
    )


def test_a_large_parent_can_replace_nine_events_by_three_with_the_same_actual_caps(
    modules: State,
) -> None:
    """
    Reopening changes the available domain, allowing fewer events without moving fixed outer poses.

    This is one authored aligned-boundary material family, not contact/native qualification.
    """
    route, lineage, history = modules
    expanded = reopen(Window(route, 4, 13), lineage, history)
    assert events(expanded.route) == 9
    simplified = expanded.splice(_bump(expanded, 0.2))
    assert events(simplified) == 3 and simplified.targets is route.targets
    assert cap_error(simplified) < 1e-10 and material_error(simplified) < 1e-10


@pytest.mark.parametrize("changed", ("id", "owner"))
def test_retired_or_replaced_piece_ranges_cannot_reopen_an_old_workspace(
    modules: State, changed: str
) -> None:
    """
    Equal geometry or a partly retained ID range cannot masquerade as the old owned module.
    """
    route, lineage, history = modules
    if changed == "id":
        lineage = lineage[:2] + ((99, 2),) + lineage[3:]
    else:
        route = replace(
            route,
            pieces=route.pieces[:2]
            + (replace(route.pieces[2], label="different owner"),)
            + route.pieces[3:],
        )
    expanded = reopen(Window(route, 1, 3), lineage, history)
    assert (expanded.begin, expanded.end) == (1, 3)


@pytest.mark.parametrize("malformed", ("missing", "duplicate"))
def test_corrupt_lineage_is_a_hard_error_before_domain_selection(
    modules: State, malformed: str
) -> None:
    """
    Do not infer an interval when the current material identity table is inconsistent.
    """
    route, lineage, history = modules
    lineage = lineage[:-1] if malformed == "missing" else (lineage[1],) + lineage[1:]
    with pytest.raises(ValueError, match="unique identity"):
        reopen(Window(route, 1, 3), lineage, history)


def test_nested_undo_revives_exact_parent_ownership_without_ordinal_guessing(
    modules: State,
) -> None:
    """
    Removing a later whole-module replacement restores the original piece objects and labels together.
    """
    route, lineage, history = modules
    window = reopen(Window(route, 1, 3), lineage, history)
    local = _bump(window, 0.2)
    children = tuple((4, i) for i in range(len(local.pieces)))
    latest = Edit(children, lineage[:5], route.pieces[:5], local.pieces)
    current = window.splice(local)
    current_ids = children + lineage[5:]
    assert history[-1].inserted_window(current, current_ids) is None
    expanded = reopen(Window(current, 1, 3), current_ids, (*history, latest))
    assert (expanded.begin, expanded.end) == (0, 5)
    restored = latest.undo(current, current_ids)
    assert restored is not None and restored[1] == lineage
    assert all(a is b for a, b in zip(restored[0].pieces, route.pieces))
    assert history[-1].inserted_window(*restored) is not None


@pytest.mark.parametrize("stale", (False, True))
def test_planning_selects_a_workspace_only_after_current_witness_validation(stale: bool) -> None:
    """
    Larger domains may be selected for valid evidence; stale material never reaches the selector.
    """
    route, hardware, evidence = _source()
    assert evidence.witness is not None
    if stale:
        evidence = replace(evidence, witness=replace(evidence.witness, material=(0.001, 0, 0)))
    window = Window(route, 0, len(route.pieces))
    selector = Mock(return_value=window)
    result = planning.plan(route, evidence, hardware, lambda: None, select_window=selector)
    if stale:
        assert result is None
        selector.assert_not_called()
    else:
        selector.assert_called_once_with(route, (0,))
        assert result is not None and result.window is window and events(result.window.route) == 6


@pytest.mark.parametrize("wrong", ("source", "member"))
def test_window_strategy_cannot_select_foreign_or_unwitnessed_material(wrong: str) -> None:
    """
    A custom domain strategy cannot bypass current source ownership or actual witness membership.
    """
    route, hardware, evidence = _source()
    chosen = Window(replace(route), 0, 1) if wrong == "source" else Window(route, 2, 3)
    with pytest.raises(ValueError, match="current witness"):
        planning.plan(
            route, evidence, hardware, lambda: None, select_window=Mock(return_value=chosen)
        )


def test_controller_reopens_overlapping_work_for_a_blocker_outside_the_owned_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise actual domain selection, cap-closed splices and lineage with explicit checker boundary doubles.
    """
    from tests.ribbon_adaptive_controls import adjacent, retained

    source, hardware, evidence, other = adjacent()
    windows: list[tuple[int, int, int]] = []

    def selected(route: FoldRoute, members: tuple[int, ...]) -> Window:
        """
        Include the actual unowned member and one overlapping piece of the existing module.
        """
        del members
        return Window(route, 0, 1) if not windows else Window(route, 4, 6)

    def proposed(
        route: FoldRoute,
        observed: Any,
        fixed: Any,
        check: Any,
        *,
        select_window: planning.WindowSelector,
    ) -> Proposal:
        """
        Use the controller's actual selector; evidence validation is tested independently.
        """
        del observed, fixed, check
        return _proposal(select_window(route, (0,)))

    def constructed(
        proposal: Proposal,
        minimum: float,
        roots: construction.Roots,
        check: Callable[[], None],
        record: Callable[[dict[str, Any]], None],
    ) -> FoldRoute:
        """
        Charge a shared fitted root and build a real boundary-closed analytical module.
        """
        del minimum, check, record
        roots.attempted += 1
        window = proposal.window
        windows.append((window.begin, window.end, events(window.route)))
        return _bump(window, 0.3 if len(windows) == 1 else 0.2)

    monkeypatch.setitem(vars(runner), "select", selected)
    monkeypatch.setitem(vars(runner), "plan", proposed)
    monkeypatch.setitem(vars(runner), "construct", constructed)
    certificate = ContactResult("separated", 2)
    inspect = Mock(return_value=certificate)
    monkeypatch.setitem(vars(runner), "inspect_contact", inspect)
    terminal = Mock(
        spec=Gate,
        hardware=hardware,
        certify=Mock(
            side_effect=lambda route, stage: (
                retained(route, source.pieces[1], other)
                if any(piece is source.pieces[1] for piece in route.pieces)
                else Report("clear", 1)
            )
        ),
    )
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(4, 2048, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is certificate
    assert windows == [(0, 1, 0), (0, 6, 3)] and events(result.route) == 9
    assert result.detail["reopened_windows"] == 1 and result.detail["roots_attempted"] == 2
    assert result.detail["iterations"] == 3 and result.detail["contact_pairs"] == 2
    assert result.detail["contact_checks_deferred"] == 2
    assert [call.kwargs["maximum_pairs"] for call in inspect.call_args_list] == [2048]
    assert result.detail["pruning_unavailable"] == 1 and result.detail["pruning_attempted"] == 1
    assert all(a is b for a, b in zip(result.route.pieces[5:], source.pieces[2:]))
