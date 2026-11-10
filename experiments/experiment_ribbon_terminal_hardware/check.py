"""
Check full thick material against finite terminal proxies with conservative analytic enclosures.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Callable, Literal

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, prepare_projection
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy, cap_region
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height
from experiments.experiment_ribbon_fold_route.contact_profile import clip_profile
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Pose, pose_error

from .model import Box, Hardware, Terminal
from .sat import BoxProjection, separated_on_piece_axes
from .witness_height import occupied_height


class ProjectionPolicy(Enum):
    """
    Preserve guidance traversal or refine whole-cell separation for candidate certification.
    """

    BOX_AXES = "box_axes"
    PIECE_AXES = "piece_axes"


@dataclass(frozen=True)
class Witness:
    """
    Retain a point inside both the actual ribbon profile and the declared proxy envelope.
    """

    terminal: str
    piece: int
    material: tuple[float, float, float]
    point: Vector3
    box_coordinates: tuple[float, float, float]


@dataclass(frozen=True)
class Report:
    """
    Distinguish certified proxy clearance, demonstrated intrusion and incomplete measurement.
    """

    status: Literal["clear", "blocked", "unresolved"]
    cells_checked: int
    witness: Witness | None = None
    reason: str = ""


def _mating_frame(route: FoldRoute, box: Box) -> bool:
    """
    Compare immutable mating frames once; each material cell still needs its cap-side proof.
    """
    at_end = box.terminal is Terminal.END
    target = route.targets
    if not route.pieces:
        return False
    expected = (
        Pose(target.end, target.end_tangent, target.end_width)
        if at_end
        else Pose(target.start, target.start_tangent, target.start_width)
    )
    piece = route.pieces[-1 if at_end else 0]
    actual = piece.end_pose() if at_end else piece.pose
    return max(pose_error(actual, expected)) < 1e-10


def inspect(
    route: FoldRoute,
    hardware: Hardware,
    *,
    maximum_cells: int = 512,
    maximum_depth: int = 36,
    checkpoint: Callable[[], None] | None = None,
    projection_policy: ProjectionPolicy = ProjectionPolicy.BOX_AXES,
) -> Report:
    """
    Enclose every material region against both boxes; test strict interior witnesses before subdivision.

    The whole lobed profile and thickness are included. A centerline miss is not
    clearance. Only the intended mating face gets the existing analytic cap-side
    proof; later pieces can still collide with either box. Exhaustion stays
    unresolved. This is floating interval evidence, not a formal exact-arithmetic
    proof, actual-hardware fit certification or a native-body collision audit.
    Certification may explicitly allow whole cells unresolved by the three box axes to use fifteen
    box/piece SAT directions before subdivision. Additional axes use outward
    box enclosures, retain all material and share the same caller work limits.
    """
    if hardware.targets != route.targets:
        raise ValueError("Hardware and route must retain the same exact targets")
    if not isinstance(projection_policy, ProjectionPolicy):
        raise ValueError("An explicit terminal projection policy is required")
    if any(type(value) is not int or value < 1 for value in (maximum_cells, maximum_depth)):
        raise ValueError("Positive finite terminal-check budgets are required")
    thickness = route.targets.diameter_mm / 2
    if any(
        isinstance(piece.geometry, CylindricalFold) and piece.geometry.radius_mm <= thickness
        for piece in route.pieces
    ):
        return Report("unresolved", 0, reason="Material thickness map is not regular")
    checked = 0
    prepared = lru_cache(maxsize=64)(prepare_projection)
    prepared_boxes = lru_cache(maxsize=2)(BoxProjection.create)
    for box in hardware.boxes:
        matching = _mating_frame(route, box)
        at_end = box.terminal is Terminal.END
        mating_index = len(route.pieces) - 1 if at_end else 0
        axes, limits = box.axes, box.bounds
        origins = tuple(dot(box.pose.origin, axis) for axis in axes)
        pending = deque(
            Cell(
                index,
                Span(0, 1),
                Span(-route.half_width_mm, route.half_width_mm),
                Span(-thickness, thickness),
            )
            for index in reversed(range(len(route.pieces)))
        )
        while pending:
            if checkpoint is not None:
                checkpoint()
            if checked >= maximum_cells:
                return Report(
                    "unresolved", checked, reason="Terminal material-cell budget exhausted"
                )
            cell = pending.popleft()
            checked += 1
            cell = clip_profile(cell, route.targets.lines, route.targets.diameter_mm)
            if cell is None:
                continue
            piece = route.pieces[cell.piece]
            if (
                matching
                and cell.piece == mating_index
                and cap_region(piece, cell, at_end, CapPolicy.ANALYTIC_SUPPORT)
            ):
                continue
            separated = False
            for axis, origin, limit in zip(axes, origins, limits):
                span = prepared(piece, axis)(cell)
                if span.high < origin + limit.low or span.low > origin + limit.high:
                    separated = True
                    break
            if (
                not separated
                and cell.depth == 0
                and projection_policy is ProjectionPolicy.PIECE_AXES
            ):
                box_projection = prepared_boxes(box)
                if box_projection is not None:
                    separated = separated_on_piece_axes(piece, cell, box_projection, checkpoint)
            if separated:
                continue
            u, q = ((span.low + span.high) / 2 for span in (cell.u, cell.q))
            guard = 1e-9 * max(1.0, route.targets.diameter_mm)
            point, velocity, width, _ = piece.surface(u, q)
            normal = unit(cross(velocity, width))
            height = occupied_height(
                point,
                normal,
                q,
                cell.height,
                box,
                route.targets.lines,
                route.targets.diameter_mm,
            )
            if height is not None:
                point = point.translated(normal, height)
                relative = difference(point, box.pose.origin)
                coordinates = (
                    dot(relative, axes[0]),
                    dot(relative, axes[1]),
                    dot(relative, axes[2]),
                )
                if profile_height(q, route.targets.lines, route.targets.diameter_mm) - abs(
                    height
                ) > guard and all(
                    limit.low + guard < value < limit.high - guard
                    for value, limit in zip(coordinates, limits)
                ):
                    witness = Witness(
                        box.terminal.value, cell.piece, (u, q, height), point, coordinates
                    )
                    return Report(
                        "blocked",
                        checked,
                        witness,
                        "Ribbon interior enters terminal proxy clearance envelope",
                    )
            if cell.depth >= maximum_depth:
                return Report("unresolved", checked, reason="Terminal near-contact depth exhausted")
            pending.extend(cell.split(piece.geometry.material_length_mm))
    return Report("clear", checked, reason="Thick material clears both finite terminal envelopes")
