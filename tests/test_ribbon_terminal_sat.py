"""
Verify conservative diagonal hardware proofs without admitting real material intrusion.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from itertools import product

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_terminal_hardware.model import Box, Dimensions, Terminal
from experiments.experiment_ribbon_terminal_hardware.sat import (
    BoxProjection,
    separated_on_piece_axes,
)


def _box(angle: float = 0.0, offset: float = 0.0) -> Box:
    """
    Retain a finite slab solid with a rotated stored frame and configurable world translation.
    """
    return Box(
        Terminal.START,
        Pose(
            Vector3(offset, -offset / 3, offset / 7),
            Vector3(math.cos(angle), math.sin(angle), 0),
            Vector3(-math.sin(angle), math.cos(angle), 0),
        ),
        Dimensions(2.0, 2.0, 1.0),
    )


def _exact_slab_projection(box: Box, coordinates: tuple[float, ...], axis: Vector3) -> Decimal:
    """
    Independently solve the coordinate slab equations at80digits before projecting a corner.
    """
    with localcontext() as context:
        context.prec = 80
        matrix = [
            [Decimal.from_float(getattr(vector, key)) for key in "xyz"]
            + [Decimal.from_float(value)]
            for vector, value in zip(box.axes, coordinates)
        ]
        for index in range(3):
            pivot = max(range(index, 3), key=lambda row: abs(matrix[row][index]))
            matrix[index], matrix[pivot] = matrix[pivot], matrix[index]
            scale = matrix[index][index]
            matrix[index] = [value / scale for value in matrix[index]]
            for row in range(3):
                if row != index:
                    factor = matrix[row][index]
                    matrix[row] = [
                        value - factor * reference
                        for value, reference in zip(matrix[row], matrix[index])
                    ]
        return sum(
            (Decimal.from_float(getattr(box.pose.origin, key)) + matrix[index][-1])
            * Decimal.from_float(getattr(axis, key))
            for index, key in enumerate("xyz")
        )


@pytest.mark.parametrize("angle", (0.0, 0.37, 1.2))
@pytest.mark.parametrize("offset", (0.0, 1e8))
@pytest.mark.parametrize("axis", (Vector3(1, 0, 0), Vector3(-0.2, 0.7, 0.6)))
def test_box_projection_encloses_high_precision_inverse_slab_corners(
    angle: float, offset: float, axis: Vector3
) -> None:
    """
    Cover actual coordinate-defined slabs, including floating nonorthogonality and large translations.
    """
    box = _box(angle, offset)
    prepared = BoxProjection.create(box)
    assert prepared is not None
    span = prepared.span(axis)
    assert span is not None
    for coordinates in product(*((bound.low, bound.high) for bound in box.bounds)):
        exact = _exact_slab_projection(box, coordinates, axis)
        assert Decimal.from_float(span.low) <= exact <= Decimal.from_float(span.high)


def _diagonal(constant: float) -> tuple[PlacedPiece, Cell]:
    """
    Place a thin strip whose centerline has x+y equal to the supplied constant.
    """
    diagonal = math.sqrt(0.5)
    piece = PlacedPiece(
        Pose(
            Vector3(-1, constant + 1, 0),
            Vector3(diagonal, -diagonal, 0),
            Vector3(diagonal, diagonal, 0),
        ),
        Straight(5.0),
        "analytical diagonal",
    )
    return piece, Cell(0, Span(0, 1), Span(-0.45, 0.45), Span(-0.375, 0.375))


def test_diagonal_separation_proves_clearance_when_all_three_box_axes_overlap() -> None:
    """
    A known thin diagonal exterior strip needs its own width axis, without subdivision or tolerance.
    """
    box = _box()
    prepared = BoxProjection.create(box)
    assert prepared is not None
    piece, cell = _diagonal(2.0)
    for axis, bound in zip(box.axes, box.bounds):
        span = projection(piece, cell, axis)
        origin = dot(box.pose.origin, axis)
        assert span.low <= origin + bound.high and origin + bound.low <= span.high
    assert separated_on_piece_axes(piece, cell, prepared)


def test_a_real_interior_witness_can_never_receive_a_diagonal_separation_proof() -> None:
    """
    Retain material intrusion when an explicit strip-interior point lies inside every hardware slab.
    """
    box = _box()
    prepared = BoxProjection.create(box)
    assert prepared is not None
    piece, cell = _diagonal(1.0)
    point = piece.surface(math.sqrt(2) / 5, -0.25)[0]
    relative = difference(point, box.pose.origin)
    assert all(
        bound.low < dot(relative, axis) < bound.high for axis, bound in zip(box.axes, box.bounds)
    )
    assert not separated_on_piece_axes(piece, cell, prepared)


def test_touching_box_corner_is_not_relabelled_strictly_separated() -> None:
    """
    Outward enclosures retain boundary contact instead of adding a clearance acceptance margin.
    """
    prepared = BoxProjection.create(_box())
    assert prepared is not None
    piece, cell = _diagonal(1 + math.sqrt(2) * 0.45)
    assert not separated_on_piece_axes(piece, cell, prepared)


def test_additional_axes_preserve_caller_cancellation() -> None:
    """
    Stop supplemental proof work immediately rather than masking a caller resource failure.
    """
    prepared = BoxProjection.create(_box())
    assert prepared is not None
    piece, cell = _diagonal(2.0)

    def stop() -> None:
        """
        Represent an already exhausted caller allowance.
        """
        raise TimeoutError("caller limit")

    with pytest.raises(TimeoutError, match="caller limit"):
        separated_on_piece_axes(piece, cell, prepared, stop)


@pytest.mark.parametrize("value", (math.inf, -math.inf, math.nan))
def test_uncertain_axis_arithmetic_cannot_certify_clearance(value: float) -> None:
    """
    Decline nonfinite interval projections before interpreting their comparisons.
    """
    prepared = BoxProjection.create(_box())
    assert prepared is not None and prepared.span(Vector3(value, 1, 0)) is None
