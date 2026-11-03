"""
Recognize bounded shared-edge precision warnings without clearing strict audit failures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SeamPrecisionWarning:
    """
    Retain strict seam discrepancies below Fusion's live point tolerance for diagnostic display.
    """

    seam_count: int
    maximum_error_mm: float
    point_tolerance_mm: float

    @property
    def message(self) -> str:
        """
        Describe the measured warning without claiming the strict seam audit passed.
        """
        return (
            f"Native precision warning: {self.seam_count} connected single-edge seams exceed "
            f"the strict 1e-6 mm endpoint check; maximum {self.maximum_error_mm:.6g} mm "
            f"is within Fusion point tolerance {self.point_tolerance_mm:.6g} mm. "
            "Surface, ordered guides and caps pass; strict seam findings are retained."
        )


def _within(value: Any, limit: float) -> bool:
    """
    Reject absent, boolean, nonfinite and negative external measurements.
    """
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= limit


def seam_precision_warning(
    audit: dict[str, Any], point_tolerance_mm: float, revision: str
) -> SeamPrecisionWarning | None:
    """
    Classify only complete fixed-revision audits with bounded single-edge endpoint failures.

    The base audit still runs and raises at its original strict gate. A positive
    endpoint residual in its direct-edge record is emitted only after proving a
    connected, unbranched, two-tip shared chain. Require exactly one shared edge;
    missing topology, merged-face failures and incomplete audits remain hard stops.
    Every original surface, ordered guide and cap threshold remains unchanged.
    No audit record or native geometry is modified. None means display is refused.
    """
    if (
        not _within(point_tolerance_mm, math.inf)
        or point_tolerance_mm <= 1e-6
        or not revision
        or audit.get("body_revision_after") != revision
        or audit.get("failed_points") != []
        or not _within(audit.get("maximum_error_mm"), 1e-6)
        or any(
            type(audit.get(key)) is not int or audit[key] <= 0
            for key in (
                "native_points_checked",
                "patches_audited",
                "seams_checked",
                "native_face_count",
            )
        )
    ):
        return None
    for key, limit in (
        ("guide_maximum_position_error_mm", 1e-6),
        ("guide_maximum_tangent_error_degrees", 0.001),
    ):
        values = audit.get(key)
        if not isinstance(values, dict) or set(values) != {"left", "center", "right"}:
            return None
        if not all(_within(value, limit) for value in values.values()):
            return None
    caps = audit.get("caps")
    if not isinstance(caps, list) or len(caps) != 2 or any(not isinstance(c, dict) for c in caps):
        return None
    if any(cap.get("side") not in ("start", "end") for cap in caps):
        return None
    if {cap["side"] for cap in caps} != {"start", "end"}:
        return None
    if any(
        not _within(cap.get(key), limit)
        for cap in caps
        for key, limit in (
            ("center_error_mm", 1e-6),
            ("ordered_width_error_degrees", 0.001),
            ("outward_normal_error_degrees", 0.001),
        )
    ):
        return None
    seams = audit.get("seam_failures")
    if not isinstance(seams, list) or not seams or len(seams) > audit["seams_checked"]:
        return None
    errors = []
    for seam in seams:
        if (
            not isinstance(seam, dict)
            or type(seam.get("edge_count")) is not int
            or seam["edge_count"] != 1
            or "kind" in seam
        ):
            return None
        faces = seam.get("faces")
        if (
            not isinstance(faces, list)
            or len(faces) != 2
            or any(
                type(face) is not int or not 0 <= face < audit["native_face_count"]
                for face in faces
            )
            or faces[0] == faces[1]
        ):
            return None
        error = seam.get("endpoint_error_mm")
        if (
            not isinstance(error, (int, float))
            or not _within(error, point_tolerance_mm)
            or error <= 1e-6
        ):
            return None
        errors.append(float(error))
    return SeamPrecisionWarning(len(errors), max(errors), point_tolerance_mm)
