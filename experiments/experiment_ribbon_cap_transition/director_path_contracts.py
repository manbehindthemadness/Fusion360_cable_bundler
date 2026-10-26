"""
Describe framed material paths without assuming constant speed in their parameter.
"""

from __future__ import annotations

from typing import Protocol

from devtools.ribbon_analysis.contracts import RibbonPath

from .director_transport import State


class FramedPath(RibbonPath, Protocol):
    """
    Supply integrated positions/directors for fixed-pose fitting and policy checks.
    """

    @property
    def states(self) -> tuple[State, ...]:
        """
        Return ordered position,tangent,width states including both endpoints.
        """
        ...

    def pose(self, u: float) -> tuple[State, State]:
        """
        Return the interpolated frame and its actual derivative with respect to u.
        """
        ...
