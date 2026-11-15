"""
Verify conservative planned-curve lengths against exact analytical examples and shared work limits.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from cable_bundler.routing import RoutePreview
from cable_bundler.routing.geometry import CubicBezier, Vector3
from experiments.experiment_ribbon_complete.capture import capture
from experiments.experiment_ribbon_complete.curve_lengths import (
    LengthWork,
    enclose_route,
    iter_branch_lengths,
)
from experiments.experiment_ribbon_complete.lengths import AllowanceState, audit_end_allowance
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint, measurements


def analytic_route() -> RoutePreview:
    """
    Return a cubic whose speed3*(2t²-2t+1) integrates exactly to2mm.
    """
    curve = CubicBezier(Vector3(0, 0, 0), Vector3(0, 1, 0), Vector3(1, 1, 0), Vector3(1, 0, 0))
    return RoutePreview(UUID(int=1), "analytic length2", (curve.start, curve.end), (curve,))


@pytest.mark.parametrize("cells,reached", ((1, False), (127, True)))
def test_curve_enclosure_contains_exact_analytical_length(cells: int, reached: bool) -> None:
    """
    Preserve an exact known2mm path even when the allocation cannot narrow its enclosure.
    """
    work = LengthWork(cells, checkpoint)
    result = enclose_route(analytic_route(), work, "analytical polynomial integral")
    assert result.length.lower_mm <= 2 <= result.length.upper_mm
    assert result.resolution_reached is reached
    assert result.cells == work.used_cells <= cells
    if reached:
        assert result.length.upper_mm - result.length.lower_mm <= 0.01
    else:
        assert result.length.lower_mm == 1 and result.length.upper_mm == 3


def test_shared_cell_allocation_is_not_renewed_for_the_next_route() -> None:
    """
    Once initialization consumed the caller's only cell, another route cannot start.
    """
    work = LengthWork(1, checkpoint)
    enclose_route(analytic_route(), work, "first bounded measurement")
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        enclose_route(analytic_route(), work, "unattempted second measurement")
    assert work.used_cells == 1


@pytest.mark.parametrize("count", (-1, 0, True))
def test_cell_debits_cannot_refund_work_or_accept_boolean_counts(count: int) -> None:
    """
    Reject invalid accounting without changing the shared allocation.
    """
    work = LengthWork(3, checkpoint)
    with pytest.raises(ValueError, match="positive integer"):
        work.claim(count)
    assert work.used_cells == 0


def test_frozen_branch_measurements_feed_complete_path_allowance_without_scalar_fitting() -> None:
    """
    Measure the fixture's actual3mm straight branches and retain route identity/order through the audit.
    """
    plan = capture(*inputs())
    work = LengthWork(len(plan.branches), checkpoint)
    pairs = tuple(iter_branch_lengths(plan, work, "synthetic straight-curve fixture"))
    branches = tuple(branch for branch, _ in pairs)
    receipts = tuple(receipt for _, receipt in pairs)
    assert tuple(row.route_id for row in branches) == tuple(
        b.source.leg.route_id for b in plan.branches
    )
    assert all(row.length.lower_mm == row.length.upper_mm == 3 for row in receipts)
    assert work.used_cells == len(plan.branches)
    trunks, _ = measurements(plan)
    findings = audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    assert all(row.state is AllowanceState.PASS for row in findings)
    assert all(row.complete_path_mm == (106, 106) for row in findings)


def test_later_scope_exhaustion_preserves_the_emitted_prefix_and_unattempted_tail() -> None:
    """
    Retain the first two branch receipts when the shared allocation blocks the third.
    """
    plan = capture(*inputs())
    work = LengthWork(2, checkpoint)
    retained = []
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        for row in iter_branch_lengths(plan, work, "bounded prefix fixture"):
            retained.append(row)
    assert len(retained) == work.used_cells == 2
    assert [row[0].source for row in retained] == [b.source.route for b in plan.branches[:2]]
    assert len(plan.branches) - len(retained) == 2


def test_resource_stop_is_not_replaced_by_an_unbounded_sampling_estimate() -> None:
    """
    Propagate a caller resource failure before additional subdivision can occur.
    """
    calls = 0

    def stop() -> None:
        """
        Fail after initializing the first curve but before refining it.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("latched test resource stop")

    work = LengthWork(127, stop)
    with pytest.raises(RuntimeError, match="latched test"):
        enclose_route(analytic_route(), work, "interrupted analytical example")
    assert work.used_cells == 1
