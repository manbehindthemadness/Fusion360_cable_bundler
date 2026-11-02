"""
Canonicalize sub-tolerance straight connectors before native construction, preserving hard gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_aesthetic.model import peak_curvature
from experiments.experiment_ribbon_bend_reduction.closure import close_lengths
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight, pose_error
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.frames import Topology


@dataclass(frozen=True)
class Policy:
    """
    Convert the live native point-comparison tolerance once, without tuning or a safety multiplier.
    """

    point_tolerance_cm: float

    def __post_init__(self) -> None:
        """
        Refuse invalid native tolerance data rather than guessing a threshold.
        """
        if not math.isfinite(self.point_tolerance_cm) or self.point_tolerance_cm <= 0:
            raise ValueError("Native point tolerance must be finite and positive")

    @property
    def threshold_mm(self) -> float:
        """
        Express Fusion's centimeter value in the numerical route's millimeters.
        """
        return self.point_tolerance_cm * 10


@dataclass(frozen=True)
class Result:
    """
    Publish changed geometry only after exact reclosure and fresh conservative contact acceptance.
    """

    route: FoldRoute | None
    status: str
    removed_lengths_mm: tuple[float, ...] = ()
    projections: int = 0
    reclosure_seconds: float = 0.0
    contact_seconds: float = 0.0
    contact_status: str = "unattempted"
    maximum_parameter_change_mm: float = 0.0
    length_change_mm: float = 0.0


def parameters(route: FoldRoute) -> tuple[float, ...]:
    """
    Retain absolute straight lengths and fold radii in shared physical millimeter slots.
    """
    values = [0.0]
    for piece in route.pieces:
        if isinstance(piece.geometry, Straight):
            values[-1] += piece.geometry.material_length_mm
        else:
            values.extend((piece.geometry.radius_mm, 0.0))
    return tuple(values)


def reclose(
    model: Model,
    initial: tuple[float, ...],
    tiny: tuple[int, ...],
    checkpoint: Callable[[], None],
) -> tuple[FoldRoute | None, int]:
    """
    Reuse complete bounded nonnegative affine projection with snapped/absent straights fixed zero.

    Public close_lengths enumerates at most1024active masks. Free coordinates are
    surviving existing straights and nonnegative radius growth, not new travel.
    The closest allocation is checked against parameter-change/material gates by the caller;
    no second objective or nonlinear correction is attempted when it fails.
    """
    free = tuple(i for i, value in enumerate(initial) if i % 2 or (value > 0 and i not in tiny))
    if len(free) > 10:
        return None, 0
    columns, right = model.equations()
    checkpoint()
    values = close_lengths(
        tuple(Vector3(*columns[i]) for i in free),
        Vector3(*right),
        tuple(initial[i] for i in free),
    )
    checkpoint()
    projections = 1 << len(free)
    if values is None:
        return None, projections
    allocation = [0.0] * model.size
    for index, value in zip(free, values):
        allocation[index] = value
    pieces = model.pieces(tuple(allocation))
    return (
        FoldRoute(model.source.targets, pieces, model.source.radius_mm) if pieces else None
    ), projections


def snap(source: FoldRoute, policy: Policy, checkpoint: Callable[[], None]) -> Result:
    """
    Fix all existing sub-tolerance straight allocations to zero and reclose once.

    Reuse public bounded nonnegative affine projection without changing the
    selected cleanup's threshold or executable policy. Angles, banks, fold order, target frames and
    profile stay fixed; radius growth is nonnegative. Absent and snapped straight
    slots stay zero. At most1024active masks and one1024-pair
    contact check run. No iterative cleanup, route search or native repair follows.
    A newly tiny connector, loss of closure, supra-tolerance parameter change or unresolved contact
    leaves this canonicalization unresolved; the original is not published as fixed.
    """
    checkpoint()
    started = perf_counter()
    if not any(
        isinstance(p.geometry, Straight) and p.geometry.material_length_mm <= policy.threshold_mm
        for p in source.pieces
    ):
        return Result(source, "not_needed", reclosure_seconds=perf_counter() - started)
    folds = tuple(p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold))
    if len(folds) > 6:
        return Result(None, "unsupported_fold_budget")
    model = Model(source, Topology("native-tolerance-zero-snap", folds, None))
    original_parameters = parameters(source)
    values = tuple(
        value / source.targets.diameter_mm if i % 2 == 0 else 0.0
        for i, value in enumerate(original_parameters)
    )
    tiny = tuple(
        i
        for i in range(0, model.size, 2)
        if 0 < values[i] * source.targets.diameter_mm <= policy.threshold_mm
    )
    removed = tuple(values[i] * source.targets.diameter_mm for i in tiny)
    candidate, projections = reclose(model, tuple(values), tiny, checkpoint)
    if candidate is None:
        return Result(None, "closure_unresolved", removed, projections, perf_counter() - started)
    change = max(abs(a - b) for a, b in zip(original_parameters, parameters(candidate)))
    length_change = candidate.material_length_mm - source.material_length_mm
    if (
        candidate.targets != source.targets
        or change > policy.threshold_mm
        or cap_error(candidate) > 1e-7
        or material_error(candidate) > 1e-10
        or peak_curvature(candidate) > peak_curvature(source) + 1e-10 / source.targets.diameter_mm
        or any(
            max(pose_error(a.end_pose(), b.pose)) > 1e-7
            for a, b in zip(candidate.pieces, candidate.pieces[1:])
        )
        or any(
            isinstance(p.geometry, Straight)
            and p.geometry.material_length_mm <= policy.threshold_mm
            for p in candidate.pieces
        )
    ):
        return Result(
            None,
            "numerical_gate_rejected",
            removed,
            projections,
            perf_counter() - started,
            maximum_parameter_change_mm=change,
            length_change_mm=length_change,
        )
    reclosure_seconds = perf_counter() - started
    contact_started = perf_counter()
    contact = inspect_contact(candidate, maximum_pairs=1024, checkpoint=checkpoint)
    contact_seconds = perf_counter() - contact_started
    return Result(
        candidate if contact.status == "separated" else None,
        "snapped_reclosed_and_separated"
        if contact.status == "separated"
        else "contact_" + contact.status,
        removed,
        projections,
        reclosure_seconds,
        contact_seconds,
        contact.status,
        change,
        length_change,
    )
