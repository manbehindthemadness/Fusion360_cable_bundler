"""
Compare actual native ending supports with their unchanged rational source tensors.

The capture adapter must bind each observation to its original body and face.
These bounds cover surface positions on the full parameter rectangle, not trim
coverage, derivatives, material metrics, junction flow or contact.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .native_branch_surface import NativeSurfaceGrid
from .native_material_chart import NativeSurfaceSnapshot


@dataclass(frozen=True)
class EndingSurfaceBound:
    """
    Retain a positional upper bound or an explicit unsupported correspondence.
    """

    status: str
    upper_mm: Fraction | None


def compare(
    original: NativeSurfaceGrid,
    actual: NativeSurfaceSnapshot,
    checkpoint: Callable[[], None],
) -> EndingSurfaceBound:
    """
    Bound source-to-native positions when complete bases and normalized weights agree.

    Under identical nonnegative rational basis functions, the largest Cartesian
    control L1 difference bounds the entire native-to-encoded support distance.
    Add the original exact-to-encoded bound once. A common positive weight scale
    is immaterial; any other weight or knot change remains unresolved. There is
    no fitting, parameter remapping, sampling or tolerance accumulation.
    """
    checkpoint()
    count_u, count_v = len(original.rows), len(original.rows[0])
    if (
        actual.degree_u != count_u - 1
        or actual.degree_v != count_v - 1
        or len(actual.rows) != count_u
        or len(actual.rows[0]) != count_v
        or actual.knots_u != (Fraction(0),) * count_u + (Fraction(1),) * count_u
        or actual.knots_v != (Fraction(0),) * count_v + (Fraction(1),) * count_v
    ):
        return EndingSurfaceBound("unresolved_native_basis", None)
    weights = tuple(value for row in actual.weights for value in row)
    encoded = tuple(Fraction(value) for value in original.weights)
    if any(a * encoded[0] != b * weights[0] for a, b in zip(weights, encoded)):
        return EndingSurfaceBound("unresolved_native_weights", None)
    distance = Fraction(0)
    points = tuple(point for row in actual.rows for point in row)
    for native, control in zip(points, original.points_cm):
        checkpoint()
        error = sum(
            (
                abs(value - Fraction(getattr(control, axis)) * 10)
                for value, axis in zip(native, "xyz")
            ),
            Fraction(0),
        )
        distance = max(distance, error)
    upper = distance + original.distance_upper_mm
    return EndingSurfaceBound(
        "within_0.01mm_position_bound"
        if upper <= Fraction(1, 100)
        else "unresolved_position_bound",
        upper,
    )
