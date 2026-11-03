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
    *, extra: bool = False, raw: bool = True, measured_error: float = 0.0
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


def test_error_and_query_budgets_never_turn_missing_evidence_into_success() -> None:
    """
    Reject actual projection error and propagate bounded native-query exhaustion.
    """
    collection, _ = _collection()
    assert not collection.item(0).getParameterAtPoint(Point(1, 0.5, 2e-7))[0]
    collection.queries = 30000
    with pytest.raises(RuntimeError, match="face-query budget"):
        collection.item(0).getParameterAtPoint(Point(1, 0.5))
