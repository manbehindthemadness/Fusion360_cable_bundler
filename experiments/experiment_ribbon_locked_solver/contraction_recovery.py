"""
Spend an unused feasibility recovery on measured shorter contractions while preserving a safe route.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result as Contraction
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
    Recovery,
    recover,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, ImprovementPolicy
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_recovery import (
    recover as recover_incident,
)
from experiments.experiment_ribbon_terminal_hardware.return_recovery import (
    recover as recover_return,
)


@dataclass
class RecoveryConsultation:
    """
    Distinguish selection-only preparation from entering a geometric recovery strategy.

    A None result after strategy entry still consumes the caller's reservation.
    Selection without entry may hand off only genuinely unused work; the caller
    must charge all preparation CPU and retain the original wall-span origin.
    """

    entered: bool = False


def recover_contracted(
    contraction: Contraction,
    frames: Frames,
    remaining_pairs: int,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_seconds: float = MAXIMUM_WALL_SECONDS,
    maximum_cpu_seconds: float = MAXIMUM_CPU_SECONDS,
    improvement_policy: ImprovementPolicy = ImprovementPolicy.GUIDE_DOMINANCE,
    terminal: Gate | None = None,
    consultation: RecoveryConsultation | None = None,
) -> Recovery | None:
    """
    Recover one measured improving contraction only when the caller reserves unused feasibility work.

    Select the shortest measured penetration or supported depth result that
    improves the declared policy. Length policy uses strict shortening without
    guide vetoes; historical monotonic policy retains both whole-guide measures.
    Recheck the same preferences after recovery.
    Selection, correction and acceptance share the original.35CPU/2wall allowance;
    certificates use only the original remaining construction pairs and at most
    1024per call. The extra analytic cap support proof changes neither contact
    policy nor geometry. A failed/worse correction returns no replacement.
    A caller may reserve earlier preparation CPU by reducing the CPU sublimit;
    neither explicit time sublimit can replenish the original allowance.
    With the same finite-hardware gate, a selected unresolved depth contact may
    prioritize a demonstrated fold/connector intrusion through one incident joint
    reversal. Known self-penetration retains the established contact-first action.
    Strategy selection, evidence and correction share the original time/pair pool;
    a failed chosen strategy does not start another full allocation.
    An optional receipt is cleared at entry and marked immediately before invoking
    any geometric strategy. It grants no work or acceptance on its own.
    """
    if consultation is not None:
        consultation.entered = False
    if (
        type(maximum_seconds) not in (int, float)
        or not math.isfinite(maximum_seconds)
        or not 0 < maximum_seconds <= MAXIMUM_WALL_SECONDS
    ):
        raise ValueError("Use a positive remaining wall allowance within the original two seconds")
    if (
        type(maximum_cpu_seconds) not in (int, float)
        or not math.isfinite(maximum_cpu_seconds)
        or not 0 < maximum_cpu_seconds <= MAXIMUM_CPU_SECONDS
    ):
        raise ValueError("Use a positive remaining CPU allowance within the original0.35seconds")
    if not contraction.rejected or remaining_pairs <= 0:
        return None
    started, cpu = perf_counter(), process_time()
    baseline = Branch.measure((), contraction.route, frames.guide)
    choices = []
    for index, (route, contact) in enumerate(contraction.rejected):
        checkpoint()
        supported = contact.status == "penetration" and contact.witness is not None
        supported |= (
            contact.status == "unresolved"
            and contact.limit == "depth"
            and contact.unresolved_pieces is not None
            and contact.unresolved_regions is not None
        )
        if supported:
            branch = Branch.measure((index,), route, frames.guide)
            if improvement_policy.accepts(branch, baseline):
                choices.append((branch, contact))
    if not choices:
        return None
    branch, contact = min(choices, key=lambda item: item[0].priority)
    if terminal is not None and contact.status == "unresolved" and contact.limit == "depth":
        evidence = terminal.measure(branch.route, "contraction_recovery_hardware_precheck")
        if (
            evidence.status == "blocked"
            and evidence.witness is not None
            and isinstance(branch.route.pieces[evidence.witness.piece].geometry, CylindricalFold)
        ):
            cpu_left = maximum_cpu_seconds - (process_time() - cpu)
            wall_left = maximum_seconds - (perf_counter() - started)
            if min(cpu_left, wall_left) <= 0:
                return None
            if consultation is not None:
                consultation.entered = True
            repaired = recover_incident(
                branch.route,
                evidence,
                terminal,
                checkpoint,
                record,
                maximum_length_mm=baseline.route.material_length_mm,
                minimum_straight_mm=threshold_mm,
                remaining_pairs=remaining_pairs,
                maximum_cpu_seconds=cpu_left,
                maximum_seconds=wall_left,
            )
            if repaired is not None:
                selected = repaired.route
                if selected is not None:
                    if repaired.contact is None or repaired.contact.status != "separated":
                        raise ArithmeticError(
                            "Incident contraction recovery lacks full contact clearance"
                        )
                    if not improvement_policy.accepts(
                        Branch.measure(branch.roots, selected, frames.guide), baseline
                    ):
                        selected = None
                if (
                    process_time() - cpu >= maximum_cpu_seconds
                    or perf_counter() - started >= maximum_seconds
                ):
                    selected = None
                    repaired.detail["stop_reason"] = "phase_budget"
                detail = {
                    **repaired.detail,
                    "purpose": "recover_contraction",
                    "source_length_mm": branch.route.material_length_mm,
                    "baseline_length_mm": baseline.route.material_length_mm,
                    "accepted_improvement": selected is not None,
                    "cpu_seconds": process_time() - cpu,
                    "elapsed_seconds": perf_counter() - started,
                }
                return replace(
                    repaired,
                    route=selected,
                    contact=repaired.contact if selected is not None else None,
                    detail=detail,
                )
            return None
    cpu_left = maximum_cpu_seconds - (process_time() - cpu)
    wall_left = maximum_seconds - (perf_counter() - started)
    if cpu_left <= 0 or wall_left <= 0:
        return None
    record(
        {
            "stage": "contraction_recovery",
            "status": "started",
            "source_length_mm": branch.route.material_length_mm,
            "baseline_length_mm": baseline.route.material_length_mm,
            "remaining_pair_budget": remaining_pairs,
        }
    )
    if consultation is not None:
        consultation.entered = True
    if terminal is not None and contact.status == "unresolved" and contact.limit == "depth":
        result = recover_return(
            branch.route,
            contact,
            terminal,
            checkpoint,
            record,
            maximum_length_mm=baseline.route.material_length_mm,
            minimum_straight_mm=threshold_mm,
            remaining_pairs=remaining_pairs,
            maximum_cpu_seconds=cpu_left,
            maximum_seconds=wall_left,
        )
    else:
        result = recover(
            branch.route,
            contact,
            remaining_pairs,
            threshold_mm,
            checkpoint,
            record,
            maximum_cpu_seconds=cpu_left,
            maximum_seconds=wall_left,
            cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        )
    selected = result.route
    if selected is not None:
        if result.contact is None or result.contact.status != "separated":
            raise ArithmeticError("Recovered contraction lacks a separated contact certificate")
        if not improvement_policy.accepts(
            Branch.measure(branch.roots, selected, frames.guide), baseline
        ):
            selected = None
    detail = {
        **result.detail,
        "purpose": "recover_contraction",
        "accepted_improvement": selected is not None,
        "source_length_mm": branch.route.material_length_mm,
        "baseline_length_mm": baseline.route.material_length_mm,
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - started,
    }
    record(
        {
            "stage": "contraction_recovery",
            "status": "improved" if selected else "baseline_retained",
            "detail": detail,
        }
    )
    return replace(
        result, route=selected, contact=result.contact if selected else None, detail=detail
    )
