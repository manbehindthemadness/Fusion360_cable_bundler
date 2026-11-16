"""
Compose a conditioned piecewise material atlas without claiming physical metric or native compliance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .branch_interior import BranchInterior
from .branch_interior import audit as audit_geometry
from .branch_plan import SpatialBranchPlan
from .root_convexity import RootConvexity
from .root_convexity import certify as certify_convexity
from .ruled_support import square_root_upper
from .transport_regularity import TransportRegularity
from .transport_regularity import certify as certify_transport


@dataclass(frozen=True)
class MaterialAtlas:
    """
    Retain source, convexity, global geometry and all source-fan derivative certificates together.
    """

    plan: SpatialBranchPlan
    geometry: BranchInterior
    convexity: RootConvexity
    transports: tuple[TransportRegularity, ...]
    status: str
    source_condition_upper: Fraction | None
    world_condition_upper: Fraction | None


def validate(atlas: MaterialAtlas, checkpoint: Callable[[], None]) -> None:
    """
    Require complete coordinate evidence on the identical source plan before borrowing its guarantees.

    Equality of regenerated plans or a copied outer status cannot transfer a
    certificate. This checks immutable receipt ownership and complete positive
    bounds, not physical metrics or native geometry. No proof work is renewed.
    """
    checkpoint()
    geometry = atlas.geometry
    sections = geometry.transverse.sections
    if (
        atlas.status != "certified_piecewise_coordinates"
        or geometry.plan is not atlas.plan
        or atlas.convexity.domain is not geometry.transverse
        or not sections
        or not atlas.plan.patches
        or len(sections) != len(atlas.plan.patches[0])
        or any(s is not p.section for s, p in zip(sections, atlas.plan.patches[0]))
        or len(atlas.transports) != len(sections)
        or not (
            geometry.transverse.status
            == geometry.world_map.status
            == geometry.local_coordinate_status
            == atlas.convexity.status
            == "certified"
        )
        or atlas.world_condition_upper is None
        or not Fraction(0) < atlas.world_condition_upper <= 1024
        or geometry.world_map.minimum_monotonicity is None
        or geometry.world_map.minimum_monotonicity <= Fraction(0)
        or geometry.world_map.inverse_root_basis is None
        or any(
            row.section is not section
            or row.status != "certified"
            or row.minimum_monotonicity is None
            or row.minimum_monotonicity <= Fraction(0)
            or row.derivative_frobenius_squared_upper is None
            or row.derivative_frobenius_squared_upper < Fraction(0)
            or row.longitudinal_rate_squared_upper is None
            or row.longitudinal_rate_squared_upper < Fraction(0)
            for row, section in zip(atlas.transports, sections)
        )
    ):
        raise ValueError("A complete material atlas bound to the same source plan is required")


def audit(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> MaterialAtlas:
    """
    Prove a sufficient global piecewise-coordinate map, including source/world conditioning.

    On a convex root disk, positive symmetric Cartesian derivatives integrate
    along source segments even across finitely many continuous fan interfaces.
    The identity collar covers the center. Thus each transverse map is strongly
    monotone/injective, and its inherited single-winding boundary bounds exactly
    the target disk. Keeping u unchanged gives global material-coordinate
    injectivity; the qualified world chart preserves it. One-sided interface
    derivatives are bounded, not asserted equal or physically isometric.

    Source block Jacobian is [[1,0],[T_u,D_xT]]. Frobenius bounds give
    condition <=sqrt((1+rate²+K²)*(1+(2+rate²)/m²)); multiply by the
    world chart's condition bound. Both use the same fixed1mm/u convention and
    the existing1024numerical-conditioning ceiling. No arc-length identity,
    inverse implementation, physical strain, contact or native pass follows.
    """
    geometry = audit_geometry(plan, checkpoint)
    convexity = certify_convexity(geometry.transverse, checkpoint)
    prerequisites = (
        geometry.transverse.status
        == geometry.world_map.status
        == geometry.local_coordinate_status
        == convexity.status
        == "certified"
    )
    measured = []
    if prerequisites:
        for section in geometry.transverse.sections:
            row = certify_transport(section, checkpoint)
            measured.append(row)
            if row.status != "certified":
                break
    transports = tuple(measured)
    valid = (
        prerequisites
        and len(transports) == len(geometry.transverse.sections)
        and bool(transports)
        and all(row.status == "certified" for row in transports)
    )
    source_condition = None
    world_condition = None
    if valid:
        lower = min(
            row.minimum_monotonicity for row in transports if row.minimum_monotonicity is not None
        )
        norm2 = max(
            row.derivative_frobenius_squared_upper
            for row in transports
            if row.derivative_frobenius_squared_upper is not None
        )
        rate2 = max(
            row.longitudinal_rate_squared_upper
            for row in transports
            if row.longitudinal_rate_squared_upper is not None
        )
        source_condition = square_root_upper((1 + rate2 + norm2) * (1 + (2 + rate2) / lower**2))
        if geometry.world_map.condition_upper is not None:
            world_condition = source_condition * geometry.world_map.condition_upper
    state = (
        "certified_piecewise_coordinates"
        if world_condition is not None and world_condition <= 1024
        else "unresolved"
    )
    checkpoint()
    return MaterialAtlas(
        plan, geometry, convexity, transports, state, source_condition, world_condition
    )
