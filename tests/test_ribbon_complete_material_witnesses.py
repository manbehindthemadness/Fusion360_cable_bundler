"""
Check exact extension witnesses and complete-chain accounting without native qualification.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.capture import capture
from experiments.experiment_ribbon_complete.contracts import BranchPlan, IncompleteRibbonInput
from experiments.experiment_ribbon_complete.execution import prepare
from experiments.experiment_ribbon_complete.material_paths import StretchWitness
from experiments.experiment_ribbon_complete.material_traces import traces
from experiments.experiment_ribbon_complete.material_witnesses import (
    BranchExtension,
    WitnessWork,
    account,
    audit,
    measure,
)
from tests.test_ribbon_complete_branch_plan import data, planned
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_execution import targets, trunk
from tests.test_ribbon_complete_lengths import checkpoint, forked_plan
from tests.test_ribbon_complete_material_paths import frame, patches


def synthetic(branch: BranchPlan, left: Fraction, right: Fraction) -> BranchExtension:
    """
    Supply explicitly synthetic lower-bound receipts for accounting, not geometry evidence.
    """
    geometry = replace(planned(data()), source=branch)
    sides = traces(tuple(p.section for p in geometry.patches[0]))
    values = tuple(
        (
            StretchWitness(
                geometry.patches[0][trace.edge_index],
                Fraction(0),
                Fraction(1),
                trace.coordinate,
                value,
                value > Fraction(1, 100),
            ),
        )
        for trace, value in zip(sides, (left, right))
    )
    return BranchExtension(geometry, 1, sides, ((values[0], values[1]),))


@pytest.mark.parametrize("per_end", (Fraction(1, 200), Fraction(3, 500)))
def test_both_ends_share_one_inclusive_allowance_and_unwitnessed_never_means_pass(
    per_end: Fraction,
) -> None:
    """
    Two individually small endings can witness a whole-path violation above0.01mm.
    """
    complete = capture(*inputs())
    rows = tuple(synthetic(branch, per_end, Fraction(0)) for branch in complete.branches)
    result = account(complete, rows, checkpoint)
    left = tuple(row for row in result.findings if row.side == "left")
    assert all(row.lower_mm == 2 * per_end for row in left)
    assert all(len(row.first_route_ids) == len(row.last_route_ids) == 1 for row in left)
    if per_end == Fraction(1, 200):
        assert result.status == "not_witnessed" and not any(
            row.violation for row in result.findings
        )
    else:
        assert result.status == "violated" and all(row.violation for row in left)


def test_descendants_are_serial_siblings_are_alternatives_and_each_side_has_a_real_pair() -> None:
    """
    Different terminal alternatives attain the left and right lower-bound maxima.
    """
    complete = forked_plan()
    values = {
        UUID(int=90000): (Fraction(2, 1000), Fraction(5, 1000)),
        UUID(int=90001): (Fraction(7, 1000), Fraction(1, 1000)),
    }
    rows = tuple(
        synthetic(branch, *values.get(branch.attachment.attachment_id, (Fraction(1, 1000),) * 2))
        for branch in complete.branches
    )
    result = account(complete, tuple(reversed(rows)), checkpoint)
    left, right = (row for row in result.findings if row.conductor.pin_number == 1)
    assert left.side == "left" and left.lower_mm == Fraction(9, 1000)
    assert right.side == "right" and right.lower_mm == Fraction(7, 1000)
    assert left.first_terminal == UUID(int=90001) and right.first_terminal == UUID(int=90000)
    assert len(left.first_route_ids) == len(right.first_route_ids) == 2
    assert len(left.last_route_ids) == len(right.last_route_ids) == 1


def test_exact_disjoint_interval_witnesses_cannot_cancel_stretch_against_compression() -> None:
    """
    The affine-in-space side returns to equal total length yet stretches0.25mm on one half.
    """
    varying = replace(frame(), width=(Vector3(0, 1, 0), Vector3(1, 1, 0), Vector3(0, 1, 0)))
    geometry = replace(planned(data()), patches=(patches(varying),))
    work = WitnessWork(4, checkpoint)
    result = measure(geometry, 2, work)
    assert work.calls == 4
    assert result.lower_mm("left") == result.lower_mm("right") == Fraction(1, 4)
    assert all(sum(p.excess_lower_mm for p in side) == Fraction(0) for side in result.samples[0])


def test_multispan_partition_keeps_global_shape_and_counts_all_original_spans() -> None:
    """
    A geometric subdivision agrees with the same fixed global partition on the original morph.
    """
    work = WitnessWork(8, checkpoint)
    whole = measure(planned(data()), 2, work)
    split = measure(planned(data(split=True)), 1, work)
    assert work.calls == 8 and len(split.samples) == 2
    assert split.lower_mm("left") == whole.lower_mm("left")
    assert split.lower_mm("right") == whole.lower_mm("right")


@pytest.mark.parametrize("fault", ("missing", "duplicate", "stale", "partition", "coordinate"))
def test_incomplete_or_stale_receipts_cannot_hide_unmeasured_geometry(fault: str) -> None:
    """
    UUID reuse and a plausible numeric amount do not establish exact interval coverage.
    """
    complete = capture(*inputs())
    rows = tuple(synthetic(branch, Fraction(0), Fraction(0)) for branch in complete.branches)
    if fault == "missing":
        rows = rows[:-1]
    elif fault == "duplicate":
        rows += (rows[0],)
    elif fault == "stale":
        rows = (
            replace(rows[0], plan=replace(rows[0].plan, source=replace(rows[0].plan.source))),
        ) + rows[1:]
    else:
        row = rows[0]
        proof = row.samples[0][0][0]
        changed = (
            replace(proof, low=Fraction(1, 2))
            if fault == "partition"
            else replace(proof, edge_coordinate=Fraction(1, 3))
        )
        rows = (replace(row, samples=(((changed,), row.samples[0][1]),)),) + rows[1:]
    with pytest.raises(IncompleteRibbonInput):
        account(complete, rows, checkpoint)


def test_shared_work_and_caller_stop_propagate_without_fallback() -> None:
    """
    Exhaustion before a fourth required witness is not an unwitnessed successful audit.
    """
    geometry = planned(data())
    work = WitnessWork(3, checkpoint)
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        measure(geometry, 2, work)
    assert work.calls == 3

    def stopped() -> None:
        """
        Represent the caller's existing cancellation or resource stop.
        """
        raise TimeoutError("caller stop")

    stopped_work = WitnessWork(4, stopped)
    with pytest.raises(TimeoutError, match="caller stop"):
        measure(geometry, 2, stopped_work)
    assert stopped_work.calls == 0


def test_complete_entry_rejects_missing_geometry_before_measurement() -> None:
    """
    An unresolved trunk or missing ending cannot acquire a partial complete-path result.
    """
    plan = prepare(targets(), trunk, checkpoint, lambda event: None)
    work = WitnessWork(32, checkpoint)
    for changed in (
        replace(plan, branches=plan.branches[:-1]),
        replace(plan, trunk=replace(plan.trunk, route=None)),
    ):
        with pytest.raises(IncompleteRibbonInput):
            audit(changed, 1, work)
    assert work.calls == 0


@pytest.mark.parametrize("count", (True, 0, 65))
def test_bad_partition_policy_does_not_spend_witness_work(count: int) -> None:
    """
    Caller policy is explicit and bounded rather than silently clamped or expanded.
    """
    work = WitnessWork(2, checkpoint)
    with pytest.raises(ValueError):
        measure(planned(data()), count, work)
    assert work.calls == 0
