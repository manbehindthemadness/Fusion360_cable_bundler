"""
Spend an unused feasibility recovery on measured shorter contractions while preserving a safe route.
"""

from __future__ import annotations

import math
from dataclasses import replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result as Contraction
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
    Recovery,
    recover,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, improves
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy


def recover_contracted(
    contraction: Contraction,
    frames: Frames,
    remaining_pairs: int,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_seconds: float = MAXIMUM_WALL_SECONDS,
) -> Recovery | None:
    """
    Recover one measured improving contraction only when the caller reserves unused feasibility work.

    Select the shortest measured penetration or supported depth result that also
    improves both whole-guide measures. Recheck those preferences after recovery.
    Selection, correction and acceptance share the original.35CPU/2wall allowance;
    certificates use only the original remaining construction pairs and at most
    1024per call. The extra analytic cap support proof changes neither contact
    policy nor geometry. A failed/worse correction returns no replacement.
    """
    if (
        type(maximum_seconds) not in (int, float)
        or not math.isfinite(maximum_seconds)
        or not 0 < maximum_seconds <= MAXIMUM_WALL_SECONDS
    ):
        raise ValueError("Use a positive remaining wall allowance within the original two seconds")
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
            if improves(branch, baseline):
                choices.append((branch, contact))
    if not choices:
        return None
    branch, contact = min(choices, key=lambda item: item[0].priority)
    cpu_left = MAXIMUM_CPU_SECONDS - (process_time() - cpu)
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
        if not improves(Branch.measure(branch.roots, selected, frames.guide), baseline):
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
