"""
Mark unsuccessful diagnostic candidates with conspicuous camera-facing red circles.

These display-only outlines enclose frozen route controls and fixed targets. They
are neither clearance envelopes nor additional physical acceptance criteria.
"""

from __future__ import annotations

import math
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .api import Evidence
from .graphics import set_color
from .provenance import mark_loaded


def outline_bounds(evidence: Evidence) -> tuple[Vector3, float]:
    """
    Enclose cubic control hulls and target widths with a padded bounding sphere.

    Its camera-facing great circle encloses every orthographic route projection;
    perspective views remain illustrative. Return local millimeter center/radius.
    """
    points = [point for guide in evidence.guides for point in guide.controls]
    case = evidence.targets
    half = case.lines * case.diameter_mm / 2
    for point, width in ((case.start, case.start_width), (case.end, case.end_width)):
        points.extend((point.translated(width, -half), point.translated(width, half)))
    center = Vector3(
        *(
            (min(getattr(p, axis) for p in points) + max(getattr(p, axis) for p in points)) / 2
            for axis in ("x", "y", "z")
        )
    )
    radius = max(magnitude(difference(point, center)) for point in points)
    return center, radius + max(radius * 0.35, half * 2, case.diameter_mm)


def retain_failure_marker(component: Any, evidence: Evidence, reason: str) -> Any:
    """
    Add or reuse one visible outline for an explicitly failed/unresolved outcome.

    Reuse preserves manual visibility. Identity includes the evidence fingerprint;
    callers must not replace old snapshots with a different solve under this API.
    No solver, analysis, native sketch or BRep operation is performed.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A failure or unresolved-outcome reason is required.")
    name = f"Failure outline - {evidence.identifier} - {evidence.fingerprint}"
    groups = component.customGraphicsGroups
    for index in range(groups.count):
        existing = groups.item(index)
        if existing.name == name:
            if existing.count != 1:
                raise RuntimeError(
                    "Existing failure outline is incomplete; inspect before retrying."
                )
            return existing
    center, radius = outline_bounds(evidence)
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("Failure outline requires finite positive bounds.")
    anchor = adsk.core.Point3D.create(center.x / 10, center.y / 10, center.z / 10)
    origin = adsk.core.Point3D.create(0, 0, 0)
    circle = adsk.core.Circle3D.createByCenter(
        origin, adsk.core.Vector3D.create(0, 0, 1), radius / 10
    )
    group = groups.add()
    group.name = name
    curve = group.addCurve(circle)
    curve.name = f"{evidence.identifier}: {reason} (display marker only)"
    curve.weight = 6
    curve.depthPriority = 100
    placement = adsk.core.Matrix3D.create()
    placement.translation = anchor.asVector()
    curve.transform = placement
    curve.billBoarding = adsk.fusion.CustomGraphicsBillBoard.create(origin)
    set_color(curve, (255, 0, 0))
    return group


mark_loaded(__file__)
