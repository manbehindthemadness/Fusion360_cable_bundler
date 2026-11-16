"""
Compose exact homogeneous section tensors with unnormalized polynomial frame fields.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, elevate, multiply

from .spatial_frame import Components

Net = tuple[tuple[tuple[Fraction, ...], ...], ...]
Fields = tuple[Components, Components, Components]


def compose_fields(section: Net, fields: Fields, checkpoint: Callable[[], None]) -> Net:
    """
    Preserve C*w+W*q+N*b and positive weights at their complete product degree.

    All inputs use the same local interval. Restriction and global provenance
    belong to the caller; no normalization, interpolation or rounding occurs.
    """
    checkpoint()
    if (
        not section
        or any(len(row) != 3 for row in section)
        or any(
            len(point) != 3 or any(type(value) is not Fraction for value in point) or point[-1] <= 0
            for row in section
            for point in row
        )
        or len(fields) != 3
        or any(len(field) != 3 or not all(field) for field in fields)
        or any(type(value) is not Fraction for field in fields for axis in field for value in axis)
    ):
        raise ValueError("Exact positive-weight sections and complete raw frame fields required")
    center, width, thickness = fields
    degree = max(len(axis) for field in fields for axis in field) + len(section) - 2
    columns = []
    for v in range(3):
        checkpoint()
        q, b, weight = (tuple(row[v][k] for row in section) for k in range(3))
        xyz = tuple(
            elevate(
                add(
                    add(multiply(center[k], weight), multiply(width[k], q)),
                    multiply(thickness[k], b),
                ),
                degree,
            )
            for k in range(3)
        )
        columns.append(xyz + (elevate(weight, degree),))
    return tuple(
        tuple(tuple(columns[v][k][u] for k in range(4)) for v in range(3))
        for u in range(degree + 1)
    )
