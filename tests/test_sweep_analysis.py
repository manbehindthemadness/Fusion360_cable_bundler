"""
Check diagnostic witness locations and capped tube topology without Fusion.
"""

from collections import Counter

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, dot, magnitude
from devtools.ribbon_analysis.tubes import (
    inspect_trace,
    transport_normal,
    tube_mesh,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.endpoint_trace_paths import TracePath
from experiments.experiment_secure_discrete_ribbon.contract import split_curve


def _straight() -> tuple[TracePath, EndpointCase]:
    """
    Supply one exact straight conductor with independently fixed target poses.
    """
    points = tuple(Vector3(i, 0, 0) for i in range(4))
    trace = TracePath(7, (CubicBezier(*points),), points, (0.0,) * 4 + (1.0,) * 4)
    case = EndpointCase(
        "straight",
        points[0],
        points[-1],
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        1,
        1.0,
    )
    return trace, case


def test_capped_mesh_is_closed_and_preserves_radius_and_targets() -> None:
    """
    Require opposite directed edge pairs and exact axial endpoints/radial size.
    """
    trace, case = _straight()
    mesh = tube_mesh(trace, case, 0, lambda: None)
    edges: Counter[tuple[int, int]] = Counter()
    for i in range(0, len(mesh.triangles), 3):
        a, b, c = mesh.triangles[i : i + 3]
        edges.update(((a, b), (b, c), (c, a)))
    assert all(count == 1 and edges[(b, a)] == 1 for (a, b), count in edges.items())
    vertices = list(zip(*(iter(mesh.vertices),) * 3))
    for x, y, z in vertices[:-2]:
        assert x in (0, 3)
        assert (y * y + z * z) ** 0.5 == pytest.approx(0.5)
    assert mesh.points == (case.start, case.end)
    assert mesh.length_mm == 3
    assert mesh.midpoint_chord_error_mm == 0
    assert not mesh.hot_triangles
    assert all(w.severity == "measured" for w in mesh.witnesses)


def test_tight_bend_is_located_and_colored_without_repair() -> None:
    """
    A sampled radius violation must identify its trace and mark its mesh interval.
    """
    points = (Vector3(0, 0, 0), Vector3(0, 1, 0), Vector3(1, 1, 0), Vector3(1, 0, 0))
    trace = TracePath(4, (CubicBezier(*points),), points, (0.0,) * 4 + (1.0,) * 4)
    case = EndpointCase(
        "tight",
        points[0],
        points[-1],
        Vector3(0, 1, 0),
        Vector3(0, -1, 0),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
        1,
        0.3,
    )
    witnesses, _ = inspect_trace(trace, case, 0, lambda: None)
    witness = next(w for w in witnesses if w.kind == "lane curvature x 3D")
    assert witness.trace == 4
    assert witness.fraction == 0.5
    assert witness.point == Vector3(0.5, 0.75, 0)
    assert witness.value == pytest.approx(2.4)
    assert witness.severity == "red"
    with pytest.raises(ValueError, match="Opposed"):
        tube_mesh(trace, case, 0, lambda: None)
    subdivided = TracePath(4, split_curve(trace.curves[0]), points, trace.knots)
    mesh = tube_mesh(subdivided, case, 0, lambda: None)
    assert mesh.hot_triangles
    assert mesh.midpoint_chord_error_mm > 0.02 * case.diameter_mm
    assert trace.controls == points


def test_endpoint_residual_is_measured_against_fixed_input() -> None:
    """
    Displayed geometry may miss its fixed target without silently moving that target.
    """
    trace, case = _straight()
    moved = tuple(p.translated(Vector3(0, 0, 1), 2) for p in trace.controls)
    wrong = TracePath(trace.number, (CubicBezier(*moved),), moved, trace.knots)
    witnesses, _ = inspect_trace(wrong, case, 0, lambda: None)
    residual = next(w for w in witnesses if w.kind == "target error mm")
    assert residual.value == 2
    assert residual.severity == "red"
    assert residual.trace == 7
    assert case.start == Vector3(0, 0, 0)
    assert case.end == Vector3(3, 0, 0)


def test_transport_keeps_orthonormal_frame_and_rejects_opposed_tangents() -> None:
    """
    Transport across a quarter turn without artificial roll or a hidden cusp fix.
    """
    x, y, z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)
    normal = transport_normal(x, y, z)
    assert magnitude(normal) == pytest.approx(1)
    assert dot(normal, y) == pytest.approx(0)
    assert normal == z
    with pytest.raises(ValueError, match="Opposed"):
        transport_normal(x, Vector3(-1, 0, 0), z)
