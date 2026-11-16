"""
Separate native support coordinate validity from small positional error and actual trim coverage.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.flat_chart import FlatChart, MaterialCut, straight
from experiments.experiment_ribbon_complete.native_flat_cylinder import (
    FlatCylinderBound,
    enclose,
    radial_field,
)
from experiments.experiment_ribbon_complete.native_flat_embedding import certify, implicit_bounds
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_native_flat_cylinder import circle, cylinder
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def chart() -> FlatChart:
    """
    Retain a source-owned identity material frame with a physical two-millimeter longitudinal domain.
    """
    return straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "straight"
        )
    )


def support() -> FlatCylinderBound:
    """
    Measure an actual rational circular profile against its explicitly captured cylinder support.
    """
    return enclose(chart(), circle(), cylinder(), 0, "revision", checkpoint)


def test_circular_support_has_global_conditioned_physical_coordinates() -> None:
    """
    The source-owned projection is injective on the complete physical rectangle without claiming native trim.
    """
    original = support()
    result = certify(original, checkpoint)
    assert result.status == "certified_flat_support_global_coordinates"
    proof = result.evidence
    assert (
        proof.support is original
        and proof.field is not None
        and proof.field.native is original.native
    )
    assert proof.separation_lower is not None and proof.separation_lower > 0
    assert proof.condition_upper is not None and proof.condition_upper <= 1024
    assert proof.interval_mm == (Fraction(0), Fraction(2))
    with pytest.raises(ValueError, match="SAME original support"):
        replace(result, support=replace(original))
    with pytest.raises(ValueError, match="SAME chart/profile/native"):
        replace(original, chart=replace(original.chart))
    with pytest.raises(ValueError, match="SAME chart/profile/native"):
        replace(original, native=replace(original.native))


def test_covering_rectangle_retains_zero_tip_and_tiny_negative_fragment() -> None:
    """
    Curved cuts are covered in physical s without normalization by their changing longitudinal extent.
    """
    original = chart()
    epsilon = Fraction(1, 10**15)
    changing = replace(
        original,
        low=MaterialCut(Fraction(0)),
        high=MaterialCut(Fraction(1) - epsilon, Fraction(-1)),
    )
    measured = enclose(changing, circle(), cylinder(), 0, "revision", checkpoint)
    result = certify(measured, checkpoint)
    assert result.status == "certified_flat_support_global_coordinates"
    assert changing.high.at(Fraction(1)) == -epsilon
    assert result.evidence.interval_mm[0] == -epsilon
    assert result.support.chart is changing


def test_small_construction_error_cannot_hide_a_rank_collapsing_projection() -> None:
    """
    A tiny radial plane projects onto one circle, destroying two-dimensional coordinates despite acceptable distance.
    """
    epsilon = Fraction(1, 1000)
    original = replace(chart(), high=MaterialCut(epsilon))
    arc = MaterialArc(((1, 1), (1, 1.0005), (1, 1.001)), (1, 1, 1), "circle")
    native = replace(cylinder(), axis=(Fraction(0), Fraction(1), Fraction(0)))
    first = Fraction(0), Fraction(1), Fraction(1)
    second = Fraction(0), Fraction(1), Fraction(1) + epsilon / 2
    assert native.radial(second) == tuple((1 + epsilon / 2) * x for x in native.radial(first))
    measured = enclose(original, arc, native, 0, "revision", checkpoint)
    assert measured.status == "within_support_construction_accuracy"
    result = certify(measured, checkpoint)
    assert result.status == "unresolved_flat_support_global_injectivity"
    assert result.evidence.separation_lower is not None and result.evidence.separation_lower <= 0


def test_positive_global_separation_does_not_waive_conditioning() -> None:
    """
    A compressed material frame can retain uniqueness yet exceed the independent1024 parameter bound.
    """
    compressed = replace(
        chart(),
        columns=(
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(1, 1000), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1, 1000)),
        ),
    )
    arc = MaterialArc(((0, 1), (0.0005, 1), (0.001, 1)), (1, 1, 1), "circle")
    measured = enclose(
        compressed, arc, replace(cylinder(), radius_mm=Fraction(1, 1000)), 0, "revision", checkpoint
    )
    result = certify(measured, checkpoint)
    assert result.status == "unresolved_flat_support_parameter_conditioning"
    assert result.evidence.separation_lower is not None and result.evidence.separation_lower > 0
    assert result.evidence.condition_upper is not None and result.evidence.condition_upper > 1024


def test_closed_profile_and_axis_crossing_do_not_receive_default_coordinate_margins() -> None:
    """
    Missing profile progress and a nonprojectable support remain explicitly unresolved.
    """
    closed = MaterialArc(((1, 0), (1, 0.001), (1, 0)), (1, 1, 1), "circle")
    measured = enclose(chart(), closed, cylinder(), 0, "revision", checkpoint)
    assert measured.status == "within_support_construction_accuracy"
    result = certify(measured, checkpoint)
    assert (
        result.status == "unresolved_flat_support_embedding"
        and result.evidence.profile_lower_mm is None
    )
    collapsed = MaterialArc(((0, 0),) * 3, (1, 1, 1), "circle")
    result = certify(enclose(chart(), collapsed, cylinder(), 0, "revision", checkpoint), checkpoint)
    assert result.status == "unresolved_flat_support_embedding" and result.evidence.field is None


def test_implicit_derivatives_are_not_inferred_from_small_residual_values() -> None:
    """
    A short covering rectangle changes physical derivatives while leaving its normalized residual coefficients fixed.
    """
    epsilon = Fraction(1, 1000)
    rows = (
        ((Fraction(0), Fraction(1), Fraction(0)),) * 3,
        ((Fraction(1), Fraction(1) + epsilon, Fraction(0)),) * 3,
    )
    field = radial_field(cylinder(), rows, (Fraction(1),) * 3, checkpoint)
    baseline = implicit_bounds(field, Fraction(2), checkpoint)
    shorter = implicit_bounds(field, Fraction(1), checkpoint)
    assert baseline[:2] == shorter[:2]
    assert shorter[2] == (2 * baseline[2][0], baseline[2][1])
    tiny = implicit_bounds(field, epsilon, checkpoint)
    assert tiny[1] < Fraction(1, 100) and tiny[2][0] > 2
    with pytest.raises(ValueError, match="positive physical"):
        implicit_bounds(field, Fraction(0), checkpoint)


def test_resource_stop_cannot_finish_a_flat_coordinate_receipt() -> None:
    """
    Profile progress, projection and gradient work remain in the caller's shared allocation.
    """
    measured = support()
    calls = 0

    def stop() -> None:
        """
        Stop during the first source-profile progress calculation.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("flat coordinates stopped")

    with pytest.raises(RuntimeError, match="coordinates stopped"):
        certify(measured, stop)
