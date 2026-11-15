"""
Allocate fixed-factor straight travel while retaining witnessed material and connector constraints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_terminal_hardware.active_projection import active_step
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    FeatureEvidence,
    member_planes,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import (
    FeatureCoverage,
    FeaturePlane,
    SignedJoints,
)
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    ProfileExtent,
)
from experiments.experiment_ribbon_terminal_hardware.model import Hardware
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from experiments.experiment_ribbon_terminal_hardware.terminal_phase import MatingPhase
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection, prepare

from .ledger import Ledger

MATERIAL_GAP_MM = 1e-7


@dataclass(frozen=True)
class HardwareRow:
    """
    Retain complete member identity alongside its unchanged hardware gap equation.
    """

    plane: FeaturePlane

    def __call__(self, coordinates: tuple[float, ...]) -> float:
        """
        Evaluate the original member's required normalized gap without granting clearance.
        """
        return self.plane.minimum_gap_mm / self.plane.model.scale - self.plane.gap(coordinates)


@dataclass(frozen=True)
class MaterialRow:
    """
    Retain the full material bound identity alongside its unchanged nonlinear gap equation.
    """

    bound: FlatSeparation
    scale: float

    def __call__(self, coordinates: tuple[float, ...]) -> float:
        """
        Measure the same complete-region gap while keeping support branches accessible.
        """
        return MATERIAL_GAP_MM / self.scale - self.bound.gap(coordinates, Side.BEFORE)


@dataclass(frozen=True)
class MaterialEvidence:
    """
    Attach each strict material witness to its actual unchanged measurement pose.
    """

    route: FoldRoute
    witness: Penetration


def constraints(
    model: SignedJoints,
    anchor: FoldRoute,
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
) -> tuple[Callable[[tuple[float, ...]], float], ...] | None:
    """
    Share complete physical guidance between fixed and orientation-eliminated coordinates.

    Keep source-mating whole-member protection and supplement its opposite flat
    so a constant touching cap cannot hide impending return motion. Both count
    toward the original thirteen rows; over-capacity preparation declines whole.
    These inequalities guide motion and never replace final physical proofs.
    """
    if model.original.targets != anchor.targets or hardware.targets != anchor.targets:
        raise ValueError("Constraint preparation must retain the same original targets")
    initial = model.initial
    inequalities: list[Callable[[tuple[float, ...]], float]] = []
    minimum = minimum_coordinate(minimum_straight_mm, model.scale)
    if minimum is None:
        return None
    floor = float(minimum)
    for index in model.straight_indices:
        if initial[index] > 0 and model.bounds(index)[0] < floor:
            inequalities.append(lambda coordinates, i=index: floor - coordinates[i])
    planes = []
    for observed in features:
        plane = FeaturePlane.create(
            model,
            observed.route,
            observed.report,
            hardware,
            initial,
            coverage=FeatureCoverage.ADJOINING_INTERNAL,
        )
        if plane is None:
            return None
        planes.extend(member_planes([plane], model, initial))
    for plane in planes:
        inequalities.append(HardwareRow(plane))
    anchor_model = StraightSlots(anchor)
    protections = prepare(anchor_model, hardware, planes, ledger.checkpoint)
    rebound = tuple(
        Protection(
            replace(protection.plane, model=model),
            protection.minimum_gap * anchor_model.scale / model.scale,
            protection.basis,
        )
        for protection in protections
    )
    inequalities.extend(rebound)
    inequalities.extend(
        phase for protection in rebound if (phase := MatingPhase.create(protection)) is not None
    )
    for observed in material:
        constraint = FlatSeparation.create(
            model,
            observed.route,
            observed.witness,
            extent=ProfileExtent.COMPLETE,
            axis_values=initial,
        )
        if constraint is None:
            return None
        inequalities.append(MaterialRow(constraint, model.scale))
    if not 1 <= len(inequalities) <= 13:
        return None
    return tuple(inequalities)


def allocate(
    source: FoldRoute,
    anchor: FoldRoute,
    material: tuple[MaterialEvidence, ...],
    features: tuple[FeatureEvidence, ...],
    hardware: Hardware,
    minimum_straight_mm: float,
    ledger: Ledger,
) -> FoldRoute | None:
    """
    Make one existing least-norm projection without minimizing total straight travel.

    Complete material regions, actual connector members, both terminal protections
    and existing-positive native floors share the original thirteen physical rows.
    Capacity or unsupported guidance declines without dropping evidence. Exact-zero
    source slots may absorb signed roundoff through the established bounded advance;
    existing positive material cannot disappear. All final proofs remain external.
    Terminal touch preferences derive from the closed pre-action anchor, not
    the positionally open algebraic factorization, and retain their physical gap
    when rebound to the working model's normalization.
    """
    if source.targets != anchor.targets:
        raise ValueError("A fixed-factor allocation must retain the anchor targets")
    model = StraightSlots(source)
    initial = model.initial
    residual = model.residual(initial)
    rows = [[0.0] * len(initial) for _ in range(6)]
    endpoint = model.pieces(initial)[-1].end_pose().origin
    for index in range(len(initial)):
        ledger.checkpoint()
        probe = list(initial)
        probe[index] += 1
        column = difference(model.pieces(tuple(probe))[-1].end_pose().origin, endpoint)
        for axis, value in enumerate((column.x, column.y, column.z)):
            rows[axis][index] = value / model.scale
    inequalities = constraints(
        model, anchor, material, features, hardware, minimum_straight_mm, ledger
    )
    if inequalities is None:
        return None
    for evaluate in inequalities:
        ledger.checkpoint()
        base = evaluate(initial)
        row = []
        for index in range(len(initial)):
            probe = list(initial)
            probe[index] += 1
            row.append(evaluate(tuple(probe)) - base)
        rows.append(row)
        residual += (base,)
    delta = active_step(model, initial, rows, residual, ledger.checkpoint)
    if delta is None:
        return None
    raw = tuple(a + b for a, b in zip(initial, delta))
    if any(
        value < 0 and (initial[i] != 0 or abs(value) > 2 * math.ulp(1.0))
        for i, value in enumerate(raw)
    ):
        return None
    delivered = advance(model, initial, delta, 1.0)
    if any(value <= 0 < old for old, value in zip(initial, delivered)):
        return None
    ledger.checkpoint()
    return model.route(delivered)
