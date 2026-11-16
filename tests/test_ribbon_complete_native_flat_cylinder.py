"""
Check exact cylindrical correspondence and retain unsupported or distorted material fields.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.flat_chart import straight
from experiments.experiment_ribbon_complete.native_flat_cylinder import (
    NativeCylinderSnapshot,
    enclose,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def circle() -> MaterialArc:
    """
    Capture the binary coefficients of a unit-circle arc with half-angle cosine3/5.
    """
    return MaterialArc(((1.0, 0.0), (1.0, 4 / 3), (-7 / 25, 24 / 25)), (1.0, 3 / 5, 1.0), "circle")


def cylinder() -> NativeCylinderSnapshot:
    """
    Observe a radius-one X-axis cylinder with deliberately nonunit axis data.
    """
    return NativeCylinderSnapshot(
        "revision",
        0,
        0,
        "straight",
        "circle",
        (Fraction(0),) * 3,
        (Fraction(7), Fraction(0), Fraction(0)),
        Fraction(1),
    )


@pytest.mark.parametrize("along_origin", (Fraction(0), Fraction(100)))
def test_circle_and_axis_scale_preserve_position_accuracy_and_zero_increment(
    along_origin: Fraction,
) -> None:
    """
    An axial origin shift and nonunit axis cannot create artificial discrepancy.
    """
    chart = straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "straight"
        )
    )
    native = replace(cylinder(), origin=(along_origin, Fraction(0), Fraction(0)))
    proof = enclose(chart, circle(), native, 0, "revision", checkpoint)
    assert proof.status == "within_support_construction_accuracy"
    assert proof.position_upper_mm is not None and proof.position_upper_mm <= Fraction(1, 100)
    assert proof.increment_upper_mm == Fraction(0)
    assert proof.radial_squared_lower_mm2 > 0


def test_radius_mismatch_is_measured_without_inventing_longitudinal_stretch() -> None:
    """
    Parallel paths on a slightly different radius have a position gap but equal axial increments.
    """
    chart = straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "straight"
        )
    )
    proof = enclose(
        chart,
        circle(),
        replace(cylinder(), radius_mm=Fraction(201, 200)),
        0,
        "revision",
        checkpoint,
    )
    assert Fraction(1, 200) <= proof.position_upper_mm <= Fraction(1, 100)
    assert proof.increment_upper_mm == Fraction(0)
    failed = enclose(
        chart, circle(), replace(cylinder(), radius_mm=Fraction(2)), 0, "revision", checkpoint
    )
    assert (
        failed.status == "unresolved_support_construction_accuracy"
        and failed.position_upper_mm > Fraction(1, 100)
    )


def test_tilted_longitudinal_field_cannot_inherit_parallel_axis_fidelity() -> None:
    """
    Source drift away from the cylinder axis contributes to continuous longitudinal discrepancy.
    """
    chart = straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0.1, 0), Vector3(0, 1, 0)), Straight(2), "tilted"
        )
    )
    proof = enclose(chart, circle(), cylinder(), 0, "revision", checkpoint)
    assert proof.increment_upper_mm > Fraction(1, 100)
    assert proof.status == "unresolved_support_construction_accuracy"


def test_axis_crossing_and_stale_identity_remain_unresolved() -> None:
    """
    A collapsed radial field cannot be projected uniquely, and foreign provenance cannot bind.
    """
    chart = straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "straight"
        )
    )
    collapsed = MaterialArc(((0, 0),) * 3, (1, 1, 1), "circle")
    proof = enclose(chart, collapsed, cylinder(), 0, "revision", checkpoint)
    assert proof.radial_squared_lower_mm2 == Fraction(0) and proof.increment_upper_mm is None
    assert proof.status == "unresolved_support_construction_accuracy"
    with pytest.raises(ValueError, match="SAME original"):
        enclose(chart, circle(), cylinder(), 1, "revision", checkpoint)
    with pytest.raises(ValueError, match="SAME original"):
        enclose(chart, circle(), cylinder(), 0, "foreign", checkpoint)
    with pytest.raises(ValueError, match="Complete exact"):
        replace(cylinder(), axis=(Fraction(0),) * 3)


def test_caller_stop_prevents_a_completed_support_receipt() -> None:
    """
    Radial algebra and derivative bounds remain under the caller's resource checkpoints.
    """
    chart = straight(
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(2), "straight"
        )
    )
    calls = 0

    def stop() -> None:
        """
        Reject the allocation after its first projection traversal.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("caller stop")

    with pytest.raises(RuntimeError, match="caller stop"):
        enclose(chart, circle(), cylinder(), 0, "revision", stop)
