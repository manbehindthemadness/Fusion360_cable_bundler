"""
Bind transverse disks and globally unique geometric coordinates to the same branch plan.

This geometric domain is not persistent interior material transport, isometry,
cross-branch contact, native construction or complete physical acceptance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .global_chart import GlobalChart, certify
from .section_domain import SectionDomain, certify_domain
from .spatial_certificate import certify as certify_coordinates


@dataclass(frozen=True)
class BranchInterior:
    """
    Keep domain, global map and local chart evidence separate without clearing other missing audits.
    """

    plan: SpatialBranchPlan
    transverse: SectionDomain
    world_map: GlobalChart
    local_coordinate_status: str


def audit(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> BranchInterior:
    """
    Establish a sufficient globally unique geometric chart on the actual filled branch domain.

    A single star-shaped transverse boundary defines its disk at every u. A
    global injectivity proof on the larger common q/b box then applies to that
    disk family. Local coordinate proofs are recomputed on the same control nets.
    Coordinate q/b are geometric/Eulerian values, not assigned persistent source
    material labels. No singular polar-center map or unimplemented inverse solver
    is smuggled into a material-validity claim.
    """
    frames = validate_patches(plan.patches, checkpoint)
    transverse = certify_domain(tuple(p.section for p in plan.patches[0]), checkpoint)
    q_values, b_values = [], []
    local_ok = True
    for span in plan.patches:
        for patch in span:
            checkpoint()
            proof = certify_coordinates(patch, checkpoint)
            local_ok = local_ok and proof.status == "certified"
            q_values.extend(proof.q_bounds)
            b_values.extend(proof.b_bounds)
    world = certify(
        frames, (min(q_values), max(q_values)), (min(b_values), max(b_values)), checkpoint
    )
    return BranchInterior(plan, transverse, world, "certified" if local_ok else "unresolved")
