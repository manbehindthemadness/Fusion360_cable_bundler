"""
Freeze section geometry and right-handed frames with positive Z along the path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from ..contracts import RibbonPath
from ..traces import TracePath, cubic_controls


@dataclass(frozen=True)
class LocalFrame:
    """
    Store a physical origin and orthonormal axes; X cross Y equals forward Z.
    """

    origin: Vector3
    x: Vector3
    y: Vector3
    z: Vector3

    def __post_init__(self) -> None:
        """
        Reject malformed frames rather than silently rotating a recorded section.
        """
        vectors = (self.origin, self.x, self.y, self.z)
        if any(not math.isfinite(v) for p in vectors for v in (p.x, p.y, p.z)):
            raise ValueError("Section frames must be finite.")
        if (
            max(
                *(abs(magnitude(axis) - 1) for axis in vectors[1:]),
                abs(dot(self.x, self.y)),
                abs(dot(self.x, self.z)),
                abs(dot(self.y, self.z)),
                magnitude(difference(cross(self.x, self.y), self.z)),
            )
            > 1e-7
        ):
            raise ValueError("Section axes must be right-handed orthonormal XYZ.")

    def point(self, x: float, y: float, z: float = 0.0) -> Vector3:
        """
        Transform a local millimeter coordinate without changing the stored basis.
        """
        return self.origin.translated(self.x, x).translated(self.y, y).translated(self.z, z)


def local_frame(origin: Vector3, forward: Vector3, across: Vector3) -> LocalFrame:
    """
    Project the supplied across direction into the section normal plane.

    Z follows the actual positive path derivative. Degenerate directions reject;
    no Frenet normal or arbitrary world-axis fallback replaces the supplied frame.
    """
    z = unit(forward)
    x = unit(across.translated(z, -dot(across, z)))
    return LocalFrame(origin, x, cross(z, x), z)


@dataclass(frozen=True)
class Section:
    """
    Keep one distinctly selectable section and its actual or declared outline.

    A material ruling is an open diagnostic segment, not an invented bonded
    profile. A circle is a declared one-conductor cross-section of diameter D.
    """

    index: int
    u: float
    frame: LocalFrame
    outline: tuple[Vector3, ...]
    kind: Literal["circle", "material_ruling"]

    def __post_init__(self) -> None:
        """
        Validate identity, fraction and contour before archive or native display.
        """
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError("Section index must be a nonnegative integer.")
        if not math.isfinite(self.u) or not 0 <= self.u <= 1:
            raise ValueError("Section fraction must lie within [0,1].")
        if self.kind not in ("circle", "material_ruling") or len(self.outline) < 2:
            raise ValueError("Choose a declared section contour.")
        if any(not math.isfinite(v) for p in self.outline for v in (p.x, p.y, p.z)):
            raise ValueError("Section contours must be finite.")
        if self.kind == "circle" and (
            len(self.outline) < 9 or magnitude(difference(self.outline[0], self.outline[-1])) > 1e-8
        ):
            raise ValueError("Circular section contour must close.")


@dataclass(frozen=True)
class PathSnapshot:
    """
    Preserve frozen cubic paths and sections independently from solver objects.

    Guide interpolation resolution is explicit; it is not a continuous collision
    certificate. This record deliberately has no overall pass/acceptance flag.
    """

    identifier: str
    lines: int
    diameter_mm: float
    intervals: int
    guides: tuple[TracePath, ...]
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        """
        Refuse incomplete or unordered geometry before persistence or display.
        """
        if (
            not isinstance(self.identifier, str)
            or not self.identifier.strip()
            or isinstance(self.lines, bool)
            or not isinstance(self.lines, int)
            or not 1 <= self.lines <= 128
        ):
            raise ValueError("Snapshot needs an identity and1..128conductors.")
        if not math.isfinite(self.diameter_mm) or self.diameter_mm <= 0:
            raise ValueError("Snapshot diameter must be positive and finite.")
        if (
            isinstance(self.intervals, bool)
            or not isinstance(self.intervals, int)
            or not 16 <= self.intervals <= 1024
            or not self.guides
        ):
            raise ValueError("Snapshot needs16..1024cubic intervals.")
        if len({g.number for g in self.guides}) != len(self.guides) or not any(
            g.number == 0 for g in self.guides
        ):
            raise ValueError("Snapshot requires unique guides including the center.")
        for frozen_guide in self.guides:
            if (
                len(frozen_guide.curves) != self.intervals
                or len(frozen_guide.controls) != 3 * self.intervals + 1
            ):
                raise ValueError("Snapshot guide resolution disagrees with controls.")
            if any(not math.isfinite(v) for p in frozen_guide.controls for v in (p.x, p.y, p.z)):
                raise ValueError("Snapshot guide controls must be finite.")
        if len(self.sections) < 2 or tuple(s.index for s in self.sections) != tuple(
            range(len(self.sections))
        ):
            raise ValueError("Snapshot sections must retain contiguous explicit order.")
        fractions = tuple(s.u for s in self.sections)
        if (
            fractions[0] != 0
            or fractions[-1] != 1
            or any(a >= b for a, b in zip(fractions, fractions[1:]))
        ):
            raise ValueError("Snapshot sections must advance from0to1.")


class SectionedCurve(Protocol):
    """
    Supply an actual center jet and explicitly defined local frame.
    """

    def jet(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Return center position and derivative in normalized path fraction.
        """
        ...

    def frame(self, u: float) -> LocalFrame:
        """
        Return the source's section basis without inferring material physics.
        """
        ...


