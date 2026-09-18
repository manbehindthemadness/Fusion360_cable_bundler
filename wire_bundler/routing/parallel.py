"""
Deterministic centerline routing through circular passage gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from .geometry import CubicBezier, Vector3


@dataclass(frozen=True)
class GateFrame:
    """
    Describe a circular routing aperture in model coordinates.
    """

    gate_id: UUID
    name: str
    origin: Vector3
    u_direction: Vector3
    v_direction: Vector3
    usable_radius_mm: float


@dataclass(frozen=True)
class RefineFrame:
    """
    Describe an oriented pathway crossing without an aperture constraint.
    """

    refine_id: UUID
    name: str
    origin: Vector3
    u_direction: Vector3
    v_direction: Vector3


@dataclass(frozen=True)
class WireRouteInput:
    """
    Describe one wire requiring a route through shared gates.

    End guides run from each terminal toward the shared pathway.
    """

    wire_id: UUID
    wire_number: str
    start: Vector3
    end: Vector3
    diameter_mm: float
    start_guides: tuple[Vector3, ...] = ()
    end_guides: tuple[Vector3, ...] = ()


@dataclass(frozen=True)
class RoutePreview:
    """
    Store one lightweight centerline preview.

    Points retain traversal order; fairing may add exact local cubic transitions.
    """

    wire_id: UUID
    wire_number: str
    points: tuple[Vector3, ...]
    curves: tuple[CubicBezier, ...] = ()


class GateCapacityError(ValueError):
    """
    Report a gate that cannot contain every requested wire.
    """

    def __init__(self, gate: GateFrame, wire_count: int) -> None:
        """
        Initialize an actionable capacity error.
        """
        self.gate_id = gate.gate_id
        self.gate_name = gate.name
        self.wire_count = wire_count
        super().__init__(
            f"{gate.name} cannot fit {wire_count} wires inside its "
            f"{gate.usable_radius_mm * 2.0:g} mm usable diameter."
        )


def solve_parallel_routes(
    wires: tuple[WireRouteInput, ...],
    gates: tuple[Union[GateFrame, RefineFrame], ...],
    clearance_mm: float = 0.0,
) -> tuple[RoutePreview, ...]:
    """
    Pack wires at each circular gate and connect corresponding crossings.

    This milestone returns piecewise-linear centerlines. Curvature fairing is a
    later solver stage and does not change the persistent wire-to-slot mapping.

    Raises:
        ValueError: If input dimensions or frames are invalid.
        GateCapacityError: If any gate cannot contain the packed wires.
    """
    if not wires:
        raise ValueError("At least one wire is required for route preview.")
    if not gates:
        raise ValueError("At least one routing gate is required for route preview.")
    if not math.isfinite(clearance_mm) or clearance_mm < 0.0:
        raise ValueError("Wire clearance must be a finite non-negative value.")
    for wire in wires:
        if not math.isfinite(wire.diameter_mm) or wire.diameter_mm <= 0.0:
            raise ValueError(f"Wire {wire.wire_number} has an invalid diameter.")

    gate_crossings = tuple(_place_crossings(wires, gate, clearance_mm) for gate in gates)
    previews = tuple(
        RoutePreview(
            wire_id=wire.wire_id,
            wire_number=wire.wire_number,
            points=(
                wire.start,
                *wire.start_guides,
                *(crossings[index] for crossings in gate_crossings),
                *reversed(wire.end_guides),
                wire.end,
            ),
        )
        for index, wire in enumerate(wires)
    )
    return previews


def place_route_crossings(
    wires: tuple[WireRouteInput, ...],
    frame: Union[GateFrame, RefineFrame],
    clearance_mm: float = 0.0,
    preferred_points: tuple[Optional[Vector3], ...] = (),
) -> tuple[Vector3, ...]:
    """
    Place a stable set of route identities at one shared routing frame.

    Network routing uses this entry point to preserve one group slot across
    every leg meeting at a junction without inventing duplicate full routes.
    """
    if not wires:
        raise ValueError("At least one wire is required for route placement.")
    if not math.isfinite(clearance_mm) or clearance_mm < 0.0:
        raise ValueError("Wire clearance must be a finite non-negative value.")
    for wire in wires:
        if not math.isfinite(wire.diameter_mm) or wire.diameter_mm <= 0.0:
            raise ValueError(f"Wire {wire.wire_number} has an invalid diameter.")
    if preferred_points and len(preferred_points) != len(wires):
        raise ValueError("Preferred route crossings must align with the wire sequence.")
    crossings = _place_crossings(wires, frame, clearance_mm)
    if not preferred_points or not any(point is not None for point in preferred_points):
        return crossings
    assignment = _minimum_cost_assignment(crossings, preferred_points)
    return tuple(crossings[index] for index in assignment)


def _minimum_cost_assignment(
    crossings: tuple[Vector3, ...],
    preferred_points: tuple[Optional[Vector3], ...],
) -> tuple[int, ...]:
    """
    Match bundle slots to transported prior crossings without greedy swaps.

    This is the square Hungarian algorithm. Tiny deterministic tie costs retain
    input order when a route has no preceding crossing or two costs are equal.
    """
    count = len(crossings)
    costs = [
        [
            (_squared_distance(preferred, crossing) if preferred is not None else 0.0)
            + abs(row_index - column_index) * 1e-12
            + column_index * 1e-15
            for column_index, crossing in enumerate(crossings)
        ]
        for row_index, preferred in enumerate(preferred_points)
    ]
    row_potentials = [0.0] * (count + 1)
    column_potentials = [0.0] * (count + 1)
    matched_row = [0] * (count + 1)
    previous_column = [0] * (count + 1)
    for row in range(1, count + 1):
        matched_row[0] = row
        minimums = [math.inf] * (count + 1)
        used = [False] * (count + 1)
        column = 0
        while True:
            used[column] = True
            active_row = matched_row[column]
            delta = math.inf
            next_column = 0
            for candidate_column in range(1, count + 1):
                if used[candidate_column]:
                    continue
                reduced = (
                    costs[active_row - 1][candidate_column - 1]
                    - row_potentials[active_row]
                    - column_potentials[candidate_column]
                )
                if reduced < minimums[candidate_column]:
                    minimums[candidate_column] = reduced
                    previous_column[candidate_column] = column
                if minimums[candidate_column] < delta:
                    delta = minimums[candidate_column]
                    next_column = candidate_column
            for candidate_column in range(count + 1):
                if used[candidate_column]:
                    row_potentials[matched_row[candidate_column]] += delta
                    column_potentials[candidate_column] -= delta
                else:
                    minimums[candidate_column] -= delta
            column = next_column
            if matched_row[column] == 0:
                break
        while True:
            prior = previous_column[column]
            matched_row[column] = matched_row[prior]
            column = prior
            if column == 0:
                break
    assignment = [0] * count
    for column in range(1, count + 1):
        assignment[matched_row[column] - 1] = column - 1
    return tuple(assignment)


def _squared_distance(left: Vector3, right: Vector3) -> float:
    """
    Return squared model-space distance for lane-assignment costs.
    """
    return (left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2


def _place_crossings(
    wires: tuple[WireRouteInput, ...],
    frame: Union[GateFrame, RefineFrame],
    clearance_mm: float,
) -> tuple[Vector3, ...]:
    """
    Place a stable bundle at one constrained gate or unconstrained refine.
    """
    if isinstance(frame, GateFrame):
        return _pack_gate(wires, frame, clearance_mm)
    _validate_frame(frame)
    largest_radius = max(wire.diameter_mm for wire in wires) / 2.0
    spacing = largest_radius * 2.0 + clearance_mm
    offsets = _center_offsets(_hexagonal_offsets(len(wires), spacing))
    return tuple(
        frame.origin.translated(frame.u_direction, u_offset).translated(frame.v_direction, v_offset)
        for u_offset, v_offset in offsets
    )


def _pack_gate(
    wires: tuple[WireRouteInput, ...],
    gate: GateFrame,
    clearance_mm: float,
) -> tuple[Vector3, ...]:
    """
    Place input-ordered wire centers on a deterministic hexagonal lattice.
    """
    _validate_gate(gate)
    largest_radius = max(wire.diameter_mm for wire in wires) / 2.0
    spacing = largest_radius * 2.0 + clearance_mm
    offsets = _center_offsets(_hexagonal_offsets(len(wires), spacing))
    crossings: list[Vector3] = []
    for wire, (u_offset, v_offset) in zip(wires, offsets):
        center_distance = math.hypot(u_offset, v_offset)
        if center_distance + wire.diameter_mm / 2.0 > gate.usable_radius_mm + 1e-9:
            raise GateCapacityError(gate, len(wires))
        crossing = gate.origin.translated(gate.u_direction, u_offset).translated(
            gate.v_direction,
            v_offset,
        )
        crossings.append(crossing)
    return tuple(crossings)


def _hexagonal_offsets(count: int, spacing: float) -> tuple[tuple[float, float], ...]:
    """
    Return center-first points on concentric six-position lattice rings.
    """
    offsets: list[tuple[float, float]] = [(0.0, 0.0)]
    ring = 1
    while len(offsets) < count:
        axial_coordinates = (
            (q, r)
            for q in range(-ring, ring + 1)
            for r in range(-ring, ring + 1)
            if max(abs(q), abs(r), abs(-q - r)) == ring
        )
        ring_offsets = [
            (
                spacing * (q + r / 2.0),
                spacing * (math.sqrt(3.0) / 2.0 * r),
            )
            for q, r in axial_coordinates
        ]
        ring_offsets.sort(key=lambda offset: math.atan2(offset[1], offset[0]))
        offsets.extend(ring_offsets)
        ring += 1
    return tuple(offsets[:count])


def _center_offsets(
    offsets: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    """
    Center a partial lattice ring by its smallest enclosing circle.

    Centering preserves every wire-to-wire spacing while making the circular
    aperture test depend on the occupied bundle radius instead of the arbitrary
    center-first insertion origin.
    """
    center_u, center_v, _radius = _smallest_enclosing_circle(offsets)
    return tuple((u_offset - center_u, v_offset - center_v) for u_offset, v_offset in offsets)


def _smallest_enclosing_circle(
    points: tuple[tuple[float, float], ...],
) -> tuple[float, float, float]:
    """
    Return the deterministic minimum circle containing a small ordered point set.
    """
    circle = (0.0, 0.0, -1.0)
    for point_index, point in enumerate(points):
        if _circle_contains(circle, point):
            continue
        circle = (point[0], point[1], 0.0)
        for second_index, second in enumerate(points[:point_index]):
            if _circle_contains(circle, second):
                continue
            circle = _diameter_circle(point, second)
            for third in points[:second_index]:
                if _circle_contains(circle, third):
                    continue
                circle = _three_point_circle(point, second, third)
    return circle


def _diameter_circle(
    first: tuple[float, float], second: tuple[float, float]
) -> tuple[float, float, float]:
    """
    Return the circle whose diameter joins two points.
    """
    center_u = (first[0] + second[0]) / 2.0
    center_v = (first[1] + second[1]) / 2.0
    radius = math.hypot(first[0] - second[0], first[1] - second[1]) / 2.0
    return center_u, center_v, radius


def _three_point_circle(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> tuple[float, float, float]:
    """
    Return the circumcircle of three points, including collinear triples.
    """
    determinant = 2.0 * (
        first[0] * (second[1] - third[1])
        + second[0] * (third[1] - first[1])
        + third[0] * (first[1] - second[1])
    )
    if abs(determinant) <= 1e-12:
        candidates = (
            _diameter_circle(first, second),
            _diameter_circle(first, third),
            _diameter_circle(second, third),
        )
        enclosing = (
            candidate
            for candidate in candidates
            if all(_circle_contains(candidate, point) for point in (first, second, third))
        )
        return min(enclosing, key=lambda candidate: candidate[2])
    first_norm = first[0] * first[0] + first[1] * first[1]
    second_norm = second[0] * second[0] + second[1] * second[1]
    third_norm = third[0] * third[0] + third[1] * third[1]
    center_u = (
        first_norm * (second[1] - third[1])
        + second_norm * (third[1] - first[1])
        + third_norm * (first[1] - second[1])
    ) / determinant
    center_v = (
        first_norm * (third[0] - second[0])
        + second_norm * (first[0] - third[0])
        + third_norm * (second[0] - first[0])
    ) / determinant
    radius = math.hypot(center_u - first[0], center_v - first[1])
    return center_u, center_v, radius


def _circle_contains(circle: tuple[float, float, float], point: tuple[float, float]) -> bool:
    """
    Return whether a point lies inside a circle within numeric tolerance.
    """
    center_u, center_v, radius = circle
    return radius >= 0.0 and math.hypot(point[0] - center_u, point[1] - center_v) <= radius + 1e-9


def _validate_gate(gate: GateFrame) -> None:
    """
    Require a finite aperture and orthonormal in-plane directions.
    """
    _validate_frame(gate)
    if not math.isfinite(gate.usable_radius_mm) or gate.usable_radius_mm <= 0.0:
        raise ValueError(f"{gate.name} has an invalid circular aperture.")


def _validate_frame(frame: Union[GateFrame, RefineFrame]) -> None:
    """
    Require finite orthonormal in-plane directions.
    """
    values = (
        frame.origin.x,
        frame.origin.y,
        frame.origin.z,
        frame.u_direction.x,
        frame.u_direction.y,
        frame.u_direction.z,
        frame.v_direction.x,
        frame.v_direction.y,
        frame.v_direction.z,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{frame.name} has an invalid routing frame.")
    u_length = _length(frame.u_direction)
    v_length = _length(frame.v_direction)
    dot_product = _dot(frame.u_direction, frame.v_direction)
    if not math.isclose(u_length, 1.0, abs_tol=1e-6):
        raise ValueError(f"{frame.name} has a non-unit U direction.")
    if not math.isclose(v_length, 1.0, abs_tol=1e-6):
        raise ValueError(f"{frame.name} has a non-unit V direction.")
    if not math.isclose(dot_product, 0.0, abs_tol=1e-6):
        raise ValueError(f"{frame.name} has non-orthogonal in-plane directions.")


def _length(vector: Vector3) -> float:
    """
    Return a vector magnitude.
    """
    return math.sqrt(_dot(vector, vector))


def _dot(left: Vector3, right: Vector3) -> float:
    """
    Return the scalar product of two vectors.
    """
    return left.x * right.x + left.y * right.y + left.z * right.z
