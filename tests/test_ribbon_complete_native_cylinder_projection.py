"""
Challenge direct actual-cylinder coordinate proofs with opposite branches, conditioning and exact point pairs.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_enclosure import NativeFaceBox
from experiments.experiment_ribbon_complete.flat_chart import certify
from experiments.experiment_ribbon_complete.flat_cut_domain import FlatCutFrame, from_chart
from experiments.experiment_ribbon_complete.native_cylinder_projection import (
    ActualCylinderProjection,
)
from experiments.experiment_ribbon_complete.native_flat_cylinder import NativeCylinderSnapshot
from tests.test_ribbon_complete_native_flat_embedding import chart
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def example(sign: int = 1) -> tuple[FlatCutFrame, NativeFaceBox]:
    """
    Enclose a unit-cylinder strip on one original physical b branch in an identity material frame.
    """
    zero, one = Fraction(0), Fraction(1)
    native = NativeCylinderSnapshot(
        "revision", 0, 0, "straight", "upper", (zero,) * 3, (one, zero, zero), one
    )
    box = NativeFaceBox(
        native,
        "owned-face",
        (one, zero, Fraction(sign)),
        ((Fraction(1, 2), zero, zero), (zero, Fraction(1, 2), zero), (zero, zero, Fraction(1, 5))),
    )
    return from_chart(certify(chart())), box


@pytest.mark.parametrize("sign", [1, -1])
def test_either_separated_branch_has_an_owned_global_physical_projection(sign: int) -> None:
    """
    Original label orientation is retained on either cylinder branch without forcing a positive b sign.
    """
    frame, box = example(sign)
    proof = ActualCylinderProjection(frame, (box,), checkpoint)
    assert proof.status == "certified_actual_native_sq_projection"
    assert proof.branch_sign == sign and proof.branch_lower == Fraction(8, 5)
    assert proof.graph_partial_bounds == (Fraction(0), Fraction(5, 8))
    assert proof.inverse_world_lipschitz == proof.condition_upper == Fraction(13, 8)


def test_global_bounds_dominate_independent_exact_points_on_the_actual_cylinder() -> None:
    """
    Rational circle points give direct whole-chord checks independently of the box derivative implementation.
    """
    frame, box = example()
    proof = ActualCylinderProjection(frame, (box,), checkpoint)
    partials, inverse = proof.graph_partial_bounds, proof.inverse_world_lipschitz
    assert partials is not None and inverse is not None
    first = (Fraction(1), Fraction(0), Fraction(1))
    for second in (
        (Fraction(1), Fraction(5, 13), Fraction(12, 13)),
        (Fraction(3, 2), Fraction(-5, 13), Fraction(12, 13)),
    ):
        assert second[1] ** 2 + second[2] ** 2 == 1
        ds, dq, db = (abs(b - a) for a, b in zip(first, second))
        assert db <= partials[0] * ds + partials[1] * dq
        assert ds + dq + db <= inverse * (ds + dq)


def test_raw_axis_scale_and_common_world_translation_do_not_change_the_proof() -> None:
    """
    The projection uses the raw nonunit cylinder axis and world displacements, not hidden normalization assumptions.
    """
    frame, box = example()
    original = ActualCylinderProjection(frame, (box,), checkpoint)
    native = replace(
        box.native,
        axis=tuple(7 * x for x in box.native.axis),
        origin=tuple(x + 1000000 for x in box.native.origin),
    )
    moved = replace(box, native=native, center_mm=tuple(x + 1000000 for x in box.center_mm))
    translated = replace(frame, origin=tuple(x + 1000000 for x in frame.origin))
    proof = ActualCylinderProjection(translated, (moved,), checkpoint)
    assert proof.derivative_intervals == original.derivative_intervals
    assert proof.condition_upper == original.condition_upper
    sheared = replace(
        translated,
        columns=(
            translated.columns[0],
            (Fraction(0), Fraction(1), Fraction(1, 4)),
            translated.columns[2],
        ),
    )
    changed = ActualCylinderProjection(sheared, (moved,), checkpoint)
    assert changed.status == "certified_actual_native_sq_projection"
    assert changed.graph_partial_bounds != proof.graph_partial_bounds


def test_two_branches_are_unresolved_until_a_whole_face_enclosure_separates_them() -> None:
    """
    Two actual cylinder points with identical s/q demonstrate why a loose box cannot establish a global inverse.
    """
    frame, box = example()
    broad = replace(
        box,
        center_mm=(Fraction(1), Fraction(0), Fraction(0)),
        half_axes_mm=(
            box.half_axes_mm[0],
            box.half_axes_mm[1],
            (Fraction(0), Fraction(0), Fraction(6, 5)),
        ),
    )
    unresolved = ActualCylinderProjection(frame, (broad,), checkpoint)
    assert unresolved.status == "unresolved_actual_native_sq_projection"
    assert unresolved.branch_lower is None and unresolved.graph_partial_bounds is None
    same_projection_points = (
        (Fraction(1), Fraction(0), Fraction(1)),
        (Fraction(1), Fraction(0), Fraction(-1)),
    )
    assert same_projection_points[0][:2] == same_projection_points[1][:2]
    assert same_projection_points[0] != same_projection_points[1]
    assert (
        ActualCylinderProjection(frame, (broad, box), checkpoint).status
        == "certified_actual_native_sq_projection"
    )


def test_branch_sign_alone_cannot_hide_bad_physical_projection_conditioning() -> None:
    """
    A near-vertical graph can be injective yet fail the unchanged numerical conditioning ceiling.
    """
    frame, box = example()
    steep = replace(
        box,
        center_mm=(Fraction(1), Fraction(1), Fraction(1, 1000)),
        half_axes_mm=(
            box.half_axes_mm[0],
            (Fraction(0), Fraction(1, 500), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1, 2000)),
        ),
    )
    proof = ActualCylinderProjection(frame, (steep,), checkpoint)
    assert proof.branch_lower is not None and proof.condition_upper is not None
    assert proof.condition_upper > 1024
    assert proof.status == "unresolved_actual_native_sq_projection"


def test_foreign_tokens_inconsistent_enclosures_and_stopped_allocations_are_rejected() -> None:
    """
    Numeric bounds cannot transfer between faces or excuse contradictory whole-face enclosures.
    """
    frame, box = example()
    for foreign in (replace(box, native=replace(box.native)), replace(box, face_token="other")):
        with pytest.raises(ValueError, match="SAME actual native"):
            ActualCylinderProjection(frame, (box, foreign), checkpoint)
    lower = replace(box, center_mm=(Fraction(1), Fraction(0), Fraction(-1)))
    with pytest.raises(ValueError, match="Consistent enclosures"):
        ActualCylinderProjection(frame, (box, lower), checkpoint)

    def stop() -> None:
        """
        Refuse work after the shared allocation expires.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        ActualCylinderProjection(frame, (box,), stop)
