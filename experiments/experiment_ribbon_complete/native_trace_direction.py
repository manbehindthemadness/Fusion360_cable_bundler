"""
Bind native trace direction through owned physical vertex positions instead of inferred parameter conventions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction

from .exact_frame import Point
from .native_boundary_distance import FiniteBoundaryTrace
from .native_surface_trace import NativeSurfaceTrace
from .projected_filled_domain import DirectedBoundaryTrace


@dataclass(frozen=True)
class NativeEdgeEndpoints:
    """
    Retain captured component-local millimetre vertex positions and discrete native edge ownership.
    """

    revision: str
    edge_id: int
    vertex_ids: tuple[int, int]
    points_mm: tuple[Point, Point]
    incident_faces: tuple[int, ...]

    def __post_init__(self) -> None:
        """
        Reject incomplete coordinates, repeated identities and malformed native provenance.
        """
        if (
            not isinstance(self.revision, str)
            or not self.revision.strip()
            or type(self.edge_id) is not int
            or self.edge_id < 0
            or type(self.vertex_ids) is not tuple
            or len(self.vertex_ids) != 2
            or any(type(x) is not int or x < 0 for x in self.vertex_ids)
            or len(set(self.vertex_ids)) != 2
            or type(self.points_mm) is not tuple
            or len(self.points_mm) != 2
            or any(
                type(p) is not tuple or len(p) != 3 or any(type(x) is not Fraction for x in p)
                for p in self.points_mm
            )
            or type(self.incident_faces) is not tuple
            or not self.incident_faces
            or any(type(x) is not int or x < 0 for x in self.incident_faces)
        ):
            raise ValueError(
                "Complete distinct native endpoint identities and exact world coordinates required"
            )


@dataclass(frozen=True)
class NativeTraceDirection:
    """
    Measure both complete endpoint assignments and accept only one within the physical accuracy.

    A tiny edge may have two acceptable assignments; that is unresolved discrete
    direction, never permission to choose the smaller error or a metadata flag.
    No curve, target, coordinate label or native vertex is moved. Endpoint matches
    alone establish neither whole-curve fidelity nor native filled-domain coverage.
    """

    trace: NativeSurfaceTrace
    native: NativeEdgeEndpoints
    directed_vertices: tuple[int, int]
    checkpoint: InitVar[Callable[[], None]]
    assignment_errors_mm: tuple[tuple[Fraction, Fraction], tuple[Fraction, Fraction]] = field(
        init=False
    )
    reversed: bool | None = field(init=False)
    endpoint_upper_mm: Fraction | None = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Require exact ownership before any numerical comparison and preserve both assignment errors.
        """
        checkpoint()
        if (
            self.native.revision != self.trace.surface.revision
            or self.trace.surface.face_index not in self.native.incident_faces
            or self.native.edge_id != self.trace.curve.edge_id
            or type(self.directed_vertices) is not tuple
            or len(self.directed_vertices) != 2
            or any(type(x) is not int for x in self.directed_vertices)
            or set(self.directed_vertices) != set(self.native.vertex_ids)
        ):
            raise ValueError(
                "The SAME revision, incident face, edge and directed native vertices required"
            )
        expected = tuple(
            self.native.points_mm[self.native.vertex_ids.index(identity)]
            for identity in self.directed_vertices
        )
        actual = (
            self.trace.point(Fraction(0), checkpoint),
            self.trace.point(Fraction(1), checkpoint),
        )
        errors: list[tuple[Fraction, Fraction]] = []
        for points in (actual, actual[::-1]):
            checkpoint()
            distances = [
                sum((abs(a - b) for a, b in zip(p, q)), Fraction(0))
                for p, q in zip(points, expected)
            ]
            errors.append((distances[0], distances[1]))
        eligible = [i for i, row in enumerate(errors) if max(row) <= Fraction(1, 100)]
        reverse = bool(eligible[0]) if len(eligible) == 1 else None
        object.__setattr__(self, "assignment_errors_mm", (errors[0], errors[1]))
        object.__setattr__(self, "reversed", reverse)
        object.__setattr__(
            self, "endpoint_upper_mm", None if reverse is None else max(errors[int(reverse)])
        )
        checkpoint()

    def directed(self, finite: FiniteBoundaryTrace) -> DirectedBoundaryTrace:
        """
        Bind the SAME finite trace only after unique physical endpoint association is established.
        """
        if self.reversed is None or finite.trace is not self.trace:
            raise ValueError("A uniquely directed SAME finite trace required")
        return DirectedBoundaryTrace(finite, *self.directed_vertices, self.reversed)
