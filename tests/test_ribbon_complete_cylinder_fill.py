"""
Check whole-face axial-exit premises, complete boundaries and source ownership without normalized lead coordinates.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_coordinates import CylinderChart, build
from experiments.experiment_ribbon_complete.cylinder_fill import (
    BoundaryImage,
    CompactCylinderFace,
    NativeEdgeUse,
    certify,
)
from tests.test_ribbon_complete_cylinder_coordinates import reference
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def fixture() -> tuple[CompactCylinderFace, CylinderChart, tuple[BoundaryImage, ...]]:
    """
    Retain a bounded cylindrical strip with actual-style complete circular/axial boundary images.
    """
    ref = reference()
    native = ref.native
    chart = build(ref, checkpoint)
    high = tuple((Fraction(2), p[1], p[2]) for p in ref.controls)
    face = CompactCylinderFace(
        native,
        "native-face",
        ((Fraction(0), Fraction(-1), Fraction(0)), (Fraction(2), Fraction(1), Fraction(2))),
        Fraction(3),
        (1, 2, 3, 4),
        (
            (
                NativeEdgeUse(1, 1, 2),
                NativeEdgeUse(2, 2, 3),
                NativeEdgeUse(3, 3, 4),
                NativeEdgeUse(4, 4, 1),
            ),
        ),
    )
    boundary = (
        BoundaryImage(native, 1, ref.controls, ref.weights, "arc3d_identical_nurbs"),
        BoundaryImage(native, 2, (ref.controls[-1], high[-1]), (Fraction(1),) * 2, "line3d"),
        BoundaryImage(native, 3, high, ref.weights, "arc3d_identical_nurbs"),
        BoundaryImage(native, 4, (high[0], ref.controls[0]), (Fraction(1),) * 2, "line3d"),
    )
    return face, chart, boundary


def test_complete_boundary_bounds_extend_through_strip_and_zero_height_tip() -> None:
    """
    Axial exit covers full bounded faces and a triangular domain without division by its vanishing tip height.
    """
    face, chart, boundary = fixture()
    result = certify(face, chart, boundary, checkpoint)
    assert result.status == "certified_filled_intrinsic_cylinder_face"
    assert result.evidence.window is not None and result.evidence.window.chart is chart
    assert (
        result.evidence.window.condition_upper is not None
        and result.evidence.window.condition_upper <= 1024
    )
    high = tuple((1 - p[1], p[1], p[2]) for p in chart.reference.controls)
    triangle = replace(
        face,
        edge_ids=(1, 2, 3),
        loops=((NativeEdgeUse(1, 1, 2), NativeEdgeUse(2, 2, 3), NativeEdgeUse(3, 3, 1)),),
    )
    images = (
        boundary[0],
        replace(boundary[1], controls=(chart.reference.controls[-1], high[-1])),
        replace(boundary[2], controls=high, source_kind="ellipticalarc3d_identical_nurbs"),
    )
    assert high[0] == chart.reference.controls[0]
    assert (
        certify(triangle, chart, images, checkpoint).status
        == "certified_filled_intrinsic_cylinder_face"
    )


def test_missing_duplicate_or_omitted_hole_boundary_never_receives_filled_coverage() -> None:
    """
    Compactness and successful sampled charts cannot substitute for every actual face boundary component.
    """
    face, chart, boundary = fixture()
    assert (
        certify(face, chart, boundary[:-1], checkpoint).status
        == "unresolved_complete_native_boundary"
    )
    assert (
        certify(face, chart, boundary[:-1] + (boundary[0],), checkpoint).status
        == "unresolved_complete_native_boundary"
    )
    hole = (
        NativeEdgeUse(5, 10, 11),
        NativeEdgeUse(6, 11, 12),
        NativeEdgeUse(7, 12, 13),
        NativeEdgeUse(8, 13, 10),
    )
    perforated = replace(face, edge_ids=face.edge_ids + (5, 6, 7, 8), loops=face.loops + (hole,))
    assert (
        certify(perforated, chart, boundary, checkpoint).status
        == "unresolved_complete_native_boundary"
    )


def test_unbounded_or_inconsistent_metadata_and_vertex_gaps_cannot_be_assumed_compact() -> None:
    """
    Invalid enclosure, missing edge identities and unclosed topology fail before the axial-exit theorem is used.
    """
    face, _, _ = fixture()
    with pytest.raises(ValueError, match="finite nonempty"):
        replace(face, area_mm2=Fraction(0))
    with pytest.raises(ValueError, match="finite nonempty"):
        replace(face, bounding_box_mm=(face.bounding_box_mm[1], face.bounding_box_mm[0]))
    with pytest.raises(ValueError, match="Every actual face edge"):
        replace(face, edge_ids=(1, 2, 3))
    bad = face.loops[0][:-1] + (NativeEdgeUse(4, 4, 99),)
    with pytest.raises(ValueError, match="positions cannot weld"):
        replace(face, loops=(bad,))


def test_wrong_branch_foreign_sources_and_stale_replacements_remain_unqualified() -> None:
    """
    Boundary coefficient enclosures and exact ownership are independent mandatory gates.
    """
    face, chart, boundary = fixture()
    result = certify(face, chart, boundary, checkpoint)
    with pytest.raises(ValueError, match="SAME actual compact"):
        replace(result, face=replace(face))
    foreign = replace(boundary[0], native=replace(face.native))
    with pytest.raises(ValueError, match="SAME native compact"):
        certify(face, chart, (foreign,) + boundary[1:], checkpoint)
    back = replace(boundary[0], controls=((Fraction(0), Fraction(-1), Fraction(0)),) * 3)
    assert (
        certify(face, chart, (back,) + boundary[1:], checkpoint).status
        == "unresolved_native_boundary_branch"
    )


def test_resource_stop_prevents_filled_domain_acceptance() -> None:
    """
    Whole-boundary traversal and nonlinear window proof remain under one shared caller allocation.
    """
    face, chart, boundary = fixture()
    calls = 0

    def stop() -> None:
        """
        Stop while beginning the first boundary enclosure.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("filled domain allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        certify(face, chart, boundary, stop)
