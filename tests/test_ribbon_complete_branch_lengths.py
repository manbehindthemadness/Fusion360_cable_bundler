"""
Verify actual branch geometry lengths, complete coverage and rejection of stale preview transfers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from typing import cast

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_lengths import (
    SpatialBranchLength,
    audit_end_allowance,
    iter_lengths,
    measure,
)
from experiments.experiment_ribbon_complete.branch_plan import SpatialBranchPlan, assemble
from experiments.experiment_ribbon_complete.capture import capture
from experiments.experiment_ribbon_complete.contracts import (
    CompleteRibbonInput,
    IncompleteRibbonInput,
)
from experiments.experiment_ribbon_complete.curve_lengths import LengthWork, enclose_segments
from experiments.experiment_ribbon_complete.lengths import AllowanceState
from experiments.experiment_ribbon_complete.root_profiles import bind_frame, partition
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from experiments.experiment_ribbon_complete.spatial_transition import compose
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint, measurements


def complete_plans(
    lines: int = 2, check: Callable[[], None] = checkpoint
) -> tuple[CompleteRibbonInput, tuple[SpatialBranchPlan, ...]]:
    """
    Assemble every synthetic root branch under the supplied shared preparation/measurement checkpoint.
    """
    check()
    complete = capture(*inputs(lines))
    roots = partition(lines, 0.75)
    output = []
    for source in complete.branches:
        check()
        index = complete.group.connection_ids.index(source.source.leg.start_connection_id)
        side = "start" if index == 0 else "end"
        port = complete.caps[index]
        cap = bind_frame(complete.trunk, side, port.target.point, port.target.tangent)
        curve = source.source.route.curves[0]
        frame = FrameSpan(
            Fraction(0),
            Fraction(1),
            (curve.end, curve.control_b, curve.control_a, curve.start),
            (Vector3(0, 1, 0),),
            (Vector3(0, 0, 1),),
            ChartOrientation.NEGATIVE if index == 0 else ChartOrientation.POSITIVE,
        )
        center = (source.conductor.pin_number - (lines + 1) / 2) * 0.75
        output.append(
            assemble(
                complete,
                source.source.leg.route_id,
                roots[source.conductor.pin_number - 1],
                center,
                cap,
                (frame,),
                check,
            )
        )
    return complete, tuple(output)


@pytest.mark.parametrize("degree", (0, 1, 2, 3, 5))
def test_shared_length_kernel_preserves_degree_and_physical_units(degree: int) -> None:
    """
    Degree elevation and local parameterization do not change a ten-millimeter segment.
    """
    segment = (
        tuple((Fraction(10 * i, degree), Fraction(0), Fraction(0)) for i in range(degree + 1))
        if degree
        else ((Fraction(2), Fraction(0), Fraction(0)),)
    )
    result = enclose_segments((segment,), LengthWork(1, checkpoint), "analytical affine polynomial")
    expected = 10 if degree else 0
    assert result.length.lower_mm <= expected <= result.length.upper_mm
    assert result.cells == 1 and result.resolution_reached


def test_actual_lengths_cover_all_branches_and_keep_other_physical_checks() -> None:
    """
    Measure every constructed source field rather than projecting original preview receipts onto it.
    """
    complete, plans = complete_plans()
    work = LengthWork(len(plans), checkpoint)
    measured = tuple(iter_lengths(plans, work, "complete analytical branch plans"))
    assert tuple(row.plan for row in measured) == plans
    assert all(row.center.length.lower_mm == row.center.length.upper_mm == 3 for row in measured)
    assert all(row.material_envelope is not None for row in measured)
    trunks, _ = measurements(complete, trunk=10)
    findings = audit_end_allowance(complete, trunks, plans, measured, checkpoint=checkpoint)
    assert len(findings.findings) == len(plans)
    assert all(row.state is AllowanceState.FAIL for row in findings.findings)
    assert all("native_junctions" in row.plan.outstanding for row in findings.branches)


def test_same_preview_and_uuid_do_not_transfer_receipts_to_regenerated_plan() -> None:
    """
    Even equal field values in a new plan object need an explicitly bound geometry receipt.
    """
    complete, plans = complete_plans()
    measured = tuple(iter_lengths(plans, LengthWork(len(plans), checkpoint), "original plans"))
    trunks, _ = measurements(complete)
    changed = (replace(plans[0]),) + plans[1:]
    with pytest.raises(IncompleteRibbonInput, match="stale geometry provenance"):
        audit_end_allowance(complete, trunks, changed, measured, checkpoint=checkpoint)


def test_missing_geometry_receipts_do_not_become_preview_fallbacks() -> None:
    """
    Refuse incomplete coverage and missing material bounds even when all preview routes exist.
    """
    complete, plans = complete_plans()
    measured = tuple(iter_lengths(plans, LengthWork(len(plans), checkpoint), "original plans"))
    trunks, _ = measurements(complete)
    with pytest.raises(IncompleteRibbonInput, match="exactly one"):
        audit_end_allowance(complete, trunks, plans, measured[:-1], checkpoint=checkpoint)
    missing = (replace(measured[0], material_envelope=None),) + measured[1:]
    with pytest.raises(IncompleteRibbonInput, match="unresolved"):
        audit_end_allowance(complete, trunks, plans, missing, checkpoint=checkpoint)


def test_shared_cell_stop_retains_only_the_measured_prefix() -> None:
    """
    Actual spatial measurements cannot acquire a fresh subdivision allocation for each branch.
    """
    _complete, plans = complete_plans()
    work = LengthWork(1, checkpoint)
    stream = iter_lengths(plans, work, "bounded actual geometry")
    first = next(stream)
    assert first.plan is plans[0]
    with pytest.raises(RuntimeError, match="allocation exhausted"):
        next(stream)
    assert work.used_cells == 1


def test_changed_center_fields_are_measured_without_using_the_old_preview_length() -> None:
    """
    A source preview with unchanged identity cannot conceal a longer actual polynomial center path.
    """
    _complete, plans = complete_plans()
    original = plans[0]
    span = original.patches[0][0].frame
    bent = replace(
        span,
        center=(span.center[0], span.center[0].translated(Vector3(0, 0, 1), 2), span.center[-1]),
    )
    geometry = replace(
        original,
        patches=(tuple(compose(patch.section, bent, checkpoint) for patch in original.patches[0]),),
    )
    result = measure(geometry, LengthWork(127, checkpoint), "explicit changed analytical geometry")
    assert result.plan.source.source.route is original.source.source.route
    assert result.center.length.lower_mm > 3


def test_patches_cannot_use_different_center_references_inside_one_span() -> None:
    """
    Refuse inconsistent geometry before combining lengths relative to two different centers.
    """
    _complete, plans = complete_plans()
    original = plans[0]
    span = original.patches[0]
    shifted = replace(
        span[-1].frame,
        center=tuple(p.translated(Vector3(0, 0, 1), 1) for p in span[-1].frame.center),
    )
    changed = replace(
        original, patches=(span[:-1] + (compose(span[-1].section, shifted, checkpoint),),)
    )
    with pytest.raises(ValueError, match="same ordered section and frame"):
        measure(changed, LengthWork(127, checkpoint), "inconsistent reference fields")


def test_analytical_preparation_honors_the_callers_resource_stop() -> None:
    """
    A frozen mechanism packet cannot hide its plan preparation outside the shared resource guard.
    """

    def stopped() -> None:
        """
        Simulate a latched resource failure before constructing the analytical plan.
        """
        raise RuntimeError("latched preparation stop")

    with pytest.raises(RuntimeError, match="latched preparation stop"):
        complete_plans(2, stopped)


def test_preview_only_receipts_are_not_actual_geometry_measurements() -> None:
    """
    Refuse the alternate receipt type explicitly even though all frozen route identities match.
    """
    complete, plans = complete_plans()
    trunks, previews = measurements(complete)
    malformed = cast(tuple[SpatialBranchLength, ...], cast(object, previews))
    with pytest.raises(IncompleteRibbonInput, match="preview-only receipts"):
        audit_end_allowance(complete, trunks, plans, malformed, checkpoint=checkpoint)
