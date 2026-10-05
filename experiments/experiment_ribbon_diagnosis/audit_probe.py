"""
Retain independent containment evidence at the existing auditor's first finding.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing import RibbonShape, RoutePreview, Vector3
from cable_bundler.routing.geometry import difference, dot, unit
from experiments.experiment_secure_discrete_ribbon.audits import (
    AuditFailure,
    _planned_lane_reference,
)


def _point(point: Vector3) -> adsk.core.Point3D:
    """
    Convert routing millimeters to native Fusion centimeters.
    """
    return adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)


def _containment(body: adsk.fusion.BRepBody, point: Vector3) -> str:
    """
    Ask the solid directly, independently of the wire bounding-box heuristic.
    """
    result = body.pointContainment(_point(point))
    kinds = adsk.fusion.PointContainment
    for name in (
        "PointInsidePointContainment",
        "PointOutsidePointContainment",
        "PointOnPointContainment",
        "UnknownPointContainment",
    ):
        if hasattr(kinds, name) and result == getattr(kinds, name):
            return name
    return str(result)


@dataclass
class SectionAuditProbe:
    """
    Preserve the original verdict and add measurements without changing the body.
    """

    original: Callable[..., dict[str, int]]
    findings: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        body: adsk.fusion.BRepBody,
        route: RoutePreview,
        expected_edges: int | None,
        shape: RibbonShape | None = None,
    ) -> dict[str, int]:
        """
        Probe the reported station even when the main section audit rejects it.
        """
        try:
            return self.original(body, route, expected_edges, shape)
        except AuditFailure as error:
            record: dict[str, object] = {"error": str(error), "body": body.name}
            self.findings.append(record)
            match = re.match(r"Cubic (\d+)/(\d+) station (\d+)/40", str(error))
            if match is not None:
                try:
                    self._witness(
                        record,
                        body,
                        route,
                        shape,
                        int(match.group(1)) - 1,
                        int(match.group(3)) / 40,
                    )
                except (AttributeError, RuntimeError, TypeError, ValueError) as probe_error:
                    record["probe_error"] = str(probe_error)
            raise

    @staticmethod
    def _witness(
        record: dict[str, object],
        body: adsk.fusion.BRepBody,
        route: RoutePreview,
        shape: RibbonShape | None,
        curve_index: int,
        parameter: float,
    ) -> None:
        """
        Measure the failed station; unavailable diagnostics never replace its verdict.
        """
        curve = route.curves[curve_index]
        point = curve.point(parameter)
        tangent = unit(curve.derivative(parameter))
        reference = _planned_lane_reference(shape, point) if shape is not None else point
        reference = reference.translated(tangent, -dot(difference(reference, point), tangent))
        record.update(
            route_point_mm=(point.x, point.y, point.z),
            audit_reference_mm=(reference.x, reference.y, reference.z),
            route_point_containment=_containment(body, point),
            audit_reference_containment=_containment(body, reference),
            solid=body.isSolid,
        )
        plane = adsk.core.Plane.create(
            _point(point), adsk.core.Vector3D.create(tangent.x, tangent.y, tangent.z)
        )
        section = adsk.fusion.TemporaryBRepManager.get().planeIntersection(body, plane)
        record["wire_edge_counts"] = (
            [] if section is None else [wire.edges.count for wire in section.wires]
        )
