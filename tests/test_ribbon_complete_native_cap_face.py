"""
Exercise explicit cap/face correspondence, whole-curve error and independent invertibility gates.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_cap_chain import (
    ConformingCapChain,
    conform,
    orient_endpoints,
)
from experiments.experiment_ribbon_complete.native_cap_face import (
    NativeFaceCoedge,
    adopt,
    trace_bounds,
)
from experiments.experiment_ribbon_complete.native_cap_material import (
    MaterialCapSource,
    NativeCapCurve,
    bind,
)
from experiments.experiment_ribbon_complete.native_face_condition import (
    NativeFaceCondition,
    certify,
)
from experiments.experiment_ribbon_complete.native_trim_boundary import NativeTrimCurve
from tests.test_ribbon_complete_native_face_condition import embedding
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.fixture
def cap() -> tuple[NativeFaceCondition, ConformingCapChain, NativeFaceCoedge]:
    """
    Bind a real analytical face and its unchanged end-cap row through the complete qualification factories.
    """
    condition = certify(embedding(), checkpoint)
    chart = condition.embedding.chart
    native = condition.native
    curve = NativeCapCurve(native.revision, 7, native.rows[-1], native.weights[-1])
    first = MaterialCapSource(
        (native.piece_index, "bend"), chart.arc, curve.controls, Fraction(0), "actual cap"
    )
    pair = first, replace(first, region=(native.piece_index + 1, "before"))
    bound = bind(curve, pair, (Fraction(0), Fraction(1)), native.revision, checkpoint)
    endpoints = orient_endpoints(
        curve, (10, 11), (curve.controls[0], curve.controls[-1]), checkpoint
    )
    volume = chart.volume
    chain = conform((bound,), (endpoints,), (-volume.sine / volume.cosine, Fraction(0)), checkpoint)
    phase = volume.source.surface.basis.breaks[-1]
    coedge = NativeFaceCoedge(
        native, NativeTrimCurve(7, ((phase, Fraction(0)), (phase, Fraction(1))), (Fraction(1),) * 2)
    )
    return condition, chain, coedge


@pytest.mark.parametrize("reverse", (False, True))
def test_whole_boundary_decodes_shared_labels_with_explicit_native_parameters(
    cap: tuple[NativeFaceCondition, ConformingCapChain, NativeFaceCoedge], reverse: bool
) -> None:
    """
    Coedge direction changes the explicit correspondence while geometry and original q/b labels stay intact.
    """
    condition, chain, coedge = cap
    if reverse:
        coedge = replace(
            coedge, curve=replace(coedge.curve, controls=tuple(reversed(coedge.curve.controls)))
        )
    binding = chain.bindings[0]
    result = adopt(condition, chain, binding, coedge, checkpoint)
    assert result.status == "qualified_native_cap_face_labels"
    assert result.reversed_coedge is reverse
    with pytest.raises(ValueError, match="SAME owned evidence"):
        replace(result, coedge=replace(coedge))
    with pytest.raises(ValueError, match="SAME owned evidence"):
        replace(result, phase=result.phase + 1)
    assert result.world_upper_mm == result.label_upper_mm == 0
    assert binding.mapping is not None
    for i in range(9):
        z = Fraction(i, 8)
        v = 1 - z if reverse else z
        assert result.material_parameter(z) == v
        assert result.native_parameters(z) == (result.phase, v)
        assert binding.mapping.parameter(result.cap_coordinate(z)) == v
    with pytest.raises(ValueError, match="SAME native"):
        adopt(condition, chain, binding, replace(coedge, native=replace(coedge.native)), checkpoint)
    with pytest.raises(ValueError, match="shared cap edge"):
        adopt(
            condition,
            chain,
            binding,
            replace(coedge, curve=replace(coedge.curve, edge_id=99)),
            checkpoint,
        )


def test_matching_endpoints_cannot_hide_a_bowed_whole_boundary(
    cap: tuple[NativeFaceCondition, ConformingCapChain, NativeFaceCoedge],
) -> None:
    """
    A quadratic inward excursion exceeds dimensional acceptance despite unchanged cap endpoints.
    """
    condition, chain, coedge = cap
    phase = coedge.curve.controls[0][0]
    curve = NativeTrimCurve(
        7,
        ((phase, Fraction(0)), (phase - Fraction(1, 20), Fraction(1, 2)), (phase, Fraction(1))),
        (Fraction(1),) * 3,
    )
    result = adopt(condition, chain, chain.bindings[0], replace(coedge, curve=curve), checkpoint)
    assert result.status == "unresolved_native_cap_face_labels"
    with pytest.raises(ValueError, match="qualified boundary"):
        result.material_parameter(Fraction(1, 2))


def test_small_native_uv_deviation_is_accepted_with_measured_physical_error(
    cap: tuple[NativeFaceCondition, ConformingCapChain, NativeFaceCoedge],
) -> None:
    """
    Nonzero native discrepancy qualifies within0.01mm without snapping the original boundary.
    """
    condition, chain, coedge = cap
    epsilon = Fraction(1, 100000)
    phase = coedge.curve.controls[0][0]
    curve = NativeTrimCurve(
        7, ((phase - epsilon, epsilon), (phase - epsilon, 1 - epsilon)), (Fraction(1),) * 2
    )
    result = adopt(condition, chain, chain.bindings[0], replace(coedge, curve=curve), checkpoint)
    assert result.status == "qualified_native_cap_face_labels"
    assert result.world_upper_mm is not None and result.world_upper_mm > 0
    assert result.label_upper_mm is not None and result.label_upper_mm > 0
    assert result.world_upper_mm + result.label_upper_mm <= Fraction(1, 100)
    assert result.native_parameters(Fraction(0)) == curve.controls[0]
    assert result.material_parameter(Fraction(0)) == 0


def test_small_label_discrepancy_does_not_waive_zero_progress() -> None:
    """
    A tiny cubic with stationary progress cannot receive a valid inverse from its small position error.
    """
    epsilon = Fraction(1, 1000)
    curve = NativeTrimCurve(
        7,
        tuple((Fraction(0), v) for v in (Fraction(0), epsilon, Fraction(0), epsilon)),
        (Fraction(1),) * 4,
    )
    du, dv, lower, upper = trace_bounds(curve, Fraction(0), (Fraction(0), epsilon))
    assert du == 0 and dv <= epsilon and lower <= 0 < upper


def test_resource_stop_cannot_produce_a_boundary_receipt(
    cap: tuple[NativeFaceCondition, ConformingCapChain, NativeFaceCoedge],
) -> None:
    """
    Both possible coedge directions remain inside the caller's fixed allocation.
    """
    condition, chain, coedge = cap
    calls = 0

    def stop() -> None:
        """
        Stop during correspondence selection after entry validation.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boundary allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        adopt(condition, chain, chain.bindings[0], coedge, stop)


