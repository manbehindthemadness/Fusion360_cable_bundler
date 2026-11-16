"""
Check finite original-native edge bounds without inventing volume or sampled curve coverage.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from experiments.experiment_ribbon_complete.native_boundary_enclosure import (
    FiniteNativeBoundarySide,
    NativeEdgeBox,
    boundary_axes,
)
from experiments.experiment_ribbon_complete.native_flat_cylinder import NativeCylinderSnapshot
from tests.test_ribbon_complete_native_boundary_distance import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def edge_box() -> NativeEdgeBox:
    """
    Enclose the lower cut in a plane with a deliberately large b extent and zero s width.
    """
    zero, one = Fraction(0), Fraction(1)
    native = NativeCylinderSnapshot(
        "revision", 0, 0, "straight", "upper", (zero,) * 3, (one, zero, zero), one
    )
    low, high = Fraction(-0.6), Fraction(0.6)
    return NativeEdgeBox(
        native,
        "owned-face",
        1,
        (10, 11),
        ((zero, low, Fraction(0.8)), (zero, high, Fraction(0.8))),
        (zero, zero, one),
        ((zero, (high - low) / 2, zero), (zero, zero, Fraction(10)), (zero,) * 3),
    )


def test_degenerate_planar_edge_box_does_not_inflate_the_projected_bound() -> None:
    """
    Curvature along b cannot invent a projected s/q error or require a nonzero box volume.
    """
    _, frame, graph = fixture()
    box = edge_box()
    proof = FiniteNativeBoundarySide(box, frame, graph, BoundarySide.LOW, checkpoint)
    assert proof.status == "within_actual_native_finite_side"
    assert proof.tube_upper_mm == Fraction(0)
    assert proof.q_interval_mm == graph.interval
    assert len(set(box.corners())) == 4


def test_line_generator_and_zero_tip_remain_valid_without_box_inflation() -> None:
    """
    A one-dimensional or point enclosure still provides exact finite affine extrema.
    """
    _, frame, graph = fixture()
    box = edge_box()
    q, b = map(Fraction, graph.conic.arc.controls[0])
    zero = Fraction(0)
    line = replace(
        box,
        vertex_points_mm=((zero, q, b), (Fraction(2), q, b)),
        center_mm=(Fraction(1), q, b),
        half_axes_mm=((Fraction(1), zero, zero), (zero,) * 3, (zero,) * 3),
    )
    proof = FiniteNativeBoundarySide(line, frame, graph, BoundarySide.END0, checkpoint)
    assert proof.tube_upper_mm == Fraction(0) and len(set(line.corners())) == 2
    point = replace(
        line,
        directed_vertices=(10, 10),
        vertex_points_mm=((zero, q, b), (zero, q, b)),
        center_mm=(zero, q, b),
        half_axes_mm=((zero,) * 3,) * 3,
    )
    assert FiniteNativeBoundarySide(
        point, frame, graph, BoundarySide.END0, checkpoint
    ).tube_upper_mm == Fraction(0)


def test_finite_overhang_and_wrong_side_are_retained_as_unresolved() -> None:
    """
    Coincidence with an infinite cut plane cannot hide finite q overrun or assignment to the opposite cut.
    """
    _, frame, graph = fixture()
    box = edge_box()
    extended = replace(
        box,
        half_axes_mm=(
            (Fraction(0), Fraction(0.6) + Fraction(1, 50), Fraction(0)),
            *box.half_axes_mm[1:],
        ),
    )
    proof = FiniteNativeBoundarySide(extended, frame, graph, BoundarySide.LOW, checkpoint)
    assert proof.tube_upper_mm == Fraction(1, 50)
    assert proof.status == "unresolved_actual_native_finite_side"
    opposite = FiniteNativeBoundarySide(box, frame, graph, BoundarySide.HIGH, checkpoint)
    assert opposite.tube_upper_mm == Fraction(2)
    assert opposite.status == "unresolved_actual_native_finite_side"


@pytest.mark.parametrize("side", list(BoundarySide))
def test_original_normal_and_progress_axes_are_perpendicular_under_frame_shear(
    side: BoundarySide,
) -> None:
    """
    Both request axes annihilate the original b column while preserving physical s/q labels.
    """
    _, frame, _ = fixture()
    changed = replace(
        frame,
        columns=(
            (Fraction(1), Fraction(1, 5), Fraction(0)),
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(1, 4), Fraction(1, 2), Fraction(1)),
        ),
    )
    normal, width = boundary_axes(changed, side)
    assert sum(a * b for a, b in zip(normal, width)) == 0
    assert any(width)
    for axis in (normal, width):
        assert sum(a * b for a, b in zip(axis, changed.columns[2])) == 0


def test_foreign_profile_and_resource_stop_cannot_inherit_boundary_accuracy() -> None:
    """
    Numerical coincidence does not waive source ownership or the caller's allocation.
    """
    _, frame, graph = fixture()
    box = edge_box()
    with pytest.raises(ValueError, match="SAME original native"):
        FiniteNativeBoundarySide(
            replace(box, native=replace(box.native, profile_label="other")),
            frame,
            graph,
            BoundarySide.LOW,
            checkpoint,
        )

    def stop() -> None:
        """
        Refuse further work after the shared allocation expires.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        FiniteNativeBoundarySide(box, frame, graph, BoundarySide.LOW, stop)
