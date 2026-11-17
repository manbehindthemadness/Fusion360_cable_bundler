"""
Report source-measured longitudinal bounds without granting physical qualification.
"""

from __future__ import annotations

from time import perf_counter, process_time
from typing import Any

from experiments.experiment_ribbon_complete.execution import RibbonPlan
from experiments.experiment_ribbon_complete.planned_material import audit
from experiments.experiment_ribbon_complete.trunk_material import TrunkMetricWork


def measure(plan: RibbonPlan, work: TrunkMetricWork) -> dict[str, Any]:
    """
    Retain exact complete-path bounds and separately named source correspondence gaps.

    All work shares the worker's existing clock and memory checkpoint. An
    overlarge upper bound remains unresolved; it is not a violation witness.
    An unresolved trunk never invokes an ending or trunk metric measurement.
    """
    work.checkpoint()
    if plan.trunk.route is None:
        return {"status": "unattempted", "reason": "trunk_unresolved", "metric_spans": 0}
    wall, cpu = perf_counter(), process_time()
    measured = audit(plan, work)
    gaps = tuple(g for path in measured.trunk.paths for g in path.piece_join_gaps_upper_mm)
    gaps += tuple(
        g
        for path in measured.trunk.paths
        for piece in path.pieces
        for g in piece.seam_gaps_upper_mm
    )
    work.checkpoint()
    return {
        "status": "within_planned_increment_bound"
        if all(row.status == "within_declared_bound" for row in measured.findings)
        else "unresolved_bound",
        "scope": "source-owned piecewise longitudinal metrics; conditional seam/junction/native correspondence",
        "allowance_mm": "1/100",
        "findings": [
            {
                "pin": row.conductor.pin_number,
                "terminal": str(row.terminal_attachment_id),
                "status": row.status,
                "upper_mm": None if row.upper_mm is None else str(row.upper_mm),
            }
            for row in measured.findings
        ],
        "trunk": [
            {
                "pin": row.conductor.pin_number,
                "upper_mm": None if row.upper_mm is None else str(row.upper_mm),
            }
            for row in measured.trunk.conductors
        ],
        "maximum_source_seam_gap_upper_mm": str(max(gaps, default=0)),
        "maximum_prefix_residual_mm": str(
            max(map(abs, measured.trunk.prefix_residuals_mm), default=0)
        ),
        "outstanding": measured.outstanding,
        "metric_spans": work.spans,
        "wall_seconds": perf_counter() - wall,
        "cpu_seconds": process_time() - cpu,
    }
