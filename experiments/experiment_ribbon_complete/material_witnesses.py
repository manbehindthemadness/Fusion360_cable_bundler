"""
Witness planned material extension across both ordered ending chains of a complete ribbon.

Exact chords lower-bound boundary length and center control polygons upper-bound
center length. Positive interval excesses lower-bound absolute corresponding
increment discrepancy without cancellation. An unwitnessed violation is never a
compliance pass. Native fidelity and junction material correspondence remain open.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal
from uuid import UUID

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .contracts import CompleteRibbonInput, ConductorKey, IncompleteRibbonInput
from .execution import RibbonPlan
from .material_paths import StretchWitness, witness
from .material_traces import MaterialTrace, traces
from .topology import terminal_chains

Side = Literal["left", "right"]
SideSamples = tuple[StretchWitness, ...]
SpanSamples = tuple[SideSamples, SideSamples]


@dataclass
class WitnessWork:
    """
    Debit every exact chord witness from one explicit caller-owned aggregate allocation.
    """

    maximum_calls: int
    checkpoint: Callable[[], None]
    calls: int = 0

    def __post_init__(self) -> None:
        """
        Reject malformed limits rather than silently granting additional work.
        """
        if type(self.maximum_calls) is not int or self.maximum_calls < 1 or self.calls != 0:
            raise ValueError("Declare a positive fresh witness allocation")

    def take(self) -> None:
        """
        Stop before the next witness when caller cancellation or the shared count is exhausted.
        """
        self.checkpoint()
        if self.calls >= self.maximum_calls:
            raise RuntimeError("Shared material witness allocation exhausted")
        self.calls += 1


@dataclass(frozen=True)
class BranchExtension:
    """
    Retain actual source-labelled interval witnesses on every original spatial span.
    """

    plan: SpatialBranchPlan
    intervals_per_span: int
    traces: tuple[MaterialTrace, MaterialTrace]
    samples: tuple[SpanSamples, ...]

    def lower_mm(self, side: Side) -> Fraction:
        """
        Sum positive disjoint-interval excesses; compression elsewhere cannot cancel them.
        """
        if side not in ("left", "right"):
            raise ValueError("Choose an original ordered material side")
        index = 0 if side == "left" else 1
        return sum(
            (
                max(Fraction(0), proof.excess_lower_mm)
                for span in self.samples
                for proof in span[index]
            ),
            Fraction(0),
        )


def measure(plan: SpatialBranchPlan, intervals_per_span: int, work: WitnessWork) -> BranchExtension:
    """
    Measure a fixed exact partition of every span without search, quadrature or refinement.

    A positive chord excess certifies extension on that interval. It lower-bounds
    absolute speed discrepancy even when a different interval compresses. The
    fixed partition can miss violations and is therefore a rejection witness
    only. Source frames, targets, controls and global intervals are unchanged.
    """
    if type(intervals_per_span) is not int or not 1 <= intervals_per_span <= 64:
        raise ValueError("Freeze1..64intervals per original span before measurement")
    validate_patches(plan.patches, work.checkpoint)
    sides = traces(tuple(p.section for p in plan.patches[0]))
    output: list[SpanSamples] = []
    for span in plan.patches:
        measured = []
        for trace in sides:
            samples = []
            for index in range(intervals_per_span):
                work.take()
                samples.append(
                    witness(
                        span[trace.edge_index],
                        Fraction(index, intervals_per_span),
                        Fraction(index + 1, intervals_per_span),
                        trace.coordinate,
                        work.checkpoint,
                    )
                )
            measured.append(tuple(samples))
        output.append((measured[0], measured[1]))
    return BranchExtension(plan, intervals_per_span, sides, tuple(output))


def iter_extensions(
    plans: tuple[SpatialBranchPlan, ...], intervals_per_span: int, work: WitnessWork
) -> Iterator[BranchExtension]:
    """
    Yield complete branch receipts in supplied order, preserving a prefix on caller stop.
    """
    for plan in plans:
        yield measure(plan, intervals_per_span, work)


@dataclass(frozen=True)
class CompletePathWitness:
    """
    Identify a real terminal pair attaining the largest observed bound for one ordered side.
    """

    conductor: ConductorKey
    side: Side
    first_terminal: UUID
    last_terminal: UUID
    first_route_ids: tuple[UUID, ...]
    last_route_ids: tuple[UUID, ...]
    lower_mm: Fraction

    @property
    def violation(self) -> bool:
        """
        Apply the single inclusive0.01mm rule; a lower bound equal to it is inconclusive.
        """
        return self.lower_mm > Fraction(1, 100)


@dataclass(frozen=True)
class CompleteWitnessAudit:
    """
    Report planned rejection evidence without clearing any whole-ribbon qualification gate.

    Ordered source left/right labels are preserved across the declared conductor.
    Actual junction/native correspondence is not proved here. The trunk's
    nonnegative absolute discrepancy is omitted from a lower bound, never set
    to zero in an upper-bound certificate. No result from this adapter is a pass.
    """

    plan: CompleteRibbonInput
    branches: tuple[BranchExtension, ...]
    findings: tuple[CompletePathWitness, ...]

    @property
    def status(self) -> Literal["violated", "not_witnessed"]:
        """
        Distinguish a proven planned-path discrepancy from absence of a witness.
        """
        return (
            "violated" if any(finding.violation for finding in self.findings) else "not_witnessed"
        )


def account(
    plan: CompleteRibbonInput,
    measured: tuple[BranchExtension, ...],
    checkpoint: Callable[[], None],
) -> CompleteWitnessAudit:
    """
    Sum serial descendants and both ends once while keeping siblings as alternatives.

    Every captured branch must retain its exact plan object and every fixed
    interval must own the expected patch and source coordinate. Maximize each
    side independently over actual terminal chains at both connections, retaining
    the selected terminal identities. Missing, duplicated or stale coverage is
    refused, not silently excluded. Supplied proof values are trusted receipts
    from measure; this is not a verifier for externally fabricated numerics.
    """
    checkpoint()
    expected = {branch.source.leg.route_id: branch for branch in plan.branches}
    receipts = {row.plan.source.source.leg.route_id: row for row in measured}
    if (
        len(expected) != len(plan.branches)
        or len(receipts) != len(measured)
        or set(receipts) != set(expected)
    ):
        raise IncompleteRibbonInput("Every original branch needs exactly one witness receipt")
    for identity, row in receipts.items():
        checkpoint()
        if row.plan.source is not expected[identity]:
            raise IncompleteRibbonInput("Witness receipt has stale complete-input ownership")
        validate_patches(row.plan.patches, checkpoint)
        if row.traces != traces(tuple(p.section for p in row.plan.patches[0])) or len(
            row.samples
        ) != len(row.plan.patches):
            raise IncompleteRibbonInput("Witnesses need original trace and complete span coverage")
        if type(row.intervals_per_span) is not int or not 1 <= row.intervals_per_span <= 64:
            raise IncompleteRibbonInput("Witness interval policy is invalid")
        for patches, span in zip(row.plan.patches, row.samples):
            if len(span) != 2:
                raise IncompleteRibbonInput("Both original material sides require witnesses")
            for trace, samples in zip(row.traces, span):
                if len(samples) != row.intervals_per_span:
                    raise IncompleteRibbonInput("Witness partition is incomplete")
                for index, proof in enumerate(samples):
                    checkpoint()
                    if (
                        proof.patch is not patches[trace.edge_index]
                        or proof.edge_coordinate != trace.coordinate
                        or proof.low != Fraction(index, row.intervals_per_span)
                        or proof.high != Fraction(index + 1, row.intervals_per_span)
                    ):
                        raise IncompleteRibbonInput(
                            "Witness interval/source correspondence changed"
                        )
    chains = terminal_chains(plan.branches, checkpoint)
    output = []
    sides: tuple[Side, Side] = ("left", "right")
    for conductor in plan.conductors:
        for side in sides:
            checkpoint()
            selected = []
            for connection in plan.group.connection_ids:
                candidates = [
                    chain
                    for chain in chains
                    if chain[0].conductor == conductor
                    and chain[0].source.leg.start_connection_id == connection
                ]
                if not candidates:
                    raise IncompleteRibbonInput(
                        "Both ends need an original conductor terminal chain"
                    )

                amounts = [
                    (
                        chain,
                        sum(
                            (receipts[b.source.leg.route_id].lower_mm(side) for b in chain),
                            Fraction(0),
                        ),
                    )
                    for chain in candidates
                ]
                selected.append(max(amounts, key=lambda item: item[1]))
            first, last = selected
            output.append(
                CompletePathWitness(
                    conductor,
                    side,
                    first[0][0].attachment.attachment_id,
                    last[0][0].attachment.attachment_id,
                    tuple(b.source.leg.route_id for b in first[0]),
                    tuple(b.source.leg.route_id for b in last[0]),
                    first[1] + last[1],
                )
            )
    return CompleteWitnessAudit(plan, measured, tuple(output))


def audit(plan: RibbonPlan, intervals_per_span: int, work: WitnessWork) -> CompleteWitnessAudit:
    """
    Audit one fully prepared original plan, with no constructor or additional work reserve.
    """
    if plan.trunk.route is None or plan.unattempted_route_ids:
        raise IncompleteRibbonInput("A complete prepared trunk and every ending are required")
    expected = {b.source.leg.route_id: b for b in plan.captured.branches}
    if len(plan.branches) != len(expected) or any(
        branch.source is not expected.get(branch.source.source.leg.route_id)
        for branch in plan.branches
    ):
        raise IncompleteRibbonInput("Prepared branches differ from the complete captured input")
    return account(
        plan.captured,
        tuple(iter_extensions(plan.branches, intervals_per_span, work)),
        work.checkpoint,
    )
