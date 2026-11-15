"""
Compose frozen section transitions with explicit spatial fields as exact rational boundary patches.

The result defines geometry between sections. It does not replace the isometric
trunk solver or certify branch material metrics, interior ownership or contact.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, elevate, multiply
from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude

from .capture import same_direction, same_point
from .profile_transition import TransitionEdge, evaluate
from .root_profiles import CapFrame
from .spatial_frame import FrameSpan, restrict

Point = tuple[Fraction, ...]
Net = tuple[tuple[Point, ...], ...]


@dataclass(frozen=True)
class SpatialJet:
    """
    Retain world geometry derivatives with respect to global branch u and source edge v.
    """

    point: Vector3
    along: Vector3
    along_second: Vector3
    around: Vector3


def evaluate_net(net: Net, u: float, v: float) -> tuple[float, ...]:
    """
    Evaluate an unchanged homogeneous tensor with all four components and both-axis weights.
    """
    rows = tuple(evaluate(tuple(tuple(float(x) for x in p) for p in row), v) for row in net)
    return evaluate(rows, u)


def derive(net: Net, axis: int) -> Net:
    """
    Differentiate each exact scalar component on the requested local tensor axis.
    """
    if axis not in (0, 1):
        raise ValueError("Choose one of the two tensor axes")
    if axis == 1:
        degree = len(net[0]) - 1
        return tuple(
            tuple(tuple(degree * (b[k] - a[k]) for k in range(4)) for a, b in zip(row, row[1:]))
            for row in net
        )
    degree = len(net) - 1
    return tuple(
        tuple(tuple(degree * (b[k] - a[k]) for k in range(4)) for a, b in zip(first, second))
        for first, second in zip(net, net[1:])
    )


@dataclass(frozen=True)
class SpatialPatch:
    """
    Preserve exact world homogeneous controls and their original shape/frame provenance.
    """

    section: TransitionEdge
    frame: FrameSpan
    rows: Net
    section_rows: Net

    def __post_init__(self) -> None:
        """
        Require complete positive-weight world and section tensors before evaluation.
        """
        expected = max(len(self.frame.center), len(self.frame.width), len(self.frame.thickness)) + 5
        for net, rows, size in ((self.rows, expected, 4), (self.section_rows, 6, 3)):
            if (
                len(net) != rows
                or any(len(row) != 3 for row in net)
                or any(
                    len(p) != size or any(type(x) is not Fraction for x in p) or p[-1] <= 0
                    for row in net
                    for p in row
                )
            ):
                raise ValueError("A complete positive-weight spatial composition is required")

    def jet(self, u: float, v: float) -> SpatialJet:
        """
        Evaluate actual quotient jets without unit-speed substitution or local-parameter resetting.
        """
        low, high = float(self.frame.low), float(self.frame.high)
        if not math.isfinite(u) or not math.isfinite(v) or not low <= u <= high or not 0 <= v <= 1:
            raise ValueError("Choose the declared global frame interval and unit edge coordinate")
        t = (u - low) / (high - low)
        point = evaluate_net(self.rows, t, v)
        first = evaluate_net(derive(self.rows, 0), t, v)
        second = evaluate_net(derive(derive(self.rows, 0), 0), t, v)
        across = evaluate_net(derive(self.rows, 1), t, v)
        weight = point[3]
        if weight <= 0 or not math.isfinite(weight):
            raise ValueError("Spatial patch has no positive rational denominator")
        p = tuple(point[k] / weight for k in range(3))
        d = tuple((first[k] - p[k] * first[3]) / weight for k in range(3))
        dd = tuple((second[k] - 2 * d[k] * first[3] - p[k] * second[3]) / weight for k in range(3))
        dv = tuple((across[k] - p[k] * across[3]) / weight for k in range(3))
        scale = high - low
        return SpatialJet(
            Vector3(*p),
            Vector3(*(x / scale for x in d)),
            Vector3(*(x / scale**2 for x in dd)),
            Vector3(*dv),
        )


def compose(
    section: TransitionEdge, frame: FrameSpan, checkpoint: Callable[[], None]
) -> SpatialPatch:
    """
    Form(C*weight + width*q + thickness*b, weight) with exact Bernstein products.

    Restrict the single original section morph onto the frame's global interval.
    Degree elevation preserves complete products; no loft-station interpolation,
    flattened weights, frame normalization or changed target is introduced.
    """
    checkpoint()
    source = tuple(
        tuple(
            restrict(tuple(row[v][k] for row in section.rows), frame.low, frame.high)
            for k in range(3)
        )
        for v in range(3)
    )
    center, width, thickness = frame.fields()
    columns = []
    degree = max(len(frame.center), len(frame.width), len(frame.thickness)) + 4
    for q, b, weight in source:
        checkpoint()
        xyz = tuple(
            elevate(
                add(
                    add(multiply(center[k], weight), multiply(width[k], q)),
                    multiply(thickness[k], b),
                ),
                degree,
            )
            for k in range(3)
        )
        columns.append(xyz + (elevate(weight, degree),))
    rows = tuple(
        tuple(tuple(columns[v][k][u] for k in range(4)) for v in range(3))
        for u in range(degree + 1)
    )
    section_rows = tuple(
        tuple(tuple(source[v][k][u] for k in range(3)) for v in range(3)) for u in range(6)
    )
    return SpatialPatch(section, frame, rows, section_rows)


def bind_root(patch: SpatialPatch, cap: CapFrame) -> None:
    """
    Check unchanged root placement, material axes, handedness and full boundary approach.

    The cap must already have explicit native ownership. Planned fields are never
    projected, normalized or reversed to obtain a pass. Actual boundary tangent
    direction retains the existing0.001degree coordinate-flow gate. Curvature and
    native junction flow remain separate measurements.
    """
    frame = patch.frame
    if frame.low != Fraction(0):
        raise ValueError("Only the first global branch span can bind the native root")
    same_point(frame.center[0], cap.point(patch.section.center_q_mm, 0), "Spatial root center")
    same_direction(frame.width[0], cap.width, "Root material width")
    same_direction(frame.thickness[0], cap.thickness, "Root material thickness")
    if abs(magnitude(frame.width[0]) - 1) > 1e-8 or abs(magnitude(frame.thickness[0]) - 1) > 1e-8:
        raise ValueError("Root material axes must preserve the native coordinate scale")
    outward = difference(Vector3(0, 0, 0), cap.inward)
    expected = 1 if dot(outward, cross(cap.width, cap.thickness)) > 0 else -1
    if frame.orientation.value != expected:
        raise ValueError("Root material handedness cannot be changed between spans")

    def first(values: tuple[Vector3, ...]) -> Vector3:
        """
        Evaluate a raw frame derivative at the local span's root.
        """
        if len(values) == 1:
            return Vector3(0, 0, 0)
        delta = difference(values[1], values[0])
        degree = len(values) - 1
        return Vector3(delta.x * degree, delta.y * degree, delta.z * degree)

    center = first(frame.center)
    width = first(frame.width)
    thickness = first(frame.thickness)
    for q, b, weight in patch.section.rows[0]:
        local_q, local_b = float(q / weight), float(b / weight)
        actual = (
            frame.center[0]
            .translated(frame.width[0], local_q)
            .translated(frame.thickness[0], local_b)
        )
        same_point(
            actual,
            cap.point(local_q + patch.section.center_q_mm, local_b),
            "Full spatial root profile",
        )
        velocity = center.translated(width, local_q).translated(thickness, local_b)
        speed = magnitude(velocity)
        if (
            speed <= 0
            or dot(velocity, outward) <= 0
            or magnitude(cross(velocity, outward)) > speed * math.sin(math.radians(0.001))
        ):
            raise ValueError("Spatial root boundary flow differs from the actual cap normal")
