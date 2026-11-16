"""
Check physical parameter units, conservative conditioning and immutable native embedding ownership.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from artifacts.verification.resume3216.field import Midsurface
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.c2_material import prepare
from experiments.experiment_ribbon_complete.native_face_condition import certify, parameter_bounds
from experiments.experiment_ribbon_complete.native_face_embedding import (
    NativeFaceEmbedding,
)
from experiments.experiment_ribbon_complete.native_face_embedding import (
    certify as embedding_bounds,
)
from experiments.experiment_ribbon_complete.native_material_chart import bind
from experiments.experiment_ribbon_complete.volume_injectivity import audit
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_native_material_chart import snapshot
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def embedding(shear: bool = False) -> NativeFaceEmbedding:
    """
    Build an actual source-owned analytical embedding rather than importing a scalar separation.
    """
    volume = replace(candidate(shear), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    chart = bind(volume, material_profile(2, 0.75)[0], native, 0, native.revision, checkpoint)
    return embedding_bounds(chart, audit(volume, checkpoint), checkpoint)


@pytest.mark.parametrize("shear", (False, True))
def test_same_native_embedding_receives_owned_parameter_conditioning(shear: bool) -> None:
    """
    Complete derivative bounds use the original native surface and declared physical parameter scales.
    """
    owned = embedding(shear)
    result = certify(owned, checkpoint)
    assert result.embedding is owned and result.native is owned.chart.native
    assert result.status == "certified_native_face_parameter_conditioning"
    assert result.condition_upper is not None and result.condition_upper <= 1024
    assert result.forward_upper is not None and result.inverse_upper is not None
    assert result.condition_upper == result.forward_upper * result.inverse_upper
    with pytest.raises(ValueError, match="SAME native"):
        replace(result, native=replace(result.native))
    with pytest.raises(ValueError, match="SAME chart"):
        replace(owned, chart=replace(owned.chart))
    with pytest.raises(ValueError, match="SAME chart"):
        replace(owned, canonical=replace(owned.canonical))


def test_physical_scales_and_uniform_unit_changes_are_explicit() -> None:
    """
    The affine field X=(2U,3V,0) has an identity physical chart when scales are2/3, not1/1.
    """
    partials = Fraction(2), Fraction(3)
    scales = Fraction(2), Fraction(3)
    forward, inverse, upper = parameter_bounds(partials, scales, Fraction(1))
    assert (forward, inverse, upper) == (Fraction(2), Fraction(2), Fraction(4))
    assert parameter_bounds(
        (10 * partials[0], 10 * partials[1]), (10 * scales[0], 10 * scales[1]), Fraction(1)
    ) == (forward, inverse, upper)
    assert parameter_bounds(partials, (Fraction(1), Fraction(1)), Fraction(1))[2] > upper


def test_sheared_and_ill_conditioned_affine_fields_are_not_hidden_by_parameter_names() -> None:
    """
    Bounds cover an independently known shear condition and exceed1024 for an actual thin coordinate axis.
    """
    shear = Fraction(2)
    actual_shear_condition = (1 + shear) ** 2
    upper = parameter_bounds((Fraction(1), 1 + shear), (Fraction(1), Fraction(1)), 1 / (1 + shear))[
        2
    ]
    assert upper >= actual_shear_condition
    thin = Fraction(1, 2000)
    thin_upper = parameter_bounds((Fraction(1), thin), (Fraction(1), Fraction(1)), thin)[2]
    assert thin_upper >= 1 / thin > 1024
    with pytest.raises(ValueError, match="positive physical"):
        parameter_bounds((Fraction(1), Fraction(1)), (Fraction(1), Fraction(1)), Fraction(0))


def test_unresolved_embedding_does_not_receive_conditioning_from_a_default_margin() -> None:
    """
    Missing global source evidence propagates instead of becoming an invented inverse norm.
    """
    owned = embedding()
    missing = replace(
        owned.canonical,
        reference_lower=None,
        gradient_upper=None,
        separation_lower=None,
        spans=(),
        status="unresolved_reference_domain",
    )
    unresolved = embedding_bounds(owned.chart, missing, checkpoint)
    result = certify(unresolved, checkpoint)
    assert result.status == "unresolved_native_face_embedding"
    assert result.condition_upper is None and result.partial_upper is None


def test_strong_transverse_compression_is_unresolved_at_the_owned_conditioning_entry() -> None:
    """
    A globally injective compressed field must still satisfy the independent1024 conditioning gate.
    """
    base = replace(candidate(), half_thickness_mm=Fraction(1))
    scale = Fraction(1, 2048)
    surface = Midsurface(
        base.source.surface.basis,
        tuple(
            tuple(Vector3(p.x, p.y / 2048, p.z / 2048) for p in row)
            for row in base.source.surface.rows
        ),
    )
    source = prepare(surface, base.source.half_mm, "analytical transverse compression", checkpoint)
    volume = replace(
        base,
        source=source,
        origin=(base.origin[0], base.origin[1] * scale, base.origin[2] * scale),
        across=tuple(x * scale for x in base.across),
    )
    native = snapshot(volume)
    chart = bind(volume, material_profile(2, 0.75)[0], native, 0, native.revision, checkpoint)
    owned = embedding_bounds(chart, audit(volume, checkpoint), checkpoint)
    assert owned.status == "certified_native_face_global_injectivity"
    result = certify(owned, checkpoint)
    assert result.condition_upper is not None and result.condition_upper > 1024
    assert result.status == "unresolved_native_face_parameter_conditioning"


def test_resource_stop_propagates_from_native_derivative_measurement() -> None:
    """
    Native conditioning cannot finish after a shared allocation stops during coefficient traversal.
    """
    owned = embedding()
    calls = 0

    def stop() -> None:
        """
        Stop after the conditioning entry and native derivative launch checkpoints.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("native conditioning allocation stopped")

    with pytest.raises(RuntimeError, match="native conditioning allocation"):
        certify(owned, stop)
