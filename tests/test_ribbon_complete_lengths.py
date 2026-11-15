"""
Check complete-path allowance accounting with explicitly synthetic length receipts.

These tests verify bookkeeping and interval decisions, not measured geometry.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from uuid import UUID

import pytest

from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment
from experiments.experiment_ribbon_complete.capture import capture
from experiments.experiment_ribbon_complete.contracts import (
    CompleteRibbonInput,
    IncompleteRibbonInput,
)
from experiments.experiment_ribbon_complete.lengths import (
    AllowanceState,
    BranchLength,
    LengthBasis,
    LengthEvidence,
    TrunkLength,
    audit_end_allowance,
)
from tests.test_ribbon_complete_capture import branch, inputs


def checkpoint() -> None:
    """
    Allow only the tiny deterministic arithmetic exercised by these unit tests.
    """


def length(value: float, upper: float | None = None, *, estimated: bool = False) -> LengthEvidence:
    """
    Label a synthetic interval explicitly, without claiming it measured the fixture curves.
    """
    return LengthEvidence(
        value,
        value if upper is None else upper,
        LengthBasis.SAMPLE_ESTIMATE if estimated else LengthBasis.ENCLOSURE,
        "synthetic unit-test arithmetic input; not geometry evidence",
    )


def measurements(
    plan: CompleteRibbonInput,
    *,
    trunk: float = 100,
    ending: float = 3,
    internal: float = 0,
) -> tuple[tuple[TrunkLength, ...], tuple[BranchLength, ...]]:
    """
    Supply complete synthetic receipts keyed to the immutable route and conductor identities.
    """
    trunks = tuple(
        TrunkLength(key, length(trunk), length(internal), length(internal))
        for key in plan.conductors
    )
    branches = tuple(BranchLength(b.source.route, length(ending)) for b in plan.branches)
    return trunks, branches


@pytest.mark.parametrize("lines", (2, 5, 10))
def test_allowance_uses_complete_conductor_not_trunk_only(lines: int) -> None:
    """
    Each6.5mm end fits the6.78mm allowance of a113mm complete path, although trunk6%is6mm.
    """
    plan = capture(*inputs(lines))
    findings = audit_end_allowance(plan, *measurements(plan, ending=6.5), checkpoint=checkpoint)
    assert len(findings) == 2 * lines
    assert all(row.state is AllowanceState.PASS for row in findings)
    assert all(row.complete_path_mm == (113, 113) for row in findings)
    assert all(row.margin_mm == (Fraction(7, 25), Fraction(7, 25)) for row in findings)


def test_internal_fitted_region_is_not_counted_twice_in_total_path() -> None:
    """
    A6.5mm end exceeds6.12mm; adding the already-included internal regions again would hide it.
    """
    plan = capture(*inputs())
    findings = audit_end_allowance(
        plan, *measurements(plan, ending=1, internal=5.5), checkpoint=checkpoint
    )
    assert all(row.complete_path_mm == (102, 102) for row in findings)
    assert all(row.state is AllowanceState.FAIL for row in findings)


def forked_plan() -> CompleteRibbonInput:
    """
    Add a second explicit descendant to test serial ancestry versus parallel alternatives.
    """
    definition, group_id, trunk, caps, branches = inputs(child=True)
    connection = definition.connections[0]
    assert connection.attachment is not None
    parent_id = connection.attachment.attachment_id
    sibling = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "second-child-point",
        "second child",
        attachment_id=UUID(int=90001),
        parent_attachment_id=parent_id,
    )
    parent = next(b for b in branches if b.leg.attachment_id == parent_id)
    second = branch(
        connection.connection_id, sibling.attachment_id, 98, 0, parent.terminal.point, parent_id
    )
    changed = replace(
        connection, additional_attachments=connection.additional_attachments + (sibling,)
    )
    definition = replace(definition, connections=(changed,) + definition.connections[1:])
    return capture(definition, group_id, trunk, caps, branches + (second,))


def test_descendant_lengths_follow_parent_chain_without_summing_sibling_branches() -> None:
    """
    A6mm short chain passes independently of a parallel51mm chain, whose own allowance fails.
    """
    plan = forked_plan()
    trunks, branches = measurements(plan, ending=1)
    values = {UUID(int=90000): length(5), UUID(int=90001): length(50)}
    branches = tuple(
        BranchLength(b.source.route, values.get(b.attachment.attachment_id, length(1)))
        for b in plan.branches
    )
    findings = audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    short = next(row for row in findings if row.terminal_attachment_id == UUID(int=90000))
    long = next(row for row in findings if row.terminal_attachment_id == UUID(int=90001))
    assert short.state is AllowanceState.PASS and short.complete_path_mm == (107, 107)
    assert long.state is AllowanceState.FAIL and long.complete_path_mm == (152, 152)
    assert short.route_ids == (UUID(int=10099), UUID(int=10001))
    assert not any(row.terminal_attachment_id == UUID(int=101) for row in findings)


def test_opposite_interval_extrema_retain_both_terminal_identities() -> None:
    """
    Different uncertain alternatives can supply shortest lower and shortest upper bounds.
    """
    plan = forked_plan()
    trunks, _ = measurements(plan, ending=1)
    values = {UUID(int=90000): length(2, 9), UUID(int=90001): length(3, 4)}
    branches = tuple(
        BranchLength(b.source.route, values.get(b.attachment.attachment_id, length(1)))
        for b in plan.branches
    )
    findings = audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    opposite = next(row for row in findings if row.terminal_attachment_id == UUID(int=1101))
    assert opposite.opposite_lower_terminal == UUID(int=90000)
    assert opposite.opposite_upper_terminal == UUID(int=90001)
    assert opposite.complete_path_mm == (104, 111)


@pytest.mark.parametrize("extra,state", ((0, AllowanceState.PASS), (0.0001, AllowanceState.FAIL)))
def test_single_dimensional_allowance_is_inclusive_for_complete_end(
    extra: float, state: AllowanceState
) -> None:
    """
    On a4mm complete path,0.25mm minus0.24mm is exactly the allowed0.01mm deviation.
    """
    plan = capture(*inputs())
    trunks, _ = measurements(plan, trunk=3)
    trunks = tuple(replace(t, start_region=length(extra)) for t in trunks)
    branches = tuple(
        BranchLength(
            b.source.route,
            length(0.25 if b.source.leg.start_connection_id == UUID(int=10) else 0.75),
        )
        for b in plan.branches
    )
    findings = audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    assert all(row.state is state for row in findings if row.connection_id == UUID(int=10))


@pytest.mark.parametrize("estimate", (3, 50))
def test_sampling_without_established_error_bounds_cannot_decide_allowance(estimate: float) -> None:
    """
    Neither a small estimated end nor a large one becomes a certified physical disposition.
    """
    plan = capture(*inputs())
    trunks, branches = measurements(plan)
    branches = tuple(replace(b, length=length(estimate, estimated=True)) for b in branches)
    assert all(
        row.state is AllowanceState.UNRESOLVED
        for row in audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    )


def test_established_bounds_that_straddle_the_allowance_stay_unresolved() -> None:
    """
    Real enclosure uncertainty crossing the limit cannot be rounded into a pass or failure.
    """
    plan = capture(*inputs())
    trunks, branches = measurements(plan)
    branches = tuple(replace(b, length=length(6, 8)) for b in branches)
    assert all(
        row.state is AllowanceState.UNRESOLVED
        for row in audit_end_allowance(plan, trunks, branches, checkpoint=checkpoint)
    )


def test_missing_or_duplicated_measurement_is_incomplete_evidence() -> None:
    """
    Refuse partial and duplicated coverage instead of excluding an inconvenient branch.
    """
    plan = capture(*inputs())
    trunks, branches = measurements(plan)
    for supplied in (branches[:-1], branches + (branches[0],)):
        with pytest.raises(IncompleteRibbonInput, match="exactly one"):
            audit_end_allowance(plan, trunks, supplied, checkpoint=checkpoint)


def test_persistent_uuid_does_not_allow_a_stale_route_measurement_after_regeneration() -> None:
    """
    A changed control polygon under the same UUID must not inherit an old length receipt.
    """
    plan = capture(*inputs())
    trunks, branches = measurements(plan)
    original = branches[0].source
    changed_curve = replace(original.curves[0], control_a=original.curves[0].end)
    stale = replace(branches[0], source=replace(original, curves=(changed_curve,)))
    with pytest.raises(IncompleteRibbonInput, match="frozen route geometry"):
        audit_end_allowance(plan, trunks, (stale,) + branches[1:], checkpoint=checkpoint)


def test_caller_resource_stop_propagates_before_audit_work() -> None:
    """
    A caller's latched resource stop cannot be swallowed into a geometric result.
    """
    plan = capture(*inputs())

    def stopped() -> None:
        """
        Simulate the existing caller resource guard, not a geometry rejection.
        """
        raise RuntimeError("resource stop")

    with pytest.raises(RuntimeError, match="resource stop"):
        audit_end_allowance(plan, *measurements(plan), checkpoint=stopped)
