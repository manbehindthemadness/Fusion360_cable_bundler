"""
Check source-owned native parameter charts without sampled or conditional-image acceptance.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_material_chart import (
    NativeSurfaceSnapshot,
    bind,
    decode,
)
from experiments.experiment_ribbon_complete.spatial_frame import split_at
from experiments.experiment_ribbon_complete.volume_field import BendVolume
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


def snapshot(volume: BendVolume) -> NativeSurfaceSnapshot:
    """
    Author captured-like quadratic native rows under the original global U basis and profile weights.
    """
    arc = material_profile(2, 0.75)[0]
    output = []
    for i, row in enumerate(volume.source.surface.rows):
        values = []
        for q, b in arc.controls:
            v = (Fraction(q) / volume.source.half_mm + 1) / 2
            values.append(
                tuple(
                    split_at(tuple(Fraction(getattr(p, k)) for p in row), v)[0][-1]
                    + Fraction(b) * volume.normals[axis].controls[i]
                    for axis, k in enumerate("xyz")
                )
            )
        output.append(tuple(values))
    return NativeSurfaceSnapshot(
        "analytical-revision",
        0,
        0,
        arc.label,
        5,
        2,
        volume.source.surface.basis.knots,
        (Fraction(0),) * 3 + (Fraction(1),) * 3,
        tuple(output),
        tuple(tuple(map(Fraction, arc.weights)) for _ in output),
    )


@pytest.mark.parametrize("shear", (False, True))
def test_parameter_labels_match_original_profile_and_whole_native_chart(shear: bool) -> None:
    """
    Independent rational surface evaluation stays inside the complete control enclosure.
    """
    volume = replace(candidate(shear), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    arc = material_profile(2, 0.75)[0]
    chart = bind(volume, arc, native, 0, native.revision, checkpoint)
    assert chart.status == "certified_native_material_parameter_chart"
    assert chart.position_upper_mm is not None and chart.position_upper_mm <= Fraction(1, 100)
    theta = volume.source.surface.basis.breaks[-1]
    for u in (Fraction(0), theta / 3, theta):
        for v in (Fraction(0), Fraction(1, 3), Fraction(1)):
            result = decode(chart, u, v, checkpoint)
            assert result.chart is chart and result.profile_parameter == v
            basis = ((1 - v) ** 2, 2 * v * (1 - v), v * v)
            weights = tuple(a * b for a, b in zip(basis, native.weights[0]))
            denominator = sum(weights)
            point = tuple(
                sum(
                    jet[0] * sum(w * p[k] for w, p in zip(weights, native.rows[i]))
                    for i, jet in volume.source.surface.basis.jets(u)
                )
                / denominator
                for k in range(3)
            )
            error = sum(abs(a - b) for a, b in zip(point, result.canonical_point))
            assert error <= chart.position_upper_mm
            assert result.material_coordinates[1:] == tuple(
                split_at(
                    tuple(Fraction(p[k]) * Fraction(w) for p, w in zip(arc.controls, arc.weights)),
                    v,
                )[0][-1]
                / denominator
                for k in range(2)
            )


def test_interior_control_bump_is_not_hidden_by_matching_endpoints() -> None:
    """
    Whole-control acceptance rejects a localized deviation even when both U caps are unchanged.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    rows = list(native.rows)
    row = list(rows[len(rows) // 2])
    row[1] = (row[1][0] + Fraction(1, 10), row[1][1], row[1][2])
    rows[len(rows) // 2] = tuple(row)
    changed = replace(native, rows=tuple(rows))
    assert changed.rows[0] == native.rows[0] and changed.rows[-1] == native.rows[-1]
    chart = bind(volume, material_profile(2, 0.75)[0], changed, 0, native.revision, checkpoint)
    assert chart.status == "unresolved_native_position_bound"
    with pytest.raises(ValueError, match="certified SAME-source"):
        decode(chart, Fraction(1, 20), Fraction(1, 2), checkpoint)


def test_knots_weights_identity_and_domain_are_never_guessed() -> None:
    """
    Unsupported parameterization remains unknown, while source substitutions reject explicitly.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    arc = material_profile(2, 0.75)[0]
    for changed in (
        replace(native, knots_u=tuple(2 * x for x in native.knots_u)),
        replace(native, weights=tuple(tuple(2 * w for w in row) for row in native.weights)),
    ):
        assert (
            bind(volume, arc, changed, 0, native.revision, checkpoint).status
            == "unresolved_native_parameterization"
        )
    with pytest.raises(ValueError, match="SAME native body"):
        bind(volume, arc, native, 1, native.revision, checkpoint)
    with pytest.raises(ValueError, match="SAME native body"):
        bind(volume, arc, native, 0, "wrong-revision", checkpoint)
    with pytest.raises(ValueError, match="SAME native body"):
        bind(volume, replace(arc, label="wrong-profile"), native, 0, native.revision, checkpoint)
    with pytest.raises(ValueError, match="positive weights"):
        replace(native, weights=((Fraction(0),) * 3,) + native.weights[1:])
    chart = bind(volume, arc, native, 0, native.revision, checkpoint)
    with pytest.raises(ValueError, match="original native/source"):
        decode(chart, Fraction(-1), Fraction(1, 2), checkpoint)


def test_shared_allocation_stop_propagates_before_global_composition() -> None:
    """
    A stored native surface cannot bypass caller cancellation or allocate another proof pool.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)

    def stop() -> None:
        """
        Stop the caller-owned allocation before any label or whole-chart acceptance.
        """
        raise RuntimeError("caller stopped")

    with pytest.raises(RuntimeError, match="caller stopped"):
        bind(volume, material_profile(2, 0.75)[0], native, 0, native.revision, stop)
