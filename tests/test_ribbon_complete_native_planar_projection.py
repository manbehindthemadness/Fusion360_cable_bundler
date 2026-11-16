"""
Challenge global rational projection proofs with orientation, shear, nonuniform weights and an explicit repeated image.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_chart import certify
from experiments.experiment_ribbon_complete.flat_cut_domain import from_chart
from experiments.experiment_ribbon_complete.native_planar_projection import NativePlanarProjection
from tests.test_ribbon_complete_native_flat_embedding import chart
from tests.test_ribbon_complete_native_trim_boundary import surface
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_affine_shear_reversal_and_translation_preserve_original_projection_units() -> None:
    """
    The root preconditioner proves injectivity despite reversed native orientation and off-diagonal physical shear.
    """
    native = surface(2, 3)
    changed = replace(
        native,
        rows=tuple(
            tuple((x + 10**6, 5 * x - y - 10**6, z) for x, y, z in row) for row in native.rows
        ),
    )
    proof = NativePlanarProjection(changed, from_chart(certify(chart())), checkpoint)
    assert proof.status == "certified_global_native_sq_projection"
    assert proof.root_inverse is not None and proof.monotonicity_lower is not None
    assert proof.monotonicity_lower > 0 and proof.coefficient_matrices > 0
    rebound = replace(proof, surface=surface(3, 7), checkpoint=checkpoint)
    assert rebound.status == "certified_global_native_sq_projection"
    assert rebound.root_inverse != proof.root_inverse


def test_nonuniform_rational_projection_satisfies_independent_global_coercivity_checks() -> None:
    """
    A rational bilinear map with W=1+uv retains its nonlinear Jacobian instead of using a single derivative sample.
    """
    zero, one = Fraction(0), Fraction(1)
    base = surface()
    native = replace(
        base,
        degree_u=1,
        degree_v=1,
        knots_u=(zero, zero, one, one),
        knots_v=(zero, zero, one, one),
        rows=(((zero, zero, zero), (zero, one, zero)), ((one, zero, zero), (one, one, zero))),
        weights=((one, one), (one, Fraction(2))),
    )
    proof = NativePlanarProjection(native, from_chart(certify(chart())), checkpoint)
    assert proof.status == "certified_global_native_sq_projection"
    inverse = proof.root_inverse
    lower = proof.monotonicity_lower
    assert inverse is not None and lower is not None
    for first, second in (
        ((zero, zero), (one, one)),
        ((Fraction(1, 3), one), (one, Fraction(1, 4))),
        ((zero, one), (one, zero)),
    ):
        mapped = tuple(
            (u * (1 + v) / (1 + u * v), v * (1 + u) / (1 + u * v)) for u, v in (first, second)
        )
        difference = tuple(b - a for a, b in zip(*mapped))
        transformed = tuple(sum((a * b for a, b in zip(row, difference)), zero) for row in inverse)
        delta = tuple(b - a for a, b in zip(first, second))
        assert sum(a * b for a, b in zip(transformed, delta)) >= lower * sum(x * x for x in delta)


def test_nonsingular_center_does_not_certify_a_projection_with_two_identical_images() -> None:
    """
    A shifted complex-square projection has a regular center yet maps two distinct parameter points identically.
    """
    zero, one = Fraction(0), Fraction(1)
    x_square = Fraction(16, 25), Fraction(-24, 25), Fraction(36, 25)
    y_square = one, -one, one
    x = Fraction(-4, 5), Fraction(1, 5), Fraction(6, 5)
    y = -one, zero, one
    native = replace(
        surface(),
        degree_u=2,
        knots_u=(zero,) * 3 + (one,) * 3,
        rows=tuple(
            tuple((x_square[i] - y_square[j], 2 * x[i] * y[j], Fraction(i, 2)) for j in range(3))
            for i in range(3)
        ),
        weights=((one,) * 3,) * 3,
    )
    proof = NativePlanarProjection(native, from_chart(certify(chart())), checkpoint)
    assert proof.root_inverse is not None
    assert proof.status == "unresolved_global_native_sq_projection"
    assert proof.monotonicity_lower is None
    images = tuple(
        (u * u - v * v, 2 * u * v)
        for u, v in ((Fraction(-1, 2), Fraction(-1, 2)), (Fraction(1, 2), Fraction(1, 2)))
    )
    assert images[0] == images[1]


def test_unsupported_domains_and_stopped_allocations_cannot_gain_projection_receipts() -> None:
    """
    The whole-domain proof refuses nonclamped representations and preserves the caller's resource stop.
    """
    native = surface()
    frame = from_chart(certify(chart()))
    with pytest.raises(ValueError, match="single-span"):
        NativePlanarProjection(
            replace(native, knots_u=(Fraction(-1),) + native.knots_u[1:]), frame, checkpoint
        )

    def stop() -> None:
        """
        Refuse projection work once the shared allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativePlanarProjection(native, frame, stop)


def test_actual_projection_condition_is_not_hidden_by_the_root_preconditioner() -> None:
    """
    A highly anisotropic physical projection cannot pass its numerical condition gate merely because BG is the identity.
    """
    proof = NativePlanarProjection(surface(10**6, 1), from_chart(certify(chart())), checkpoint)
    assert proof.monotonicity_lower is not None and proof.monotonicity_lower > 0
    assert proof.condition_upper is not None and proof.condition_upper > 1024
    assert proof.status == "unresolved_global_native_sq_projection"
