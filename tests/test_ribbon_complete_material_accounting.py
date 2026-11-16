"""
Verify shared complete-path discrepancy accounting without treating declared ranges as measured geometry.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from uuid import UUID

import pytest

from experiments.experiment_ribbon_complete.material_accounting import (
    TrunkDiscrepancy,
    account,
    account_ranges,
)
from experiments.experiment_ribbon_complete.material_atlas import audit
from experiments.experiment_ribbon_complete.material_contract import bind
from experiments.experiment_ribbon_complete.material_traces import audit as midlines
from tests.test_ribbon_complete_branch_lengths import complete_plans
from tests.test_ribbon_complete_lengths import checkpoint, forked_plan


@pytest.mark.parametrize("extra", (Fraction(0), Fraction(1, 100000)))
def test_one_inclusive_budget_covers_trunk_and_both_serial_end_chains(extra: Fraction) -> None:
    """
    Shared parents add once per terminal path; siblings never become additional serial material.
    """
    plan = forked_plan()
    trunks = tuple(
        TrunkDiscrepancy(plan, key, Fraction(1, 1000) + extra, "synthetic accounting declaration")
        for key in plan.conductors
    )
    bounds = {b.source.leg.route_id: Fraction(3, 1000) for b in plan.branches}
    rows = account_ranges(plan, trunks, bounds, checkpoint)
    short = next(r for r in rows if r.terminal_attachment_id == UUID(int=90000))
    assert short.route_ids == (UUID(int=10099), UUID(int=10001))
    assert short.upper_mm == Fraction(1, 100) + extra
    assert short.status == ("within_declared_bound" if extra == 0 else "unresolved")
    assert all(r.terminal_attachment_id != UUID(int=101) for r in rows)


def test_worst_opposite_chain_and_unknown_alternative_are_retained() -> None:
    """
    An unavailable sibling cannot be dropped in favor of a convenient bounded termination.
    """
    plan = forked_plan()
    trunks = tuple(
        TrunkDiscrepancy(plan, key, Fraction(0), "synthetic accounting declaration")
        for key in plan.conductors
    )
    bounds: dict[UUID, Fraction | None] = {
        b.source.leg.route_id: Fraction(1, 1000) for b in plan.branches
    }
    long = next(
        b.source.leg.route_id
        for b in plan.branches
        if b.attachment.attachment_id == UUID(int=90001)
    )
    bounds[long] = Fraction(1, 50)
    row = next(
        r
        for r in account_ranges(plan, trunks, bounds, checkpoint)
        if r.terminal_attachment_id == UUID(int=1101)
    )
    assert row.opposite_terminal == UUID(int=90001) and row.upper_mm == Fraction(22, 1000)
    bounds[long] = None
    missing = next(
        r
        for r in account_ranges(plan, trunks, bounds, checkpoint)
        if r.terminal_attachment_id == UUID(int=1101)
    )
    assert missing.status == "unresolved" and missing.upper_mm is None
    assert missing.opposite_terminal is None and missing.unavailable_routes == (long,)


def test_absent_trunk_bound_and_missing_branch_ranges_cannot_pass() -> None:
    """
    Declared but unavailable trunk evidence is distinct from invalid incomplete coverage.
    """
    plan = forked_plan()
    trunks = tuple(
        TrunkDiscrepancy(plan, key, None, "trunk material not measured") for key in plan.conductors
    )
    bounds = {b.source.leg.route_id: Fraction(0) for b in plan.branches}
    assert all(
        r.status == "unresolved" and r.upper_mm is None
        for r in account_ranges(plan, trunks, bounds, checkpoint)
    )
    bounds.pop(next(iter(bounds)))
    with pytest.raises(ValueError, match="Complete original"):
        account_ranges(plan, trunks, bounds, checkpoint)


def test_original_branch_contracts_do_not_qualify_declared_trunk_geometry() -> None:
    """
    Even bounded scalar accounting retains unresolved trunk and junction provenance explicitly.
    """
    plan, branches = complete_plans()
    contracts = tuple(
        bind(audit(b, checkpoint), midlines(b, checkpoint), checkpoint) for b in branches
    )
    trunks = tuple(
        TrunkDiscrepancy(plan, key, Fraction(0), "synthetic zero for accounting only")
        for key in plan.conductors
    )
    result = account(plan, trunks, contracts, checkpoint)
    assert all(r.status == "within_declared_bound" for r in result.findings)
    assert "trunk_geometry_and_material_label_provenance" in result.outstanding
    assert "junction_material_correspondence" in result.outstanding
    with pytest.raises(ValueError, match="exactly one"):
        account(plan, trunks, contracts[:-1], checkpoint)
    stale = (replace(trunks[0], plan=replace(plan)),) + trunks[1:]
    with pytest.raises(ValueError, match="stale"):
        account(plan, stale, contracts, checkpoint)
