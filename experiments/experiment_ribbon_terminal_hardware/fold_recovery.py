"""
Close measured fold-feature clearance and endpoint equations in one bounded nonlinear system.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .check import Report
from .feature_plane import FeaturePlane, SignedJoints
from .gate import Gate


class _Exhausted(RuntimeError):
    """
    Stop only the allocated optional recovery work, never caller resource/source failures.
    """


def recover(
    original: FoldRoute,
    evidence: Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
) -> Result | None:
    """
    Preserve all signs/radii while simultaneously solving caps and at most two measured feature planes.

    Caller validates and reserves the same idle feasibility allowance. Up to 24
    Newton steps represent four six-correction updates, with 0.2 radian trust and
    four scalar halvings. Every new constraint requires a demonstrated intrusion;
    previous constraints stay active. No angle/event/axis-family candidates are
    searched after selection. Full contact and both boxes remain mandatory.
    Local quality growth is bounded by original construction length plus the
    initial complete-feature projected penetration; it is not a physical tolerance.
    Hardware-clear proposals with sub-native runways fix those slots at zero and
    reclose all equations before final self-contact, without renewing any allowance.
    """
    started, cpu = perf_counter(), process_time()
    model = SignedJoints(original)
    values = model.initial
    fixed_zero: set[int] = set()
    initial = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
    if initial is None:
        return None
    planes = [initial]
    allowance = max(0.0, -initial.gap(values) * model.scale)
    ceiling = maximum_length_mm + allowance
    candidate, accepted, measurement = original, False, None
    detail: dict[str, Any] = {
        "status": "unresolved",
        "purpose": "terminal_clearance",
        "method": "coupled_feature_planes",
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "maximum_length_mm": ceiling,
        "local_growth_allowance_mm": allowance,
    }
    active_pairs: int | None = None
    contact_started = 0.0

    def bounded() -> None:
        """
        Keep all preparation, closure and certificates inside the original caller sublimits.
        """
        checkpoint()
        if (
            process_time() - cpu >= maximum_cpu_seconds
            or perf_counter() - started >= maximum_seconds
        ):
            raise _Exhausted("Coupled feature recovery allowance exhausted")

    def emit(status: str, **data: Any) -> None:
        """
        Preserve every constraint, motion and actual certificate in the numerical ledger.
        """
        record({"stage": "coupled_feature_recovery", "status": status, **data})

    def residual(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Close the ordered caps and all selected feature gaps together.
        """
        return model.residual(coordinates) + tuple(
            p.gap(coordinates) - 1e-7 / model.scale for p in planes
        )

    try:
        emit(
            "started",
            source=snapshot(original),
            evidence=asdict(evidence),
            length_ceiling_mm=ceiling,
        )
        while True:
            bounded()
            equation = residual(values)
            error = max(map(abs, equation))
            if error < 1e-13:
                proposed = model.route(values)
                assert proposed is not None
                candidate = proposed
                if cap_error(candidate) > 1e-7 or material_error(candidate) > 1e-10:
                    raise ArithmeticError("Coupled feature recovery lost cap/material closure")
                if not model.preserves(candidate):
                    detail["stop_reason"] = "fold_identity"
                    break
                if candidate.material_length_mm > ceiling:
                    detail["stop_reason"] = "local_growth_ceiling"
                    break
                report = terminal.measure(candidate, "coupled_feature_candidate")
                if report.status == "clear":
                    slivers = {
                        i
                        for i in model.straight_indices
                        if 0 < values[i] * model.scale <= minimum_straight_mm
                    }
                    if slivers:
                        fixed_zero.update(slivers)
                        values = tuple(0.0 if i in fixed_zero else v for i, v in enumerate(values))
                        emit("native_slots_zeroed", indices=sorted(slivers))
                        continue
                    if any(
                        isinstance(p.geometry, Straight)
                        and p.geometry.material_length_mm <= minimum_straight_mm
                        for p in candidate.pieces
                    ):
                        detail["stop_reason"] = "native_sliver"
                        break
                    pairs = min(1024, remaining_pairs - detail["contact_pairs"])
                    if pairs <= 0:
                        detail["stop_reason"] = "construction_pair_budget"
                        break
                    active_pairs, contact_started = pairs, perf_counter()
                    detail["contacts"] += 1
                    measurement = inspect_contact(
                        candidate,
                        maximum_pairs=pairs,
                        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                        checkpoint=bounded,
                    )
                    detail["contact_pairs"] += measurement.pairs_checked
                    detail["contact_seconds"] += perf_counter() - contact_started
                    active_pairs = None
                    emit("contact", route=snapshot(candidate), contact=asdict(measurement))
                    if measurement.status != "separated":
                        detail["stop_reason"] = "self_contact_not_separated"
                        break
                    bounded()
                    accepted = True
                    detail["status"] = "separated"
                    break
                if len(planes) >= 2:
                    detail["stop_reason"] = "feature_constraint_limit"
                    break
                extra = FeaturePlane.create(model, candidate, report, terminal.hardware, values)
                if extra is None:
                    detail["stop_reason"] = "unsupported_terminal_evidence"
                    break
                planes.append(extra)
                emit(
                    "constraint_added",
                    reference=asdict(extra.reference),
                    members=[asdict(m) for m in extra.members],
                    terminal=extra.box.terminal.value,
                    axis_family=extra.family,
                )
                continue
            if detail["newton_steps"] >= 24:
                detail["stop_reason"] = "joint_update_limit"
                break
            columns = []
            for index, value in enumerate(values):
                bounded()
                if index in fixed_zero:
                    columns.append([0.0] * len(equation))
                    continue
                low, high = model.bounds(index)
                a, b = list(values), list(values)
                a[index], b[index] = max(low, value - 1e-5), min(high, value + 1e-5)
                first, last = residual(tuple(a)), residual(tuple(b))
                columns.append([(y - x) / (b[index] - a[index]) for x, y in zip(first, last)])
            jacobian = [[column[row] for column in columns] for row in range(len(equation))]
            delta = projected(model, values, jacobian, [-v for v in equation], [0.0] * len(values))
            if delta is None:
                detail["stop_reason"] = "joint_projection_infeasible"
                break
            step = step_limit(model, values, delta, 1.0)
            for _ in range(4):
                bounded()
                trial = advance(model, values, delta, step)
                if max(map(abs, residual(trial))) < error:
                    values = trial
                    detail["newton_steps"] += 1
                    detail["iterations"] = math.ceil(detail["newton_steps"] / 6)
                    break
                step /= 2
            else:
                detail["stop_reason"] = "joint_no_descent"
                break
            emit("joint_update", values=values, residual=residual(values), constraints=len(planes))
    except _Exhausted:
        detail["stop_reason"] = "phase_budget"
        if active_pairs is not None:
            detail["contact_pairs"] += active_pairs
            detail["contact_seconds"] += perf_counter() - contact_started
            detail["interrupted_pairs_charged_as_upper_bound"] = active_pairs
    detail.update(
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
        length_mm=candidate.material_length_mm if accepted else original.material_length_mm,
        constraints=len(planes),
    )
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
