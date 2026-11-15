"""
Measure actual spatial branch plans and bind their lengths to complete ending-allowance audits.

Preview receipts remain separate. Native geometry requires its own fidelity and
measurement evidence; this module makes no such transfer or acceptance claim.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .contracts import CompleteRibbonInput, IncompleteRibbonInput
from .curve_lengths import CurveLength, LengthWork, enclose_segments, outward
from .lengths import EndAllowance, LengthBasis, LengthEvidence, TrunkLength, audit_ranges
from .material_traces import MidlineAudit
from .material_traces import audit as audit_midline
from .spatial_frame import components


@dataclass(frozen=True)
class SpatialBranchLength:
    """
    Retain the exact plan, center measurement and enclosing left/center/right path range.

    A missing material envelope means the midline speed denominator was unresolved;
    it is never replaced with the preview or the center alone. Length uncertainty
    and local material compatibility remain distinct checks.
    """

    plan: SpatialBranchPlan
    center: CurveLength
    midline: MidlineAudit
    material_envelope: LengthEvidence | None


def measure(plan: SpatialBranchPlan, work: LengthWork, receipt: str) -> SpatialBranchLength:
    """
    Enclose the actual center fields and expand by rigorous individual midline discrepancy bounds.

    Measure physical polynomial controls, not global parameter width or the frozen
    preview. Left/right absolute integral bounds establish length intervals about
    that same center. Their union encloses each required material path for later
    conservative serial accounting, without a new dimensional allowance.
    """
    work.checkpoint()
    frames = validate_patches(plan.patches, work.checkpoint)
    segments = tuple(
        tuple(
            tuple(field[i] for field in components(frame.center)) for i in range(len(frame.center))
        )
        for frame in frames
    )
    center = enclose_segments(segments, work, receipt)
    midline = audit_midline(plan, work.checkpoint)
    left, right = Fraction(0), Fraction(0)
    for a, b in midline.spans:
        if a.discrepancy_upper_mm is None or b.discrepancy_upper_mm is None:
            return SpatialBranchLength(plan, center, midline, None)
        left += a.discrepancy_upper_mm
        right += b.discrepancy_upper_mm
    deviation = max(left, right)
    low, high = center.length.bounds
    envelope = LengthEvidence(
        outward(max(Fraction(0), low - deviation), False),
        outward(high + deviation, True),
        LengthBasis.ENCLOSURE,
        receipt + "/left-center-right-envelope",
    )
    return SpatialBranchLength(plan, center, midline, envelope)


def iter_lengths(
    plans: tuple[SpatialBranchPlan, ...], work: LengthWork, receipt_prefix: str
) -> Iterator[SpatialBranchLength]:
    """
    Yield ordered receipts immediately under the same aggregate cell/time/memory allocation.
    """
    if not isinstance(receipt_prefix, str) or not receipt_prefix.strip():
        raise ValueError("Actual branch measurements require an explicit evidence origin")
    for plan in plans:
        work.checkpoint()
        yield measure(plan, work, f"{receipt_prefix}/route/{plan.source.source.leg.route_id}")


@dataclass(frozen=True)
class SpatialAllowanceAudit:
    """
    Retain all actual geometry receipts alongside the named allowance findings only.
    """

    branches: tuple[SpatialBranchLength, ...]
    findings: tuple[EndAllowance, ...]


def audit_end_allowance(
    complete: CompleteRibbonInput,
    trunks: tuple[TrunkLength, ...],
    plans: tuple[SpatialBranchPlan, ...],
    measured: tuple[SpatialBranchLength, ...],
    *,
    checkpoint: Callable[[], None],
) -> SpatialAllowanceAudit:
    """
    Check complete coverage and exact plan provenance before reusing the shared interval accounting.

    Matching route UUIDs/previews alone cannot transfer a length to a regenerated
    spatial plan. Every receipt must own the expected plan object and complete
    material envelope. Local equality can remain unresolved even if the separate
    six-percent allowance resolves. Trunk receipts still need their independent
    geometry provenance; synthetic receipts provide arithmetic evidence only.
    """
    checkpoint()
    if any(not isinstance(row, SpatialBranchLength) for row in measured):
        raise IncompleteRibbonInput("Actual geometry lengths cannot use preview-only receipts")
    expected = {plan.source.source.leg.route_id: plan for plan in plans}
    receipts = {row.plan.source.source.leg.route_id: row for row in measured}
    if (
        len(expected) != len(plans)
        or len(receipts) != len(measured)
        or set(expected) != {branch.source.leg.route_id for branch in complete.branches}
        or set(receipts) != set(expected)
    ):
        raise IncompleteRibbonInput(
            "Every actual branch plan needs exactly one geometry length receipt"
        )
    for branch in complete.branches:
        checkpoint()
        identity = branch.source.leg.route_id
        plan, row = expected[identity], receipts[identity]
        if plan.source is not branch or row.plan is not plan or row.midline.plan is not plan:
            raise IncompleteRibbonInput(
                "Actual branch length receipt has stale geometry provenance"
            )
        if row.material_envelope is None:
            raise IncompleteRibbonInput("Actual material path length enclosure is unresolved")
    ranges = {
        row.plan.source.source.leg.route_id: row.material_envelope
        for row in measured
        if row.material_envelope is not None
    }
    return SpatialAllowanceAudit(
        measured, audit_ranges(complete, trunks, ranges, checkpoint=checkpoint)
    )
