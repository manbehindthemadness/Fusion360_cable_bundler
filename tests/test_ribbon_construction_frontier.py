"""
Verify fair root comparison and physical length accounting within one finite construction frontier.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_constrained_construction.disjunction import Work
from experiments.experiment_ribbon_constrained_construction.envelopes import Exclusion
from experiments.experiment_ribbon_constrained_construction.frontier import Case, Frontier
from experiments.experiment_ribbon_constrained_construction.linear import Problem, Row


def checkpoint() -> None:
    """
    Allow bounded analytical work without external resources.
    """


def test_later_root_beats_first_roots_long_clearance_arrangement() -> None:
    """
    Compare both original roots before the initially cheaper relaxation grows into a long detour.
    """
    first = Case(
        "early",
        Problem((1, 1), (Row("closure", (1, 0.5), 10),), ()),
        (Exclusion("clearance", ((Row("detour", (0, 1), 12),),)),),
        1.0,
        0.0,
    )
    second = Case("later", Problem((1, 1), (Row("closure", (1, 1), 12),), ()), (), 1.0, 0.0)
    frontier = Frontier((first, second), Work())
    frontier.run(checkpoint)
    assert frontier.roots_relaxed == [0, 1]
    assert frontier.best is not None and frontier.best.root == 1
    assert frontier.best.length_mm == pytest.approx(12)
    assert frontier.status == "supplied_constraints_satisfied"
    assert [event["root"] for event in frontier.work.events[:2]] == [0, 1]
    assert frontier.work.nodes == 3


def test_root_cost_includes_fold_material_and_physical_length_units() -> None:
    """
    Small normalized travel cannot outrank a genuinely shorter route with different fixed fold cost.
    """
    first = Case("fold-heavy", Problem((1,), (Row("closure", (1,), 1),), ()), (), 0.1, 100.0)
    second = Case("shorter-total", Problem((1,), (Row("closure", (1,), 20),), ()), (), 1.0, 0.0)
    frontier = Frontier((first, second), Work())
    frontier.run(checkpoint)
    assert frontier.best is not None and frontier.best.root == 1
    assert frontier.best.length_mm == pytest.approx(20)
    assert frontier.work.events[0]["total_material_mm"] == pytest.approx(100.1)


def test_shared_work_limit_does_not_report_partial_relaxation_as_a_bound() -> None:
    """
    Incomplete LP enumeration stops with explicit unfinished roots and cannot prune as a solved optimum.
    """
    case = Case("partial", Problem((1, 1), (Row("closure", (1, 1), 10),), ()), (), 1.0, 0.0)
    frontier = Frontier((case, case), Work(maximum_vertices=1, maximum_nodes=64))
    frontier.run(checkpoint)
    assert frontier.status == "work_limit"
    assert frontier.roots_relaxed == []
    assert frontier.work.nodes == 1 and frontier.work.vertices == 1
    assert frontier.work.events[0]["status"] == "work_limit"
    assert frontier.inspection is not None
    with pytest.raises(RuntimeError, match="replayed"):
        frontier.run(checkpoint)


def test_external_stop_preserves_already_completed_feasible_allocation() -> None:
    """
    A host/wall stop propagates while the best completed geometry coordinates remain available.
    """
    first = Case(
        "early",
        Problem((1, 1), (Row("closure", (1, 0.5), 10),), ()),
        (Exclusion("clearance", ((Row("detour", (0, 1), 12),),)),),
        1.0,
        0.0,
    )
    second = Case("later", Problem((1, 1), (Row("closure", (1, 1), 12),), ()), (), 1.0, 0.0)
    frontier = Frontier((first, second), Work())

    def stop_after_feasible() -> None:
        """
        Model a hard external stop after the feasible root relaxation has completed.
        """
        if frontier.best is not None:
            raise TimeoutError("wall stop")

    with pytest.raises(TimeoutError, match="wall stop"):
        frontier.run(stop_after_feasible)
    assert frontier.best is not None and frontier.best.root == 1
