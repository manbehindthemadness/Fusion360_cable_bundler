"""
Remove numerical straight slivers with bounded affine reclosure of the same ordered caps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_aesthetic.model import peak_curvature
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.frames import Topology

SLIVER_MM = 1e-7


@dataclass(frozen=True)
class Cleanup:
    """
    Preserve unresolved cleanup explicitly instead of publishing the original failing sliver.
    """

    route: FoldRoute | None
    status: str
    removed_lengths_mm: tuple[float, ...] = ()
    projections: int = 0


def _project(
    model: Model,
    initial: tuple[float, ...],
    tiny: tuple[int, ...],
    maximum_length_mm: float,
    checkpoint: Callable[[], None],
) -> tuple[FoldRoute | None, int]:
    """
    Solve XYZ closure and, if necessary, the original length ceiling with finite active sets.

    Radius coordinates are nonnegative growth above the original radii. Only
    existing positive straight slots remain free; removed/absent slots stay zero.
    At most two passes of size+1 projections are allowed; no routing search runs.
    """
    values = tuple(0.0 if i in tiny else v for i, v in enumerate(initial))
    columns, target = model.equations()
    right = [
        target[a] - math.fsum(columns[i][a] * v for i, v in enumerate(values)) for a in range(3)
    ]
    costs = [
        1.0
        if i % 2 == 0
        else abs(model.topology.folds[i // 2].angle_radians)
        / math.cos(model.topology.folds[i // 2].bank_radians)
        for i in range(model.size)
    ]
    rows = [[column[a] for column in columns] for a in range(3)]
    free = [i for i in range(model.size) if i % 2 or values[i] > 0]
    projections = 0
    for length_active in (False, True):
        active = list(free)
        trial_rows, trial_right = list(rows), list(right)
        if length_active:
            trial_rows.append(costs)
            trial_right.append(
                math.fsum(costs[i] * (initial[i] - values[i]) for i in range(model.size))
            )
        for _ in range(model.size + 1):
            checkpoint()
            projections += 1
            delta = affine_projection(
                [[row[i] for i in active] for row in trial_rows],
                trial_right,
                [0.0] * len(active),
            )
            if delta is None:
                break
            blocked = [i for i, d in zip(active, delta) if values[i] + d < 0]
            if blocked:
                active = [i for i in active if i not in blocked]
                continue
            trial = list(values)
            for i, d in zip(active, delta):
                trial[i] += d
            pieces = model.pieces(tuple(trial))
            if not pieces:
                break
            candidate = FoldRoute(model.source.targets, pieces, model.source.radius_mm)
            if (
                candidate.material_length_mm
                <= maximum_length_mm + 1e-8 * model.source.targets.diameter_mm
            ):
                return candidate, projections
            break
    return None, projections


def remove_slivers(source: FoldRoute, checkpoint: Callable[[], None]) -> Cleanup:
    """
    Reclose sub-closure-tolerance straight slots without tightening bends or moving target poses.

    This user-approved numerical cleanup slightly changes the planned route; it
    is not an exact material-map resegmentation or a repair to a native solid.
    Angles/banks/order/profile stay fixed and radii may only grow. Contact and
    material checks remain mandatory in the caller. Routes needing no cleanup
    retain their original object, with no projections or extra contact work.
    """
    if not any(
        isinstance(p.geometry, Straight) and p.geometry.material_length_mm <= SLIVER_MM
        for p in source.pieces
    ):
        return Cleanup(source, "not_needed")
    folds = tuple(p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold))
    if len(folds) > 6:
        return Cleanup(None, "unsupported_fold_budget")
    model = Model(source, Topology("numerical-sliver-cleanup", folds, 0))
    initial = [0.0] * model.size
    index = 0
    for piece in source.pieces:
        if isinstance(piece.geometry, Straight):
            initial[2 * index] += piece.geometry.material_length_mm / source.targets.diameter_mm
        else:
            index += 1
    tiny = tuple(
        i
        for i in range(0, model.size, 2)
        if 0 < initial[i] * source.targets.diameter_mm <= SLIVER_MM
    )
    if not tiny:
        return Cleanup(source, "not_needed")
    removed = tuple(initial[i] * source.targets.diameter_mm for i in tiny)
    candidate, projections = _project(
        model, tuple(initial), tiny, source.material_length_mm, checkpoint
    )
    if candidate is None:
        return Cleanup(None, "closure_unresolved", removed, projections)
    if (
        cap_error(candidate) > 1e-7
        or peak_curvature(candidate) > peak_curvature(source) + 1e-10 / source.targets.diameter_mm
        or any(
            isinstance(p.geometry, Straight) and p.geometry.material_length_mm <= SLIVER_MM
            for p in candidate.pieces
        )
    ):
        return Cleanup(None, "numerical_gate_rejected", removed, projections)
    return Cleanup(candidate, "removed_and_reclosed", removed, projections)
