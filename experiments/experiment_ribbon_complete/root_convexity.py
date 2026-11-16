"""
Certify convexity of the original root disk before a Cartesian material monotonicity proof.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .section_domain import Pair, SectionDomain
from .transport_certificate import cross, dv, prepare


@dataclass(frozen=True)
class RootConvexity:
    """
    Retain signed arc/vertex turning evidence on the same one-winding domain.
    """

    domain: SectionDomain
    status: str
    maximum_arc_turn: Fraction | None
    maximum_vertex_turn: Fraction | None


def certify(domain: SectionDomain, checkpoint: Callable[[], None]) -> RootConvexity:
    """
    Bound all smooth arc turns and discrete corner turns clockwise on an already simple boundary.

    Nonpositive curvature and nonreflex corners on a simple one-winding closed
    curve establish convexity. Collinear joins must preserve forward tangent
    direction. Exact signs are topological premises, not dimensional tolerances.
    """
    checkpoint()
    if domain.status != "certified":
        return RootConvexity(domain, "unresolved", None, None)
    endpoints: list[tuple[Pair, Pair]] = []
    arc_max: Fraction | None = None
    for section in domain.sections:
        checkpoint()
        velocity = prepare(section).root_velocity
        turns = cross(velocity, (dv(velocity[0]), dv(velocity[1])))
        maximum = max(x for row in turns for x in row)
        arc_max = maximum if arc_max is None else max(arc_max, maximum)
        endpoints.append(
            ((velocity[0][0][0], velocity[1][0][0]), (velocity[0][0][-1], velocity[1][0][-1]))
        )
    vertex_max: Fraction | None = None
    valid = True
    for first, second in zip(endpoints, endpoints[1:] + endpoints[:1]):
        a, b = first[1], second[0]
        turn = a[0] * b[1] - a[1] * b[0]
        vertex_max = turn if vertex_max is None else max(vertex_max, turn)
        valid = valid and (
            turn < Fraction(0) or (turn == Fraction(0) and a[0] * b[0] + a[1] * b[1] > Fraction(0))
        )
    state = (
        "certified" if valid and arc_max is not None and arc_max <= Fraction(0) else "unresolved"
    )
    return RootConvexity(domain, state, arc_max, vertex_max)
