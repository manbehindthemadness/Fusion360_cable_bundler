"""
Close exact caps, finite connector clearance and complete measured flat contact regions together.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    ProjectionReuse,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .check import Report
from .feature_plane import FeaturePlane, SignedJoints
from .flat_separation import FlatSeparation
from .gate import Gate
from .joint_derivatives import jacobian as joint_jacobian
from .quality_projection import quality_step


class _Exhausted(RuntimeError):
    """
    Stop only this optional shared allocation without masking caller cancellation or resource errors.
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
    maximum_updates: int,
) -> Result | None:
    """
    Use only remaining original work on caps, one actual connector plane and up to four flat contacts.

    The parent length is an inequality ceiling, never a growth target. All signs,
    radii, material identity/order and target poses stay fixed. Negative-only hull
    probing runs only until a first actual contact; subsequent certificates use
    the complete original checker, with bounded identical projection reuse.
    Every certificate and witness comparison shares the original pair pool.
    """
    if type(maximum_updates) is not int or not 1 <= maximum_updates <= 4:
        raise ValueError("Use one to four genuinely remaining updates")
    if type(remaining_pairs) is not int or not 0 < remaining_pairs <= 2048:
        raise ValueError("Supply the remaining original pair pool")
    for value, ceiling in ((maximum_cpu_seconds, 0.35), (maximum_seconds, 2.0)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= ceiling:
            raise ValueError("Use only remaining original feasibility time")
    if any(
        type(value) not in (int, float) or not math.isfinite(value) or value <= 0
        for value in (maximum_length_mm, minimum_straight_mm)
    ):
        raise ValueError("Positive finite parent ceiling and native threshold required")
    cpu, wall = process_time(), perf_counter()
    model = SignedJoints(original)
    values = model.initial
    plane = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
    if plane is None:
        return None
    active_plane: FeaturePlane = plane
    constraints: list[tuple[FlatSeparation, Side]] = []
    keys: set[tuple[Any, ...]] = set()
    fixed: set[int] = set()
    newton, pairs, contacts, contact_seconds = 0, 0, 0, 0.0
    candidate = original
    measurement: ContactResult | None = None
    accepted = False
    stop = "unattempted"
    active_pairs: int | None = None
    contact_started = 0.0
    interrupted_pairs: int | None = None
    probe = FlatProbe()
    penetration_seen = False

    def bounded() -> None:
        """
        Charge preparation, derivatives, motion, evidence and final proof to this one allocation.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    def emit(status: str, **data: Any) -> None:
        """
        Retain all actual crossings, complete region choices and unsuccessful motions.
        """
        record({"stage": "joint_flat_contact", "status": status, **data})

    def equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Keep raw inequality derivatives alongside six ordered cap equalities.
        """
        equation_terms = model.residual(coordinates) + (
            1e-7 / model.scale - active_plane.gap(coordinates),
            (
                sum(p.geometry.material_length_mm for p in model.pieces(coordinates))
                - maximum_length_mm
            )
            / model.scale,
        )
        if constraints:
            equation_terms += (
                max(
                    1e-8 / model.scale - constraint.gap(coordinates, chosen_side)
                    for constraint, chosen_side in constraints
                ),
            )
        return equation_terms

    def merit(coordinates: tuple[float, ...]) -> float:
        """
        Reduce actual cap errors and only violated inequality terms.
        """
        merit_terms = equations(coordinates)
        return max(
            *(abs(term) for term in merit_terms[:6]), *(max(0.0, term) for term in merit_terms[6:])
        )

    try:
        emit(
            "started",
            source=snapshot(original),
            maximum_length_mm=maximum_length_mm,
            remaining_updates=maximum_updates,
            remaining_pairs=remaining_pairs,
        )
        while True:
            bounded()
            proposed = model.route(values)
            assert proposed is not None
            candidate = proposed
            terms = equations(values)
            error = merit(values)
            if error < 1e-13:
                if (
                    cap_error(candidate) > 1e-7
                    or material_error(candidate) > 1e-10
                    or not model.preserves(candidate)
                    or candidate.material_length_mm > maximum_length_mm
                ):
                    stop = "final_contract"
                    break
                slivers = {
                    i
                    for i in model.straight_indices
                    if 0 < values[i] * model.scale <= minimum_straight_mm
                }
                if slivers:
                    if newton >= 6 * maximum_updates:
                        stop = "native_zero_reclosure_limit"
                        break
                    fixed.update(slivers)
                    values = tuple(0.0 if i in fixed else value for i, value in enumerate(values))
                    newton += 1
                    continue
                if any(
                    isinstance(p.geometry, Straight)
                    and p.geometry.material_length_mm <= minimum_straight_mm
                    for p in candidate.pieces
                ):
                    stop = "native_sliver"
                    break
                if terminal.measure(candidate, "joint_flat_contact_final").status != "clear":
                    stop = "hardware_not_clear"
                    break
                allowed = min(1024, remaining_pairs - pairs)
                if allowed <= 0:
                    stop = "pair_budget"
                    break
                active_pairs = allowed
                contacts += 1
                contact_started = perf_counter()
                measured_contact = inspect_contact(
                    candidate,
                    maximum_pairs=allowed,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    checkpoint=bounded,
                    witness_probe=None if penetration_seen else probe,
                    projection_reuse=ProjectionReuse.CELLS,
                )
                measurement = measured_contact
                pairs += measured_contact.pairs_checked
                contact_seconds += perf_counter() - contact_started
                active_pairs = None
                emit("certificate", contact=asdict(measured_contact), route=snapshot(candidate))
                if measured_contact.status == "separated":
                    bounded()
                    accepted, stop = True, "accepted"
                    break
                if measured_contact.status != "penetration" or measured_contact.witness is None:
                    stop = "contact_unresolved"
                    break
                penetration_seen = True
                created_bound = FlatSeparation.create(model, candidate, measured_contact.witness)
                if created_bound is None or len(constraints) >= 4:
                    stop = "unsupported_or_exhausted_flat_constraints"
                    break
                bound: FlatSeparation = created_bound
                witness = measured_contact.witness
                key = (
                    bound.pair,
                    tuple(round(v, 8) for v in witness.first[:2]),
                    tuple(round(v, 8) for v in witness.second[:2]),
                )
                if key in keys:
                    stop = "repeated_contact_witness"
                    break
                side = max(
                    Side, key=lambda chosen: (bound.gap(model.initial, chosen), -chosen.value)
                )
                keys.add(key)
                constraints.append((bound, side))
                emit(
                    "constraint_added",
                    witness=asdict(witness),
                    pair=[asdict(tag) for tag in bound.pair],
                    parts=[
                        {"phase": part.phase.value, "q": (part.low_q, part.high_q)}
                        for part in bound.parts
                    ],
                    side=side.name,
                    gap_mm=bound.gap(values, side) * model.scale,
                )
                continue
            if newton >= 6 * maximum_updates:
                stop = "joint_update_limit"
                break
            jacobian = joint_jacobian(model, values, equations, len(terms), fixed, bounded)
            delta = quality_step(model, values, jacobian, terms, bounded)
            if delta is None:
                stop = "linear_projection_infeasible"
                break
            native_zero = {
                i
                for i in model.straight_indices
                if values[i] == 0 and abs(delta[i]) * model.scale <= minimum_straight_mm
            }
            if native_zero:
                jacobian = [
                    [0.0 if i in native_zero else value for i, value in enumerate(row)]
                    for row in jacobian
                ]
                delta = quality_step(model, values, jacobian, terms, bounded)
                if delta is None:
                    stop = "native_projection_infeasible"
                    break
            fraction = step_limit(model, values, delta, 1.0)
            for _ in range(4):
                bounded()
                trial = advance(model, values, delta, fraction)
                if merit(trial) < error:
                    values, newton = trial, newton + 1
                    break
                fraction /= 2
            else:
                stop = "joint_no_descent"
                break
            emit("update", newton=newton, values=values, residual=equations(values))
    except _Exhausted:
        stop = "phase_budget"
        pairs += active_pairs or 0
        if active_pairs is not None:
            interrupted_pairs = active_pairs
            contact_seconds += perf_counter() - contact_started
    detail: dict[str, Any] = {
        "status": "separated" if accepted else "unresolved",
        "method": "complete_flat_contacts",
        "iterations": math.ceil(newton / 6),
        "newton_steps": newton,
        "contacts": contacts,
        "contact_pairs": pairs,
        "contact_seconds": contact_seconds,
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - wall,
        "length_mm": candidate.material_length_mm,
        "maximum_length_mm": maximum_length_mm,
        "stop_reason": stop,
        "flat_constraints": len(constraints),
        "probe": asdict(probe),
    }
    if interrupted_pairs is not None:
        detail["interrupted_pairs_charged_as_upper_bound"] = interrupted_pairs
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
