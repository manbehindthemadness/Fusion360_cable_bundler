"""
Correct external mating caps with signed material joints under the remaining original actions.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import (
    fixed_fold_frames_match,
    ordered_mating_caps,
)
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import FeatureEvidence
from experiments.experiment_ribbon_terminal_hardware.flat_support_linearization import (
    SupportMemory,
    linearize,
)
from experiments.experiment_ribbon_terminal_hardware.joint_completion import (
    oriented_material_ready,
    stalled_certificate_ready,
)
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import (
    Difference,
    jacobian,
    mating_cap_jacobian,
)
from experiments.experiment_ribbon_terminal_hardware.joint_mating import SourceReadiness
from experiments.experiment_ribbon_terminal_hardware.joint_mating import restore as restore_mating
from experiments.experiment_ribbon_terminal_hardware.model import Hardware
from experiments.experiment_ribbon_terminal_hardware.native_slots import extensions
from experiments.experiment_ribbon_terminal_hardware.redistributed_projection import (
    GuidancePolicy,
    LinearPolicy,
    redistributed_step,
    strict_descent,
)
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import (
    Protection,
    ProtectionBasis,
)

from .allocation import MATERIAL_GAP_MM, MaterialEvidence, MaterialRow, constraints
from .discovery import Discovery
from .ledger import Ledger
from .native_model import NativeJoints
from .trust import LocalBox, interior_terms, radius


def _mating_ready(
    candidate: FoldRoute | None,
    model: NativeJoints,
    residual: tuple[float, ...],
    minimum_straight_mm: float,
) -> bool:
    """
    Require original physical guidance, native/material readiness and fixed-fold orientation before polishing.
    """
    return (
        candidate is not None
        and max(residual[6:], default=0.0) <= 1e-14
        and oriented_material_ready(
            candidate,
            model,
            length_ceiling_mm=None,
            minimum_straight_mm=minimum_straight_mm,
        )
    )


def _mating_step(
    candidate: FoldRoute,
    model: NativeJoints,
    values: tuple[float, ...],
    residual: tuple[float, ...],
    minimum_straight_mm: float,
    ledger: Ledger,
    record: Callable[[dict[str, Any]], None],
) -> tuple[float, ...] | None:
    """
    Spend the already charged Newton slot on one existing mating correction, without angular fallback.
    """
    polished = restore_mating(
        candidate,
        model,
        values,
        residual,
        ledger.checkpoint,
        minimum_straight_mm=minimum_straight_mm,
        length_ceiling_mm=None,
        fixed=frozenset(model.native_pins),
        readiness=SourceReadiness.ORIENTED_MATERIAL,
    )
    if polished is None:
        return None
    mating_candidate = model.route(polished)
    if mating_candidate is None:
        raise ArithmeticError("Mating correction lost its verified material placement")
    record(
        {
            "stage": "paired_mating",
            "status": "corrected",
            "newton": ledger.newton_steps,
            "route": snapshot(mating_candidate),
        }
    )
    return polished


def _proof_ready(
    candidate: FoldRoute | None,
    model: NativeJoints,
    residual: tuple[float, ...],
    minimum_straight_mm: float,
) -> bool:
    """
    Use existing source-cap, material and native readiness without treating guidance as physical proof.
    """
    return (
        candidate is not None
        and oriented_material_ready(
            candidate, model, length_ceiling_mm=None, minimum_straight_mm=minimum_straight_mm
        )
        and stalled_certificate_ready(
            candidate,
            model,
            residual,
            length_ceiling_mm=None,
            minimum_straight_mm=minimum_straight_mm,
        )
    )


def correct_owned(
    source: FoldRoute,
    anchor: FoldRoute,
    pairs: tuple[tuple[int, int], ...],
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Charge a new correction action before any signed-joint preparation.
    """
    if ledger.newton_steps >= ledger.work.newton_steps:
        return None
    ledger.start_action()
    return correct_started(
        source, anchor, pairs, material, features, hardware, minimum_straight_mm, ledger, record
    )


def correct_started(
    source: FoldRoute,
    anchor: FoldRoute,
    pairs: tuple[tuple[int, int], ...],
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
    record: Callable[[dict[str, Any]], None],
    *,
    discovery: Discovery | None = None,
) -> FoldRoute | None:
    """
    Enter correction only after charging an unused action.
    """
    if not ledger.updates or ledger.action_newton != 0:
        raise ValueError("Continue only an already charged unused correction action")
    return correct_remaining(
        source,
        anchor,
        pairs,
        material,
        features,
        hardware,
        minimum_straight_mm,
        ledger,
        record,
        discovery=discovery,
    )


