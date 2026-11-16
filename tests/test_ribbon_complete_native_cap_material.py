"""
Verify shared material labels under nonidentity native curve parameters and retained geometric uncertainty.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_cap_material import (
    MaterialCapSource,
    NativeCapCurve,
    bind,
)
from experiments.experiment_ribbon_complete.spatial_frame import restrict
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def sources() -> tuple[MaterialCapSource, MaterialCapSource]:
    """
    Keep two original regions with one unchanged rational material cap field.
    """
    profile = MaterialArc(((0, 0), (0.5, 1), (1, 0)), (1, 0.5, 1), "profile")
    controls = tuple((Fraction(0), Fraction(q), Fraction(b)) for q, b in profile.controls)
    first = MaterialCapSource((0, "straight"), profile, controls, Fraction(0), "frozen first")
    return first, replace(first, region=(1, "before"), source_tag="frozen second")


def native(interval: tuple[Fraction, Fraction], scale: Fraction) -> NativeCapCurve:
    """
    Independently author an exact restricted source image with an altered rational parameter speed.
    """
    source = sources()[0]
    axes = tuple(
        restrict(
            tuple(
                (p[k] if k < 3 else Fraction(1)) * Fraction(w)
                for p, w in zip(source.controls, source.profile.weights)
            ),
            *interval,
        )
        for k in range(4)
    )
    controls = tuple(tuple(axes[k][i] / axes[3][i] for k in range(3)) for i in range(3))
    weights = tuple(w * scale**i for i, w in enumerate(axes[3]))
    return NativeCapCurve("revision", 1, controls, weights)


@pytest.mark.parametrize("reverse", (False, True))
def test_nonidentity_parameter_and_subinterval_recover_one_shared_original_label(
    reverse: bool,
) -> None:
    """
    Positive projective changes preserve image and labels without treating native parameters as V.
    """
    interval = Fraction(1, 4), Fraction(3, 4)
    curve = native(interval, Fraction(3))
    if reverse:
        curve = replace(
            curve, controls=tuple(reversed(curve.controls)), weights=tuple(reversed(curve.weights))
        )
    result = bind(curve, sources(), interval, "revision", checkpoint)
    assert result.status == "qualified_shared_cap_material_parameter" and result.mapping is not None
    mapping = result.mapping
    assert mapping.reversed_native is reverse and mapping.projective_scale == Fraction(3)
    assert mapping.source_errors_upper_mm == (Fraction(0), Fraction(0))
    with pytest.raises(ValueError, match="SAME native"):
        replace(result, native=replace(curve))
    labels = [mapping.parameter(Fraction(i, 8)) for i in range(9)]
    assert labels[0] == interval[int(reverse)] and labels[-1] == interval[int(not reverse)]
    assert all((b < a if reverse else b > a) for a, b in zip(labels, labels[1:]))
    assert mapping.parameter(Fraction(1, 2)) == Fraction(5, 8)
    for i in range(9):
        z = Fraction(i, 8)
        v = mapping.parameter(z)
        assert mapping.native_coordinate(v) == z
        factors_native = tuple(
            w * b for w, b in zip(curve.weights, ((1 - z) ** 2, 2 * z * (1 - z), z * z))
        )
        factors_source = tuple(
            Fraction(w) * b
            for w, b in zip(sources()[0].profile.weights, ((1 - v) ** 2, 2 * v * (1 - v), v * v))
        )
        actual = tuple(
            sum((p[k] * w for p, w in zip(curve.controls, factors_native)), Fraction(0))
            / sum(factors_native)
            for k in range(3)
        )
        expected = tuple(
            sum((p[k] * w for p, w in zip(sources()[0].controls, factors_source)), Fraction(0))
            / sum(factors_source)
            for k in range(3)
        )
        assert actual == expected
        assert mapping.profile_coordinates(z) == expected[1:]


def test_both_source_errors_share_the_same_geometry_comparison_and_accuracy_gate() -> None:
    """
    Native and prior canonical errors add; a passing first cap cannot hide an incompatible second cap.
    """
    interval = Fraction(0), Fraction(1)
    curve = native(interval, Fraction(1))
    shifted = replace(
        curve, controls=tuple((p[0] + Fraction(3, 1000), p[1], p[2]) for p in curve.controls)
    )
    accepted = bind(shifted, sources(), interval, "revision", checkpoint)
    assert (
        accepted.mapping is not None
        and accepted.mapping.source_errors_upper_mm == (Fraction(3, 1000),) * 2
    )
    first, second = sources()
    uncertain = replace(first, canonical_error_upper_mm=Fraction(8, 1000))
    assert bind(shifted, (uncertain, second), interval, "revision", checkpoint).mapping is None
    incompatible = replace(
        second, controls=tuple((p[0] + Fraction(1, 10), p[1], p[2]) for p in second.controls)
    )
    assert bind(curve, (first, incompatible), interval, "revision", checkpoint).mapping is None


def test_ambiguous_orientation_is_unresolved_and_foreign_provenance_rejected() -> None:
    """
    A collapsed geometric image cannot select material direction by matching endpoints alone.
    """
    interval = Fraction(0), Fraction(1)
    first, second = sources()
    collapsed = ((Fraction(0),) * 3,) * 3
    pair = replace(first, controls=collapsed), replace(second, controls=collapsed)
    curve = replace(native(interval, Fraction(1)), controls=collapsed)
    result = bind(curve, pair, interval, "revision", checkpoint)
    assert result.mapping is None and result.status == "unresolved_shared_cap_material_parameter"
    with pytest.raises(ValueError, match="SAME native"):
        bind(curve, pair, interval, "foreign", checkpoint)
    with pytest.raises(ValueError, match="SAME native"):
        bind(
            curve,
            (first, replace(second, profile=replace(second.profile, label="foreign"))),
            interval,
            "revision",
            checkpoint,
        )


def test_resource_stop_prevents_a_cap_binding_receipt() -> None:
    """
    Both orientation candidates and all source comparisons remain inside the caller's allocation.
    """
    calls = 0

    def stop() -> None:
        """
        Stop during source restriction before the first native orientation can complete.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("caller stop")

    interval = Fraction(0), Fraction(1)
    with pytest.raises(RuntimeError, match="caller stop"):
        bind(native(interval, Fraction(1)), sources(), interval, "revision", stop)
