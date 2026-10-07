"""
Freeze quarter-turn and reversal fixtures with endpoint-equivalent bounded twist.
"""

from dataclasses import dataclass, replace

from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase

from .bounded_twist import shortest_twist
from .fixtures import _case, certificate_limit_case

CERTIFICATE_RADIUS_MM = 18.16887617111206


@dataclass(frozen=True)
class TurnFixture:
    """
    Distinguish path turning from requested winding and its actual bounded roll.
    """

    case: RibbonStressCase
    turn_degrees: float
    requested_twist_degrees: float
    actual_twist_degrees: float
    parent_case: str


def turn_fixtures() -> tuple[TurnFixture, ...]:
    """
    Keep the established passing radius, material and4x sphere without searching.

    The90-degree layout truncates the parent to its first quarter-arc; the180
    layout reuses both arcs. New cap/connection targets freeze before solving.
    Both ordered guide widths remain+Y; requested360 winding becomes0.
    """
    parent = certificate_limit_case(CERTIFICATE_RADIUS_MM)
    return tuple(
        TurnFixture(
            replace(
                _case(
                    f"sphere4_turn{turn}_requested360_bounded0",
                    parent.route.curves[:count],
                    parent.end_boundary.center,
                ),
                end_boundary=parent.end_boundary,
            ),
            float(turn),
            360.0,
            shortest_twist(360.0),
            parent.name,
        )
        for turn, count in ((90, 1), (180, 2))
    )
