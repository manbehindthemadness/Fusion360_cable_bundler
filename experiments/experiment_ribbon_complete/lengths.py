"""
Audit ending allowances against complete conductor paths without summing parallel branches.

Length evidence is supplied by a separate planned/native measurement stage. This
module does not infer enclosures from sampled quadrature or certify the geometry
that produced them. Each leaf is a termination; explicit parent links describe
serial material within an end, and the shared root pin identifies its trunk lane.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from uuid import UUID

from cable_bundler.routing import RoutePreview

from .contracts import BranchPlan, CompleteRibbonInput, ConductorKey, IncompleteRibbonInput
from .topology import ancestry, terminal_chains


class LengthBasis(Enum):
    """
    Distinguish externally established bounds from unbounded sampling observations.
    """

    ENCLOSURE = "enclosure"
    SAMPLE_ESTIMATE = "sample_estimate"


@dataclass(frozen=True)
class LengthEvidence:
    """
    Retain a length range and its measurement provenance without inventing uncertainty.

    ENCLOSURE is a caller assertion requiring the referenced measurement receipt;
    it is never inferred from a small coarse/fine quadrature difference. Estimated
    ranges can be displayed but cannot establish an allowance pass or violation.
    """

    lower_mm: float
    upper_mm: float
    basis: LengthBasis
    receipt: str

    def __post_init__(self) -> None:
        """
        Require finite ordered nonnegative millimeter values and explicit evidence origin.
        """
        if (
            type(self.lower_mm) not in (int, float)
            or type(self.upper_mm) not in (int, float)
            or not math.isfinite(self.lower_mm)
            or not math.isfinite(self.upper_mm)
            or not 0 <= self.lower_mm <= self.upper_mm
            or not isinstance(self.basis, LengthBasis)
            or not isinstance(self.receipt, str)
            or not self.receipt.strip()
        ):
            raise ValueError("A length measurement needs a finite range and evidence provenance")

    @property
    def bounds(self) -> tuple[Fraction, Fraction]:
        """
        Preserve the exact supplied binary values during subsequent interval arithmetic.
        """
        return Fraction(self.lower_mm), Fraction(self.upper_mm)


@dataclass(frozen=True)
class TrunkLength:
    """
    Supply one full trunk lane and its two internal fitted-end regions.

    The internal regions are already included in trunk length. They increase the
    end-region numerator without being added a second time to the complete path.
    """

    conductor: ConductorKey
    length: LengthEvidence
    start_region: LengthEvidence
    end_region: LengthEvidence


@dataclass(frozen=True)
class BranchLength:
    """
    Bind one measured length to its unchanged frozen route, not merely a persistent UUID.
    """

    source: RoutePreview
    length: LengthEvidence

    @property
    def route_id(self) -> UUID:
        """
        Retain the source's persistent route identity alongside its full immutable geometry.
        """
        return self.source.cable_id


class AllowanceState(Enum):
    """
    Describe only the named ending allowance, never complete physical compliance.
    """

    PASS = "pass"
    FAIL = "fail"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class EndAllowance:
    """
    Retain one terminal chain's worst allowance over all opposite-end terminations.

    Margin is0.06*complete_path minus this entire end region. Different opposite
    terminals can bound its lower and upper values; both identities are retained.
    Exact arithmetic prevents accumulating a fresh tolerance per branch or station.
    """

    conductor: ConductorKey
    connection_id: UUID
    terminal_attachment_id: UUID
    route_ids: tuple[UUID, ...]
    opposite_lower_terminal: UUID
    opposite_upper_terminal: UUID
    margin_mm: tuple[Fraction, Fraction]
    complete_path_mm: tuple[Fraction, Fraction]
    receipts: tuple[str, ...]
    state: AllowanceState


def chain(
    terminal: BranchPlan,
    branches: dict[UUID, BranchPlan],
    lengths: dict[UUID, LengthEvidence],
    checkpoint: Callable[[], None],
) -> tuple[tuple[UUID, ...], tuple[LengthEvidence, ...]]:
    """
    Walk explicit terminal-to-root links, preserving serial route order and rejecting corruption.
    """
    ordered = ancestry(terminal, branches, checkpoint)
    return (
        tuple(b.source.leg.route_id for b in ordered),
        tuple(lengths[b.source.leg.route_id] for b in ordered),
    )


def summed(evidence: tuple[LengthEvidence, ...]) -> tuple[Fraction, Fraction]:
    """
    Sum serial ranges without assigning physical slack to individual segments.
    """
    bounds = tuple(value.bounds for value in evidence)
    return sum((a for a, _ in bounds), Fraction()), sum((b for _, b in bounds), Fraction())


def audit_end_allowance(
    plan: CompleteRibbonInput,
    trunks: tuple[TrunkLength, ...],
    measured_branches: tuple[BranchLength, ...],
    *,
    checkpoint: Callable[[], None],
) -> tuple[EndAllowance, ...]:
    """
    Check each full terminal chain against six percent of its complete conductor path.

    Require exactly one measurement for every frozen branch and every trunk lane;
    incomplete evidence raises IncompleteRibbonInput, never a geometric rejection.
    Each end includes its internal fitted region plus the entire serial chain.
    Complete path includes the trunk once and both external chains. Opposite
    branches are alternatives, not extra serial length. Monotonicity chooses the
    shortest opposite chain for the worst margin in linear rather than pairwise
    comparison work. A single inclusive0.01mm dimensional allowance applies to
    each complete end check; it is not0.01 added at every segment.

    Checkpoint is mandatory so callers retain their existing time/memory limits.
    Material increments, branch curvature, contact and native flow are separate.
    """
    checkpoint()
    lengths = {value.route_id: value.length for value in measured_branches}
    measured_sources = {value.route_id: value.source for value in measured_branches}
    route_ids = {branch.source.leg.route_id for branch in plan.branches}
    if len(lengths) != len(measured_branches) or set(lengths) != route_ids:
        raise IncompleteRibbonInput(
            "Every frozen trunk and branch needs exactly one length receipt"
        )
    if any(
        measured_sources[branch.source.leg.route_id] != branch.source.route
        for branch in plan.branches
    ):
        raise IncompleteRibbonInput(
            "A branch length receipt differs from its frozen route geometry"
        )
    return audit_ranges(plan, trunks, lengths, checkpoint=checkpoint)


def audit_ranges(
    plan: CompleteRibbonInput,
    trunks: tuple[TrunkLength, ...],
    lengths: dict[UUID, LengthEvidence],
    *,
    checkpoint: Callable[[], None],
) -> tuple[EndAllowance, ...]:
    """
    Apply only complete-path interval accounting after the caller validates geometry provenance.

    Preview and spatial-plan adapters enforce their distinct source contracts
    before calling this shared arithmetic. Range coverage, positive lengths,
    ancestry, conductor identity and the single dimensional allowance are checked
    here. Range labels alone make no claim about the geometry measured.
    """
    checkpoint()
    trunk_map = {value.conductor: value for value in trunks}
    if (
        len(trunk_map) != len(trunks)
        or set(trunk_map) != set(plan.conductors)
        or set(lengths) != {branch.source.leg.route_id for branch in plan.branches}
    ):
        raise IncompleteRibbonInput(
            "Every frozen trunk and branch needs exactly one length receipt"
        )
    if any(value.length.lower_mm <= 0 for value in trunks) or any(
        value.lower_mm <= 0 for value in lengths.values()
    ):
        raise IncompleteRibbonInput("Full trunk and branch lengths must have positive lower bounds")
    ordered = terminal_chains(plan.branches, checkpoint)
    leaves = tuple(values[0] for values in ordered)
    chains = {
        values[0].attachment.attachment_id: (
            tuple(branch.source.leg.route_id for branch in values),
            tuple(lengths[branch.source.leg.route_id] for branch in values),
        )
        for values in ordered
    }
    totals = {identity: summed(evidence) for identity, (_, evidence) in chains.items()}
    output = []
    fraction, accuracy = Fraction(3, 50), Fraction(1, 100)
    for conductor in plan.conductors:
        checkpoint()
        trunk = trunk_map[conductor]
        trunk_low, trunk_high = trunk.length.bounds
        sides = tuple(
            tuple(
                leaf
                for leaf in leaves
                if leaf.conductor == conductor and leaf.source.leg.start_connection_id == connection
            )
            for connection in plan.group.connection_ids
        )
        if any(not side for side in sides):
            raise IncompleteRibbonInput("Every conductor needs a terminal chain at both ends")
        for side, internal in enumerate((trunk.start_region, trunk.end_region)):
            opposite = sides[1 - side]
            lower_leaf = min(opposite, key=lambda leaf: totals[leaf.attachment.attachment_id][0])
            upper_leaf = min(opposite, key=lambda leaf: totals[leaf.attachment.attachment_id][1])
            opposite_low = totals[lower_leaf.attachment.attachment_id][0]
            opposite_high = totals[upper_leaf.attachment.attachment_id][1]
            opposite_maximum = max(totals[leaf.attachment.attachment_id][1] for leaf in opposite)
            all_opposite = tuple(
                e for leaf in opposite for e in chains[leaf.attachment.attachment_id][1]
            )
            internal_low, internal_high = internal.bounds
            for leaf in sides[side]:
                checkpoint()
                ids, evidence = chains[leaf.attachment.attachment_id]
                low, high = totals[leaf.attachment.attachment_id]
                margin = (
                    fraction * (trunk_low + opposite_low) - (1 - fraction) * high - internal_high,
                    fraction * (trunk_high + opposite_high) - (1 - fraction) * low - internal_low,
                )
                sources = (trunk.length, internal) + evidence + all_opposite
                bounded = all(value.basis is LengthBasis.ENCLOSURE for value in sources)
                state = AllowanceState.UNRESOLVED
                if bounded:
                    if margin[0] >= -accuracy:
                        state = AllowanceState.PASS
                    elif margin[1] < -accuracy:
                        state = AllowanceState.FAIL
                output.append(
                    EndAllowance(
                        conductor,
                        plan.group.connection_ids[side],
                        leaf.attachment.attachment_id,
                        ids,
                        lower_leaf.attachment.attachment_id,
                        upper_leaf.attachment.attachment_id,
                        margin,
                        (
                            trunk_low + low + opposite_low,
                            trunk_high + high + opposite_maximum,
                        ),
                        tuple(dict.fromkeys(value.receipt for value in sources)),
                        state,
                    )
                )
    return tuple(output)
