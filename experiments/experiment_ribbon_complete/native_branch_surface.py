"""
Translate exact homogeneous branch tensors to transient native rational surfaces.

All weights remain independent in both tensor directions. This creates surface
geometry only, not a trimmed face, closed solid or accepted material structure.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction
from typing import Any

from cable_bundler.routing.geometry import Vector3

from .spatial_transition import Net


class UnsupportedNativeSurface(ValueError):
    """
    Report an unavailable accurate native encoding, never physical input infeasibility.
    """


@dataclass(frozen=True)
class NativeSurfaceGrid:
    """
    Retain an exact source grid and its bounded binary native encoding.

    Controls use millimetre homogeneous coordinates (wx, wy, wz, w). Native
    points are Cartesian centimetres, with one independent weight per point.
    U is the outer row index and V varies fastest. Encoding bounds apply over
    the complete tensor under the positive clamped Bernstein basis premise.
    """

    rows: Net
    checkpoint: InitVar[Callable[[], None]]
    points_cm: tuple[Vector3, ...] = field(init=False)
    weights: tuple[float, ...] = field(init=False)
    distance_upper_mm: Fraction = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Validate every control and bound dehomogenization and weight conversion once.

        Let D bound native Cartesian control error, R enclose source controls
        around the first control, e bound each weight error, and m be the least
        native weight. Convexity and the rational quotient identity give the
        full-surface L1 bound D + 2*R*e/m, also an Euclidean distance bound.
        Translation is removed from R, preventing a large world origin from
        unnecessarily inflating the weight-error term. No fitting is performed.
        """
        checkpoint()
        if (
            not isinstance(self.rows, tuple)
            or len(self.rows) < 2
            or not isinstance(self.rows[0], tuple)
            or len(self.rows[0]) < 2
        ):
            raise ValueError("A rectangular exact tensor with positive degrees is required")
        count_v = len(self.rows[0])
        points, weights, exact = [], [], []
        point_error, weight_error = Fraction(0), Fraction(0)
        for row in self.rows:
            checkpoint()
            if not isinstance(row, tuple) or len(row) != count_v:
                raise ValueError("A rectangular exact tensor is required")
            for control in row:
                checkpoint()
                if (
                    not isinstance(control, tuple)
                    or len(control) != 4
                    or any(type(value) is not Fraction for value in control)
                    or control[3] <= 0
                ):
                    raise ValueError("Exact homogeneous controls and positive weights required")
                position = tuple(control[k] / control[3] for k in range(3))
                try:
                    point = Vector3(*(float(value / 10) for value in position))
                    weight = float(control[3])
                except OverflowError as error:
                    raise UnsupportedNativeSurface("Native control conversion overflows") from error
                if (
                    not all(math.isfinite(value) for value in (point.x, point.y, point.z, weight))
                    or weight <= 0
                ):
                    raise UnsupportedNativeSurface(
                        "Finite native controls and positive weights required"
                    )
                encoded = (Fraction(point.x) * 10, Fraction(point.y) * 10, Fraction(point.z) * 10)
                point_error = max(
                    point_error, sum((abs(a - b) for a, b in zip(encoded, position)), Fraction(0))
                )
                weight_error = max(weight_error, abs(Fraction(weight) - control[3]))
                points.append(point)
                weights.append(weight)
                exact.append(position)
        radius = max(
            sum((abs(a - b) for a, b in zip(position, exact[0])), Fraction(0)) for position in exact
        )
        bound = point_error + 2 * radius * weight_error / min(Fraction(w) for w in weights)
        if bound > Fraction(1, 100):
            raise UnsupportedNativeSurface("Native encoding does not establish 0.01mm accuracy")
        object.__setattr__(self, "points_cm", tuple(points))
        object.__setattr__(self, "weights", tuple(weights))
        object.__setattr__(self, "distance_upper_mm", bound)
        checkpoint()


def create(grid: NativeSurfaceGrid, checkpoint: Callable[[], None]) -> Any:
    """
    Create one transient Fusion surface with the complete original weight grid.

    Fusion supplies adsk; importing this module alone remains host independent.
    This does not mutate a document or infer face orientation/trim topology.
    SDK refusal propagates without a lower-degree, separable-weight or sweep
    fallback. The caller owns resource checks and native provenance receipts.
    """
    checkpoint()
    # noinspection PyUnresolvedReferences
    import adsk.core

    count_u, count_v = len(grid.rows), len(grid.rows[0])
    points = []
    for point in grid.points_cm:
        checkpoint()
        points.append(adsk.core.Point3D.create(point.x, point.y, point.z))
    properties = (
        adsk.core.NurbsSurfaceProperties.OpenNurbsSurface
        | adsk.core.NurbsSurfaceProperties.RationalNurbsSurface
    )
    checkpoint()
    surface = adsk.core.NurbsSurface.create(
        count_u - 1,
        count_v - 1,
        count_u,
        count_v,
        points,
        [0.0] * count_u + [1.0] * count_u,
        [0.0] * count_v + [1.0] * count_v,
        list(grid.weights),
        properties,
        properties,
    )
    if surface is None:
        raise RuntimeError("Native branch surface creation failed")
    checkpoint()
    return surface