def guide(
    number: int, jet: Callable[[float], tuple[Vector3, Vector3]], intervals: int
) -> TracePath:
    """
    Freeze one explicit cubic interpolation using the shared trace representation.
    """
    from cable_bundler.routing.geometry import CubicBezier

    controls, knots = cubic_controls(jet, intervals)
    curves = tuple(CubicBezier(*controls[i : i + 4]) for i in range(0, len(controls) - 1, 3))
    return TracePath(number, curves, controls, knots)


def circle_section(index: int, u: float, frame: LocalFrame, diameter_mm: float) -> Section:
    """
    Sample a single circular cable profile in its local XY plane.
    """
    radius = diameter_mm / 2
    outline = tuple(
        frame.point(radius * math.cos(i * math.pi / 16), radius * math.sin(i * math.pi / 16))
        for i in range(32)
    )
    return Section(index, u, frame, outline + (outline[0],), "circle")


def freeze_curve(
    identifier: str,
    curve: SectionedCurve,
    diameter_mm: float,
    *,
    intervals: int = 512,
    sections: int = 33,
) -> PathSnapshot:
    """
    Capture a declared one-conductor curve without fabricating ribbon field metrics.
    """
    if isinstance(sections, bool) or not isinstance(sections, int) or not 2 <= sections <= 65:
        raise ValueError("Use2..65distinct sections.")
    records = tuple(
        circle_section(i, i / (sections - 1), curve.frame(i / (sections - 1)), diameter_mm)
        for i in range(sections)
    )
    return PathSnapshot(
        identifier, 1, diameter_mm, intervals, (guide(0, curve.jet, intervals),), records
    )


def freeze_path(
    identifier: str, path: RibbonPath, *, intervals: int, sections: int = 17
) -> PathSnapshot:
    """
    Freeze the centre and, for ribbons, both material guides with ordered sections.

    For multi-conductor paths, the profile is intentionally recorded as an open
    material ruling until the true bonded profile is supplied. No wire-body
    surrogate or invented solid outline participates in this diagnostic capture.
    """
    if isinstance(sections, bool) or not isinstance(sections, int) or not 2 <= sections <= 65:
        raise ValueError("Use2..65distinct sections.")
    half = path.field.half_width_mm
    guide_offsets = ((0, 0.0),) if path.field.lines == 1 else ((-1, half), (0, 0.0), (-2, -half))
    guides = tuple(
        guide(n, lambda fraction, q=q: path.lane(fraction, q), intervals) for n, q in guide_offsets
    )
    records = []
    for i in range(sections):
        u = i / (sections - 1)
        origin, velocity = path.lane(u, 0)
        a, b = path.lane(u, half)[0], path.lane(u, -half)[0]
        frame = local_frame(origin, velocity, difference(a, b))
        records.append(
            circle_section(i, u, frame, path.field.diameter_mm)
            if path.field.lines == 1
            else Section(i, u, frame, (a, b), "material_ruling")
        )
    return PathSnapshot(
        identifier, path.field.lines, path.field.diameter_mm, intervals, guides, tuple(records)
    )
