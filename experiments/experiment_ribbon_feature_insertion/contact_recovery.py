"""
Recover one rejected closed plan through bounded joint separation without accepting its baseline.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends, retract_active
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .separation import Separation, Side, TopologyChanged


class _Exhausted(RuntimeError):
    """
    Stop optional local work without catching caller resource or source errors.
    """


@dataclass(frozen=True)
class Recovery:
    """
    Return only a newly separated route, with all recovery work accounted separately.
    """

    route: FoldRoute | None
    contact: ContactResult | None
    pairs: int
    contacts: int
    contact_seconds: float
    detail: dict[str, Any]


def recover(
    source: FoldRoute,
    measurement: ContactResult,
    remaining_pairs: int,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Recovery:
    """
    Apply at most four gap-increasing joint updates and strict contact certificates.

    Keep radii, profile, fold count/order and both caps. Use a minimum-norm
    linearized separation constraint, bounded joint steps and existing nonlinear
    cap retraction. Local limits are0.35CPU/2wall seconds, subordinate to caller
    limits. Never return the rejected source as an accepted fallback. Pair/depth
    ambiguity and failed improvement remain unresolved; caller hard errors propagate.
    """
    if type(remaining_pairs) is not int or not 0 < remaining_pairs <= 2048:
        raise ValueError("Supply positive remaining first-pass work, at most2048pairs")
    if not math.isfinite(threshold_mm) or threshold_mm <= 0:
        raise ValueError("A positive native straight threshold is required")
    started, cpu = perf_counter(), process_time()
    model = MovableBends(source)
    values, route = model.initial, source
    bound: Separation | None = None
    side: Side | None = None
    selected = None
    accepted = None
    spent, contacts, contact_seconds = 0, 0, 0.0
    detail: dict[str, Any] = {"status": "unresolved", "iterations": 0}

    def bounded() -> None:
        """
        Preserve caller hard gates and distinguish exhaustion of this optional operation.
        """
        checkpoint()
        if process_time() - cpu >= 0.35 or perf_counter() - started >= 2:
            raise _Exhausted("Joint separation recovery exhausted its local allowance")

    try:
        for iteration in range(4):
            bounded()
            detail["iterations"] += 1
            if bound is None:
                if measurement.witness is None:
                    detail["stop_reason"] = "no_penetration_witness"
                    break
                bound = Separation.create(model, route, measurement.witness)
            assert bound is not None
            residual, rows = model.residual(values), model.jacobian(values)
            options: list[tuple[float, Side, float, tuple[float, ...]]] = []
            for direction in (s for s in Side if side is None or s is side):
                gap = bound.gap(values, direction)
                gradient = bound.gradient(values, direction, bounded)
                delta = projected(
                    model,
                    values,
                    rows + [gradient],
                    [-v for v in residual] + [1e-8 / model.scale - gap],
                    [0.0] * len(values),
                )
                if delta is not None:
                    options.append((math.fsum(d * d for d in delta), direction, gap, delta))
            if not options:
                detail["stop_reason"] = "no_projected_separation"
                break
            _, chosen_side, gap, delta = min(options, key=lambda item: (item[0], item[1].value))
            side = chosen_side
            step = step_limit(model, values, delta, 1.0)
            changed = None
            for _ in range(2):
                bounded()
                candidate = retract_active(model, advance(model, values, delta, step), bounded)
                if candidate is not None and bound.gap(candidate, chosen_side) > gap:
                    changed = candidate
                    break
                step /= 2
            if changed is None:
                detail["stop_reason"] = "no_gap_improvement"
                break
            values = changed
            route = FoldRoute(source.targets, model.pieces(values), source.radius_mm)
            if cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                raise ArithmeticError("Joint recovery lost its exact cap/material contract")
            gap_mm = bound.gap(values, chosen_side) * model.scale
            record(
                {
                    "stage": "joint_separation_recovery",
                    "status": "gap_improved",
                    "iteration": iteration,
                    "gap_mm": gap_mm,
                    "route": snapshot(route),
                }
            )
            if gap_mm <= 0:
                continue
            if any(
                isinstance(p.geometry, Straight) and p.geometry.material_length_mm <= threshold_mm
                for p in route.pieces
            ):
                detail["stop_reason"] = "sub_tolerance_straight"
                break
            allowance = min(1024, remaining_pairs - spent)
            if allowance <= 0:
                detail["stop_reason"] = "pair_budget"
                break
            now = perf_counter()
            measurement = inspect_contact(route, maximum_pairs=allowance, checkpoint=bounded)
            if (
                type(measurement.pairs_checked) is not int
                or not 0 <= measurement.pairs_checked <= allowance
            ):
                raise ArithmeticError("Recovery contact exceeded its pair allowance")
            contact_seconds += perf_counter() - now
            contacts += 1
            spent += measurement.pairs_checked
            record(
                {
                    "stage": "joint_separation_recovery",
                    "status": measurement.status,
                    "iteration": iteration,
                    "contact": asdict(measurement),
                    "remaining_pair_budget": remaining_pairs - spent,
                    "route": snapshot(route),
                }
            )
            if measurement.status == "separated":
                selected, accepted = route, measurement
                detail["status"] = "separated"
                break
            bound, side = None, None
    except _Exhausted:
        detail["stop_reason"] = "local_budget"
    except TopologyChanged:
        detail["stop_reason"] = "fold_topology_changed"
    detail.update(
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
        contacts=contacts,
        pairs=spent,
        remaining_pair_budget=remaining_pairs - spent,
    )
    record({"stage": "joint_separation_recovery", "status": detail["status"], "detail": detail})
    return Recovery(selected, accepted, spent, contacts, contact_seconds, detail)
