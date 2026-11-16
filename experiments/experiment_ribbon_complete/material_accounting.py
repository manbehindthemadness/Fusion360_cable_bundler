"""
Accumulate declared longitudinal discrepancy bounds over complete conductor paths.

This is conditional bound accounting. It does not establish that a supplied trunk
bound measures the actual volume, or that material labels correspond at junctions.
Those missing geometry qualifications are retained explicitly in the result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID

from .contracts import BranchPlan, CompleteRibbonInput, ConductorKey, IncompleteRibbonInput
from .material_contract import MaterialPathContract, bind
from .topology import terminal_chains


@dataclass(frozen=True)
class TrunkDiscrepancy:
    """
    Declare one whole-trunk pairwise increment bound with original input ownership and provenance.

    None means unavailable. A numeric value is a caller assertion, not inferred
    from targets or length receipts. It includes both internal fitted regions
    exactly once. Geometry-qualified trunk extraction remains a separate adapter.
    """

    plan: CompleteRibbonInput
    conductor: ConductorKey
    upper_mm: Fraction | None
    receipt: str

    def __post_init__(self) -> None:
        """
        Refuse negative/ambiguous bounds or absent evidence origin.
        """
        if (
            (
                self.upper_mm is not None
                and (type(self.upper_mm) is not Fraction or self.upper_mm < Fraction(0))
            )
            or not isinstance(self.receipt, str)
            or not self.receipt.strip()
        ):
            raise ValueError(
                "A trunk discrepancy needs a nonnegative exact bound or None and provenance"
            )


@dataclass(frozen=True)
class CompleteMaterialFinding:
    """
    Retain one end's worst opposite termination and one complete-path discrepancy budget.

    Overlarge upper bounds stay unresolved, never witnessed physical violations.
    An unknown opposite chain cannot be discarded in favor of a bounded sibling.
    """

    conductor: ConductorKey
    connection_id: UUID
    terminal_attachment_id: UUID
    route_ids: tuple[UUID, ...]
    opposite_terminal: UUID | None
    opposite_route_ids: tuple[UUID, ...]
    upper_mm: Fraction | None
    status: str
    unavailable_routes: tuple[UUID, ...]
    receipts: tuple[str, ...]


@dataclass(frozen=True)
class CompleteMaterialAccounting:
    """
    Keep conditional arithmetic separate from incomplete complete-geometry qualifications.
    """

    plan: CompleteRibbonInput
    trunks: tuple[TrunkDiscrepancy, ...]
    branches: tuple[MaterialPathContract, ...]
    findings: tuple[CompleteMaterialFinding, ...]
    outstanding: tuple[str, ...] = (
        "trunk_geometry_and_material_label_provenance",
        "junction_material_correspondence",
        "native_material_correspondence",
    )


def account(
    plan: CompleteRibbonInput,
    trunks: tuple[TrunkDiscrepancy, ...],
    contracts: tuple[MaterialPathContract, ...],
    checkpoint: Callable[[], None],
) -> CompleteMaterialAccounting:
    """
    Sum trunk once plus both serial external chains, retaining alternatives and missing evidence.

    Require every original branch contract and one explicit trunk declaration per
    conductor. The branch adapter rechecks atlas/metric/source ownership. Declared
    trunk ranges are not geometry-qualified merely by passing this arithmetic.
    Whole-profile and persistent junction label correspondence remain outstanding.

    Absolute local-increment discrepancy bounds add without cancellation. Maximize
    over opposite terminal chains in linear witness-selection work; never sum
    siblings as serial material. One inclusive0.01mm allowance applies to the full
    path. No per-component slack, fitted-region double count or work pool is added.
    """
    checkpoint()
    expected = {b.source.leg.route_id: b for b in plan.branches}
    supplied = {r.atlas.plan.source.source.leg.route_id: r for r in contracts}
    trunk_map = {r.conductor: r for r in trunks}
    if (
        len(supplied) != len(contracts)
        or set(supplied) != set(expected)
        or len(trunk_map) != len(trunks)
        or set(trunk_map) != set(plan.conductors)
    ):
        raise IncompleteRibbonInput(
            "Every original branch and trunk conductor needs exactly one material receipt"
        )
    if any(row.plan is not plan for row in trunks):
        raise IncompleteRibbonInput(
            "Trunk discrepancy declaration has stale complete-input ownership"
        )
    bounds: dict[UUID, Fraction | None] = {}
    for identity, receipt in supplied.items():
        checkpoint()
        if receipt.atlas.plan.source is not expected[identity]:
            raise IncompleteRibbonInput(
                "Material contract differs from the original captured branch"
            )
        validated = bind(receipt.atlas, receipt.midline, checkpoint)
        if validated != receipt:
            raise IncompleteRibbonInput(
                "Material contract differs from its canonical source trajectories"
            )
        bounds[identity] = receipt.midline.pairwise_upper_mm
    return CompleteMaterialAccounting(
        plan, trunks, contracts, account_ranges(plan, trunks, bounds, checkpoint)
    )


def account_ranges(
    plan: CompleteRibbonInput,
    trunks: tuple[TrunkDiscrepancy, ...],
    bounds: dict[UUID, Fraction | None],
    checkpoint: Callable[[], None],
) -> tuple[CompleteMaterialFinding, ...]:
    """
    Apply conditional bound arithmetic only after an adapter validates source geometry and material correspondence.

    Synthetic ranges are useful for accounting tests but establish no geometry
    qualification. None propagates as missing evidence. No measured violation is
    inferred from an overlarge upper bound. Internal fitted regions have no
    separate input because they already belong to the whole-trunk declaration.
    """
    checkpoint()
    trunk_map = {r.conductor: r for r in trunks}
    if (
        set(bounds) != {b.source.leg.route_id for b in plan.branches}
        or len(trunk_map) != len(trunks)
        or set(trunk_map) != set(plan.conductors)
        or any(r.plan is not plan for r in trunks)
    ):
        raise IncompleteRibbonInput(
            "Complete original trunk and branch material ranges are required"
        )
    if any(
        value is not None and (type(value) is not Fraction or value < Fraction(0))
        for value in bounds.values()
    ):
        raise IncompleteRibbonInput(
            "Material ranges must be nonnegative exact bounds or unavailable"
        )
    ordered = terminal_chains(plan.branches, checkpoint)
    leaves = tuple(chain[0] for chain in ordered)
    chains = {chain[0].attachment.attachment_id: chain for chain in ordered}
    ids = {key: tuple(b.source.leg.route_id for b in chain) for key, chain in chains.items()}
    missing = {key: tuple(i for i in routes if bounds[i] is None) for key, routes in ids.items()}
    sums: dict[UUID, Fraction | None] = {
        key: None if missing[key] else sum((bounds[i] or Fraction(0) for i in routes), Fraction(0))
        for key, routes in ids.items()
    }
    output = []
    for conductor in plan.conductors:
        checkpoint()
        trunk = trunk_map[conductor]
        sides = tuple(
            tuple(
                b
                for b in leaves
                if b.conductor == conductor and b.source.leg.start_connection_id == connection
            )
            for connection in plan.group.connection_ids
        )
        if any(not side for side in sides):
            raise IncompleteRibbonInput(
                "Every material conductor needs terminal chains at both ends"
            )
        for index, side in enumerate(sides):
            opposite = sides[1 - index]
            unavailable = tuple(i for b in opposite for i in missing[b.attachment.attachment_id])
            witness: BranchPlan | None = (
                None
                if unavailable
                else max(opposite, key=lambda b: sums[b.attachment.attachment_id] or Fraction(0))
            )
            opposite_id = None if witness is None else witness.attachment.attachment_id
            for leaf in side:
                checkpoint()
                key = leaf.attachment.attachment_id
                a = sums[key]
                b = None if opposite_id is None else sums[opposite_id]
                total = (
                    None
                    if trunk.upper_mm is None or a is None or b is None
                    else trunk.upper_mm + a + b
                )
                output.append(
                    CompleteMaterialFinding(
                        conductor,
                        plan.group.connection_ids[index],
                        key,
                        ids[key],
                        opposite_id,
                        () if opposite_id is None else ids[opposite_id],
                        total,
                        "within_declared_bound"
                        if total is not None and total <= Fraction(1, 100)
                        else "unresolved",
                        tuple(dict.fromkeys(missing[key] + unavailable)),
                        (trunk.receipt,)
                        + tuple(
                            str(i)
                            for i in ids[key] + (() if opposite_id is None else ids[opposite_id])
                        ),
                    )
                )
    return tuple(output)
