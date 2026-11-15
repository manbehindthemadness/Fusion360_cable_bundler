"""
Define continuous rational boundary transitions from exact split roots to prescribed round sections.

This is a transverse shape plan, not a spatial branch solution. Longitudinal
framing, material compatibility, full-volume Jacobians, contact and native
construction remain separate. No interior material-coordinate map is implied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import cast

from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc

from .root_profiles import RootEdge, RootProfile

Point = tuple[Fraction, Fraction, Fraction]
Row = tuple[Point, ...]
Net = tuple[Row, ...]
Pair = tuple[float, float]


@dataclass(frozen=True)
class SectionJet:
    """
    Retain actual unit-parameter boundary position and derivatives without speed normalization.
    """

    point: Pair
    longitudinal: Pair
    longitudinal_second: Pair
    around: Pair


def evaluate(values: tuple[tuple[float, ...], ...], parameter: float) -> tuple[float, ...]:
    """
    Evaluate one homogeneous Bernstein row with de Casteljau arithmetic.
    """
    while len(values) > 1:
        values = tuple(
            tuple((1 - parameter) * x + parameter * y for x, y in zip(a, b))
            for a, b in zip(values, values[1:])
        )
    return values[0]


def difference(a: Point, b: Point, degree: int) -> Point:
    """
    Form one exact homogeneous derivative control without losing its three-component shape.
    """
    return degree * (b[0] - a[0]), degree * (b[1] - a[1]), degree * (b[2] - a[2])


def derivative(net: Net, axis: int) -> Net:
    """
    Differentiate a rectangular exact net on its declared unit axis.
    """
    if axis not in (0, 1):
        raise ValueError("Choose one of the two tensor axes")
    if axis == 1:
        degree = len(net[0]) - 1
        if degree == 0:
            return tuple(((Fraction(0), Fraction(0), Fraction(0)),) for _ in net)
        return tuple(tuple(difference(a, b, degree) for a, b in zip(row, row[1:])) for row in net)
    degree = len(net) - 1
    if degree == 0:
        return (tuple((Fraction(0), Fraction(0), Fraction(0)) for _ in net[0]),)
    return tuple(
        tuple(difference(a, b, degree) for a, b in zip(first, second))
        for first, second in zip(net, net[1:])
    )


def homogeneous(net: Net, u: float, v: float) -> tuple[float, ...]:
    """
    Evaluate the supplied tensor without changing its rational parameterization.
    """
    rows = tuple(evaluate(tuple(tuple(float(x) for x in p) for p in row), v) for row in net)
    return evaluate(rows, u)


@dataclass(frozen=True)
class TransitionEdge:
    """
    Retain one degree5/2 homogeneous loft patch and original edge/material identity.

    Coordinates are local to the conductor's fixed nominal root center. First
    three rows reproduce the root and last three the terminal circle. This gives
    zero first/second longitudinal shape derivatives at both ends. Rational
    weights vary in both parameters and must not be replaced by separable weights.
    """

    source: RootEdge
    center_q_mm: float
    terminal_radius_mm: float
    terminal: MaterialArc
    rows: Net

    def __post_init__(self) -> None:
        """
        Refuse altered tensor structure or provenance that would invalidate the blend certificate.
        """
        if not math.isfinite(self.terminal_radius_mm) or self.terminal_radius_mm <= 0:
            raise ValueError("A positive prescribed terminal radius is required")
        if (
            len(self.rows) != 6
            or any(len(row) != 3 for row in self.rows)
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for row in self.rows
                for p in row
            )
            or self.rows[:3] != (self.rows[0],) * 3
            or self.rows[3:] != (self.rows[-1],) * 3
            or self.rows[0] != homogeneous_row(self.source.geometry, self.center_q_mm)
            or self.rows[-1] != homogeneous_row(self.terminal, 0.0)
        ):
            raise ValueError("A complete provenance-matched quintic endpoint blend is required")

    def jet(self, u: float, v: float) -> SectionJet:
        """
        Evaluate boundary jets for a future independently audited spatial branch frame.
        """
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in (u, v)):
            raise ValueError("Transition coordinates must lie in the unit square")
        position = homogeneous(self.rows, u, v)
        along = homogeneous(derivative(self.rows, 0), u, v)
        second = homogeneous(derivative(derivative(self.rows, 0), 0), u, v)
        around = homogeneous(derivative(self.rows, 1), u, v)
        weight = position[2]
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Transition denominator is not positive")
        point = (position[0] / weight, position[1] / weight)
        velocity = cast(Pair, tuple((along[i] - point[i] * along[2]) / weight for i in range(2)))
        acceleration = cast(
            Pair,
            tuple(
                (second[i] - 2 * velocity[i] * along[2] - point[i] * second[2]) / weight
                for i in range(2)
            ),
        )
        transverse = cast(
            Pair, tuple((around[i] - point[i] * around[2]) / weight for i in range(2))
        )
        return SectionJet(point, velocity, acceleration, transverse)


def homogeneous_row(arc: MaterialArc, center: float) -> Row:
    """
    Retain exact stored control values and canonical endpoint weights for shared-edge continuity.
    """
    if (
        len(arc.controls) != 3
        or len(arc.weights) != 3
        or any(len(p) != 2 or any(not math.isfinite(x) for x in p) for p in arc.controls)
        or any(not math.isfinite(w) or w <= 0 for w in arc.weights)
        or arc.weights[0] != 1
        or arc.weights[-1] != 1
    ):
        raise ValueError(
            "Finite quadratic root controls and positive canonical endpoint weights required"
        )
    return tuple(
        (Fraction(w) * (Fraction(q) - Fraction(center)), Fraction(w) * Fraction(b), Fraction(w))
        for (q, b), w in zip(arc.controls, arc.weights)
    )


def circle_edge(source: MaterialArc, center: float, radius: float) -> MaterialArc:
    """
    Match ordered endpoint rays with a clockwise rational circle arc, preserving edge seams.
    """
    unit_points = []
    for q, b in (source.controls[0], source.controls[-1]):
        x = q - center
        distance = math.hypot(x, b)
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError("A root boundary endpoint must have a nonzero radial direction")
        unit_points.append((x / distance, b / distance))
    first, last = unit_points
    cross = first[0] * last[1] - first[1] * last[0]
    cosine = first[0] * last[0] + first[1] * last[1]
    if cross >= 0 or 1 + cosine <= 0:
        raise ValueError("A root edge needs a clockwise radial sector narrower than a half-circle")
    weight = math.sqrt((1 + cosine) / 2)
    start = (radius * first[0], radius * first[1])
    end = (radius * last[0], radius * last[1])
    control = ((start[0] + end[0]) / (1 + cosine), (start[1] + end[1]) / (1 + cosine))
    return MaterialArc((start, control, end), (1.0, weight, 1.0), source.label)


def build(
    profile: RootProfile, center_q_mm: float, terminal_radius_mm: float
) -> tuple[TransitionEdge, ...]:
    """
    Freeze positive-weight transitions for every root edge without changing its exact cap outline.
    """
    if (
        not math.isfinite(center_q_mm)
        or not math.isfinite(terminal_radius_mm)
        or terminal_radius_mm <= 0
    ):
        raise ValueError("Finite root center and positive prescribed terminal radius required")
    if not profile.edges:
        raise ValueError("A complete closed root profile is required")
    root_rows = tuple(homogeneous_row(edge.geometry, center_q_mm) for edge in profile.edges)
    patches = []
    for first, second in zip(profile.edges, profile.edges[1:] + profile.edges[:1]):
        if first.geometry.controls[-1] != second.geometry.controls[0]:
            raise ValueError("Root boundary must retain exact shared chart vertices")
    for edge, root in zip(profile.edges, root_rows):
        arc = edge.geometry
        terminal = circle_edge(arc, center_q_mm, terminal_radius_mm)
        end = homogeneous_row(terminal, 0.0)
        patches.append(
            TransitionEdge(
                edge, center_q_mm, terminal_radius_mm, terminal, (root,) * 3 + (end,) * 3
            )
        )
    return tuple(patches)
