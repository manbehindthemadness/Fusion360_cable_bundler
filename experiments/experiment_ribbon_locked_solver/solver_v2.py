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
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import ImprovementPolicy, Policy
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, construct
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_spline_guide.guide import agreement
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery import recover as recover_terminal
from experiments.experiment_ribbon_terminal_hardware.reversal import correct as correct_terminal

from .branch_recovery import recover_construction
from .contraction_recovery import recover_contracted
from .coordinates import metadata
from .placement import guide_parameters
from .settings import Settings
from .smoothing_contact import smooth_with_contact
from .solver import Result
from .terminal_allowance import remaining_completed
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
    receive four joint-separation updates using remaining pair work and at most
    0.35CPU/2wall seconds within that deadline. If a different pair then penetrates,
    unused updates may pass to the next derived branch within those same totals.
    Monotonic construction may instead use that same unused work on one measured
    penetrating branch that is shorter and better-guided than a separated fallback.
    Initial guide allocation and branch selection remain feasibility initializers.
    Failed recovery retains the separated fallback and counts all work performed.
    Enabled first-pass optimization then contracts existing bends with four steps,
    at most0.35CPU seconds and two additional strict certificates, within the same
    four-second deadline. Failed improvement retains the accepted baseline.
    With terminal hardware enabled, a demonstrated intrusion may substitute one
    witness-incident fold reversal for that contraction, using the same work
    allowance. It couples all other angles/banks/runways to the unchanged endpoint
    frame, preserves their signs and all radii, and accepts only a shorter route
    certified against full self-contact and both terminal boxes. Failed correction
    retains the baseline for ordinary smoothing; it does not start another contraction.
    If feasibility recovery was unused, a measured shorter contraction may use
    that same four-update/.35CPU allowance and original remaining construction
    pairs. Its analytic cap support certificate grants no contact exemption.
    This terminal improvement compares against the already-contracted baseline;
    guide preferences cannot veto shortening after that work is complete.
    A fallback correction deferred before its first motion leaves only its unused
    preparation-adjusted CPU and remaining wall span for that contraction recovery.
    A selected depth-unresolved contraction may prioritize an actual fold/connector
    intrusion using one free incident reversal and coupled complete-flat contact
    constraints. Proven self-penetration retains the established contact-first
    strategy. This action shares all original work and requires strict parent
    shortening, exact caps/material and full contact/proxy checks. Its optional
    convex witness probes never establish clearance; identical cell projections
    may be reused within one complete certificate.
    No v1 fallback, extra features or radius relaxation occurs in that phase.
    Unchanged routes retain their separation certificate, including an exact
    final geometry match to an accepted aesthetic proposal. Otherwise the final
    route requires the normal bounded contact check.
    Native point tolerance rejects tiny explicit straights; it is not a bend rule.
    Enabled optimization replaces the single midpoint frame by the guide's turn
    midpoint only if every exact midpoint factorization already requires more
    flat runway material than the whole guide. This changes placement, not feature/root
    counts, physical rules or the first-construction work limits.
    An explicitly configured temporary gym policy may retain pair-limit exhaustion
    with contact unmeasured; ordinary calls retain strict contact acceptance.
    Optional terminal hardware eligibility is strict independently of that override.
    Temporary work proposals may need contraction or smoothing to clear hardware;
    do not reject their coarse initializer prematurely. Measure the completed first
    pass and final smoothed route. Blocked smoothing retains a cleared first pass
    with its own contact certificate. If both fail hardware clearance, retain the
    original construction only when its exact route still has strict self-contact
    separation and terminal clearance. This declines the unsafe optimization;
    it never moves geometry, repeats smoothing or borrows a different certificate.
    If all three routes fail hardware, actual first-pass evidence may use only
    genuinely unused feasibility work. Straight evidence retains one incident
    reflection and at most one complete straight/finite-box separation plane.
    A closed reflection exceeding construction length may spend only its unused
    updates/time/pairs on original signed joints with caps, measured feature gaps
    and the original quality ceiling solved together. No new sign/event search,
    length allowance or renewed budget follows that rejection.
    Fold evidence instead preserves every sign and radius while solving ordered
    caps with at most two measured bend/runway feature planes simultaneously.
    Its growth ceiling is construction length plus the initial complete-feature
    projected penetration. Sub-native runway slots become exact zero, with all
    constraints reclosed and final contact rechecked inside the same allowance.
    Prior failed recovery consultation cannot renew that allowance.
    A completed separated self-contact recovery may pass only
    its unused updates, CPU, wall span and construction pairs to late terminal
    recovery, with all counters combined; a consulted contraction recovery still
    prevents another action. No failed/prepared history grants a fresh allowance.
    Otherwise return no accepted output. All checks
    share 0.1CPU/0.25wall seconds and1024cells within existing caller limits.
    """
    if (
        type(native_point_tolerance_mm) not in (int, float)
        or not math.isfinite(native_point_tolerance_mm)
        or native_point_tolerance_mm <= 0
    ):
        raise ValueError("Native point tolerance must be finite and positive")
    started, cpu_started = perf_counter(), process_time()
    targets = Targets.capture(source)
    terminal = Gate(targets, checkpoint, record) if settings.terminal_hardware else None
    frames = Frames.create(targets)
    radius = targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)

    def first_checkpoint() -> None:
        """
        Retain the measured first-construction time cap within the worker's outer cancellation guard.
        """
        checkpoint()
        if perf_counter() - started > 4:
            raise TimeoutError("V2 first construction exceeded four seconds")

    boundary = Boundary(targets, radius)
    parameters = (
        guide_parameters(boundary, frames, first_checkpoint, record)
        if settings.first_pass_optimization
        else (0.5,)
    )
    result = construct(
        boundary,
        frames,
        parameters,
        native_point_tolerance_mm,
        first_checkpoint,
        record,
        selection_policy=Policy.MONOTONIC if settings.first_pass_optimization else Policy.MIDPOINT,
        contact_policy=contact_policy,
        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
    )
    recovery_started = perf_counter()
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
            "cap_support_policy": CapPolicy.ANALYTIC_SUPPORT.value,
            "contact_seconds": result.contact_seconds,
            "closed_branches": result.closed_branches,
            "unattempted_contacts": result.unattempted_contacts,
            "selection": "monotonic" if settings.first_pass_optimization else "midpoint",
            "initialization": "guide_site_error_then_length",
            "guide_parameters": parameters,
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
        "terminal_hardware": terminal.detail() if terminal is not None else {"enabled": False},
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
    contraction_recovery_consulted = False
    remaining = 4 - (perf_counter() - started)
    if settings.first_pass_optimization and measurement.status == "separated" and remaining > 0:
        contraction = (
            correct_terminal(
                first,
                terminal,
                first_checkpoint,
                record,
                minimum_straight_mm=native_point_tolerance_mm,
                maximum_seconds=min(2.0, remaining),
            )
            if terminal is not None
            else None
        )
        if contraction is None:
            first_checkpoint()
            contraction = contract(
                first,
                checkpoint,
                record,
                minimum_straight_mm=native_point_tolerance_mm,
                maximum_seconds=min(2.0, 4 - (perf_counter() - started)),
            )
        first = contraction.route
        measurement = contraction.contact or measurement
        detail["contraction"] = contraction.detail
        remaining = 4 - (perf_counter() - started)
        allowance = _remaining_recovery(recovery_detail, recovery_started, remaining)
        if (
            allowance is not None
            and result.contact_pairs < CONTACT_PAIR_BUDGET
            and contraction.rejected
        ):
            cpu_left, wall_left = allowance
            contraction_recovery_consulted = True
            recovered = recover_contracted(
                contraction,
                frames,
                CONTACT_PAIR_BUDGET - result.contact_pairs,
                native_point_tolerance_mm,
                checkpoint,
                record,
                maximum_seconds=wall_left,
                maximum_cpu_seconds=cpu_left,
                improvement_policy=ImprovementPolicy.MATERIAL_LENGTH,
                terminal=terminal,
            )
            if recovered is not None:
                recovered_detail = dict(recovered.detail)
                if recovery_detail is not None:
                    recovered_detail.update(
                        deferred_before_contraction=recovery_detail,
                        cpu_seconds=recovery_detail["cpu_seconds"]
                        + recovered.detail["cpu_seconds"],
                        elapsed_seconds=perf_counter() - recovery_started,
                    )
                    record({"stage": "deferred_recovery_complete", "detail": recovered_detail})
                detail["construction"]["recovery"] = recovered_detail
                detail["construction"]["contacts"] += recovered.contacts
                detail["construction"]["contact_pairs"] += recovered.pairs
                detail["construction"]["contact_seconds"] += recovered.contact_seconds
                if recovered.route is not None:
                    first = recovered.route
                    assert recovered.contact is not None
                    measurement = recovered.contact
    elif settings.first_pass_optimization:
        detail["contraction"] = {
            "status": "requires_separated_baseline"
            if measurement.status != "separated"
            else "first_pass_deadline"
        }
    detail["first_pass_seconds"] = perf_counter() - started
    if terminal is not None:
        terminal.permits(first, "first_pass")
    smoothing_started = perf_counter()
    smoothed = smooth_with_contact(first, settings.smoothing_percent, checkpoint, record)
    final = smoothed.route
    detail.update(stages=smoothed.stages, smoothing_seconds=perf_counter() - smoothing_started)
    retained = terminal is not None and not terminal.permits(final, "smoothing")
    if retained:
        final = first
        detail["stages"]["terminal_hardware"] = "first_pass_retained"
        detail["final_contact_source"] = "hardware_safe_first_pass"
    elif smoothed.contact is not None:
        measurement = smoothed.contact
        detail["final_contact_source"] = "identical_accepted_smoothing_geometry"
    elif final is not first:
        measurement = inspect_contact(final, maximum_pairs=1024, checkpoint=checkpoint)
        detail["final_contact_source"] = "final_geometry_audit"
    else:
        detail["final_contact_source"] = "unchanged_first_pass"
    if terminal is not None:
        permitted = terminal.permits(final, "final")
        if (
            not permitted
            and final is not result.route
            and result.contact is not None
            and result.contact.status == "separated"
            and terminal.permits(result.route, "construction_fallback")
        ):
            record(
                {
                    "stage": "terminal_hardware_fallback",
                    "status": "construction_retained",
                    "discarded_first_pass": snapshot(first),
                    "discarded_smoothed": snapshot(smoothed.route),
                    "route": snapshot(result.route),
                    "contact": asdict(result.contact),
                }
            )
            first = final = result.route
            measurement = result.contact
            permitted = True
            detail["stages"]["terminal_hardware"] = "construction_retained"
            detail["contraction"]["selection"] = "declined_for_terminal_clearance"
            detail["final_contact_source"] = "hardware_safe_construction"
        if (
            not permitted
            and settings.first_pass_optimization
            and not contraction_recovery_consulted
        ):
            prior_recovery = detail["construction"]["recovery"]
            reservation_cpu = process_time()
            allowance = _remaining_recovery(
                prior_recovery, recovery_started, 4 - (perf_counter() - started)
            )
            partial = (
                remaining_completed(
                    prior_recovery, recovery_started, 4 - (perf_counter() - started)
                )
                if allowance is None
                else None
            )
            if partial is not None:
                allowance = partial.cpu_seconds, partial.wall_seconds
            pairs_left = CONTACT_PAIR_BUDGET - detail["construction"]["contact_pairs"]
            terminal_cpu_left = (
                allowance[0] - (process_time() - reservation_cpu)
                if partial is not None and allowance is not None
                else allowance[0]
                if allowance is not None
                else 0.0
            )
            if allowance is not None and pairs_left > 0 and terminal_cpu_left > 0:
                recovered = recover_terminal(
                    first,
                    terminal,
                    first_checkpoint,
                    record,
                    maximum_length_mm=result.route.material_length_mm,
                    minimum_straight_mm=native_point_tolerance_mm,
                    remaining_pairs=pairs_left,
                    maximum_cpu_seconds=terminal_cpu_left,
                    maximum_seconds=allowance[1],
                    maximum_updates=partial.updates if partial is not None else 4,
                )
                if recovered is not None:
                    recovery = dict(recovered.detail)
                    if prior_recovery is not None:
                        recovery.update(
                            deferred_before_terminal=prior_recovery,
                            cpu_seconds=prior_recovery["cpu_seconds"] + recovery["cpu_seconds"],
                            elapsed_seconds=perf_counter() - recovery_started,
                        )
                        if partial is not None:
                            recovery.update(
                                iterations=prior_recovery["iterations"] + recovery["iterations"],
                                contacts=prior_recovery["contacts"] + recovery["contacts"],
                                contact_pairs=prior_recovery["pairs"] + recovery["contact_pairs"],
                                cpu_seconds=prior_recovery["cpu_seconds"]
                                + process_time()
                                - reservation_cpu,
                                newton_steps_scope="terminal_reclosure_only",
                                contact_seconds_scope="terminal_certificate_only",
                            )
                    detail["construction"]["recovery"] = recovery
                    detail["construction"]["contacts"] += recovered.detail["contacts"]
                    detail["construction"]["contact_pairs"] += recovered.detail["contact_pairs"]
                    detail["construction"]["contact_seconds"] += recovered.detail["contact_seconds"]
                    detail["first_pass_seconds"] += recovered.detail["elapsed_seconds"]
                    if recovered.contact is not None:
                        first = final = recovered.route
                        measurement = recovered.contact
                        permitted = True
                        detail["stages"]["terminal_hardware"] = "recovered_first_pass"
                        detail["final_contact_source"] = "deferred_terminal_recovery"
        detail["terminal_hardware"] = terminal.detail()
        detail["terminal_hardware"]["final_status"] = "clear" if permitted else "unresolved"
        if not permitted:
            detail["stages"]["terminal_hardware"] = "unresolved"
            detail["final_contact_source"] = "first_pass_rejected_by_terminal_hardware"
            detail.update(
                status="unresolved",
                rejection_reason="Terminal hardware clearance was not established for the final candidate",
                elapsed_seconds=perf_counter() - started,
                cpu_seconds=process_time() - cpu_started,
            )
            return Result(None, first, detail, None, inspection_route=smoothed.route)
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
        return Result(None, first, detail, None, inspection_route=final)
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
    uv_seconds = perf_counter() - uv_started
    quality_started = perf_counter()
    guide_agreement = agreement(final, frames.guide)
    detail.update(
        status="geometry_ready_contact_unmeasured" if warning else "numerically_accepted",
        material_uv_seconds=uv_seconds,
        quality_measurement_seconds=perf_counter() - quality_started,
        cap_error_mm=caps,
        material_metric_error=metric,
        contact=contact,
        quality={
            "objective": "strict_material_shortening_then_guide_ties",
            "construction_length_mm": result.route.material_length_mm,
            "first_pass_length_mm": first.material_length_mm,
            "final_length_mm": final.material_length_mm,
            "guide_length_mm": frames.guide.distances[-1],
            "final_guide_agreement": asdict(guide_agreement),
            "first_pass_outcome": "disabled"
            if not settings.first_pass_optimization
            else "shortened"
            if first.material_length_mm < result.route.material_length_mm
            else "construction_retained",
            "optimality": "unproved; guide agreement and compactness are preferences, not physical certificates",
        },
        elapsed_seconds=perf_counter() - started,
        cpu_seconds=process_time() - cpu_started,
    )
    return Result(final, first, detail, material_uv)


def _remaining_recovery(
    detail: dict[str, Any] | None, started: float, first_pass_remaining: float
) -> tuple[float, float] | None:
    """
    Reserve only unused optional recovery work, including preparation and intervening wall time.

    Deferral must have executed zero updates and certificates. Its CPU cost is
    subtracted from0.35seconds; the wall span includes intervening contraction.
    Any consumed recovery keeps its existing outcome without another attempt.
    """
    if first_pass_remaining <= 0:
        return None
    if detail is None:
        return MAXIMUM_CPU_SECONDS, min(MAXIMUM_WALL_SECONDS, first_pass_remaining)
    if detail.get("status") != "deferred":
        return None
    if any(detail.get(field) != 0 for field in ("iterations", "contacts", "pairs")):
        raise ArithmeticError("Deferred recovery already consumed geometry work")
    cpu_left = MAXIMUM_CPU_SECONDS - detail["cpu_seconds"]
    wall_left = min(first_pass_remaining, MAXIMUM_WALL_SECONDS - (perf_counter() - started))
    return (cpu_left, wall_left) if cpu_left > 0 and wall_left > 0 else None
