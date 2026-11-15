"""
Bound the geometric ruled midplane support without assuming a valid interior material map.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, elevate
from artifacts.verification.resume3217.metric import Polynomial, product

from .material_paths import combine, square_root_lower
from .spatial_frame import Components, FrameSpan, differentiated

Vector = tuple[Polynomial, Polynomial, Polynomial]


def square_root_upper(value: Fraction) -> Fraction:
    """
    Enclose a nonnegative square root on the existing forty-bit arithmetic grid.
    """
    low = square_root_lower(value)
    return low if low * low == value else low + Fraction(1, 1 << 40)


def lift(field: Components) -> Vector:
    """
    Preserve a u polynomial as a field constant across physical q.
    """
    return (
        tuple((x,) for x in field[0]),
        tuple((x,) for x in field[1]),
        tuple((x,) for x in field[2]),
    )


def affine(a: Components, b: Components, bounds: tuple[Fraction, Fraction]) -> Vector:
    """
    Form a(u)+q*b(u) exactly over the specified physical q interval.
    """
    output = []
    for first, second in zip(a, b):
        low, high = (add(first, second, q) for q in bounds)
        degree = max(len(low), len(high)) - 1
        output.append(tuple(zip(elevate(low, degree), elevate(high, degree))))
    return output[0], output[1], output[2]


def dot(a: Vector, b: Vector) -> Polynomial:
    """
    Keep exact scalar products in a shared two-parameter Bernstein basis.
    """
    return combine(combine(product(a[0], b[0]), product(a[1], b[1])), product(a[2], b[2]))


def cross(a: Vector, b: Vector) -> Vector:
    """
    Form the unnormalized geometric support normal without concealing singularity.
    """
    return (
        combine(product(a[1], b[2]), product(a[2], b[1]), Fraction(-1)),
        combine(product(a[2], b[0]), product(a[0], b[2]), Fraction(-1)),
        combine(product(a[0], b[1]), product(a[1], b[0]), Fraction(-1)),
    )


def range_of(values: Polynomial) -> tuple[Fraction, Fraction]:
    """
    Enclose a whole parameter rectangle with its exact Bernstein coefficient hull.
    """
    flat = tuple(x for row in values for x in row)
    return min(flat), max(flat)


@dataclass(frozen=True)
class SupportBound:
    """
    Separate principal curvature, metric regularity and physical normal-field correspondence.

    None means this finite coefficient enclosure did not establish the denominator;
    it is not infeasibility or a witnessed violation. Parameterization is unchanged.
    """

    frame: FrameSpan
    q_bounds_mm: tuple[Fraction, Fraction]
    metric_squared_lower: Fraction
    principal_upper_per_mm: Fraction | None
    normal_distance_upper_mm: Fraction | None
    physical_half_thickness_upper_mm: Fraction
    transverse_reach_upper_mm: Fraction


def enclose(
    frame: FrameSpan, q_bounds: tuple[Fraction, Fraction], half_b: Fraction
) -> SupportBound:
    """
    Enclose both principal curvatures of X(u,q)=C(u)+q*W(u) over the full q envelope.

    With unnormalized normal n, D=n.n, e=n.X_uu, f=n.W_u and
    T=e*G-2*f*F, principal magnitude is at most |T|/D^(3/2)+|f|/D.
    This follows directly from the two fundamental forms, including saddle terms;
    centerline curvature alone cannot substitute. Thickness field correspondence
    is bounded independently against the oriented unit normal, in millimeters.
    Raw thickness scaling is included in physical reach, never normalized away.
    """
    if not q_bounds[0] < q_bounds[1] or half_b < Fraction(0):
        raise ValueError("Increasing physical width bounds and nonnegative thickness required")
    center, width, thickness = frame.fields()
    dc, dw = differentiated(center), differentiated(width)
    velocity = affine(dc, dw, q_bounds)
    acceleration = affine(differentiated(dc), differentiated(dw), q_bounds)
    ruling, ruling_rate = lift(width), lift(dw)
    normal = cross(velocity, ruling)
    metric = dot(normal, normal)
    low_d, high_d = range_of(metric)
    thickness_squared = range_of(dot(lift(thickness), lift(thickness)))[1]
    physical_half = half_b * square_root_upper(max(Fraction(0), thickness_squared))
    width_squared = range_of(dot(ruling, ruling))[1]
    reach = (
        max(abs(q) for q in q_bounds) * square_root_upper(max(Fraction(0), width_squared))
        + physical_half
    )
    root_d = square_root_lower(low_d) if low_d > Fraction(0) else Fraction(0)
    if root_d <= Fraction(0):
        return SupportBound(frame, q_bounds, low_d, None, None, physical_half, reach)
    e, f = dot(normal, acceleration), dot(normal, ruling_rate)
    trace = combine(
        product(e, dot(ruling, ruling)), product(f, dot(velocity, ruling)), Fraction(-2)
    )
    trace_range, f_range = range_of(trace), range_of(f)
    principal = (
        max(abs(x) for x in trace_range) / (low_d * root_d) + max(abs(x) for x in f_range) / low_d
    )
    alignment = tuple(
        tuple(frame.orientation.value * x for x in row) for row in dot(normal, lift(thickness))
    )
    dot_lower = range_of(alignment)[0]
    if dot_lower < Fraction(0):
        return SupportBound(frame, q_bounds, low_d, principal, None, physical_half, reach)
    squared_gap = thickness_squared + 1 - 2 * dot_lower / square_root_upper(high_d)
    gap = half_b * square_root_upper(max(Fraction(0), squared_gap))
    return SupportBound(frame, q_bounds, low_d, principal, gap, physical_half, reach)
