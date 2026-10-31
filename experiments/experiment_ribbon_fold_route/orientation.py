"""
Factor endpoint rotations into folds whose crease directions follow the target frame.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .geometry import ZERO, Pose, relative
from .primitives import fold

Quaternion = tuple[float, float, float, float]


def orthogonal(
    start: Pose, end: Pose, radius: float, width: float, runway: float
) -> tuple[CylindricalFold, ...]:
    """
    Preserve the previously measured three-fold orthogonal-crease construction.
    """
    if magnitude(difference(start.width, end.width)) < 1e-10:
        angle = math.atan2(
            dot(end.tangent, cross(start.tangent, start.width)), dot(end.tangent, start.tangent)
        )
        return () if abs(angle) < 1e-12 else (fold(radius, width, angle, 0.0, runway),)
    root = math.sqrt(0.5)
    axes = (Vector3(root, root, 0), Vector3(-root, root, 0), Vector3(0, 0, 1))
    columns = tuple(
        relative(start, v) for v in (end.tangent, end.width, cross(end.tangent, end.width))
    )

    def rotate(vector: Vector3) -> Vector3:
        """
        Express the requested final frame in the departure coordinates.
        """
        return (
            ZERO.translated(columns[0], vector.x)
            .translated(columns[1], vector.y)
            .translated(columns[2], vector.z)
        )

    matrix = tuple(tuple(dot(a, rotate(b)) for b in axes) for a in axes)
    middle = math.acos(max(-1.0, min(1.0, matrix[0][0])))
    if abs(math.sin(middle)) < 1e-10:
        first, last = math.atan2(matrix[2][1], matrix[1][1]), 0.0
    else:
        first = math.atan2(matrix[1][0], -matrix[2][0])
        last = math.atan2(matrix[0][1], matrix[0][2])
    return tuple(
        fold(radius, width, -angle, bank, runway)
        for angle, bank in ((first, -math.pi / 4), (middle, math.pi / 4), (last, -math.pi / 4))
        if abs(angle) >= 1e-12
    )


def _quaternion(start: Pose, end: Pose) -> Quaternion:
    """
    Extract a normalized relative rotation using its largest quaternion component.
    """
    columns = [relative(start, v) for v in (end.tangent, end.width, cross(end.tangent, end.width))]
    matrix = [[getattr(column, axis) for column in columns] for axis in ("x", "y", "z")]
    a, b, c = matrix[0][0], matrix[1][1], matrix[2][2]
    terms = (1 + a + b + c, 1 + a - b - c, 1 - a + b - c, 1 - a - b + c)
    index = max(range(4), key=lambda component: terms[component])
    size = math.sqrt(max(0.0, terms[index]))
    q = [0.0] * 4
    q[index] = size / 2
    if index == 0:
        q[1:] = [
            (matrix[2][1] - matrix[1][2]) / (2 * size),
            (matrix[0][2] - matrix[2][0]) / (2 * size),
            (matrix[1][0] - matrix[0][1]) / (2 * size),
        ]
    else:
        i = index - 1
        j, k = (i + 1) % 3, (i + 2) % 3
        q[0] = (matrix[k][j] - matrix[j][k]) / (2 * size)
        q[j + 1] = (matrix[j][i] + matrix[i][j]) / (2 * size)
        q[k + 1] = (matrix[k][i] + matrix[i][k]) / (2 * size)
    norm = math.sqrt(math.fsum(value * value for value in q))
    sign = -1.0 if q[0] < 0 else 1.0
    return sign * q[0] / norm, sign * q[1] / norm, sign * q[2] / norm, sign * q[3] / norm


def _remaining(first: Quaternion, target: Quaternion) -> Quaternion:
    """
    Compute inverse(first)*target without imposing a crease direction.
    """
    a, b, c, d = first
    w, x, y, z = target
    return (
        a * w + b * x + c * y + d * z,
        a * x - b * w - c * z + d * y,
        a * y + b * z - c * w - d * x,
        a * z - b * y + c * x - d * w,
    )


def _piece(
    q: Quaternion, radius: float, width: float, runway: float
) -> tuple[CylindricalFold, ...]:
    """
    Translate a transverse-axis quaternion into one regular material fold.
    """
    w, x, y, z = q
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    size = math.hypot(x, y)
    if size < 1e-12:
        return ()
    if abs(z) > 1e-9:
        raise ValueError("Rotation factor leaves the material crease plane.")
    angle = 2 * math.atan2(size, max(0.0, w))
    if y < 0:
        x, y, angle = -x, -y, -angle
    bank = math.atan2(-x, y)
    if abs(bank) >= math.pi / 2 - 1e-6:
        raise ValueError("Rotation factor needs a longitudinal crease.")
    return (fold(radius, width, -angle, bank, runway),)


def _roots(a: float, b: float, c: float) -> tuple[float, ...]:
    """
    Solve the crease-balance quadratic without canceling its smaller root.
    """
    scale = max(abs(a), abs(b), abs(c))
    if scale == 0:
        raise ValueError("Indeterminate crease balance.")
    a, b, c = a / scale, b / scale, c / scale
    if abs(a) < 1e-14:
        return (-c / b,) if abs(b) > 1e-14 else ()
    discriminant = b * b - 4 * a * c
    if discriminant < -1e-12:
        raise ValueError("No real balanced crease factorization.")
    value = -0.5 * (b + math.copysign(math.sqrt(max(0.0, discriminant)), b))
    return (value / a, c / value) if value else (-b / (2 * a),)


def orient(
    start: Pose,
    end: Pose,
    radius: float,
    width: float,
    runway: float,
    material_cost: Callable[[tuple[CylindricalFold, ...]], float] | None = None,
) -> tuple[CylindricalFold, ...]:
    """
    Derive continuous crease/bend angles from the exact endpoint rotation.

    Two transverse-axis quaternion factors use equal and opposite crease banks.
    Their two algebraic roots describe exact factorizations, not route seeds;
    choose the smaller material length before contact checking. A supplied cost
    includes the analytically closed connecting pieces rather than only these folds.
    A pure longitudinal rotation requires three regular folds; its45degree
    bisector is geometric, rather than a grid imposed on general rotations.
    """
    q = _quaternion(start, end)
    w, x, y, z = q
    if math.hypot(x, y, z) < 1e-12:
        return ()
    if abs(z) < 1e-12:
        if abs(y) > 1e-9:
            return _piece(q, radius, width, runway)
        # A balanced three-fold roll avoids the longitudinal-axis singularity.
        outer = math.atan2(x / math.sqrt(2), w)
        middle = -2 * math.asin(x / math.sqrt(2))
        return (
            fold(radius, width, -outer, -math.pi / 4, runway),
            fold(radius, width, -middle, math.pi / 4, runway),
            fold(radius, width, -outer, -math.pi / 4, runway),
        )
    m2 = x * x + y * y
    if m2 < 1e-20:
        angle = 2 * math.atan2(z, w)
        return (
            fold(radius, width, -math.pi, angle / 4, runway),
            fold(radius, width, math.pi, -angle / 4, runway),
        )
    a = -2 * w * x * y + z * (x * x - y * y)
    b = 2 * x * y * (m2 + 2 * z * z) + 2 * w * z * (x * x - y * y)
    c = z * (y * y - x * x) * (m2 + z * z) + 2 * w * z * z * x * y
    choices = []
    for value in _roots(a, b, c):
        px, py = (value * x + z * y) / m2, (value * y - z * x) / m2
        norm = math.sqrt(1 + px * px + py * py)
        first = (1 / norm, px / norm, py / norm, 0.0)
        try:
            pieces = _piece(first, radius, width, runway) + _piece(
                _remaining(first, q), radius, width, runway
            )
        except ValueError:
            continue
        choices.append(pieces)
    if not choices:
        raise ValueError("Balanced factors have no regular material creases.")
    cost = (
        material_cost
        if material_cost is not None
        else lambda factors: sum(p.material_length_mm for p in factors)
    )
    return min(choices, key=cost)
