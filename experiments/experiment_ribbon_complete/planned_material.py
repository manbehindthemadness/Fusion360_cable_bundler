"""
Combine source-measured trunk and ending increments under one complete-path allowance.

Piecewise longitudinal metrics do not establish continuous source/native material
ownership, transverse metrics, junction flow, contact or physical qualification.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ending_material import branch_bound
from .execution import RibbonPlan
from .material_accounting import CompleteMaterialFinding, account_ranges
from .trunk_material import TrunkMetricAudit, TrunkMetricWork
from .trunk_material import audit as audit_trunk


@dataclass(frozen=True)
class PlannedMaterialAudit:
    """
    Keep geometry-owned measurement receipts with conditional complete-path accounting.
    """

    trunk: TrunkMetricAudit
    findings: tuple[CompleteMaterialFinding, ...]
    outstanding: tuple[str, ...] = (
        "source_seam_material_correspondence",
        "junction_material_correspondence",
        "native_material_correspondence",
        "transverse_material_metrics",
        "interior_material_ownership",
    )


def audit(plan: RibbonPlan, work: TrunkMetricWork) -> PlannedMaterialAudit:
    """
    Measure all actual planned paths once and combine serial branches without cancellation.

    The unchanged shared accounting checks coverage and original conductor
    identities. Overlarge upper bounds remain unresolved, not proven violations.
    Source/native correspondence stays outstanding even when the scalar bound fits.
    No synthetic trunk value or per-ending tolerance is introduced.
    """
    trunk = audit_trunk(plan, work)
    bounds = {}
    for branch in plan.branches:
        work.checkpoint()
        bounds[branch.source.source.leg.route_id] = branch_bound(branch, work.checkpoint)
    findings = account_ranges(plan.captured, trunk.conductors, bounds, work.checkpoint)
    return PlannedMaterialAudit(trunk, findings)
