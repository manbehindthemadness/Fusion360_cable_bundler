"""
Define closed oriented branch-shell incidence without kernel-dependent geometry choices.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .spatial_frame import ChartOrientation

EdgeKey = tuple[Literal["along", "station"], int, int]


@dataclass(frozen=True)
class EdgeUse:
    """
    Reference one canonical edge with its explicit coedge traversal direction.
    """

    key: EdgeKey
    opposed: bool


def loops(
    spans: int, edges: int, orientation: ChartOrientation, checkpoint: Callable[[], None]
) -> tuple[tuple[EdgeUse, ...], ...]:
    """
    Return lateral loops in span/edge order followed by root and terminal caps.

    Every station edge and longitudinal edge is shared by exactly two opposed
    uses. Negative material handedness reverses each complete loop, including
    its coedge directions. No face omission or proximity-based welding occurs.
    """
    checkpoint()
    if type(spans) is not int or spans < 1 or type(edges) is not int or edges < 3:
        raise ValueError("A nonempty span sequence and closed contour are required")
    if not isinstance(orientation, ChartOrientation):
        raise ValueError("Explicit material handedness required")
    result = []
    for span in range(spans):
        for edge in range(edges):
            checkpoint()
            result.append(
                (
                    EdgeUse(("along", span, edge), False),
                    EdgeUse(("station", span + 1, edge), False),
                    EdgeUse(("along", span, (edge + 1) % edges), True),
                    EdgeUse(("station", span, edge), True),
                )
            )
    result.append(tuple(EdgeUse(("station", 0, edge), False) for edge in range(edges)))
    result.append(tuple(EdgeUse(("station", spans, edge), True) for edge in reversed(range(edges))))
    if orientation is ChartOrientation.NEGATIVE:
        result = [
            tuple(EdgeUse(use.key, not use.opposed) for use in reversed(loop)) for loop in result
        ]
    checkpoint()
    return tuple(result)
