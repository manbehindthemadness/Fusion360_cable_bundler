"""
Check native derivative units, split boundary order and unresolved domain extrapolation.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_material_chart import NativeSurfaceSnapshot
from experiments.experiment_ribbon_complete.native_trim_boundary import (
    NativeTrimCurve,
    derivative_bounds,
    inspect_rectangle,
)
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def surface(scale_u: int = 1, scale_v: int = 1) -> NativeSurfaceSnapshot:
    """
    Keep an exact affine native surface X=(scale_u*U,scale_v*V,0) in a quintic/quadratic basis.
    """
    return NativeSurfaceSnapshot(
        "revision",
        0,
        0,
        "profile",
        5,
        2,
        (Fraction(0),) * 6 + (Fraction(1),) * 6,
        (Fraction(0),) * 3 + (Fraction(1),) * 3,
        tuple(
            tuple(
                (Fraction(scale_u * i, 5), Fraction(scale_v * j, 2), Fraction(0)) for j in range(3)
            )
            for i in range(6)
        ),
        ((Fraction(1),) * 3,) * 6,
    )


def rectangle() -> tuple[NativeTrimCurve, ...]:
    """
    Retain a split right side without counting its pieces as additional faces or domains.
    """
    vertices = ((0, 0), (1, 0), (1, Fraction(1, 2)), (1, 1), (0, 1), (0, 0))
    return tuple(
        NativeTrimCurve(
            i,
            ((Fraction(a[0]), Fraction(a[1])), (Fraction(b[0]), Fraction(b[1]))),
            (Fraction(1),) * 2,
        )
        for i, (a, b) in enumerate(zip(vertices, vertices[1:]))
    )


def test_derivatives_use_world_units_instead_of_equating_uv_with_millimeters() -> None:
    """
    Exact linear maps expose independent longitudinal and transverse scaling.
    """
    assert derivative_bounds(surface(2, 3), checkpoint) == (Fraction(2), Fraction(3))


def test_rational_profile_derivative_bounds_cover_independent_quotient_evaluation() -> None:
    """
    Nonconstant weights retain the quotient derivative instead of using ordinary control differences.
    """
    native = replace(surface(), weights=((Fraction(1), Fraction(1, 2), Fraction(1)),) * 6)
    along, across = derivative_bounds(native, checkpoint)
    assert along == Fraction(1) and Fraction(4, 3) <= across <= Fraction(4)
    for i in range(11):
        t = Fraction(i, 10)
        numerator, denominator = (t + t * t) / 2, 1 - t + t * t
        speed = abs(
            ((Fraction(1, 2) + t) * denominator - numerator * (-1 + 2 * t)) / denominator**2
        )
        assert speed <= across


@pytest.mark.parametrize("reverse", (False, True))
def test_split_sides_preserve_cyclic_boundary_order_in_both_directions(reverse: bool) -> None:
    """
    Splits and winding direction do not invent a gap or change original side identity.
    """
    curves = rectangle()
    if reverse:
        curves = tuple(replace(c, controls=tuple(reversed(c.controls))) for c in reversed(curves))
    bound = inspect_rectangle(surface(), curves, checkpoint)
    assert bound.ordered_sides and bound.controls_inside_parameter_domain
    assert bound.boundary_upper_mm == bound.endpoint_gap_upper_mm == Fraction(0)
    assert bound.status == "within_parameter_boundary_accuracy"


def test_small_parameter_gap_does_not_waive_extrapolation_or_trim_coverage() -> None:
    """
    A tiny out-of-domain trace is retained even when its scaled discrepancy is acceptable.
    """
    curves = rectangle()
    shifted = replace(
        curves[0], controls=((Fraction(0), -Fraction(1, 1000)), (Fraction(1), -Fraction(1, 1000)))
    )
    bound = inspect_rectangle(surface(2, 3), (shifted,) + curves[1:], checkpoint)
    assert bound.boundary_upper_mm == Fraction(3, 1000)
    assert not bound.controls_inside_parameter_domain
    assert bound.status == "within_parameter_boundary_accuracy"


def test_bowed_trace_is_bounded_between_endpoints_and_wrong_order_stays_unresolved() -> None:
    """
    Interior controls expose a bowed edge despite matching corners; reordered edges cannot pass.
    """
    curves = rectangle()
    bowed = replace(
        curves[0],
        controls=(
            (Fraction(0), Fraction(0)),
            (Fraction(1, 2), Fraction(1, 20)),
            (Fraction(1), Fraction(0)),
        ),
        weights=(Fraction(1),) * 3,
    )
    bound = inspect_rectangle(surface(), (bowed,) + curves[1:], checkpoint)
    assert bound.boundary_upper_mm >= Fraction(1, 20)
    assert bound.status == "unresolved_parameter_boundary_accuracy"
    wrong = inspect_rectangle(
        surface(), (curves[0], curves[3], curves[1], curves[2], curves[4]), checkpoint
    )
    assert not wrong.ordered_sides and wrong.status == "unresolved_parameter_boundary_accuracy"


def test_foreign_weight_rows_and_duplicate_edges_cannot_receive_a_receipt() -> None:
    """
    The derivative proof's shared denominator and original-loop identity are required.
    """
    native = surface()
    with pytest.raises(ValueError, match="SAME positive"):
        derivative_bounds(
            replace(native, weights=((Fraction(2),) * 3,) + native.weights[1:]), checkpoint
        )
    with pytest.raises(ValueError, match="unique native edges"):
        inspect_rectangle(native, rectangle() + rectangle()[:1], checkpoint)
