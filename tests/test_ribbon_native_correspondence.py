"""
Verify real face-family coverage and strict geometric rejection without a Fusion session.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.material_surfaces import MaterialPatch
from experiments.experiment_ribbon_locked_solver.accuracy import (
    DISPLAY_ACCURACY,
    STRICT_ACCURACY,
    DimensionalAccuracy,
)
from experiments.experiment_ribbon_locked_solver.correspondence import MaterialFaces


# Native test-double method names mirror Fusion's public API.
# noinspection PyPep8Naming
@dataclass
class Point:
    """
    Model native centimeter points for independent projection/distance assertions.
    """

    x: float
    y: float
    z: float = 0.0

    def distanceTo(self, other: Point) -> float:
        """
        Measure native-space Euclidean distance without returning the expected point.
        """
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))

    def copy(self) -> Point:
        """
        Preserve the original query when assembly-space measurement transforms its copy.
        """
        return Point(self.x, self.y, self.z)

    def transformBy(self, matrix: Any) -> bool:
        """
        Model the identity assembly transform used by these boundary tests.
        """
        return matrix is None and all(math.isfinite(v) for v in (self.x, self.y, self.z))


def _face(x0: float, x1: float, y0: float, y1: float, raw: bool = True) -> Any:
    """
    Supply a trimmed planar native face whose inverse evaluates its own real support.
    """
    evaluator = SimpleNamespace(
        getParameterAtPoint=lambda p: (True, (p.x, p.y)),
        getPointAtParameter=lambda uv: (True, Point(*uv)),
        isParameterOnFace=lambda uv: raw and x0 <= uv[0] <= x1 and y0 <= uv[1] <= y1,
        getNormalAtPoint=lambda p: (True, Point(0, 0, 1)),
    )
    face = SimpleNamespace(
        boundingBox=SimpleNamespace(minPoint=Point(x0, y0), maxPoint=Point(x1, y1)),
        evaluator=evaluator,
        geometry=SimpleNamespace(objectType="plane"),
        edges=[],
    )
    face.createForAssemblyContext = lambda occurrence: face
    return face


def _collection(
    *,
    extra: bool = False,
    raw: bool = True,
    measured_error: float = 0.0,
    accuracy: DimensionalAccuracy = STRICT_ACCURACY,
    collapsed_boundary_tolerance_mm: float | None = None,
) -> tuple[MaterialFaces, list[Any]]:
    """
    Model two authored regions merged into one native profile face, plus another profile and caps.
    """
    faces = [
        _face(0, 4, 0, 1, raw),
        _face(0, 4, 1, 2),
        _face(-1.1, -0.9, 0, 1),
        _face(4.9, 5.1, 0, 1),
    ]
    if extra:
        faces.append(_face(10, 11, 0, 1))
    body = SimpleNamespace(
        faces=SimpleNamespace(count=len(faces), item=lambda i: faces[i]), isSolid=True, volume=1.0
    )
    patches = cast(
        tuple[MaterialPatch, ...],
        cast(
            object,
            tuple(
                SimpleNamespace(
                    profile_index=profile,
                    piece_index=i,
                    region="straight",
                    profile=SimpleNamespace(label=f"profile-{profile}"),
                )
                for i, profile in enumerate((0, 0, 1))
            ),
        ),
    )
    route = cast(
        FoldRoute,
        cast(
            object,
            SimpleNamespace(targets=SimpleNamespace(start=Point(-1, 0.5), end=Point(5, 0.5))),
        ),
    )
    output: dict[str, Any] = {}
    collection = MaterialFaces(
        body,
        route,
        patches,
        SimpleNamespace(transform2=None),
        Mock(),
        lambda p: p,
        lambda point, entity: measured_error,
        output,
        accuracy=accuracy,
        collapsed_boundary_tolerance_mm=collapsed_boundary_tolerance_mm,
    )
    return collection, faces


def _cover(collection: MaterialFaces) -> None:
    """
    Establish all three authored interior regions before validating real cap coverage.
    """
    assert collection.item(0).getParameterAtPoint(Point(1, 0.5))[0]
    assert collection.item(1).getParameterAtPoint(Point(3, 0.5))[0]
    assert collection.item(2).getParameterAtPoint(Point(1, 1.5))[0]


def test_merged_regions_keep_real_geometry_and_unique_profile_ownership() -> None:
    """
    Preserve all physical faces and multi-region provenance without inventing native entities.
    """
    collection, faces = _collection()
    _cover(collection)
    collection.seal_surfaces()
    records = collection.records()
    assert collection.count == 5 and len(faces) == len(records) == 4
    assert collection.shared(0, 1)
    assert len(records[0]["sources"]) == 2
    assert records[0]["profile_index"] == 0
    assert not collection.shared(0, 2)
    family = collection.item(0)
    ok, uv = family.getParameterAtPoint(Point(1, 0.5, 5e-8))
    assert ok and family.isParameterOnFace(uv)
    assert family.getPointAtParameter(uv)[1].z == 0.0


def test_cross_profile_queries_and_missing_native_coverage_reject() -> None:
    """
    Never relabel a claimed native face to another conductor or ignore an extra face.
    """
    collection, _ = _collection(extra=True)
    _cover(collection)
    assert not collection.item(2).getParameterAtPoint(Point(1, 0.5))[0]
    with pytest.raises(RuntimeError, match="Uncovered native faces"):
        collection.seal_surfaces()


@pytest.mark.parametrize("error, accepted", ((5e-7, True), (2e-6, False)))
def test_raw_membership_failure_requires_independent_trimmed_distance(
    error: float, accepted: bool
) -> None:
    """
    Preserve the1e-6mm physical gate even when native parameter membership is ambiguous.
    """
    collection, _ = _collection(raw=False, measured_error=error)
    assert collection.item(0).getParameterAtPoint(Point(1, 0.5))[0] is accepted
    records = collection.output["face_correspondence"]["trim_distance_corroborations"]
    assert records and records[-1]["distance_mm"] == error
    assert records[-1]["raw_membership"] is False


def test_shared_edge_subsegment_requires_real_edge_distance() -> None:
    """
    Admit a shorter source boundary on a real shared edge, rejecting an off-edge witness.
    """
    collection, faces = _collection()
    edge = SimpleNamespace(tempId=99, createForAssemblyContext=lambda occurrence: "actual-edge")
    faces[0].edges = faces[1].edges = [edge]
    _cover(collection)
    collection.seal_surfaces()
    points = (Point(0.3, 1), Point(3.7, 1))
    assert collection.edge_seam_error(0, 2, points) == 0.0
    collection.distance = lambda point, entity: 2e-6
    assert collection.edge_seam_error(0, 2, points) > 1e-6
    faces[1].edges = []
    assert math.isinf(collection.edge_seam_error(0, 2, points))


def _vertex_boundary(faces: list[Any], connected: bool) -> None:
    """
    Give neighboring faces one shared vertex identity or geometrically coincident separate vertices.
    """
    common = SimpleNamespace(tempId=71, geometry=Point(1, 1))
    other = common if connected else SimpleNamespace(tempId=72, geometry=Point(1, 1))
    faces[0].edges = [SimpleNamespace(tempId=90, startVertex=common, endVertex=common)]
    faces[1].edges = [SimpleNamespace(tempId=91, startVertex=other, endVertex=other)]


@pytest.mark.parametrize("connected", (True, False))
def test_collapsed_seam_requires_a_real_shared_vertex_and_strict_control_hull(
    connected: bool,
) -> None:
    """
    Admit a sub-goal kernel vertex boundary, rejecting coincident but topologically separate vertices.
    """
    collection, faces = _collection(accuracy=DISPLAY_ACCURACY)
    _vertex_boundary(faces, connected)
    _cover(collection)
    collection.seal_surfaces()
    controls = (Point(1, 1), Point(1 + 4.708e-8, 1))
    residual = collection.edge_seam_error(0, 2, controls, controls=controls)
    assert (residual <= 1e-6) is connected
    records = collection.output["face_correspondence"]["native_vertex_boundaries"]
    assert bool(records) is connected
    if connected:
        assert records[-1]["vertex"] == 71 and records[-1]["control_hull_bound_mm"] == residual
    # A source curve can leave the point even when its endpoints coincide.
    outside = (*controls, Point(1 + 1e-5, 1))
    assert math.isinf(collection.edge_seam_error(0, 2, controls, controls=outside))
    assert math.isinf(collection.edge_seam_error(0, 2, controls))


@pytest.mark.parametrize("accuracy", (STRICT_ACCURACY, DISPLAY_ACCURACY))
@pytest.mark.parametrize("connected", (True, False))
def test_kernel_collapsed_seam_retains_goal_miss_without_waiving_topology(
    accuracy: DimensionalAccuracy, connected: bool
) -> None:
    """
    Permit a real2.261nm collapse only under the warning policy and explicit10nm kernel bound.
    """
    collection, faces = _collection(accuracy=accuracy, collapsed_boundary_tolerance_mm=1e-5)
    _vertex_boundary(faces, connected)
    _cover(collection)
    collection.seal_surfaces()
    controls = (Point(1, 1), Point(1 + 2.261e-7, 1))
    residual = collection.edge_seam_error(0, 2, controls, controls=controls)
    accepted = connected and accuracy is DISPLAY_ACCURACY
    assert math.isfinite(residual) is accepted
    if accepted:
        assert residual == pytest.approx(2.261e-6)
        assert accuracy.observe(collection.output, "seam", residual, faces=[0, 2])
        warning = collection.output["accuracy_warnings"][-1]
        assert warning["goal_mm"] == 1e-6 and warning["error_mm"] == residual
        record = collection.output["face_correspondence"]["native_vertex_boundaries"][-1]
        assert record["collapsed_boundary_tolerance_mm"] == 1e-5
    # The display ceiling cannot license a source hull beyond native collapse precision.
    outside = (*controls, Point(1 + 2e-6, 1))
    assert math.isinf(collection.edge_seam_error(0, 2, controls, controls=outside))


def test_collapsed_seam_rejects_nonfinite_control_distances() -> None:
    """
    Check every control rather than allowing a NaN to disappear inside a maximum reduction.
    """
    collection, faces = _collection()
    vertex = SimpleNamespace(tempId=71, geometry=Point(1, 1))
    faces[0].edges = [SimpleNamespace(tempId=90, startVertex=vertex, endVertex=vertex)]
    faces[1].edges = [SimpleNamespace(tempId=91, startVertex=vertex, endVertex=vertex)]
    _cover(collection)
    collection.seal_surfaces()
    points = (Point(1, 1),)
    assert math.isinf(
        collection.edge_seam_error(0, 2, points, controls=(*points, Point(math.nan, 1)))
    )


def test_error_and_query_budgets_never_turn_missing_evidence_into_success() -> None:
    """
    Reject actual projection error and propagate bounded native-query exhaustion.
    """
    collection, _ = _collection()
    assert not collection.item(0).getParameterAtPoint(Point(1, 0.5, 2e-7))[0]
    collection.queries = 30000
    with pytest.raises(RuntimeError, match="face-query budget"):
        collection.item(0).getParameterAtPoint(Point(1, 0.5))


@pytest.mark.parametrize("error,accepted", [(0.005, True), (0.0099999, True), (0.01, False)])
def test_display_policy_uses_the_same_exclusive_bound_for_trim_distance(
    error: float, accepted: bool
) -> None:
    """
    Corroborated native trim distance uses the policy and retains every accepted goal miss.
    """
    collection, _ = _collection(raw=False, measured_error=error, accuracy=DISPLAY_ACCURACY)
    assert collection.item(0).getParameterAtPoint(Point(1, 0.5))[0] is accepted
    warnings = collection.output.get("accuracy_warnings", [])
    assert bool(warnings) is accepted
    if accepted:
        assert warnings[-1]["goal_mm"] == 1e-6
        assert warnings[-1]["error_mm"] == error


def test_warning_distance_does_not_relax_face_identity_or_coverage() -> None:
    """
    A sub-limit displacement does not allow reassigning conductor profile ownership.
    """
    collection, _ = _collection(extra=True, accuracy=DISPLAY_ACCURACY)
    _cover(collection)
    family = collection.item(0)
    ok, uv = family.getParameterAtPoint(Point(1, 0.5, 0.0005))
    assert ok and family.getPointAtParameter(uv)[1].z == 0
    assert not collection.item(2).getParameterAtPoint(Point(1, 0.5, 0.0005))[0]
    with pytest.raises(RuntimeError, match="Uncovered native faces"):
        collection.seal_surfaces()


def test_verified_region_member_avoids_repeated_search_without_reusing_old_measurement() -> None:
    """
    Query each new point on the actual previously covered face and preserve exact-point caching.
    """
    collection, _ = _collection()
    collection.boxes[1] = collection.boxes[0]
    first = collection.select(0, Point(1, 0.5))
    assert first is not None and first.index == 0
    before = collection.queries
    second = collection.select(0, Point(2, 0.5))
    assert second is not None and second.index == 0 and second.error_mm == 0
    assert second.uv != first.uv
    assert collection.queries == before + 1
    assert collection.select(0, Point(2, 0.5)) is second
    assert collection.queries == before + 1


def test_member_warning_retains_full_search_for_an_original_goal_witness() -> None:
    """
    A known face meeting only display tolerance cannot displace an available strict native witness.
    """
    collection, _ = _collection(accuracy=DISPLAY_ACCURACY)
    assert collection.select(0, Point(1, 0.5)) is not None
    alternative = _face(0, 4, 0, 1)
    alternative.evaluator.getPointAtParameter = lambda uv: (True, Point(*uv, 0.0005))
    collection.native[1] = alternative
    collection.boxes[1] = ((0, 4), (0, 1), (0, 0.0005))
    selected = collection.select(0, Point(2, 0.5, 0.0005))
    assert selected is not None and selected.index == 1 and selected.error_mm == 0
    assert collection.owners[0] == collection.owners[1] == 0


def test_known_member_still_debits_the_original_native_query_budget() -> None:
    """
    Earlier verified ownership never grants a new point a free inverse or a renewed allowance.
    """
    collection, _ = _collection()
    assert collection.select(0, Point(1, 0.5)) is not None
    collection.queries = 30000
    with pytest.raises(RuntimeError, match="face-query budget"):
        collection.select(0, Point(2, 0.5))