def test_rational_trace_bounds_enclose_independent_values_and_derivatives() -> None:
    """
    Positive nonconstant weights use quotient derivatives rather than polynomial control differences.
    """
    epsilon = Fraction(1, 1000)
    curve = NativeTrimCurve(
        7,
        ((epsilon, Fraction(0)), (Fraction(0), Fraction(1, 2)), (epsilon, Fraction(1))),
        (Fraction(1), Fraction(1, 2), Fraction(1)),
    )
    du, dv, lower, upper = trace_bounds(curve, Fraction(0), (Fraction(0), Fraction(1)))
    assert du == epsilon
    for i in range(17):
        z = Fraction(i, 16)
        basis = (1 - z) ** 2, 2 * z * (1 - z), z**2
        derivative_basis = -2 * (1 - z), 2 - 4 * z, 2 * z
        denominator = sum(w * b for w, b in zip(curve.weights, basis))
        denominator_prime = sum(w * b for w, b in zip(curve.weights, derivative_basis))
        numerator = sum(p[1] * w * b for p, w, b in zip(curve.controls, curve.weights, basis))
        numerator_prime = sum(
            p[1] * w * b for p, w, b in zip(curve.controls, curve.weights, derivative_basis)
        )
        assert abs(numerator / denominator - z) <= dv
        rate = (numerator_prime * denominator - numerator * denominator_prime) / denominator**2
        assert lower <= rate <= upper
