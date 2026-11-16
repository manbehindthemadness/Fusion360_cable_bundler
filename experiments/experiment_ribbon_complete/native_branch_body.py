"""
Construct transient closed branch bodies from unchanged exact rational patch plans.

Native construction is diagnostic until material, contact, junction and complete
structure checks qualify the same geometry. No document persistence occurs here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cable_bundler.routing.geometry import cross, unit

from .branch_plan import SpatialBranchPlan
from .branch_reference import validate_patches
from .branch_shell_topology import EdgeKey, loops
from .native_branch_surface import NativeSurfaceGrid
from .native_branch_surface import create as create_surface
from .spatial_frame import ChartOrientation


@dataclass(frozen=True)
class NativeBranchBody:
    """
    Preserve body/source identity and kernel diagnostics without physical acceptance.
    """

    source: SpatialBranchPlan
    body: Any
    outcome_info: tuple[str, ...]


def build(plan: SpatialBranchPlan, checkpoint: Callable[[], None]) -> NativeBranchBody:
    """
    Author one shared-edge closed shell and call the native kernel exactly once.

    Shared source boundaries must agree exactly before SDK authoring. Their
    float conversion is shared, not healed or merged by distance. Preserve all
    nonseparable weights, orientation and spans. A refusal retains kernel outcome
    information and raises without retries or fallback construction.
    """
    checkpoint()
    frames = validate_patches(plan.patches, checkpoint)
    spans, count = len(plan.patches), len(plan.patches[0])
    orientation = frames[0].orientation
    incidence = loops(spans, count, orientation, checkpoint)
    for span_index, span in enumerate(plan.patches):
        checkpoint()
        for edge_index, patch in enumerate(span):
            following = span[(edge_index + 1) % count]
            if tuple(row[-1] for row in patch.rows) != tuple(row[0] for row in following.rows):
                raise ValueError("Branch patches need exact shared longitudinal boundaries")
            if span_index and plan.patches[span_index - 1][edge_index].rows[-1] != patch.rows[0]:
                raise ValueError("Branch spans need exact shared station boundaries")
    grids = tuple(
        tuple(NativeSurfaceGrid(p.rows, checkpoint) for p in span) for span in plan.patches
    )
    checkpoint()
    # noinspection PyUnresolvedReferences
    import adsk.core

    # noinspection PyUnresolvedReferences
    import adsk.fusion

    definition = adsk.fusion.BRepBodyDefinition.create()
    definition.doFullHealing = False
    shell = definition.lumpDefinitions.add().shellDefinitions.add()
    vertices = {}
    for station in range(spans + 1):
        checkpoint()
        for edge in range(count):
            grid = grids[min(station, spans - 1)][edge]
            point = grid.points_cm[0 if station < spans else -len(grid.rows[0])]
            vertices[station, edge] = definition.createVertexDefinition(
                adsk.core.Point3D.create(point.x, point.y, point.z)
            )
    boundaries: dict[EdgeKey, Any] = {}
    for uses in incidence:
        for use in uses:
            checkpoint()
            if use.key in boundaries:
                continue
            kind, index, edge = use.key
            grid = grids[min(index, spans - 1)][edge]
            n, m = len(grid.rows), len(grid.rows[0])
            if kind == "along":
                indices = tuple(i * m for i in range(n))
                start, end = vertices[index, edge], vertices[index + 1, edge]
            else:
                low = 0 if index < spans else (n - 1) * m
                indices = tuple(range(low, low + m))
                start, end = vertices[index, edge], vertices[index, (edge + 1) % count]
            points = [grid.points_cm[i] for i in indices]
            curve = adsk.core.NurbsCurve3D.createRational(
                [adsk.core.Point3D.create(p.x, p.y, p.z) for p in points],
                len(points) - 1,
                [0.0] * len(points) + [1.0] * len(points),
                [grid.weights[i] for i in indices],
                False,
            )
            if curve is None:
                raise RuntimeError("Native branch boundary curve creation failed")
            boundary = definition.createEdgeDefinitionByCurve(start, end, curve)
            if boundary is None:
                raise RuntimeError("Native branch edge definition failed")
            boundary.associativeID = 10000 + len(boundaries)
            boundary.isMergeable = False
            boundaries[use.key] = boundary
    for index, uses in enumerate(incidence):
        checkpoint()
        if index < spans * count:
            surface = create_surface(grids[index // count][index % count], checkpoint)
            reversed_surface = orientation is ChartOrientation.NEGATIVE
        else:
            first = index == spans * count
            frame = frames[0] if first else frames[-1]
            point = frame.center[0 if first else -1]
            width, thickness = frame.width[0 if first else -1], frame.thickness[0 if first else -1]
            normal = unit(cross(width, thickness))
            sign = orientation.value * (-1 if first else 1)
            surface = adsk.core.Plane.create(
                adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10),
                adsk.core.Vector3D.create(normal.x * sign, normal.y * sign, normal.z * sign),
            )
            reversed_surface = False
        face = shell.faceDefinitions.add(surface, reversed_surface)
        if face is None:
            raise RuntimeError("Native branch face definition failed")
        face.associativeID = index + 1
        loop = face.loopDefinitions.add()
        for use in uses:
            loop.bRepCoEdgeDefinitions.add(boundaries[use.key], use.opposed)
    checkpoint()
    body = definition.createBody()
    outcome = tuple(definition.outcomeInfo)
    if body is None:
        raise RuntimeError(f"Native branch body creation failed: {outcome}")
    checkpoint()
    return NativeBranchBody(plan, body, outcome)
