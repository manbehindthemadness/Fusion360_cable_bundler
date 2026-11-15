"""
Bind required left/center/right length comparisons to explicit mid-thickness source traces.

This does not require equal lengths through thickness, or certify transverse
metrics, an interior material map, curvature, contact or native correspondence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .material_paths import SpanPathBound, enclose
from .profile_transition import TransitionEdge
from .spatial_frame import split_at


@dataclass(frozen=True)
class MaterialTrace:
    """
    Retain a source edge and exact parameter for one ordered mid-thickness boundary path.
    """

    edge_index: int
    coordinate: Fraction
    root_q_mm: Fraction


def traces(sections: tuple[TransitionEdge, ...]) -> tuple[MaterialTrace, MaterialTrace]:
    """
    Identify all root b=0 crossings before selecting their ordered left/right extrema.

    Supported joined-profile edges either have one thickness sign, an endpoint
    zero, or a strictly monotone symmetric crossing at v=1/2. Any unsupported
    crossing is refused instead of silently sampled away. Selected source traces
    must remain exactly b=0 and on their original q side for the complete morph;
    this is coordinate identity, not a tightened physical distance tolerance.
    """
    candidates: list[MaterialTrace] = []
    for index, section in enumerate(sections):
        b = tuple(p[1] for p in section.rows[0])
        if not any(b):
            raise ValueError("A boundary lying in the midplane needs an explicit trace contract")
        coordinates = [Fraction(i) for i in (0, 1) if b[2 * i] == Fraction(0)]
        if min(b) < Fraction(0) < max(b):
            middle = split_at(b, Fraction(1, 2))[0][-1]
            derivative = (b[1] - b[0], b[2] - b[1])
            if middle != Fraction(0) or not (
                min(derivative) > Fraction(0) or max(derivative) < Fraction(0)
            ):
                raise ValueError(
                    "Unsupported midplane crossing requires an explicit trace contract"
                )
            coordinates.append(Fraction(1, 2))
        for coordinate in coordinates:
            values = tuple(
                tuple(split_at(tuple(p[k] for p in row), coordinate)[0][-1] for k in range(3))
                for row in section.rows
            )
            if any(p[1] != Fraction(0) for p in values):
                raise ValueError("Original mid-thickness trace leaves the material midplane")
            q = values[0][0] / values[0][2]
            candidates.append(MaterialTrace(index, coordinate, q))
    if not candidates:
        raise ValueError("Both ordered mid-thickness boundary traces are required")
    left = min(candidates, key=lambda candidate: candidate.root_q_mm)
    right = max(candidates, key=lambda candidate: candidate.root_q_mm)
    if not left.root_q_mm < Fraction(0) < right.root_q_mm:
        raise ValueError("Mid-thickness traces must bracket the original conductor center")
    for trace, sign in ((left, -1), (right, 1)):
        section = sections[trace.edge_index]
        if any(
            sign * split_at(tuple(p[0] for p in row), trace.coordinate)[0][-1] <= Fraction(0)
            for row in section.rows
        ):
            raise ValueError("Ordered mid-thickness trace changes material side")
    return left, right


@dataclass(frozen=True)
class MidlineAudit:
    """
    Keep corresponding left/center/right interval bounds on the same immutable branch geometry.
    """

    plan: SpatialBranchPlan
    left: MaterialTrace
    right: MaterialTrace
    status: str
    pairwise_upper_mm: Fraction | None
    spans: tuple[tuple[SpanPathBound, SpanPathBound], ...]


def audit(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> MidlineAudit:
    """
    Bound the required mid-thickness path discrepancies without per-span slack or total cancellation.

    The branch assembler owns closed ordered span and profile validation. This
    entry preserves its source and patch identities and never clears its missing
    physical/native checks. Unsupported trace identity is a contract error;
    overlarge metric bounds remain unresolved, not a proof of infeasibility.
    Left-to-right discrepancy is bounded by the sum of their center-relative
    discrepancies, which also bounds either center comparison. Accumulate that
    sum once across spans; doubling the worse side is unnecessary for two traces.
    """
    checkpoint()
    validate_patches(plan.patches, checkpoint)
    left, right = traces(tuple(patch.section for patch in plan.patches[0]))
    proofs = tuple(
        (
            enclose(span[left.edge_index], checkpoint, edge_coordinate=left.coordinate),
            enclose(span[right.edge_index], checkpoint, edge_coordinate=right.coordinate),
        )
        for span in plan.patches
    )
    accumulated = Fraction(0)
    for first, second in proofs:
        a, b = first.discrepancy_upper_mm, second.discrepancy_upper_mm
        if a is None or b is None:
            return MidlineAudit(plan, left, right, "unresolved", None, proofs)
        accumulated += a + b
    pairwise = accumulated
    return MidlineAudit(
        plan,
        left,
        right,
        "certified" if pairwise <= Fraction(1, 100) else "unresolved",
        pairwise,
        proofs,
    )
