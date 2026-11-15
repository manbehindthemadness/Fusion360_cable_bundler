"""
Partition the unchanged joined cap into ordered split-loft roots on its actual native plane.

These roots preserve the original exterior arcs. Internal seams are shared in
opposite directions. No termination target, branch path or loft interpolation is
invented, and root correspondence alone does not certify junction flow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc, material_profile

from .capture import ACCURACY_MM, finite
from .contracts import IncompleteRibbonInput


@dataclass(frozen=True)
class RootEdge:
    """
    Retain one exact exterior arc or a newly introduced internal partition seam.
    """

    geometry: MaterialArc
    source_profile_index: int | None


@dataclass(frozen=True)
class RootProfile:
    """
    Preserve one numbered conductor's closed boundary in the original q/b material chart.
    """

    pin_number: int
    edges: tuple[RootEdge, ...]


@dataclass(frozen=True)
class CapFrame:
    """
    Bind the original material chart to an actual plane without moving fixed input targets.

    Width keeps increasing pin order. Thickness keeps the trunk's material sign
    at both ends, even though inward normals point oppositely along the route.
    Projection is native section placement, not a repair of the saved targets.
    """

    origin: Vector3
    width: Vector3
    thickness: Vector3
    inward: Vector3
    maximum_control_deviation_mm: float

    def point(self, q: float, b: float) -> Vector3:
        """
        Place an unchanged material-profile coordinate in the native cap plane.
        """
        return self.origin.translated(self.width, q).translated(self.thickness, b)


def seam(start: tuple[float, float], end: tuple[float, float], label: str) -> RootEdge:
    """
    Represent a straight partition edge in the same rational quadratic chart as the arcs.
    """
    middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    return RootEdge(MaterialArc((start, middle, end), (1.0, 1.0, 1.0), label), None)


def partition(lines: int, diameter_mm: float) -> tuple[RootProfile, ...]:
    """
    Cover the full original cap with ordered lobe partitions, including both outer side arcs.

    Adjacent profiles share only their vertical seam. Every original exterior
    segment belongs to exactly one root, including the single-conductor case.
    """
    if (
        type(lines) is not int
        or not 1 <= lines <= 128
        or type(diameter_mm) not in (int, float)
        or not math.isfinite(diameter_mm)
        or diameter_mm <= 0
    ):
        raise ValueError("A positive diameter and1..128ordered conductors are required")
    original = material_profile(lines, diameter_mm)
    by_label = {arc.label: RootEdge(arc, i) for i, arc in enumerate(original)}
    profiles = []
    for lane in range(lines):
        top, bottom = by_label[f"top-{lane}"], by_label[f"bottom-{lane}"]
        right = (
            (by_label["right-top"], by_label["right-bottom"])
            if lane == lines - 1
            else (
                seam(top.geometry.controls[-1], bottom.geometry.controls[0], f"right-seam-{lane}"),
            )
        )
        left = (
            (by_label["left-bottom"], by_label["left-top"])
            if lane == 0
            else (
                seam(bottom.geometry.controls[-1], top.geometry.controls[0], f"left-seam-{lane}"),
            )
        )
        profiles.append(RootProfile(lane + 1, (top,) + right + (bottom,) + left))
    return tuple(profiles)


def bind_frame(
    targets: Targets,
    side: Literal["start", "end"],
    plane_origin: Vector3,
    inward_normal: Vector3,
) -> CapFrame:
    """
    Use the explicitly identified actual cap plane and preserve ordered material orientation.

    Retain the qualified0.001degree cap-frame gate for consistent material-coordinate
    inversion. Position changes are bounded over the full positive-weight profile
    by its control deviations against the fixed target section, to0.01mm inclusive.
    The caller must verify native face ownership/provenance; no nearest face is chosen.
    """
    targets = Targets.capture(targets)
    if side not in ("start", "end") or not finite(plane_origin) or not finite(inward_normal):
        raise IncompleteRibbonInput("An explicit finite native cap plane is required")
    if magnitude(inward_normal) <= 0:
        raise IncompleteRibbonInput("The actual cap has no usable normal")
    inward = unit(inward_normal)
    fixed_center = getattr(targets, side)
    fixed_forward = getattr(targets, side + "_tangent")
    fixed_width = getattr(targets, side + "_width")
    forward = inward if side == "start" else difference(Vector3(0, 0, 0), inward)
    if magnitude(difference(forward, fixed_forward)) > 2 * math.sin(math.radians(0.001) / 2):
        raise IncompleteRibbonInput(
            "Actual cap orientation differs from its ordered material frame"
        )
    origin = fixed_center.translated(inward, -dot(difference(fixed_center, plane_origin), inward))
    width = unit(fixed_width.translated(inward, -dot(fixed_width, inward)))
    thickness = unit(cross(forward, width))
    fixed_thickness = unit(cross(fixed_forward, fixed_width))
    errors = []
    for arc in material_profile(targets.lines, targets.diameter_mm):
        for q, b in arc.controls:
            actual = origin.translated(width, q).translated(thickness, b)
            fixed = fixed_center.translated(fixed_width, q).translated(fixed_thickness, b)
            errors.append(magnitude(difference(actual, fixed)))
    maximum = max(errors)
    if not math.isfinite(maximum) or maximum > ACCURACY_MM:
        raise IncompleteRibbonInput(
            "Actual cap section differs from the fixed profile by over0.01mm"
        )
    return CapFrame(origin, width, thickness, inward, maximum)
