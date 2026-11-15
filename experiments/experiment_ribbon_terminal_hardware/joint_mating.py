"""
Restore actual mating precision on a retained native-ready joint state without new material slots.
"""

from __future__ import annotations

import math
from typing import Callable

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.straight_closure import (
    SourceReadiness as SourceReadiness,
)
from experiments.experiment_ribbon_fold_route.straight_closure import correction

from .feature_plane import SignedJoints
from .joint_completion import oriented_material_ready, stalled_certificate_ready
from .joint_mating_native import at_floor, project


def restore(
    route: FoldRoute,
    model: SignedJoints,
    values: tuple[float, ...],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    minimum_straight_mm: float,
    length_ceiling_mm: float | None,
    fixed: frozenset[int],
    readiness: SourceReadiness = SourceReadiness.FINAL_SHAPE,
) -> tuple[float, ...] | None:
    """
    Apply one shared fixed-fold correction to exact current occupied joint slots only.

    The caller must debit one remaining correction before entry and prevent
    later motion once final certification is requested. Coordinates, targets
    and placement must agree exactly. Permanent native pins remain fixed;
    bounds, material identity, native sizes and the original length policy hold.
    Angles/banks/radii are never changed. An already active native floor selects
    the existing bounded linear kernel before projection; other poses retain
    the affine kernel. No root, zero-face or alternate projection attempt follows
    a decline. Only actual strict mating after recomposition
    supplies restored coordinates; all physical certificates remain separate.
    Explicit oriented-material entry removes only the source positional
    readiness assumption. It retains native/material/orientation eligibility,
    one original linear kernel and the same strict final cap certification.
    """
    checkpoint()
    if not isinstance(readiness, SourceReadiness):
        raise ValueError("Select explicit mating source readiness")
    if not model.admissible(values):
        return None
    if any(type(i) is not int or not 0 <= i < len(values) for i in fixed):
        raise ValueError("Fix only existing joint coordinates")
    placed = model.route(values)
    if (
        placed is None
        or placed.targets != route.targets
        or placed.pieces != route.pieces
        or placed.radius_mm != route.radius_mm
    ):
        raise ValueError("Mating restoration requires the exact current joint placement")
    if len(residual) < 6 or any(not math.isfinite(term) for term in residual):
        return None
    source_ready = (
        stalled_certificate_ready(
            route,
            model,
            residual,
            minimum_straight_mm=minimum_straight_mm,
            length_ceiling_mm=length_ceiling_mm,
        )
        if readiness is SourceReadiness.FINAL_SHAPE
        else oriented_material_ready(
            route,
            model,
            minimum_straight_mm=minimum_straight_mm,
            length_ceiling_mm=length_ceiling_mm,
        )
    )
    if not source_ready:
        return None
    indices = model.straight_indices
    if any(0 < values[i] * model.scale <= max(1e-12, minimum_straight_mm) for i in indices):
        return None
    if ordered_mating_caps(route.pieces, route.targets):
        return values
    if at_floor(model, values, minimum_straight_mm):
        coordinates = project(
            route,
            model,
            values,
            checkpoint,
            minimum_mm=minimum_straight_mm,
            fixed=fixed,
            readiness=readiness,
        )
        if coordinates is None:
            return None
    else:
        delta = correction(
            route.pieces,
            route.targets,
            tuple(values[i] * model.scale for i in indices),
            checkpoint,
            fixed_slots=frozenset(slot for slot, i in enumerate(indices) if i in fixed),
            readiness=readiness,
        )
        if delta is None:
            return None
        proposed = list(values)
        for index, change in zip(indices, delta):
            proposed[index] += change / model.scale
        coordinates = tuple(proposed)
    checkpoint()
    if (
        any(coordinates[i] != values[i] for i in fixed)
        or any(
            (
                coordinates[i] != 0
                if values[i] == 0
                else coordinates[i] * model.scale <= minimum_straight_mm
            )
            for i in indices
        )
        or not model.admissible(coordinates)
    ):
        return None
    candidate = model.route(coordinates)
    if candidate is None:
        return None
    ready = stalled_certificate_ready(
        candidate,
        model,
        residual,
        minimum_straight_mm=minimum_straight_mm,
        length_ceiling_mm=length_ceiling_mm,
    )
    closed = ordered_mating_caps(candidate.pieces, candidate.targets)
    checkpoint()
    return coordinates if ready and closed else None
