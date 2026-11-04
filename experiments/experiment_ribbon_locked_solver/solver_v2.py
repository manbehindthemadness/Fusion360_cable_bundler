"""
Expose the measured tight guide-frame constructor as the gym's version-two method.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.contracts import TargetPose, Targets
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.solve import contract
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Policy
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, construct
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .branch_recovery import recover_construction
from .coordinates import metadata
from .settings import Settings
from .smoothing_contact import smooth_with_contact
from .solver import Result
from .versions import V2


def solve(
    source: TargetPose,
    settings: Settings,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    native_point_tolerance_mm: float = 1e-5,
    contact_policy: ContactPolicy = ContactPolicy.STRICT,
) -> Result:
    """
    Construct two tight guide stages once, with optional separately timed smoothing and UV metadata.

    First construction is bounded to four seconds and2048contact subdivision pairs,
    with at most1024per certificate over already-derived branches. If all reject,
    one existing closed plan, selected by its bounded separation correction, may
    receive four joint-separation updates using the
    remaining pair work and at most0.35CPU/2wall seconds within that deadline.
    Monotonic optimization may instead use that same unused work on one measured
    penetrating branch that is shorter and better-guided than a separated fallback.
    Failed recovery retains the separated fallback and counts all work performed.
    Enabled first-pass optimization then contracts existing bends with four steps,
    at most0.35CPU seconds and two additional strict certificates, within the same
    four-second deadline. Failed improvement retains the accepted baseline.
    No v1 fallback, extra features or radius relaxation occurs in that phase.
    Unchanged routes retain their separation certificate, including an exact
    final geometry match to an accepted aesthetic proposal. Otherwise the final
    route requires the normal bounded contact check.
    Native point tolerance rejects tiny explicit straights; it is not a bend rule.
    An explicitly configured temporary gym policy may retain pair-limit exhaustion
    with contact unmeasured; ordinary calls retain strict contact acceptance.
    """
    if (
        type(native_point_tolerance_mm) not in (int, float)
        or not math.isfinite(native_point_tolerance_mm)
        or native_point_tolerance_mm <= 0
    ):
        raise ValueError("Native point tolerance must be finite and positive")
    started, cpu_started = perf_counter(), process_time()
    targets = Targets.capture(source)
    frames = Frames.create(targets)
    radius = targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)

    def first_checkpoint() -> None:
        """
        Retain the measured first-construction time cap within the worker's outer cancellation guard.
        """
        checkpoint()
        if perf_counter() - started > 4:
            raise TimeoutError("V2 first construction exceeded four seconds")

    result = construct(
        Boundary(targets, radius),
        frames,
        (0.5,),
        native_point_tolerance_mm,
        first_checkpoint,
        record,
        selection_policy=Policy.MONOTONIC if settings.first_pass_optimization else Policy.MIDPOINT,
        contact_policy=contact_policy,
    )
    result, recovery_detail = recover_construction(
        result,
        frames,
        native_point_tolerance_mm,
        first_checkpoint,
        record,
        selection_policy=Policy.MONOTONIC if settings.first_pass_optimization else Policy.MIDPOINT,
    )
    first_seconds = perf_counter() - started
    detail: dict[str, Any] = {
        "version": V2,
        "status": "unresolved",
        "construction": {
            "status": result.status,
            "contacts": result.contacts,
            "contact_pairs": result.contact_pairs,
            "contact_pair_budget": CONTACT_PAIR_BUDGET,
            "contact_seconds": result.contact_seconds,
            "closed_branches": result.closed_branches,
            "unattempted_contacts": result.unattempted_contacts,
            "selection": "monotonic" if settings.first_pass_optimization else "midpoint",
            "recovery": recovery_detail,
        },
        "first_pass_seconds": first_seconds,
        "native_point_tolerance_mm": native_point_tolerance_mm,
        "material_uv_seconds": 0.0,
        "smoothing_seconds": 0.0,
        "contact_measurement_policy": contact_policy.value,
        "native_construction": "unattempted",
        "native_fidelity": "unmeasured",
        "full_physical_audit": "unmeasured",
    }
    if result.route is None:
        detail.update(
            elapsed_seconds=perf_counter() - started, cpu_seconds=process_time() - cpu_started
        )
        return Result(None, None, detail, None)
    first = result.route
    measurement = result.contact
    if measurement is None:
        raise ArithmeticError("V2 geometry lacks its contact measurement provenance")
    detail["construction"]["raw_length_mm"] = first.material_length_mm
    detail["contraction"] = {"status": "disabled"}
    remaining = 4 - (perf_counter() - started)
    if settings.first_pass_optimization and measurement.status == "separated" and remaining > 0:
        contraction = contract(
            first,
            checkpoint,
            record,
            minimum_straight_mm=native_point_tolerance_mm,
            maximum_seconds=min(2.0, remaining),
        )
        first = contraction.route
        measurement = contraction.contact or measurement
        detail["contraction"] = contraction.detail
    elif settings.first_pass_optimization:
        detail["contraction"] = {
            "status": "requires_separated_baseline"
            if measurement.status != "separated"
            else "first_pass_deadline"
        }
    detail["first_pass_seconds"] = perf_counter() - started
    smoothing_started = perf_counter()
    smoothed = smooth_with_contact(first, settings.smoothing_percent, checkpoint, record)
    final = smoothed.route
    detail.update(stages=smoothed.stages, smoothing_seconds=perf_counter() - smoothing_started)
    if smoothed.contact is not None:
        measurement = smoothed.contact
        detail["final_contact_source"] = "identical_accepted_smoothing_geometry"
    elif final is not first:
        measurement = inspect_contact(final, maximum_pairs=1024, checkpoint=checkpoint)
        detail["final_contact_source"] = "final_geometry_audit"
    else:
        detail["final_contact_source"] = "unchanged_first_pass"
    contact = measurement.status
    warning = contact != "separated" and contact_policy.permits_geometry(measurement)
    detail.update(contact=contact, contact_measurement=asdict(measurement), contact_warning=warning)
    caps, metric = cap_error(final), material_error(final)
    if not contact_policy.permits_geometry(measurement):
        detail.update(
            status="unresolved",
            contact=contact,
            elapsed_seconds=perf_counter() - started,
            cpu_seconds=process_time() - cpu_started,
        )
        return Result(None, first, detail, None)
    if (
        final.targets != targets
        or caps > 1e-7
        or metric > 1e-10
        or final.material_length_mm
        > first.material_length_mm * (1 + settings.smoothing_percent / 100)
        + 1e-8 * targets.diameter_mm
    ):
        raise ArithmeticError("V2 lost its material/cap/length contract")
    uv_started = perf_counter()
    material_uv = metadata(final) if settings.material_uv else None
    detail.update(
        status="geometry_ready_contact_unmeasured" if warning else "numerically_accepted",
        material_uv_seconds=perf_counter() - uv_started,
        cap_error_mm=caps,
        material_metric_error=metric,
        contact=contact,
        elapsed_seconds=perf_counter() - started,
        cpu_seconds=process_time() - cpu_started,
    )
    return Result(final, first, detail, material_uv)
