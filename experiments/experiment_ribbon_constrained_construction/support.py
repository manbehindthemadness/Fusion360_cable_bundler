"""
Express conservative fixed-fold clearance bounds as affine construction inequalities.

Fixed fold angles, banks, radii and profiles leave each fold's occupied shape
unchanged as straight lengths vary. Its translation is affine in those lengths.
Support intervals therefore yield affine separation guidance. Existing interval
rounding margins depend on world translation; independently recompute physical
contact on a constructed route before accepting it. This adapter is not a proof.
Choosing the separation arrangement, straight-piece constraints and complete
contact qualification remain separate unfinished construction responsibilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_terminal_hardware.model import Box

from .linear import Row


@dataclass(frozen=True)
class Support:
    """
    Bound a whole fold's projection in millimeters over normalized straight coordinates.
    """

    low_mm: float
    high_mm: float
    translation_mm: tuple[float, ...]
    axis: Vector3


def fold_support(model: Model, ordinal: int, axis: Vector3) -> Support:
    """
    Derive whole-profile support without sampling collision points or moving either target.

    The direction is an explicitly selected unit separation axis. Original fold
    bounds include complete width and thickness. Straight coordinates use the
    existing diameter normalization; radius-growth coordinates remain zero.
    """
    if type(ordinal) is not int or not 0 <= ordinal < len(model.topology.folds):
        raise ValueError("Use an existing zero-based fold ordinal")
    if (
        any(not math.isfinite(v) for v in (axis.x, axis.y, axis.z))
        or abs(magnitude(axis) - 1) > 1e-10
    ):
        raise ValueError("Separation axes must be finite unit vectors")
    count = len(model.topology.folds) + 1
    values = tuple(float(i % 2 == 0) for i in range(model.size))

    def placed(coordinates: tuple[float, ...]) -> PlacedPiece:
        """
        Resolve fold identity independently of vanishing straight-slot indices.
        """
        return tuple(
            piece
            for piece in model.pieces(coordinates)
            if isinstance(piece.geometry, CylindricalFold)
        )[ordinal]

    piece = placed(values)
    cell = Cell(
        0,
        Span(0, 1),
        Span(-model.source.half_width_mm, model.source.half_width_mm),
        Span(-model.source.targets.diameter_mm / 2, model.source.targets.diameter_mm / 2),
    )
    bound = projection(piece, cell, axis)
    coefficients = []
    for i in range(count):
        changed = list(values)
        changed[2 * i] += 1
        coefficients.append(
            dot(difference(placed(tuple(changed)).pose.origin, piece.pose.origin), axis)
        )
    base = math.fsum(coefficients)
    return Support(bound.low - base, bound.high - base, tuple(coefficients), axis)


def separated(first: Support, second: Support, *, minimum_gap_mm: float = 0.0) -> Row:
    """
    Require the second complete fold interval to follow the first on the shared axis.

    This fixes one ordered separation arrangement, not a claim that other
    arrangements or bend branches are impossible. Units remain millimeters.
    """
    if (
        len(first.translation_mm) != len(second.translation_mm)
        or first.axis != second.axis
        or type(minimum_gap_mm) not in (int, float)
        or not math.isfinite(minimum_gap_mm)
        or minimum_gap_mm < 0
    ):
        raise ValueError("Use matching supports and a nonnegative finite gap")
    return Row(
        "ordered occupied-fold separation",
        tuple(b - a for a, b in zip(first.translation_mm, second.translation_mm)),
        first.high_mm - second.low_mm + minimum_gap_mm,
    )


def outside_box(support: Support, box: Box) -> tuple[Row, Row]:
    """
    Return the two alternative separating sides along the supplied support axis.

    Either row guides this fold/box separation. They are alternatives,
    never a conjunction, and failure of both leaves other axes/curved regions open.
    Use the axis retained with the support, preventing mismatched projections.
    """
    corners = tuple(dot(point, support.axis) for point in box.corners())
    return (
        Row(
            "fold before hardware",
            tuple(-c for c in support.translation_mm),
            support.high_mm - min(corners),
        ),
        Row("fold after hardware", support.translation_mm, max(corners) - support.low_mm),
    )
