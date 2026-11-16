"""
Recover approximate source material labels with exact unchanged-world residual acceptance.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .branch_plan import SpatialBranchPlan
from .collared_transport import MaterialLabel, label, world
from .curve_lengths import distance
from .material_atlas import MaterialAtlas, validate
from .profile_transition import TransitionEdge
from .ruled_support import square_root_upper

Vector = tuple[float, ...]


def polynomial(values: Vector, t: float) -> float:
    """
    Evaluate a fixed stored control sequence for numerical inverse proposals only.
    """
    while len(values) > 1:
        values = tuple((1 - t) * a + t * b for a, b in zip(values, values[1:]))
    return values[0]


def derivative(values: Vector) -> Vector:
    """
    Preserve constant fields under numerical derivative evaluation.
    """
    return tuple((len(values) - 1) * (b - a) for a, b in zip(values, values[1:])) or (0.0,)


def solve(columns: tuple[Vector, ...], residual: Vector) -> Vector | None:
    """
    Solve one small Newton system, refusing singular or nonfinite proposals.
    """
    size = len(residual)
    if size not in (2, 3) or len(columns) != size or any(len(c) != size for c in columns):
        raise ValueError("Only two/three-dimensional inverse systems are supported")
    if not all(math.isfinite(x) for c in columns + (residual,) for x in c):
        return None

    def determinant(values: tuple[Vector, ...]) -> float:
        """
        Evaluate the small inverse systems directly; exact world residual remains authoritative.
        """
        if size == 2:
            return values[0][0] * values[1][1] - values[0][1] * values[1][0]
        return sum(
            values[0][i]
            * (
                values[1][(i + 1) % 3] * values[2][(i + 2) % 3]
                - values[1][(i + 2) % 3] * values[2][(i + 1) % 3]
            )
            for i in range(3)
        )

    divisor = determinant(columns)
    if divisor == 0 or not math.isfinite(divisor):
        return None
    result = tuple(
        determinant(tuple(residual if j == i else c for j, c in enumerate(columns))) / divisor
        for i in range(size)
    )
    return result if all(math.isfinite(x) for x in result) else None


def frame(plan: SpatialBranchPlan, coordinates: Vector) -> tuple[Vector, tuple[Vector, ...]]:
    """
    Evaluate the original world chart and global-u Jacobian without normalizing its fields.
    """
    u, q, b = coordinates
    span = next(
        p[0].frame for p in plan.patches if float(p[0].frame.low) <= u <= float(p[0].frame.high)
    )
    h = float(span.high - span.low)
    t = (u - float(span.low)) / h
    fields = tuple(
        tuple(tuple(float(x) for x in axis) for axis in field) for field in span.fields()
    )
    c, w, n = tuple(tuple(polynomial(axis, t) for axis in field) for field in fields)
    dc, dw, dn = tuple(
        tuple(polynomial(derivative(axis), t) / h for axis in field) for field in fields
    )
    return tuple(c[k] + q * w[k] + b * n[k] for k in range(3)), (
        tuple(dc[k] + q * dw[k] + b * dn[k] for k in range(3)),
        w,
        n,
    )


def section_jet(section: TransitionEdge, u: float, v: float) -> tuple[Vector, ...]:
    """
    Evaluate root/current Cartesian edge points and edge derivatives for inverse proposals.
    """
    output = []
    for phase in (0.0, u):
        controls = tuple(
            tuple(
                polynomial(tuple(float(row[j][k]) for row in section.rows), phase) for j in range(3)
            )
            for k in range(3)
        )
        p = tuple(polynomial(axis, v) for axis in controls)
        d = tuple(polynomial(derivative(axis), v) for axis in controls)
        point = tuple(p[k] / p[2] for k in range(2))
        velocity = tuple((d[k] - point[k] * d[2]) / p[2] for k in range(2))
        output.extend((point, velocity))
    return tuple(output)


def quantize(value: float) -> Fraction:
    """
    Bound proposal representation size on a fixed dyadic grid; exact residual decides acceptance.
    """
    return Fraction(round(value * (1 << 24)), 1 << 24)


@dataclass(frozen=True)
class MaterialInverse:
    """
    Retain a source label and actual world error, without asserting exact point membership or physical compliance.
    """

    atlas: MaterialAtlas
    status: str
    phase: Fraction | None
    source_label: MaterialLabel | None
    residual_upper_mm: Fraction | None
    root_error_upper_if_in_image_mm: Fraction | None


def recover(
    atlas: MaterialAtlas,
    target: tuple[Fraction, Fraction, Fraction],
    take_step: Callable[[], None],
    checkpoint: Callable[[], None],
) -> MaterialInverse:
    """
    Invert the geometric chart, then its transverse transport, with caller-owned Newton debits.

    Each Newton proposal calls take_step first; it must debit the existing shared
    work/CPU pool, including recovery0.4CPU/24Newton when used there. No new pool,
    automatic renewal, geometry adjustment or route discovery is granted here.
    The geometric stage and each source fan permit at most6steps. Fans are ordered
    by angular alignment of their current boundary midpoint with the query, with
    source index breaking ties. This orders proposals only; it rejects no fan.
    Exhaustion
    or caller stops propagate; finite nonconvergence remains unresolved.

    Numerical proposals never establish membership or acceptance. Only a canonical
    source label in the SAME certified atlas whose exact world evaluation is within
    one inclusive0.01mm Euclidean allowance can be returned. This approximates an
    inverse to dimensional accuracy; it does not prove the target is exactly in
    the material volume or certify strain/contact/native correspondence. Dyadic
    proposal storage and linear solves are internal numerical choices, not tighter
    dimensional acceptance rules.

    For a target known to lie in this atlas image, root-coordinate error is bounded
    by sqrt(1+max|T_u|²)*||B^-1||/(m_transverse*m_world) times the world residual.
    This follows by strong monotonicity of B^-1*F and of each T(u,.), then varying
    u at fixed source point. Both world and conditional root errors must be<=0.01mm.
    The numerical stage goal is tighter only to leave room for that required
    source-coordinate bound; it is not a new physical dimensional accuracy goal.
    """
    checkpoint()
    if len(target) != 3 or any(type(x) is not Fraction for x in target):
        raise ValueError("Three exact finite world coordinates are required")
    validate(atlas, checkpoint)
    sections = atlas.geometry.transverse.sections
    try:
        wanted = tuple(float(x) for x in target)
    except OverflowError as error:
        raise ValueError("World coordinates exceed the numerical proposal range") from error
    if not all(math.isfinite(x) for x in wanted):
        raise ValueError("World coordinates exceed the numerical proposal range")
    chart = atlas.geometry.world_map
    if chart.inverse_root_basis is None or chart.minimum_monotonicity is None:
        raise ValueError("The geometric inverse bound is required")
    minimum = min(
        p.minimum_monotonicity for p in atlas.transports if p.minimum_monotonicity is not None
    )
    rate2 = max(
        p.longitudinal_rate_squared_upper
        for p in atlas.transports
        if p.longitudinal_rate_squared_upper is not None
    )
    inverse_norm = square_root_upper(
        sum((x * x for row in chart.inverse_root_basis for x in row), Fraction(0))
    )
    root_lipschitz = (
        square_root_upper(1 + rate2) * inverse_norm / (minimum * chart.minimum_monotonicity)
    )
    numerical_goal = float(Fraction(1, 400) / max(Fraction(1), root_lipschitz))
    bounds = (
        (0.0, 1.0),
        tuple(map(float, atlas.geometry.world_map.q_bounds_mm)),
        tuple(map(float, atlas.geometry.world_map.b_bounds_mm)),
    )
    coordinates = (0.5, 0.0, 0.0)
    for _ in range(6):
        checkpoint()
        actual, columns = frame(atlas.plan, coordinates)
        residual = tuple(a - b for a, b in zip(actual, wanted))
        if math.hypot(*residual) <= numerical_goal:
            break
        take_step()
        delta = solve(columns, residual)
        if delta is None:
            return MaterialInverse(atlas, "unresolved", None, None, None, None)
        coordinates = tuple(
            min(high, max(low, x - d)) for x, d, (low, high) in zip(coordinates, delta, bounds)
        )
    actual, _columns = frame(atlas.plan, coordinates)
    if math.dist(actual, wanted) > numerical_goal:
        return MaterialInverse(atlas, "unresolved", None, None, None, None)
    u, q, b = coordinates
    phase = quantize(u)

    def receipt(edge_index: int, radial: float, angular: float) -> MaterialInverse | None:
        """
        Validate the proposal on unchanged exact controls, with one world-distance allowance.
        """
        point = label(atlas.plan, edge_index, quantize(angular), quantize(radial))
        actual_point = world(atlas.plan, point, phase, checkpoint)
        upper = distance(actual_point, target)[1]
        root_error = root_lipschitz * upper
        return (
            MaterialInverse(atlas, "within_dimensional_tolerance", phase, point, upper, root_error)
            if max(upper, root_error) <= Fraction(1, 100)
            else None
        )

    center = receipt(0, 0.0, 0.0)
    if center is not None:
        return center

    def angular_order(index: int) -> tuple[float, int]:
        """
        Prefer query-aligned fans without changing source labels or acceptance evidence.
        """
        midpoint = section_jet(sections[index], u, 0.5)[2]
        norm = math.hypot(*midpoint)
        alignment = (midpoint[0] * q + midpoint[1] * b) / norm if norm else -math.inf
        return -alignment, index

    for edge in sorted(range(len(sections)), key=angular_order):
        section = sections[edge]
        s, v = 0.5, 0.5
        for _ in range(6):
            checkpoint()
            accepted = receipt(edge, s, v)
            if accepted is not None:
                return accepted
            r, rv, p, pv = section_jet(section, u, v)
            chi = 0.0 if s <= 0.25 else ((4 * s - 1) / 3) ** 3
            chi_s = 0.0 if s <= 0.25 else 4 * ((4 * s - 1) / 3) ** 2
            value = tuple(s * r[k] + chi * (p[k] - r[k]) for k in range(2))
            columns = (
                tuple(r[k] + chi_s * (p[k] - r[k]) for k in range(2)),
                tuple(s * rv[k] + chi * (pv[k] - rv[k]) for k in range(2)),
            )
            take_step()
            delta = solve(columns, (value[0] - q, value[1] - b))
            if delta is None:
                break
            s, v = (min(1.0, max(0.0, x - d)) for x, d in zip((s, v), delta))
        accepted = receipt(edge, s, v)
        if accepted is not None:
            return accepted
    return MaterialInverse(atlas, "unresolved", None, None, None, None)
