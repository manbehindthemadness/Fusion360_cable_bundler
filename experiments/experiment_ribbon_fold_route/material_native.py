"""
Author one joined BRep from prescribed material surfaces, without a free sweep.

Fusion supplies adsk. This experimental constructor does not change production
builders. Full healing, side relabeling and corrective post-processing are disabled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .geometry import PlacedPiece
from .material_surfaces import MaterialPatch


def native_point(point: Vector3) -> Any:
    """
    Convert planned millimetres to Fusion centimetres once at the API boundary.
    """
    return adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)


def native_surface(patch: MaterialPatch) -> Any:
    """
    Retain the supplied tensor controls, rational profile weights and phase knots.
    """
    count = len(patch.rows)
    surface = adsk.core.NurbsSurface.create(
        patch.degree_u,
        2,
        count,
        3,
        [native_point(point) for row in patch.rows for point in row],
        list(patch.knots_u),
        [0, 0, 0, 1, 1, 1],
        [weight for _ in patch.rows for weight in patch.profile.weights],
        adsk.core.NurbsSurfaceProperties.OpenNurbsSurface
        | adsk.core.NurbsSurfaceProperties.RationalNurbsSurface,
        adsk.core.NurbsSurfaceProperties.OpenNurbsSurface
        | adsk.core.NurbsSurfaceProperties.RationalNurbsSurface,
    )
    if surface is None:
        raise RuntimeError("Native material surface creation failed.")
    # Verify API grid convention before paying for a complete body definition.
    for u, row in ((patch.knots_u[0], patch.rows[0]), (patch.knots_u[-1], patch.rows[-1])):
        for v, point in ((0.0, row[0]), (1.0, row[-1])):
            ok, actual = surface.evaluator.getPointAtParameter(adsk.core.Point2D.create(u, v))
            if not ok or actual.distanceTo(native_point(point)) * 10 > 1e-9:
                raise RuntimeError("Native surface parameter convention mismatch.")
    return surface


@dataclass(frozen=True)
class NativeMaterialDefinition:
    """
    Retain authored topology and provenance before a single kernel construction.
    """

    definition: Any
    face_records: tuple[dict[str, Any], ...]
    collapsed_tip_edges: int


def define_material_body(
    pieces: tuple[PlacedPiece, ...],
    patches: tuple[MaterialPatch, ...],
    checkpoint: Callable[[], None],
) -> NativeMaterialDefinition:
    """
    Share exact station and longitudinal edges across a closed oriented shell.

    Only corresponding vertices at consecutive stations may coincide. Zero
    material-tip lead edges are omitted explicitly; their side faces have three
    coedges. Unrelated nearby points are never merged by proximity.
    """
    definition = adsk.fusion.BRepBodyDefinition.create()
    definition.doFullHealing = False
    shell = definition.lumpDefinitions.add().shellDefinitions.add()
    count = 1 + max(patch.profile_index for patch in patches)
    groups = [patches[i : i + count] for i in range(0, len(patches), count)]
    records = []
    edge_id = 10000
    collapsed = 0

    def edge(
        start: Any,
        end_vertex: Any,
        points: tuple[Vector3, ...],
        degree: int,
        knots: tuple[float, ...],
        weights: tuple[float, ...] | None = None,
    ) -> Any:
        """
        Define a persistent edge once; never allow merging to erase side provenance.
        """
        nonlocal edge_id
        if start == end_vertex:
            return None
        native_points = [native_point(p) for p in points]
        curve = (
            adsk.core.NurbsCurve3D.createNonRational(native_points, degree, list(knots), False)
            if weights is None
            else adsk.core.NurbsCurve3D.createRational(
                native_points, degree, list(knots), list(weights), False
            )
        )
        if curve is None:
            raise RuntimeError("Native material edge creation failed.")
        result = definition.createEdgeDefinitionByCurve(start, end_vertex, curve)
        result.associativeID = edge_id
        result.isMergeable = False
        edge_id += 1
        return result

    def station(
        station_group: tuple[MaterialPatch, ...], last: bool, previous: list[Any] | None = None
    ) -> tuple[list[Any], list[Any]]:
        """
        Reuse only collapsed consecutive material vertices, keeping contour order.
        """
        row_index = -1 if last else 0
        station_vertices = []
        for i, patch in enumerate(station_group):
            position = patch.rows[row_index][0]
            if (
                previous is not None
                and previous[i].position.distanceTo(native_point(position)) * 10 < 1e-10
            ):
                station_vertices.append(previous[i])
            else:
                station_vertices.append(definition.createVertexDefinition(native_point(position)))
        edges = [
            edge(
                station_vertices[i],
                station_vertices[(i + 1) % count],
                patch.rows[row_index],
                2,
                (0, 0, 0, 1, 1, 1),
                patch.profile.weights,
            )
            for i, patch in enumerate(station_group)
        ]
        return station_vertices, edges

    vertices, first_edges = station(groups[0], False)
    previous_edges = first_edges
    for group_number, group in enumerate(groups):
        checkpoint()
        # A shared material cap must agree before native topology is authored.
        for i, patch in enumerate(group):
            if vertices[i].position.distanceTo(native_point(patch.rows[0][0])) * 10 > 1e-9:
                raise RuntimeError("Material station continuity mismatch.")
            following = group[(i + 1) % count]
            if magnitude(difference(patch.rows[0][-1], following.rows[0][0])) > 1e-9:
                raise RuntimeError("Material contour continuity mismatch.")
        next_vertices, next_edges = station(group, True, vertices)
        longitudinal = [
            edge(
                vertices[i],
                next_vertices[i],
                tuple(row[0] for row in patch.rows),
                patch.degree_u,
                patch.knots_u,
            )
            for i, patch in enumerate(group)
        ]
        collapsed += sum(item is None for item in longitudinal)
        for i, patch in enumerate(group):
            face = shell.faceDefinitions.add(native_surface(patch), False)
            face.associativeID = 1 + group_number * count + i
            loop = face.loopDefinitions.add()
            for boundary, opposed in (
                (longitudinal[i], False),
                (next_edges[i], False),
                (longitudinal[(i + 1) % count], True),
                (previous_edges[i], True),
            ):
                if boundary is not None:
                    loop.bRepCoEdgeDefinitions.add(boundary, opposed)
            records.append(
                {
                    "associative_id": face.associativeID,
                    "piece_index": patch.piece_index,
                    "region": patch.region,
                    "profile_index": i,
                    "label": patch.profile.label,
                }
            )
        vertices, previous_edges = next_vertices, next_edges
    for end, boundaries, pose in (
        (False, first_edges, pieces[0].pose),
        (True, previous_edges, pieces[-1].end_pose()),
    ):
        normal = pose.tangent
        plane = adsk.core.Plane.create(
            native_point(pose.origin),
            adsk.core.Vector3D.create(
                normal.x * (1 if end else -1),
                normal.y * (1 if end else -1),
                normal.z * (1 if end else -1),
            ),
        )
        face = shell.faceDefinitions.add(plane, False)
        face.associativeID = 9001 if end else 9000
        loop = face.loopDefinitions.add()
        for boundary in reversed(boundaries) if end else boundaries:
            loop.bRepCoEdgeDefinitions.add(boundary, end)
        records.append({"associative_id": face.associativeID, "region": "end" if end else "start"})
    return NativeMaterialDefinition(definition, tuple(records), collapsed)
