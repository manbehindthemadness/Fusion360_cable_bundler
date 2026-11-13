"""
Close exact caps, finite connector clearance and complete measured material contact regions together.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from enum import Enum
from functools import partial
from time import perf_counter, process_time
from typing import Any, Callable, Union, cast

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance, step_limit
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    Penetration,
    ProbeOrder,
    ProjectionReuse,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_affine_witness import AffineWitnesses
from experiments.experiment_ribbon_fold_route.contact_axes import (
    AxisContinuation,
    AxisLearning,
    ProposedAxes,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.contact_phase_core import ProfileProbe
from experiments.experiment_ribbon_fold_route.contact_subdivision import Subdivision
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import (
    fixed_fold_frames_match,
    ordered_mating_caps,
)

from .active_projection import active_step
from .bank_events import BankEvent, ZeroBanks
from .cap_completion import ordered_caps_complete
from .check import Report
from .contact_addition import Addition, ContactPolicy
from .contact_addition import prepare as prepare_contact_addition
from .curved_discovery import CurvedProbe
from .feature_guidance import (
    ContactGuidance,
    ContactMotion,
    IncidentGuidance,
    MaterialGuidance,
    ReturnLength,
    member_planes,
)
from .feature_plane import FeatureCoverage, FeaturePlane, SignedJoints
from .flat_continuation import ClosedFlatContinuation, ContactContinuation
from .flat_separation import FlatSeparation, ProfileExtent
from .gate import Gate
from .hardware_halfspaces import separated_alternatives
from .hardware_motion import expand as expand_hardware
from .hardware_motion import straight_growth_requires_angles
from .incident_model import IncidentJoints
from .incident_window import IncidentWindow, ReturnCoordinates
from .joint_completion import closed_material, stalled_certificate_ready
from .joint_derivatives import Difference
from .joint_derivatives import jacobian as joint_jacobian
from .joint_evaluation import JointEvaluation
from .joint_handoff import JointHandoff
from .joint_mating import restore as restore_mating
from .line_search import contracted_fraction
from .material_constraint import MaterialConstraint
from .material_halfspaces import separated_alternatives as separated_material_alternatives
from .material_return_selection import UnreflectedReturns
from .material_working_set import least_binding
from .moving_probe import moving_domain
from .native_slots import bind_proposal as bind_native_slots
from .native_slots import extensions as extend_native_slots
from .native_slots import zero_step
from .quality_projection import quality_step
from .radius_model import RadiusJoints
from .recovery_limits import validate
from .redistributed_projection import (
    GuidancePolicy,
    LinearPolicy,
    ProjectionEvidence,
    redistributed_step,
    strict_descent,
)
from .restoration_handoff import RestorationHandoff, RestorationStop
from .restoration_order import FocusKind, MaterialFocus
from .restoration_screen import represented_phases
from .restoration_screen import screen as screen_restoration
from .retained_directions import RetainedDirections
from .reversal_model import incident_fold
from .run_translation import StraightSlots
from .straight_projection import RunwayEvidence, shortest_run_step
from .straight_quality import StraightQuality
from .terminal_protection import Protection
from .terminal_protection import prepare as prepare_terminal_protection
from .terminal_protection import uncovered as uncovered_terminal_protection


class JointMode(Enum):
    """
    Distinguish parent improvement, mating quality policies and one-radius physical restoration.
    """

    PARENT_CEILING = "parent_ceiling"
    MATING_CEILING = "mating_ceiling"
    BLOCKED_MATING = "blocked_mating"
    RADIUS_RESTORATION = "radius_restoration"


class _Exhausted(RuntimeError):
    """
    Stop only this optional shared allocation without masking caller cancellation or resource errors.
    """


RecoveryMode = Union[JointMode, IncidentGuidance, MaterialGuidance, ContactGuidance]


def recover(
    original: FoldRoute,
    evidence: Report | Penetration | ContactResult,
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
    maximum_newton_steps: int = 24,
    mode: RecoveryMode = JointMode.PARENT_CEILING,
    on_blocked: Callable[[JointHandoff], None] | None = None,
    on_restoration_blocked: Callable[[RestorationHandoff], None] | None = None,
    early_material_return: UnreflectedReturns | None = None,
) -> Result | None:
    """
    Use remaining original work on caps and actual connector or flat-contact evidence.

    An opted-in adaptive hardware stage may retain its first actual complete
    flat crossing in the same straight-only model before a closed handoff. All
    earlier hardware constraints, clocks, pairs and update limits remain. A
    projection/descent decline can yield only its identical retained closed state;
    motion invalidates that fallback and every success needs fresh full proofs.

    An opted-in sequence may stop an angular hardware/contact or reflected material stage at a newly retained
    strict crossing selecting a distinct unreflected turn, while another logical
    update remains. The same current-pose inverse validation and original clocks
    guard this uncertified transfer. It grants no closure, clearance or new work.

    Negative discovery also covers already closed corrections and straight-only
    motion. Exact current model movement and sampled spatial proximity propose
    a bounded pair prefix, interleaved with retained material neighborhoods when
    present. Already represented pairs follow unknown pairs. Samples grant no
    clearance. A verified strict witness on this same iteration can advance to
    the existing negative handling after all material/native/hardware gates;
    no positive certificate or witness transfers to a later pose. Every accepted
    route still needs the complete current contact certificate. Stalled final
    requests never resume discovery or motion.
    Distinct material bounds use the unused original thirteen physical-equation
    slots rather than a separate four-bound ceiling. Their preparation and all
    subsequent correction still share the original clocks and motion allocation.

    A final current-pose certificate may consume the genuinely unused part of
    the original shared contact allocation. An internal1024comparison slice
    must not strand that work. The single traversal still shares the original
    CPU/pair ceiling with every earlier pose; no request or geometry is retried.

    The parent length is an inequality ceiling, never a growth target. All signs,
    radii, material identity/order and target poses stay fixed. Negative-only hull
    probing runs only until a first actual contact; subsequent certificates use
    the complete original checker, with bounded identical projection reuse.
    Every certificate and witness comparison shares the original pair pool.
    The default retains every radius and the parent length ceiling. Explicit
    radius restoration grows only the evidence-incident radius and treats the
    invalid source length as a quality goal rather than a physical veto. It
    receives only genuinely unused work after a measured fold-domain boundary.
    All material, cap, contact and finite-hardware requirements remain strict.
    Actual ordered mating caps within the existing1e-7contract may advance to
    ordinary physical certification even when their normalized progress metric
    remains above1e-13. Every represented inequality retains its original gate;
    native slots, material identity, hardware and full contact still must pass.
    Explicit mating restoration retains every radius and the strict parent
    ceiling, placing its length target inside that ceiling with the existing
    StraightQuality margin. It avoids rounded equality without accepting any
    excess or changing physical tolerances. Default parent targeting is unchanged.
    Contact guidance jointly retains depth-limited flat phases and actual
    hardware members without reflecting folds. It uses the same bounded-cap
    projector and complete independent inequalities, treating invalid-source
    length as a reported quality goal. It does not turn uncertain contact into
    a penetration witness or clearance. Final hardware uses refined certification.
    A confirmed curved crossing can add the shared analytic whole-piece
    projection while retaining earlier flat/hardware constraints. Mixed curved
    depth uncertainty remains unsupported; no local witness patch is accepted.
    Mating restoration retains each witnessed flat contact as an independent
    full-profile inequality. More than four scalar inequalities use the existing
    sixteen-step active projection; constraint, update, time and pair limits stay
    unchanged. Other modes retain their original aggregated profile-arc guidance.
    A strict material crossing can initialize complete-profile flat guidance
    without inventing hardware intrusion. That entry can subsequently add
    up to two demonstrated connector planes. One-radius restoration can also
    retain a second actually witnessed hardware feature after clearing its
    initial constraint. Each occupied member gets its own closest box halfspace;
    adjoining members need not clear the same box face. Up to thirteen physical
    inequalities use the existing sixteen-step projection when needed. Both
    features share the same remaining updates, clocks and pair pool; no additional
    radius is released. Other legacy hardware entries retain their single-plane
    stopping behavior and profile-arc guidance.
    Incident guidance retains actual prior reports, reflects their one witnessed
    event and gives occupied members independent separating planes. At most four
    features/thirteen physical inequalities use sixteen dual active-set steps,
    replacing scalar subset enumeration under the same caller work allocation.
    Angular restoration shares independent cap residuals across incident,
    material and coupled guidance. Cap residuals may change independently
    within the previous maximum merit, using the same single
    bounded projector and strict predicted/nonlinear maximum-merit descent.
    Motion regularization decays with the square of that merit; original bounds
    receive an equivalent positive coordinate transform inside the projector.
    A working set declined for exhaustion or raw inequalities can supply its
    already-computed geometry after one
    coordinate-box projection, still requiring the same predicted/nonlinear gates.
    Exhaustion and bounded proposals are reported separately from accepted work.
    Physical violations retain their shared restoration fraction; satisfied rows
    cannot acquire a positive linear violation. Material guidance selects a fold
    from an actual crossing and retains its complete regions. It allows equal
    parent length, with no compulsory shortening, and chooses its initial
    separating side in the reflected geometry. Confirmed curved crossings use
    analytic whole-piece guidance. All subsequent material and hardware
    certificates remain mandatory.
    Coupled and reflected correction constrain both terminal fold neighborhoods
    before motion, including the opposite connector without an intrusion witness.
    Uncertified enclosures target separation; only a complete analytic mating-cap
    certificate permits retaining source touch. These are conservative motion
    preferences, not clearance reports. Source axis families rebind with the
    motion model and share the original inequality/time limits. Necessary tiny
    positive zero-slot directions select a native-valid lower face in the one
    existing replacement projection; zero/outward directions remain frozen.
    Before that signed-joint replacement, an original zero slot may stay absent
    only if its zeroed proposal retains the same predicted constraint limits and
    strict maximum-merit descent. Otherwise positive-floor selection remains.
    Existing positive material is never removed and no projection is added.
    Fixed-bend cleanup uses that pass for feasibility without another runway
    minimization. Nonlinear steps and final native minimum checks remain strict.
    A positive sub-native straight found at cap closure extends to the smallest
    representable native floor instead of being deleted in coupled/reflected
    correction. Pin that length during the existing charged reclosure action;
    remaining coordinates must restore caps and pass every final certificate.
    Fixed-bend reclosure performs feasibility without restarting minimization.
    The existing replacement projection also enforces native feasibility when
    a positive slot would contract to a sub-native positive length. Choose its
    face from the target coordinate, retaining the same projection/trial limits.
    Explicit blocked-mating entry initially retains the same mating ceiling.
    Only after linear projection failure may its inherited quality ceiling become
    a reported length goal, with independent occupied hardware-member halfspaces
    rebound at the same coordinates. Every existing physical constraint and spent
    update remains; clear mating improvement never enters that release.
    An explicit continuation can retain a closed proposal at its first actual
    blocker. It receives no work allocation or clearance. Unresolved evidence
    never yields a guessed blocker; default local correction remains unchanged.
    Material return keeps its legacy parent ceiling by default. The explicit
    sequence restoration policy reports invalid-source length as a quality goal;
    all material, cap, radius and contact/hardware requirements remain strict.
    Adaptive hardware motion first minimizes travel in the straight-only domain.
    An initial projection returning no step,
    before any Newton motion and without material uncertainty, may rebind the
    same actual hardware features to the signed-joint domain. This preference
    does not prove global infeasibility. A feasible straight extension proceeds
    through unchanged nonlinear descent and final certificates; the shortest-run
    objective is a preference, not a veto on necessary travel. Model-bound caches are replaced, all original clocks and
    counters continue, and no second expansion or alternative sign is tried.
    Rejected nonlinear steps use safeguarded quadratic contraction from the
    existing linear prediction and observed merit. Inadmissible trials halve.
    The same four trials and strict nonlinear descent remain mandatory.
    All four ordinary trials, the original stalled-certificate request and
    prepared physical-evidence handoffs keep priority. Otherwise a crossed
    bank-zero change point may use two
    remaining Newton slots: one debits the four failed ordinary trials, and one
    debits a single change-point measurement, without another linear solve.
    No root, logical update, global trial-work or clock allowance is renewed.
    At exact bank zeros only,
    measured endpoint merit selects one matching derivative/projector side;
    nonzero bank signs remain free. A declined projection never tries another
    side, and all final physical and native-size gates remain unchanged.
    Reflected/coupled angular restoration permits only already-positive guidance
    terms to trade below a strictly decreasing maximum residual. Satisfied linear
    guidance stays strict; final material, cap and physical gates are unchanged.
    Changed open-cap angular/reflected proposals receive a negative-only flat
    screen, at most32comparisons per pose and256total from the original pair
    allowance. The existing probe support ceiling is shared. Strict new witnesses
    retain complete material guidance under the same four-constraint/thirteen-row
    limits; a miss grants no clearance. Screening times are included in contact
    time and reported separately as a subset. Final certificates stay mandatory.
    An opt-in restoration callback can yield a newly screened strict material
    witness after an ordinary projection/descent stop at that unchanged pose.
    It revalidates both inverse maps and material consistency under this same
    clock, grants no cap closure, and cannot follow resource or caller failure.
    After an angular native replacement declines, its original linear vector
    can remain usable if every candidate already had exact zero source and
    increment. Recheck that vector's strict predicted gates on the masked
    matrix; no new optimizer or trial is allocated. A successful replacement
    remains preferred. Positive material and nonzero candidate increments never
    qualify; nonlinear and physical gates are unchanged.
    After accepted angular motion, a stale hardware member plane may change
    only when another existing complete-member halfspace already meets the same
    positive gap. Still-intruding or uncertain members keep their original
    guidance. Each pose permits one selection per violated member within the
    original clocks; terminal protections and final whole-route proofs remain.
    The motion_attempted receipt includes initial reflection, native-coordinate
    changes and every retraction trial, including trials with zero accepted
    Newton steps. A linear preparation decline is distinct from failed motion.
    Initial hardware-only straight growth beyond both source length and inherited
    quality goal enables the same signed-joint domain before any motion. This
    selection changes no final length gate and allocates no additional correction.
    After accepted correction, ordinary no-descent or native-projection decline
    may request the same final physical certificates once for native-ready
    material. Before ordinary or stalled proof, one unspent correction may close
    actual mating frames using only occupied unfixed straight slots. This shares
    the fixed-fold affine kernel with construction allocation, debits one Newton
    attempt even if unresolved, and cannot renew roots, bounds, clocks or pins.
    A restored pose is recomposed and checked before any final request. Its
    finite optimization guidance need not be a clearance proof. This request
    never resumes motion or inserts constraints; all original final contracts,
    actual certificates, handoff evidence and remaining clocks/pairs still apply.
    After accepted angular/reflected motion, ordinary negative discovery retains
    priority. If it supplies no new constraint, actual native/material readiness
    with straight-correctable terminal frames may request that same final proof
    before microscopic guidance descent spends
    the remaining clock. Finite guidance alone cannot accept geometry. The once-only
    request prevents subsequent motion in this stage; original strict-witness
    callbacks may still hand off under the unchanged remaining allocation.
    """
    if not isinstance(mode, (JointMode, IncidentGuidance, MaterialGuidance, ContactGuidance)):
        raise ValueError("Supply an explicit joint recovery mode")
    coupled_contact = isinstance(mode, ContactGuidance)
    straight_contact = isinstance(mode, ContactGuidance) and mode.motion in (
        ContactMotion.STRAIGHT_SLOTS,
        ContactMotion.ADAPTIVE_HARDWARE,
    )
    adaptive_hardware = (
        isinstance(mode, ContactGuidance) and mode.motion is ContactMotion.ADAPTIVE_HARDWARE
    )
    if adaptive_hardware and isinstance(evidence, ContactResult) and evidence.status != "separated":
        raise ValueError(
            "Adaptive hardware motion requires hardware-only or separated contact evidence"
        )
    if isinstance(evidence, ContactResult) and not coupled_contact:
        raise ValueError("Contact guidance requires an actual material measurement")
    if coupled_contact and not isinstance(evidence, (ContactResult, Report)):
        raise ValueError("Contact guidance requires measured contact or retained hardware evidence")
    if isinstance(mode, MaterialGuidance) and not isinstance(evidence, Penetration):
        raise ValueError("Material reversal requires an actual material crossing")
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        maximum_newton_steps=maximum_newton_steps,
    )
    newton_limit = min(6 * maximum_updates, maximum_newton_steps)
    cpu, wall = process_time(), perf_counter()
    mating_mode = mode in (JointMode.MATING_CEILING, JointMode.BLOCKED_MATING)
    reflected = isinstance(mode, (IncidentGuidance, MaterialGuidance))
    selected: int | None = None
    model: SignedJoints
    if isinstance(mode, (IncidentGuidance, MaterialGuidance)):
        if (
            isinstance(mode, MaterialGuidance)
            and mode.coordinates is ReturnCoordinates.WITNESSED_INTERVAL
        ):
            assert isinstance(evidence, Penetration)
            model = IncidentWindow(original, mode.selected_fold, evidence)
        else:
            model = IncidentJoints(original, mode.selected_fold)
        selected = mode.selected_fold
    elif mode is JointMode.RADIUS_RESTORATION:
        if (
            not isinstance(evidence, Report)
            or evidence.status != "blocked"
            or evidence.witness is None
        ):
            return None
        selected = incident_fold(original, evidence.witness)
        if selected is None:
            return None
        model = RadiusJoints(original, selected)
    elif straight_contact:
        model = StraightSlots(original)
    else:
        model = SignedJoints(original)
    values = model.initial
    constraints: list[tuple[FlatSeparation | MaterialConstraint, Side]] = []
    planes: list[FeaturePlane] = []
    if isinstance(mode, (IncidentGuidance, ContactGuidance)) or (
        isinstance(mode, MaterialGuidance) and mode.evidence
    ):
        prepared = mode.planes(model, terminal.hardware, values)
        if prepared is None:
            return None
        planes = prepared
    if coupled_contact:
        if isinstance(evidence, ContactResult):
            initial = MaterialConstraint.create(model, original, evidence)
            if initial is None:
                if evidence.status != "separated" or not planes:
                    return None
            else:
                constraints.append((initial, Side.BEFORE))
        elif (
            not isinstance(evidence, Report)
            or evidence.status != "blocked"
            or evidence.witness is None
            or not planes
        ):
            return None
    elif isinstance(mode, IncidentGuidance):
        pass
    elif isinstance(evidence, Report):
        plane = FeaturePlane.create(model, original, evidence, terminal.hardware, values)
        if plane is None:
            return None
        planes.append(plane)
    elif isinstance(evidence, Penetration):
        initial = (
            MaterialConstraint.from_witness(model, original, evidence, axis_values=values)
            if isinstance(mode, MaterialGuidance)
            else FlatSeparation.create(model, original, evidence, extent=ProfileExtent.COMPLETE)
        )
        if initial is None:
            return None
        side = Side.BEFORE
        if isinstance(mode, MaterialGuidance) and initial.gap(values, Side.AFTER) > initial.gap(
            values, Side.BEFORE
        ):
            side = Side.AFTER
        constraints.append((initial, side))
    else:
        raise ValueError(
            "Initialize joint work from measured hardware or material crossing evidence"
        )
    independent_members = reflected or coupled_contact or mode is JointMode.RADIUS_RESTORATION
    independent_contacts = mating_mode or coupled_contact or isinstance(mode, MaterialGuidance)
    scalar_planes = member_planes(planes, model, values) if independent_members else planes
    protections: tuple[Protection, ...] = ()
    if (
        independent_members
        and len(scalar_planes) + len(constraints) + int(not coupled_contact) > 13
    ):
        return None
    projection_evidence = ProjectionEvidence()
    restoration_policy = GuidancePolicy.RESTORATION_MERIT
    linear_policy = LinearPolicy.DUAL
    runway_evidence = RunwayEvidence()
    project = (
        partial(shortest_run_step, evidence=runway_evidence)
        if straight_contact
        else partial(
            redistributed_step,
            evidence=projection_evidence,
            guidance_policy=restoration_policy,
            linear_policy=linear_policy,
        )
        if reflected or coupled_contact
        else quality_step
    )
    length_released = False
    hardware_expanded = False
    bounded_length = (
        mode is not JointMode.RADIUS_RESTORATION
        and not coupled_contact
        and not (
            isinstance(mode, MaterialGuidance) and mode.length is ReturnLength.RESTORATION_GOAL
        )
    )
    length_target = (
        StraightQuality(maximum_length_mm, maximum_updates).target_mm
        if mating_mode
        else maximum_length_mm - 1e-7
        if isinstance(mode, IncidentGuidance)
        else maximum_length_mm
    )
    keys: set[tuple[Any, ...]] = (
        {(bound.pair, bound.parts) for bound, _ in constraints} if coupled_contact else set()
    )
    constraint_keys: list[tuple[Any, ...] | None] = [
        (bound.pair, bound.parts) if coupled_contact else None for bound, _ in constraints
    ]
    material_guidance_releases = 0
    fixed: set[int] = set()
    native_pins: dict[int, float] = {}
    newton, pairs, contacts, contact_seconds = 0, 0, 0, 0.0
    motion_attempted = reflected
    candidate = original
    measurement: ContactResult | None = None
    accepted = False
    stop = "unattempted"
    active_pairs: int | None = None
    contact_started = 0.0
    interrupted_pairs: int | None = None
    probe = FlatProbe()
    flat_core_probe = ProfileProbe()
    curved_probe = CurvedProbe()
    penetration_seen = False
    native_positive_projections = 0
    native_zero_face_selections = 0
    native_zero_face_reuses = 0
    hardware_halfspace_attempts = 0
    hardware_halfspace_rebindings = 0
    hardware_guidance_values: tuple[float, ...] | None = None
    material_guidance_values: tuple[float, ...] | None = None
    material_halfspace_attempts = 0
    material_halfspace_rebindings = 0
    ordered_cap_completions = 0
    stalled_certificate_requests = 0
    mating_attempts, mating_restored = 0, 0
    screen_checks, screen_pairs, screen_seconds = 0, 0, 0.0
    focused_screens = 0
    motion_focused_screens = 0
    combined_focused_screens = 0
    screen_preparation_seconds = 0.0
    screened_values: tuple[float, ...] | None = None
    restoration_witness: tuple[tuple[float, ...], ContactResult] | None = None
    flat_continuation: ClosedFlatContinuation | None = None
    straight_contact_preparations = 0
    straight_contact_fallbacks = 0
    straight_contact_decline: str | None = None
    next_return: int | None = None
    restoration_decline: str | None = None
    restoration_inverse_checks = 0
    screen_active = False
    hardware_screened_values: tuple[float, ...] | None = None
    hardware_probe_checks = hardware_probe_cells = hardware_probe_constraints = 0
    retained_axis_contexts: list[ProposedAxes] = []
    affine_witness_contexts: list[AffineWitnesses] = []

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

    def raw_equations(coordinates: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reuse identical raw equations only while the actual constraint set remains fixed.
        """
        equation_terms = model.residual(coordinates) + tuple(
            1e-7 / model.scale - feature.gap(coordinates) for feature in scalar_planes
        )
        equation_terms += tuple(protection.residual(coordinates) for protection in protections)
        if bounded_length:
            equation_terms += (
                (
                    sum(p.geometry.material_length_mm for p in model.pieces(coordinates))
                    - length_target
                )
                / model.scale,
            )
        if constraints:
            flat_terms = tuple(
                1e-8 / model.scale - constraint.gap(coordinates, chosen_side)
                for constraint, chosen_side in constraints
            )
            equation_terms += flat_terms if independent_contacts else (max(flat_terms),)
        return equation_terms

    evaluation = JointEvaluation(raw_equations, model.admissible)
    equations, admissible = evaluation.equations, evaluation.admissible

    def merit(coordinates: tuple[float, ...]) -> float:
        """
        Reduce actual cap errors and only violated inequality terms.
        """
        merit_terms = equations(coordinates)
        return max(
            *(abs(term) for term in merit_terms[:6]), *(max(0.0, term) for term in merit_terms[6:])
        )

    def retain_addition(entry: Addition | None) -> str | None:
        """
        Retain distinct complete material guidance within the original physical equation ceiling.
        """
        nonlocal material_guidance_releases
        if entry is None:
            return "unsupported_or_exhausted_flat_constraints"
        if entry.key in keys:
            return "repeated_contact_witness"
        inequalities = (
            len(scalar_planes)
            + len(protections)
            + (len(constraints) + 1 + int(bounded_length) if independent_contacts else 2)
        )
        if independent_members and inequalities > 13:
            inactive = (
                least_binding(constraints, values, model.scale, bounded)
                if independent_contacts and inequalities == 14
                else None
            )
            if inactive is None:
                return "physical_inequality_capacity"
            old, old_side = constraints.pop(inactive.index)
            old_key = constraint_keys.pop(inactive.index)
            if old_key is not None:
                keys.remove(old_key)
            material_guidance_releases += 1
            emit(
                "material_guidance_released",
                reason="strictly_inactive_at_physical_capacity",
                pair=[asdict(tag) for tag in old.pair],
                parts=[
                    {"phase": part.phase.value, "q": (part.low_q, part.high_q)}
                    for part in old.parts
                ],
                side=old_side.name,
                gap_mm=inactive.gap * model.scale,
            )
        keys.add(entry.key)
        constraints.append((entry.bound, entry.side))
        constraint_keys.append(entry.key)
        evaluation.constraints_changed()
        emit(
            "constraint_added",
            witness=None if entry.witness is None else asdict(entry.witness),
            pair=[asdict(tag) for tag in entry.bound.pair],
            parts=[
                {"phase": part.phase.value, "q": (part.low_q, part.high_q)}
                for part in entry.bound.parts
            ],
            side=entry.side.name,
            gap_mm=entry.bound.gap(values, entry.side) * model.scale,
        )
        return None

    addition: Addition | None = None

    def retain_hardware(report: Report) -> str | None:
        """
        Add the same witnessed whole-member hardware guidance within existing feature/equation limits.
        """
        nonlocal scalar_planes, protections
        extra = FeaturePlane.create(
            model,
            candidate,
            report,
            terminal.hardware,
            values,
            coverage=FeatureCoverage.ADJOINING_INTERNAL
            if reflected or coupled_contact
            else FeatureCoverage.TERMINAL_RUNWAY,
        )
        if (
            len(planes) >= (4 if reflected or coupled_contact else 2)
            or extra is None
            or extra in planes
        ):
            return "hardware_not_clear"
        planes.append(extra)
        if independent_members:
            scalar_planes = member_planes(planes, model, values)
            protections = uncovered_terminal_protection(protections, scalar_planes)
            inequalities = (
                len(scalar_planes)
                + len(protections)
                + (
                    len(constraints) + int(bounded_length)
                    if independent_contacts
                    else 1 + bool(constraints)
                )
            )
            if inequalities > 13:
                return "physical_inequality_capacity"
        evaluation.constraints_changed()
        emit(
            "hardware_constraint_added",
            terminal=extra.box.terminal.value,
            reference=asdict(extra.reference),
        )
        return None

    def new_witness(witness: Penetration) -> bool:
        """
        Bind a new complete current-pose region without duplicating retained material.
        """
        nonlocal addition
        proposed_addition = prepare_contact_addition(
            model,
            candidate,
            ContactResult("penetration", 0, witness=witness),
            values,
            ContactPolicy.RESTORATION,
        )
        if proposed_addition is None or any(
            old.pair == proposed_addition.bound.pair and old.parts == proposed_addition.bound.parts
            for old, _ in constraints
        ):
            return False
        addition = proposed_addition
        return True

    def polish_current() -> bool:
        """
        Debit at most one unspent correction before actual fixed-slot mating restoration.
        """
        nonlocal newton, motion_attempted, values, candidate, mating_attempts, mating_restored
        if (
            newton == 0
            or newton >= newton_limit
            or mating_attempts
            or stalled_certificate_requests
            or ordered_mating_caps(candidate.pieces, candidate.targets)
            or not stalled_certificate_ready(
                candidate,
                model,
                equations(values),
                length_ceiling_mm=maximum_length_mm if bounded_length else None,
                minimum_straight_mm=minimum_straight_mm,
            )
        ):
            return False
        before = cap_error(candidate)
        mating_attempts, newton, motion_attempted = 1, newton + 1, True
        bounded()
        restored = restore_mating(
            candidate,
            model,
            values,
            equations(values),
            bounded,
            minimum_straight_mm=minimum_straight_mm,
            length_ceiling_mm=maximum_length_mm if bounded_length else None,
            fixed=frozenset(fixed) | frozenset(native_pins),
        )
        if restored is not None and restored != values:
            values = restored
            updated = model.route(values)
            assert updated is not None
            candidate, mating_restored = updated, 1
        emit(
            "mating_restoration",
            status_detail="closed" if mating_restored else "unresolved",
            newton_steps=newton,
            before_cap_error_mm=before,
            cap_error_mm=cap_error(candidate),
            values=values,
            route=snapshot(candidate),
        )
        bounded()
        return bool(mating_restored)

    def request_final(original_stop: str) -> bool:
        """
        Request original physical proof once for native-ready material after accepted motion.
        """
        nonlocal stalled_certificate_requests
        if newton == 0 or stalled_certificate_requests:
            return False
        ready = stalled_certificate_ready(
            candidate,
            model,
            equations(values),
            length_ceiling_mm=maximum_length_mm if bounded_length else None,
            minimum_straight_mm=minimum_straight_mm,
        )
        bounded()
        if not ready:
            return False
        polish_current()
        stalled_certificate_requests = 1
        emit(
            "stalled_certificate_requested",
            original_stop=original_stop,
            newton_steps=newton,
            route=snapshot(candidate),
        )
        bounded()
        return True

    try:
        bounded()
        if reflected or coupled_contact:
            protections = prepare_terminal_protection(
                model, terminal.hardware, scalar_planes, bounded
            )
            if len(scalar_planes) + len(protections) + len(constraints) + int(bounded_length) > 13:
                return None
        emit(
            "started",
            source=snapshot(original),
            maximum_length_mm=maximum_length_mm,
            remaining_updates=maximum_updates,
            remaining_pairs=remaining_pairs,
            initial_flat_constraints=len(constraints),
            initial_hardware_members=len(scalar_planes),
            terminal_protections=[
                {
                    "terminal": protection.plane.box.terminal.value,
                    "member": asdict(protection.plane.reference),
                    "minimum_gap_mm": protection.minimum_gap * model.scale,
                    "guidance_basis": protection.basis.value,
                }
                for protection in protections
            ],
            material_evidence_status=evidence.status
            if isinstance(evidence, ContactResult)
            else None,
        )
        while True:
            bounded()
            if not stalled_certificate_requests:
                proposed = model.route(values)
                assert proposed is not None
                candidate = proposed
            if (
                (reflected or coupled_contact)
                and not straight_contact
                and scalar_planes
                and not stalled_certificate_requests
                and newton > 0
                and hardware_guidance_values != values
            ):
                hardware_guidance_values = values
                refreshed = separated_alternatives(
                    scalar_planes, values, bounded, minimum_gap_mm=1e-7
                )
                hardware_halfspace_attempts += refreshed.attempts
                if refreshed.changed:
                    emit(
                        "hardware_halfspaces_rebound",
                        members=[
                            {
                                "terminal": scalar_planes[i].box.terminal.value,
                                "member": asdict(scalar_planes[i].reference),
                                "old_family": scalar_planes[i].family,
                                "old_side": scalar_planes[i].side.name,
                                "old_gap_mm": scalar_planes[i].gap(values) * model.scale,
                                "new_family": refreshed.planes[i].family,
                                "new_side": refreshed.planes[i].side.name,
                                "new_gap_mm": refreshed.planes[i].gap(values) * model.scale,
                            }
                            for i in refreshed.changed
                        ],
                    )
                    scalar_planes = refreshed.planes
                    hardware_halfspace_rebindings += len(refreshed.changed)
                    evaluation.constraints_changed()
            if (
                (reflected or coupled_contact)
                and not straight_contact
                and constraints
                and not stalled_certificate_requests
                and newton > 0
                and material_guidance_values != values
            ):
                material_guidance_values = values
                refreshed_material = separated_material_alternatives(
                    constraints, values, bounded, minimum_gap_mm=1e-8
                )
                material_halfspace_attempts += refreshed_material.attempts
                if refreshed_material.changed:
                    emit(
                        "material_halfspaces_rebound",
                        constraints=list(refreshed_material.changed),
                        gaps=[
                            {
                                "old_gap_mm": constraints[index][0].gap(
                                    values, constraints[index][1]
                                )
                                * model.scale,
                                "new_gap_mm": refreshed_material.constraints[index][0].gap(
                                    values, refreshed_material.constraints[index][1]
                                )
                                * model.scale,
                            }
                            for index in refreshed_material.changed
                        ],
                    )
                    constraints = refreshed_material.constraints
                    material_halfspace_rebindings += len(refreshed_material.changed)
                    evaluation.constraints_changed()
            terms = equations(values)
            error = merit(values)
            caps_complete = (
                bool(stalled_certificate_requests)
                or error < 1e-13
                or ordered_caps_complete(candidate, terms)
            )
            if caps_complete and error >= 1e-13 and not stalled_certificate_requests:
                ordered_cap_completions += 1
                emit(
                    "ordered_caps_complete",
                    normalized_error=error,
                    cap_error_mm=cap_error(candidate),
                )
            if (
                (reflected or coupled_contact)
                and not straight_contact
                and not caps_complete
                and newton > 0
                and hardware_screened_values != values
            ):
                hardware_screened_values = values
                domain = moving_domain(
                    candidate,
                    model,
                    values,
                    terminal.hardware,
                    (*planes, *(protection.plane for protection in protections)),
                    bounded,
                )
                if domain is not None:
                    hardware_probe_checks += 1
                    hardware_probe = terminal.probe(
                        candidate, "joint_moving_material", domain=domain, checkpoint=bounded
                    )
                    hardware_probe_cells += hardware_probe.cells_checked
                    emit(
                        "moving_hardware_probe",
                        report=asdict(hardware_probe),
                        member_pairs=len(domain.pairs),
                    )
                    bounded()
                    if hardware_probe.status == "blocked" and hardware_probe.witness is not None:
                        reason = retain_hardware(hardware_probe)
                        if reason is not None:
                            stop = reason
                            break
                        hardware_probe_constraints += 1
                        continue
            screen_eligible = (
                (reflected or coupled_contact)
                and not caps_complete
                and not stalled_certificate_requests
                and newton > 0
                and screened_values != values
                and screen_pairs < 256
                and probe.supports < 2048
            )
            focus = None
            allowed = 0
            if screen_eligible:
                allowed = min(32, 256 - screen_pairs, remaining_pairs - pairs)
                if allowed <= 0:
                    stop = "pair_budget"
                    break
                focus_started = perf_counter()
                try:
                    focus = MaterialFocus.for_correction(
                        candidate, model, values, constraints, bounded
                    )
                finally:
                    preparation_seconds = perf_counter() - focus_started
                    screen_preparation_seconds += preparation_seconds
                    screen_seconds += preparation_seconds
                    contact_seconds += preparation_seconds
            if screen_eligible:
                screened_values = values
                addition = None

                active_pairs, screen_active = allowed, True
                screen_checks += 1
                contact_started = perf_counter()
                focused_screens += int(focus is not None)
                motion_focused_screens += int(
                    focus is not None and focus.kind in (FocusKind.MOTION, FocusKind.COMBINED)
                )
                combined_focused_screens += int(
                    focus is not None and focus.kind is FocusKind.COMBINED
                )
                screened = screen_restoration(
                    candidate,
                    probe,
                    allowed,
                    bounded,
                    new_witness,
                    covered_phases=represented_phases(candidate, constraints),
                    focus=focus,
                    curved_probe=curved_probe,
                    flat_core_probe=flat_core_probe,
                )
                spent = perf_counter() - contact_started
                pairs += screened.pairs_checked
                screen_pairs += screened.pairs_checked
                screen_seconds += spent
                contact_seconds += spent
                active_pairs, screen_active = None, False
                emit(
                    "restoration_screen",
                    contact=asdict(screened),
                    focus_pairs=0 if focus is None else len(focus.priority),
                    focus_first_pair=None if focus is None else focus.priority[0],
                    focus_kind=None if focus is None else focus.kind.value,
                    caps_complete=caps_complete,
                    straight_only=straight_contact,
                )
                if addition is not None:
                    reason = retain_addition(addition)
                    if reason is not None:
                        stop = reason
                        break
                    penetration_seen = True
                    restoration_witness = (values, screened)
                    if (
                        early_material_return is not None
                        and on_restoration_blocked is not None
                        and not straight_contact
                        and (
                            isinstance(mode, ContactGuidance)
                            or isinstance(mode, MaterialGuidance)
                            and mode.selected_fold in early_material_return.reflected_folds
                        )
                        and math.ceil(newton / 6) < maximum_updates
                        and pairs < remaining_pairs
                        and screened.witness is not None
                    ):
                        bounded()
                        next_return = early_material_return.select(candidate, screened.witness)
                        if next_return is not None:
                            stop = "new_material_return"
                            break
                    continue
            if (
                not caps_complete
                and (reflected or coupled_contact)
                and not straight_contact
                and fixed_fold_frames_match(candidate.pieces, candidate.targets)
                and request_final("material_ready")
            ):
                continue
            if caps_complete:
                if not closed_material(
                    candidate,
                    model,
                    length_ceiling_mm=maximum_length_mm if bounded_length else None,
                ):
                    stop = "final_contract"
                    break
                slivers = {
                    i
                    for i in model.straight_indices
                    if 0 < values[i] * model.scale <= minimum_straight_mm
                }
                if slivers:
                    if stalled_certificate_requests:
                        stop = "native_sliver"
                        break
                    if newton >= newton_limit:
                        stop = "native_zero_reclosure_limit"
                        break
                    if (reflected or coupled_contact) and minimum_straight_mm > 0:
                        extended = extend_native_slots(
                            model, values, frozenset(slivers), minimum_straight_mm, model.scale
                        )
                        if extended is None:
                            stop = "native_extension_infeasible"
                            break
                        native_pins.update(extended)
                        emit(
                            "native_sliver_extended",
                            original_lengths_mm={str(i): values[i] * model.scale for i in slivers},
                            pinned_lengths_mm={
                                str(i): value * model.scale for i, value in extended.items()
                            },
                        )
                    fixed.update(slivers)
                    motion_attempted = True
                    values = tuple(
                        native_pins.get(i, 0.0) if i in fixed else value
                        for i, value in enumerate(values)
                    )
                    newton += 1
                    continue
                if any(
                    isinstance(p.geometry, Straight)
                    and p.geometry.material_length_mm <= minimum_straight_mm
                    for p in candidate.pieces
                ):
                    stop = "native_sliver"
                    break
                if polish_current():
                    continue
                hardware_report = (
                    terminal.certify(candidate, "joint_flat_contact_final")
                    if coupled_contact or on_blocked is not None
                    else terminal.measure(candidate, "joint_flat_contact_final")
                )
                bounded()
                if hardware_report.status != "clear":
                    if (
                        on_blocked is not None
                        and hardware_report.status == "blocked"
                        and hardware_report.witness is not None
                    ):
                        on_blocked(JointHandoff(candidate, hardware_report))
                        stop = "hardware_handoff"
                        break
                    if stalled_certificate_requests:
                        stop = "hardware_not_clear"
                        break
                    if (
                        not isinstance(evidence, Penetration)
                        and not reflected
                        and not coupled_contact
                        and mode is not JointMode.RADIUS_RESTORATION
                    ):
                        stop = "hardware_not_clear"
                        break
                    reason = retain_hardware(hardware_report)
                    if reason is not None:
                        stop = reason
                        break
                    continue
                allowed = remaining_pairs - pairs
                if allowed <= 0:
                    stop = "pair_budget"
                    break
                active_pairs = allowed
                contacts += 1
                contact_started = perf_counter()
                known_contact = (
                    penetration_seen
                    or isinstance(evidence, Penetration)
                    or (
                        isinstance(evidence, ContactResult)
                        and evidence.status == "penetration"
                        and evidence.witness is not None
                    )
                )
                learned = (
                    RetainedDirections.prepare(candidate, model, values, constraints, bounded)
                    if known_contact
                    else None
                )
                axis_context = ProposedAxes(
                    AxisContinuation.MATERIAL_CELLS,
                    learning=AxisLearning.LOCAL_SEPARATIONS,
                )
                retained_axis_contexts.append(axis_context)
                affine_context = AffineWitnesses()
                affine_witness_contexts.append(affine_context)
                measured_contact = inspect_contact(
                    candidate,
                    maximum_pairs=allowed,
                    cap_policy=CapPolicy.FACTORED_SUPPORT,
                    checkpoint=bounded,
                    witness_probe=learned if known_contact else probe,
                    probe_order=ProbeOrder.MATERIAL_CELLS
                    if known_contact
                    else ProbeOrder.ORIGINAL_PAIRS,
                    projection_reuse=ProjectionReuse.CELLS,
                    proposed_axes=axis_context,
                    affine_witnesses=affine_context,
                    subdivision=Subdivision.MATERIAL_PHASES,
                )
                pairs += measured_contact.pairs_checked
                contact_seconds += perf_counter() - contact_started
                active_pairs = None
                emit(
                    "certificate",
                    contact=asdict(measured_contact),
                    retained_direction_pairs=0 if learned is None else len(learned.axes),
                    retained_axis_context=None
                    if axis_context is None
                    else axis_context.statistics(),
                    route=snapshot(candidate),
                    affine_witnesses=affine_context.statistics(),
                )
                measurement = measured_contact
                bounded()
                if measured_contact.status == "separated":
                    bounded()
                    accepted, stop = True, "accepted"
                    break
                if (
                    on_blocked is not None
                    and measured_contact.status == "penetration"
                    and measured_contact.witness is not None
                ):
                    if (
                        adaptive_hardware
                        and straight_contact
                        and not stalled_certificate_requests
                        and isinstance(mode, ContactGuidance)
                        and mode.continuation is ContactContinuation.FIRST_FLAT
                        and flat_continuation is None
                    ):
                        bounded()
                        straight_contact_preparations += 1
                        retained = ClosedFlatContinuation.prepare(
                            model, candidate, measured_contact, values
                        )
                        if retained is not None and retain_addition(retained.addition) is None:
                            flat_continuation = retained
                            penetration_seen = True
                            emit("straight_contact_retained", cap_error_mm=cap_error(candidate))
                            bounded()
                            continue
                    bounded()
                    on_blocked(JointHandoff(candidate, measured_contact))
                    stop = "material_handoff"
                    break
                if stalled_certificate_requests:
                    stop = "contact_unresolved"
                    break
                if not coupled_contact and (
                    measured_contact.status != "penetration" or measured_contact.witness is None
                ):
                    stop = "contact_unresolved"
                    break
                penetration_seen = penetration_seen or measured_contact.status == "penetration"
                policy = (
                    ContactPolicy.COUPLED
                    if coupled_contact
                    else ContactPolicy.MATERIAL_RETURN
                    if isinstance(mode, MaterialGuidance)
                    else ContactPolicy.COMPLETE_FLAT
                    if mating_mode
                    else ContactPolicy.ARC_FLAT
                )
                reason = retain_addition(
                    prepare_contact_addition(model, candidate, measured_contact, values, policy)
                )
                if reason is not None:
                    stop = reason
                    break
                continue
            if newton >= newton_limit:
                stop = "joint_update_limit"
                break
            zero_banks = (
                ZeroBanks.at(model, values, merit, admissible, bounded)
                if (reflected or coupled_contact) and not straight_contact
                else None
            )
            linear_model = model if zero_banks is None else zero_banks
            if zero_banks is not None:
                emit(
                    "bank_zero_linearization",
                    positive=sorted(zero_banks.positive),
                    negative=sorted(zero_banks.negative),
                )
            jacobian = joint_jacobian(
                linear_model,
                values,
                equations,
                len(terms),
                fixed,
                bounded,
                admissible=admissible,
                difference=Difference.ONE_SIDED,
            )
            project_step = (
                active_step
                if (straight_contact and native_pins)
                or (
                    not reflected
                    and not coupled_contact
                    and (mating_mode or independent_members)
                    and len(terms) > 10
                )
                else project
            )
            delta = project_step(linear_model, values, jacobian, terms, bounded)
            initial_hardware_motion = (
                adaptive_hardware
                and straight_contact
                and not motion_attempted
                and newton == 0
                and not constraints
            )
            straight_growth = (
                initial_hardware_motion
                and delta is not None
                and straight_growth_requires_angles(model, delta, maximum_length_mm)
            )
            if delta is None or straight_growth:
                if initial_hardware_motion:
                    assert isinstance(mode, ContactGuidance)
                    prepared_domain = expand_hardware(original, mode, terminal.hardware, bounded)
                    if prepared_domain is None:
                        stop = "unsupported_hardware_domain"
                        break
                    model = prepared_domain.model
                    planes, scalar_planes = prepared_domain.planes, prepared_domain.members
                    values = model.initial
                    protections = prepare_terminal_protection(
                        model, terminal.hardware, scalar_planes, bounded
                    )
                    if len(scalar_planes) + len(protections) + len(constraints) > 13:
                        stop = "physical_inequality_capacity"
                        break
                    fixed.clear()
                    native_pins.clear()
                    straight_contact, hardware_expanded = False, True
                    linear_policy = LinearPolicy.COUPLED_RESTORATION
                    project = partial(
                        redistributed_step,
                        evidence=projection_evidence,
                        guidance_policy=restoration_policy,
                        linear_policy=linear_policy,
                    )
                    evaluation = JointEvaluation(raw_equations, model.admissible)
                    equations, admissible = evaluation.equations, evaluation.admissible
                    emit(
                        "hardware_motion_expanded",
                        newton_steps=newton,
                        reason="straight_growth_beyond_goal"
                        if straight_growth
                        else "linear_projection_infeasible",
                    )
                    continue
                if mode is JointMode.BLOCKED_MATING and not length_released:
                    parts = member_planes(planes, model, values)
                    if len(parts) + len(constraints) > 13:
                        stop = "physical_inequality_capacity"
                        break
                    length_released, bounded_length, independent_members = True, False, True
                    scalar_planes = parts
                    evaluation.constraints_changed()
                    emit(
                        "blocked_length_goal_released",
                        newton_steps=newton,
                        length_goal_mm=maximum_length_mm,
                    )
                    continue
                stop = "linear_projection_infeasible"
                break
            native_candidates = {
                i
                for i in model.straight_indices
                if values[i] == 0 and abs(delta[i]) * model.scale <= minimum_straight_mm
            }
            if reflected or coupled_contact:
                native_candidates.update(
                    i
                    for i in model.straight_indices
                    if 0 < (values[i] + delta[i]) * model.scale <= minimum_straight_mm
                )
            if native_candidates:
                native_incumbent = (
                    delta
                    if (reflected or coupled_contact)
                    and not straight_contact
                    and all(values[i] == 0.0 and delta[i] == 0.0 for i in native_candidates)
                    else None
                )
                if (reflected or coupled_contact) and not straight_contact:
                    absent_step = zero_step(
                        values,
                        frozenset(native_candidates),
                        delta,
                        jacobian,
                        terms,
                        restoration_policy,
                    )
                    if absent_step is not None:
                        native_zero_face_selections += 1
                        emit(
                            "native_zero_faces_selected",
                            slots=sorted(i for i in native_candidates if values[i] == 0),
                        )
                        delta = absent_step
                native_domain = None
                frozen_native = native_candidates
                if (
                    (reflected or coupled_contact)
                    and minimum_straight_mm > 0
                    and any(values[index] + delta[index] > 0 for index in native_candidates)
                ):
                    native_domain = bind_native_slots(
                        linear_model,
                        values,
                        frozenset(native_candidates),
                        delta,
                        minimum_straight_mm,
                        model.scale,
                    )
                    if native_domain is None:
                        stop = "native_projection_infeasible"
                        if request_final(stop):
                            continue
                        break
                    frozen_native = set(native_domain.frozen)
                    native_positive_projections += 1
                    emit(
                        "native_positive_slot_projection",
                        positive_slots=sorted(native_domain.positive),
                        frozen_slots=sorted(native_domain.frozen),
                        floor_mm=native_domain.minimum * model.scale,
                        original_steps_mm={
                            str(i): delta[i] * model.scale for i in native_candidates
                        },
                        original_lengths_mm={
                            str(i): values[i] * model.scale for i in native_candidates
                        },
                        proposed_lengths_mm={
                            str(i): (values[i] + delta[i]) * model.scale for i in native_candidates
                        },
                    )
                jacobian = [
                    [0.0 if i in frozen_native else value for i, value in enumerate(row)]
                    for row in jacobian
                ]
                if native_domain is None:
                    delta = project_step(linear_model, values, jacobian, terms, bounded)
                elif straight_contact:
                    delta = active_step(native_domain, values, jacobian, terms, bounded)
                else:
                    delta = redistributed_step(
                        native_domain,
                        values,
                        jacobian,
                        terms,
                        bounded,
                        evidence=projection_evidence,
                        guidance_policy=restoration_policy,
                        linear_policy=linear_policy,
                    )
                if delta is None and native_incumbent is not None:
                    retained_prediction = tuple(
                        term + math.fsum(a * b for a, b in zip(row, native_incumbent))
                        for row, term in zip(jacobian, terms)
                    )
                    if strict_descent(terms, retained_prediction, restoration_policy):
                        delta = native_incumbent
                        native_zero_face_reuses += 1
                        emit("native_zero_faces_reused", slots=sorted(native_candidates))
                if delta is None:
                    stop = "native_projection_infeasible"
                    if request_final(stop):
                        continue
                    break
            if native_pins:
                delta = tuple(0.0 if i in native_pins else change for i, change in enumerate(delta))
            fraction = step_limit(model, values, delta, 1.0)
            bank_event = (
                BankEvent.first(
                    values,
                    delta,
                    (i for i, full in enumerate(model.indices) if full % 4 == 2),
                    fraction,
                )
                if (reflected or coupled_contact) and not straight_contact
                else None
            )
            predicted = tuple(
                term + math.fsum(a * b for a, b in zip(row, delta))
                for row, term in zip(jacobian, terms)
            )
            linear_error = max(
                tuple(abs(term) for term in predicted[:6])
                + tuple(max(0.0, term) for term in predicted[6:])
            )
            predicted_change = linear_error - error
            last_trial_fraction = fraction
            for _ in range(4):
                bounded()
                motion_attempted = True
                last_trial_fraction = fraction
                trial = advance(model, values, delta, fraction)
                if bank_event is not None:
                    trial = bank_event.coordinates(trial, fraction)
                    if fraction == bank_event.fraction:
                        emit(
                            "bank_event_trial", fraction=fraction, banks=sorted(bank_event.indices)
                        )
                trial_error = merit(trial) if admissible(trial) else None
                if trial_error is not None and trial_error < error:
                    values, newton = trial, newton + 1
                    break
                fraction = contracted_fraction(fraction, error, trial_error, predicted_change)
            else:
                stop = "joint_no_descent"
                if request_final(stop):
                    continue
                event_accepted = False
                if (
                    bank_event is not None
                    and bank_event.fraction < last_trial_fraction
                    and newton + 2 <= newton_limit
                    and not (
                        on_blocked is not None
                        and flat_continuation is not None
                        and flat_continuation.unchanged(values, candidate)
                    )
                    and not (
                        on_restoration_blocked is not None
                        and restoration_witness is not None
                        and restoration_witness[0] == values
                    )
                ):
                    bounded()
                    newton += 2
                    emit(
                        "bank_event_restoration_debit",
                        newton_steps=newton,
                        failed_correction_slots=1,
                        event_correction_slots=1,
                        fraction=bank_event.fraction,
                        banks=sorted(bank_event.indices),
                    )
                    trial = bank_event.coordinates(
                        advance(model, values, delta, bank_event.fraction), bank_event.fraction
                    )
                    trial_error = merit(trial) if admissible(trial) else None
                    if trial_error is not None and trial_error < error:
                        values, event_accepted = trial, True
                if not event_accepted:
                    break
            emit("update", newton=newton, values=values, residual=equations(values))
        if (
            on_blocked is not None
            and stop in ("linear_projection_infeasible", "joint_no_descent")
            and flat_continuation is not None
            and flat_continuation.unchanged(values, candidate)
        ):
            bounded()
            emit("straight_contact_fallback_prepared", original_stop=stop)
            bounded()
            on_blocked(flat_continuation.state)
            straight_contact_decline, stop = stop, "material_handoff"
            straight_contact_fallbacks += 1
        if (
            on_restoration_blocked is not None
            and stop in ("linear_projection_infeasible", "joint_no_descent", "new_material_return")
            and restoration_witness is not None
            and restoration_witness[0] == values
        ):
            bounded()
            state = RestorationHandoff(
                candidate,
                restoration_witness[1],
                cast(RestorationStop, stop),
            )
            restoration_inverse_checks = 2
            emit(
                "material_restoration_prepared",
                original_stop=stop,
                next_fold=next_return,
                cap_error_mm=cap_error(candidate),
                witness=asdict(state.evidence.witness),
                inverse_checks=2,
            )
            bounded()
            on_restoration_blocked(state)
            restoration_decline, stop = stop, "material_restoration_handoff"
    except _Exhausted:
        stop = "phase_budget"
        pairs += active_pairs or 0
        if active_pairs is not None:
            interrupted_pairs = active_pairs
            if screen_active:
                screen_pairs += active_pairs
                screen_seconds += perf_counter() - contact_started
            contact_seconds += perf_counter() - contact_started
    detail: dict[str, Any] = {
        "status": "separated" if accepted else "unresolved",
        "method": "complete_flat_contacts",
        "iterations": math.ceil(newton / 6),
        "newton_steps": newton,
        "derivative_scheme": Difference.ONE_SIDED.value,
        "motion_attempted": motion_attempted,
        "contacts": contacts,
        "contact_pairs": pairs,
        "contact_seconds": contact_seconds,
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - wall,
        "length_mm": candidate.material_length_mm,
        "maximum_length_mm": maximum_length_mm,
        "stop_reason": stop,
        "flat_constraints": len(constraints),
        "material_guidance_releases": material_guidance_releases,
        "probe": asdict(probe),
        "curved_discovery": asdict(curved_probe),
        "flat_core_discovery": asdict(flat_core_probe),
        "flat_core_preparations": flat_core_probe.preparations(),
        "flat_probe_preparations": probe.shape_preparations(),
        "terminal_protection_constraints": len(protections),
        "native_positive_slot_projections": native_positive_projections,
        "native_zero_face_selections": native_zero_face_selections,
        "native_zero_face_reuses": native_zero_face_reuses,
        "hardware_halfspace_attempts": hardware_halfspace_attempts,
        "hardware_halfspace_rebindings": hardware_halfspace_rebindings,
        "material_halfspace_attempts": material_halfspace_attempts,
        "material_halfspace_rebindings": material_halfspace_rebindings,
        "material_halfspace_counter_scope": "completed_refreshes_only",
        "hardware_halfspace_counter_scope": "completed_refreshes_only",
        "ordered_cap_completions": ordered_cap_completions,
        "stalled_certificate_requests": stalled_certificate_requests,
        "mating_restoration_attempts": mating_attempts,
        "mating_restorations": mating_restored,
        "flat_region_cache": model.flat_regions.statistics(),
        "moving_hardware_probe_checks": hardware_probe_checks,
        "moving_hardware_probe_cells": hardware_probe_cells,
        "moving_hardware_probe_constraints": hardware_probe_constraints,
        "retained_axis_contexts": [context.statistics() for context in retained_axis_contexts],
        "affine_witnesses": [context.statistics() for context in affine_witness_contexts],
        "straight_contact_preparations": straight_contact_preparations,
        "straight_contact_retained": int(flat_continuation is not None),
        "straight_contact_fallbacks": straight_contact_fallbacks,
        "native_sliver_extensions": len(native_pins),
        "restoration_screen_checks": screen_checks,
        "restoration_focused_screens": focused_screens,
        "motion_focused_screens": motion_focused_screens,
        "combined_focused_screens": combined_focused_screens,
        "closed_contact_discoveries": 0,
        "restoration_preparation_seconds": screen_preparation_seconds,
        "restoration_screen_pairs": screen_pairs,
        "restoration_screen_seconds": screen_seconds,
        "restoration_handoff_inverse_checks": restoration_inverse_checks,
    }
    if straight_contact_decline is not None:
        detail["straight_contact_decline"] = straight_contact_decline
    if restoration_decline is not None:
        detail["restoration_decline"] = restoration_decline
    if length_released:
        detail.update(
            length_ceiling_released=True,
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
        )
    if runway_evidence.attempts:
        detail["runway_minimization"] = asdict(runway_evidence)
    if mode is JointMode.RADIUS_RESTORATION:
        detail.update(
            radius_restoration=True,
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            selected_fold=selected,
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            radius_floor_mm=original.radius_mm,
        )
    if isinstance(mode, (IncidentGuidance, MaterialGuidance)):
        detail.update(
            method="complete_material_return"
            if isinstance(mode, MaterialGuidance)
            else "complete_incident_features",
            selected_fold=selected,
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            maximum_linear_steps=16,
            linear_projection="redistributed_cap_restoration",
        )
        if isinstance(mode, MaterialGuidance):
            detail.update(
                length_policy=mode.length.value,
                return_coordinates=mode.coordinates.value,
                movable_coordinates=len(model.initial),
                length_goal_mm=maximum_length_mm,
                length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            )
    if isinstance(mode, ContactGuidance):
        detail.update(
            method="coupled_contact_refinement",
            feature_constraints=len(planes),
            scalar_feature_constraints=len(scalar_planes),
            maximum_linear_steps=16,
            linear_projection="fixed_bend_active_projection"
            if straight_contact
            else "redistributed_cap_restoration",
            length_goal_mm=maximum_length_mm,
            length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
            motion_policy=mode.motion.value,
            hardware_domain_expanded=hardware_expanded,
        )
    if reflected or (coupled_contact and not straight_contact):
        detail.update(
            motion_regularization="cap_step_normalized_merit_squared",
            guidance_restoration=restoration_policy.value,
            guidance_tradeoff_proposals=projection_evidence.guidance_tradeoff_proposals,
            coordinate_seed_attempts=projection_evidence.coordinate_seed_attempts,
            coordinate_seed_faces=projection_evidence.coordinate_seed_faces,
            primal_projection_attempts=projection_evidence.primal_attempts,
            primal_projection_completed=projection_evidence.primal_completed,
            primal_projection_updates=projection_evidence.primal_updates,
            primal_projection_prefixes=projection_evidence.primal_prefixes,
            primal_projection_proposals=projection_evidence.primal_proposals,
            primal_projection_stops=projection_evidence.primal_stops,
            primal_projection_update_scope="completed_actions_only",
            cap_metric_calibrations=projection_evidence.cap_metric_calibrations,
            active_face_restorations=projection_evidence.active_face_restorations,
            working_set_exhaustions=projection_evidence.exhaustions,
            raw_gate_rejected_vectors=projection_evidence.raw_gate_rejections,
            bounded_projection_proposals=projection_evidence.bounded_proposals,
            bound_clipped_proposals=projection_evidence.bound_clipped_proposals,
            halfspace_contracted_proposals=projection_evidence.halfspace_contracted_proposals,
        )
    if interrupted_pairs is not None:
        detail["interrupted_pairs_charged_as_upper_bound"] = interrupted_pairs
    emit(detail["status"], detail=detail, candidate=snapshot(candidate))
    return Result(candidate if accepted else original, measurement if accepted else None, detail)