def correct_remaining(
    source: FoldRoute,
    anchor: FoldRoute,
    pairs: tuple[tuple[int, int], ...],
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
    record: Callable[[dict[str, Any]], None],
    *,
    discovery: Discovery | None = None,
) -> FoldRoute | None:
    """
    Spend only remaining original actions, with six Newton/four-trial corrections per action.

    No new orientation roots are enumerated. All signed angular changes obey
    the original0.2radian bound, and every attempted correction consumes Newton
    work even if projection or trials fail. Geometry is only a closed proposal;
    the owning sequence still owes material/native/hardware/full-contact proofs.
    Failure retains its last unclosed proposal in the journal, not acceptance.
    Once original material/native readiness and fixed-fold orientation hold,
    one remaining charged Newton step may use the existing mating correction
    instead of another angular projector. Decline cannot start another solve;
    the retained inequalities continue to guide motion. With explicit gate
    ownership, original stalled-source readiness may instead request one mating
    correction and actual hardware proof. That request ends this stage without
    further motion or constraint insertion. Conservative guidance cannot replace
    the unchanged final material, native, hardware and full-contact gates.
    """
    if ledger.newton_steps >= ledger.work.newton_steps:
        return None
    if not ledger.updates or not 0 <= ledger.action_newton < 6:
        raise ValueError("Continue only a charged action with unused Newton work")
    available_steps = 6 - ledger.action_newton + 6 * (ledger.work.updates - ledger.updates)
    maximum_steps = min(available_steps, ledger.work.newton_steps - ledger.newton_steps)
    model = NativeJoints(source, minimum_straight_mm)
    values = model.initial
    physical = constraints(model, anchor, material, features, hardware, minimum_straight_mm, ledger)
    if physical is None:
        return None
    retained = tuple(physical)
    if discovery is not None:
        discovery.begin(model, ledger)
    material_bounds = tuple(
        (row.bound, Side.BEFORE) for row in retained if isinstance(row, MaterialRow)
    )
    support_memory = SupportMemory()
    touching_rows = frozenset(
        index
        for index, row in enumerate(retained, 6)
        if isinstance(row, Protection) and row.basis is ProtectionBasis.MATING_BOUNDARY
    )
    boundary_curvature = False

    def equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Evaluate current geometry and the same retained full-member inequalities.
        """
        return model.residual(coordinates) + tuple(evaluate(coordinates) for evaluate in retained)

    stop = "newton_limit"
    discovery_stop: str | None = None
    screened_values: tuple[float, ...] | None = None
    trust_radius = math.inf
    for _ in range(maximum_steps):
        ledger.checkpoint()
        residual = equations(values)
        candidate = model.route(values)
        if discovery is not None and values != model.initial and candidate is not None:
            screened_values = values
            refreshed = discovery.scan(model, candidate, values, retained)
            if refreshed.stop is not None:
                stop = discovery_stop = refreshed.stop
                break
            retained = refreshed.rows
            residual = equations(values)
        slivers = frozenset(
            i for i in model.straight_indices if 0 < values[i] * model.scale <= minimum_straight_mm
        )
        if (
            candidate is not None
            and ordered_mating_caps(candidate.pieces, candidate.targets)
            and cap_error(candidate) <= 1e-7
            and max(residual[6:], default=0.0) <= 1e-14
        ):
            if not slivers:
                return candidate
        elif candidate is None or not fixed_fold_frames_match(candidate.pieces, candidate.targets):
            slivers = frozenset()
        if ledger.action_newton >= 6:
            ledger.start_action()
        ledger.start_newton()
        if (
            discovery is not None
            and values != model.initial
            and _proof_ready(candidate, model, residual, minimum_straight_mm)
        ):
            assert candidate is not None
            polished = _mating_step(
                candidate, model, values, residual, minimum_straight_mm, ledger, record
            )
            if polished is not None:
                values = polished
                proposal = model.route(values)
                assert proposal is not None
                if discovery.certify_stalled(proposal):
                    record(
                        {
                            "stage": "paired_family",
                            "status": "strict_hardware_proposal",
                            "newton": ledger.newton_steps,
                            "guidance_residual": equations(values)[6:],
                        }
                    )
                    return proposal
            stop = discovery_stop = "stalled_proof_unresolved"
            break
        if _mating_ready(candidate, model, residual, minimum_straight_mm):
            assert candidate is not None
            polished = _mating_step(
                candidate, model, values, residual, minimum_straight_mm, ledger, record
            )
            if polished is None:
                stop = "mating_correction_unresolved"
                break
            values = polished
            continue
        if slivers:
            pinned = extensions(model, values, slivers, minimum_straight_mm, model.scale)
            if pinned is None:
                stop = "native_extension_unresolved"
                break
            model.native_pins.update(pinned)
            values = tuple(pinned.get(i, value) for i, value in enumerate(values))
            residual = equations(values)
            record(
                {
                    "stage": "paired_native",
                    "status": "extended",
                    "newton": ledger.newton_steps,
                    "pinned_coordinates": pinned,
                }
            )
        rows = jacobian(
            model,
            values,
            equations,
            len(residual),
            set(model.native_pins),
            ledger.checkpoint,
            admissible=model.admissible,
            difference=Difference.ONE_SIDED,
        )
        centered = mating_cap_jacobian(
            model,
            values,
            residual[:6],
            model.residual,
            set(model.native_pins),
            ledger.checkpoint,
            admissible=model.admissible,
        )
        if centered is not None:
            rows[:6] = centered
        linear = linearize(
            material_bounds,
            values,
            residual,
            rows,
            model,
            set(model.native_pins),
            model.admissible,
            ledger.checkpoint,
            memory=support_memory,
            minimum_gap_mm=MATERIAL_GAP_MM,
        )
        support_memory.remember(linear.supports)
        projected_terms = (
            interior_terms(linear.terms, touching_rows) if boundary_curvature else linear.terms
        )
        delta = redistributed_step(
            LocalBox(model, values, trust_radius),
            values,
            [list(row) for row in linear.rows],
            projected_terms,
            ledger.checkpoint,
            guidance_policy=GuidancePolicy.RESTORATION_MERIT,
            linear_policy=LinearPolicy.COUPLED_RESTORATION,
        )
        if delta is None:
            stop = "linear_projection_unresolved"
            break
        fraction = step_limit(model, values, delta, 1.0)
        accepted = None
        for _ in range(4):
            ledger.checkpoint()
            raw = tuple(a + fraction * b for a, b in zip(values, delta))
            if any(
                raw[i] < 0 and (values[i] != 0 or abs(raw[i]) > 2 * math.ulp(1.0))
                for i in model.straight_indices
            ):
                fraction *= 0.5
                continue
            trial = advance(model, values, delta, fraction)
            if model.admissible(trial) and model.allows_step(values, trial):
                actual_terms = equations(trial)
                if strict_descent(residual, actual_terms, GuidancePolicy.RESTORATION_MERIT):
                    accepted = trial
                    break
                if any(
                    old <= 0 and new > 1e-14 for old, new in zip(residual[6:], actual_terms[6:])
                ):
                    boundary_curvature = True
            fraction *= 0.5
        if accepted is None:
            stop = "nonlinear_descent_unresolved"
            break
        observed = equations(accepted)
        trust_radius = radius(
            values, accepted, rows, residual, observed, previous_radius=trust_radius
        )
        values = accepted
        record(
            {
                "stage": "paired_family",
                "status": "update",
                "newton": ledger.newton_steps,
                "values": values,
                "owned_pairs": pairs,
                "motion_model": "signed_external_caps",
                "bank_indices": model.bank_indices,
                "residual": observed,
                "trust_radius": None if math.isinf(trust_radius) else trust_radius,
                "interior_slack_rows": tuple(
                    index
                    for index, (raw, projected) in enumerate(zip(linear.terms, projected_terms))
                    if raw != projected
                ),
                "support_bundles": linear.bundles,
                "support_added_rows": linear.added_rows,
                "support_capacity_declines": linear.capacity_declines,
                "support_topology_declines": linear.topology_declines,
            }
        )
    candidate = model.route(values)
    if candidate is not None:
        if (
            discovery is not None
            and discovery_stop is None
            and values != model.initial
            and values != screened_values
        ):
            refreshed = discovery.scan(model, candidate, values, retained)
            retained = refreshed.rows
            if refreshed.stop is not None:
                stop = discovery_stop = refreshed.stop
        residual = equations(values)
        if (
            discovery_stop is None
            and ordered_mating_caps(candidate.pieces, candidate.targets)
            and cap_error(candidate) <= 1e-7
            and max(residual[6:], default=0.0) <= 1e-14
            and not any(
                0 < values[i] * model.scale <= minimum_straight_mm for i in model.straight_indices
            )
        ):
            return candidate
        record(
            {
                "stage": "paired_family",
                "status": "unresolved",
                "reason": stop,
                "candidate": snapshot(candidate),
            }
        )
    return None


def correct(
    source: FoldRoute,
    anchor: FoldRoute,
    pair: tuple[int, int],
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
    record: Callable[[dict[str, Any]], None],
) -> FoldRoute | None:
    """
    Retain the single-pair correction entry point under the same shared implementation.
    """
    return correct_owned(
        source, anchor, (pair,), material, features, hardware, minimum_straight_mm, ledger, record
    )
