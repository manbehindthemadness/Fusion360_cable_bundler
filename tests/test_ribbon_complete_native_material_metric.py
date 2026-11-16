"""
Check continuous increment bounds, noncancelling coverage and source-owned reuse.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.basis import Basis
from experiments.experiment_ribbon_complete.native_material_chart import bind
from experiments.experiment_ribbon_complete.native_material_metric import (
    enclose,
    enclose_trunk_chain,
    increment_upper,
)
from experiments.experiment_ribbon_complete.volume_boundary import RationalBoundaryResidual
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_native_material_chart import snapshot
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def residual(values: tuple[Fraction, ...]) -> RationalBoundaryResidual:
    """
    Retain a simple exact scalar error field in X with constant positive denominator.
    """
    return RationalBoundaryResidual(
        tuple(((value, Fraction(0), Fraction(0)),) * 5 for value in values), (Fraction(1),) * 5
    )


def test_constant_translation_has_position_error_but_no_increment_error() -> None:
    """
    Offset fields do not acquire fictitious strain from their absolute displacement.
    """
    error = residual((Fraction(1, 200),) * 6)
    assert error.position_upper_mm == Fraction(1, 200)
    assert increment_upper(error, Basis((Fraction(0), Fraction(1))), checkpoint) == Fraction(0)


def test_small_position_and_matching_endpoints_cannot_hide_longitudinal_variation() -> None:
    """
    A noncancelling bound sees intermediate oscillation that endpoint subtraction erases.
    """
    values = tuple(Fraction(x, 1000) for x in (0, 4, -4, 4, -4, 0))
    error = residual(values)
    assert error.position_upper_mm < Fraction(1, 100) and values[0] == values[-1]
    actual_bound = increment_upper(error, Basis((Fraction(0), Fraction(1))), checkpoint)
    assert actual_bound == sum(abs(b - a) for a, b in zip(values, values[1:]))
    assert actual_bound > Fraction(1, 100)


def test_bound_is_invariant_to_nonuniform_knot_spacing_and_shared_parameter_scale() -> None:
    """
    The derivative/integral knot factors cancel rather than charging a fresh station allowance.
    """
    first = Basis(tuple(Fraction(i, 4) for i in range(5)))
    second = Basis((Fraction(0), Fraction(1, 1000), Fraction(1, 50), Fraction(1, 2), Fraction(1)))
    values = tuple(Fraction((-1) ** i, 1000) for i in range(first.count))
    error = residual(values)
    assert increment_upper(error, first, checkpoint) == increment_upper(error, second, checkpoint)
    with pytest.raises(ValueError, match="SAME complete global"):
        increment_upper(error, Basis((Fraction(0), Fraction(1))), checkpoint)


def test_native_chart_ownership_translation_and_missing_coverage_remain_explicit() -> None:
    """
    Source replacement cannot reuse old controls, and missing flat charts cannot count as zero.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    arc = material_profile(2, 0.75)[0]
    chart = bind(volume, arc, native, 0, native.revision, checkpoint)
    measured = enclose(chart, checkpoint)
    translated_rows = tuple(
        tuple((p[0] + Fraction(1, 10000), p[1], p[2]) for p in row) for row in native.rows
    )
    shifted = bind(
        volume, arc, replace(native, rows=translated_rows), 0, native.revision, checkpoint
    )
    assert enclose(shifted, checkpoint).upper_mm == measured.upper_mm
    with pytest.raises(ValueError, match="SAME original source"):
        replace(chart, native=replace(native))
    partial = enclose_trunk_chain(
        ((0, "before"), (0, "bend"), (0, "after")),
        (measured,),
        arc.label,
        native.revision,
        checkpoint,
    )
    assert partial.missing_regions == ((0, "before"), (0, "after"))
    assert (
        partial.complete_trunk_upper_mm is None and partial.measured_upper_mm == measured.upper_mm
    )
    assert partial.status == "unresolved_missing_trunk_regions"
    complete = enclose_trunk_chain(
        ((0, "bend"),), (measured,), arc.label, native.revision, checkpoint
    )
    assert complete.complete_trunk_upper_mm == measured.upper_mm
    with pytest.raises(ValueError, match="exactly once"):
        enclose_trunk_chain(
            ((0, "bend"),), (measured, measured), arc.label, native.revision, checkpoint
        )
    with pytest.raises(ValueError, match="exactly once"):
        enclose_trunk_chain(((0, "bend"),), (measured,), arc.label, "wrong-revision", checkpoint)


def test_resource_stop_is_checked_during_control_variation() -> None:
    """
    A proof cannot complete after a caller stop inside its finite coefficient traversal.
    """
    calls = 0

    def stop() -> None:
        """
        Stop after entering the shared allocation and beginning its first control pair.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        increment_upper(residual((Fraction(0),) * 6), Basis((Fraction(0), Fraction(1))), stop)
