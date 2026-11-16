"""
Check whole native face separation, derivative-sensitive rejection and canonical source ownership.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_face_embedding import (
    certify,
    profile_separation,
    residual_derivatives,
)
from experiments.experiment_ribbon_complete.native_material_chart import bind
from experiments.experiment_ribbon_complete.volume_injectivity import audit
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc, material_profile
from tests.test_ribbon_complete_native_material_chart import snapshot
from tests.test_ribbon_complete_volume_injectivity import candidate, checkpoint


@pytest.mark.parametrize("shear", (False, True))
def test_whole_native_face_inherits_only_same_source_positive_global_separation(
    shear: bool,
) -> None:
    """
    A shared complete basis and a positive physical profile scale support uniqueness over the whole rectangle.
    """
    volume = replace(candidate(shear), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    chart = bind(volume, material_profile(2, 0.75)[0], native, 0, native.revision, checkpoint)
    canonical = audit(volume, checkpoint)
    result = certify(chart, canonical, checkpoint)
    assert result.status == "certified_native_face_global_injectivity"
    assert result.chart is chart and result.canonical is canonical
    assert result.profile_lower_mm is not None and result.profile_lower_mm > Fraction(0)
    assert result.separation_lower is not None and result.separation_lower > Fraction(0)
    assert (
        result.perturbation_upper is not None
        and result.perturbation_upper < canonical.separation_lower
    )
    with pytest.raises(ValueError, match="SAME original"):
        certify(chart, replace(canonical, volume=replace(volume)), checkpoint)


def test_constant_translation_changes_positions_without_changing_residual_derivatives() -> None:
    """
    Exact quotient cancellation avoids inventing derivative error from a constant positional displacement.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    arc = material_profile(2, 0.75)[0]
    original = bind(volume, arc, native, 0, native.revision, checkpoint)
    translated = replace(
        native,
        rows=tuple(
            tuple((p[0] + Fraction(1, 200), p[1], p[2]) for p in row) for row in native.rows
        ),
    )
    changed = bind(volume, arc, translated, 0, native.revision, checkpoint)
    assert changed.status == "certified_native_material_parameter_chart"
    assert changed.position_upper_mm is not None and original.position_upper_mm is not None
    assert changed.position_upper_mm > original.position_upper_mm
    assert residual_derivatives(original, checkpoint) == residual_derivatives(changed, checkpoint)
    assert (
        certify(changed, audit(volume, checkpoint), checkpoint).status
        == "certified_native_face_global_injectivity"
    )


def test_small_position_error_cannot_hide_a_large_native_derivative_perturbation() -> None:
    """
    A local control bump can pass position accuracy while failing the global separation certificate.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    rows = list(native.rows)
    index = len(rows) // 2
    rows[index] = tuple((p[0] + Fraction(1, 200), p[1], p[2]) for p in rows[index])
    assert rows[0] == native.rows[0] and rows[-1] == native.rows[-1]
    chart = bind(
        volume,
        material_profile(2, 0.75)[0],
        replace(native, rows=tuple(rows)),
        0,
        native.revision,
        checkpoint,
    )
    assert chart.status == "certified_native_material_parameter_chart"
    result = certify(chart, audit(volume, checkpoint), checkpoint)
    assert result.status == "unresolved_native_face_gradient_margin"
    assert result.separation_lower is not None and result.separation_lower <= Fraction(0)


def test_profile_endpoints_alone_do_not_establish_positive_material_separation() -> None:
    """
    Closed and backtracking profiles remain unresolved despite complete endpoint metadata.
    """
    closed = MaterialArc(((0, 0), (1, 1), (0, 0)), (1, 1, 1), "closed")
    returning = MaterialArc(((0, 0), (2, 0), (1, 0)), (1, 1, 1), "returning")
    assert profile_separation(closed, checkpoint) is None
    assert profile_separation(returning, checkpoint) is None


def test_caller_stop_propagates_from_inside_native_residual_traversal() -> None:
    """
    Exact coefficient work cannot produce a certificate after the caller exhausts its allocation.
    """
    volume = replace(candidate(), half_thickness_mm=Fraction(1))
    native = snapshot(volume)
    chart = bind(volume, material_profile(2, 0.75)[0], native, 0, native.revision, checkpoint)
    calls = 0

    def stop() -> None:
        """
        Reject the shared allocation after entering a derivative control difference.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("native derivative allocation stopped")

    with pytest.raises(RuntimeError, match="native derivative allocation"):
        residual_derivatives(chart, stop)
