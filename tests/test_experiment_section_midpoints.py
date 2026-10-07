"""
Check explicit side-cap vertices without importing Fusion or moving a contour.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import NamedTuple

import pytest

from experiments.experiment_ribbon_cap_transition.section_midpoints import (
    split_outer_edge_midpoints,
)


class Point(NamedTuple):
    """
    Represent a sketch-space test coordinate.
    """

    x: float
    y: float
    z: float


class Evaluator:
    """
    Evaluate a circular side cap with configurable API rejection.
    """

    def __init__(self, left: bool) -> None:
        self.left = left
        self.range_success = True
        self.point_success = True
        self.start = math.pi / 2 if left else -math.pi / 2
        self.end = self.start + math.pi

    def getParameterExtents(self) -> tuple[bool, float, float]:
        """
        Return the declared circular parameter interval.
        """
        return self.range_success, self.start, self.end

    def getPointAtParameter(self, parameter: float) -> tuple[bool, Point]:
        """
        Evaluate the unchanged circle in centimeters.
        """
        center = -0.9 if self.left else 0.9
        return self.point_success, Point(
            center + 0.1 * math.cos(parameter), 0.1 * math.sin(parameter), 0
        )


class Arc:
    """
    Capture the API split point and append one additional contour arc.
    """

    def __init__(self, arcs: Arcs, left: bool) -> None:
        self.arcs = arcs
        self.geometry = SimpleNamespace(evaluator=Evaluator(left))
        self.split_points: list[Point] = []
        self.result_count = 2

    def split(self, point: Point) -> SimpleNamespace:
        """
        Record one split without changing the source circle or lobe list.
        """
        self.split_points.append(point)
        self.arcs.items.append(object())
        return SimpleNamespace(count=self.result_count)


class Arcs:
    """
    Supply the established numbered-lobes-first, side-caps-last ordering.
    """

    def __init__(self) -> None:
        self.items: list[object] = [object() for _ in range(38)]
        self.caps = (Arc(self, True), Arc(self, False))
        self.items.extend(self.caps)

    @property
    def count(self) -> int:
        """
        Expose the current contour topology count.
        """
        return len(self.items)

    def item(self, index: int) -> object:
        """
        Return a contour element by original creation order.
        """
        return self.items[index]


class Section:
    """
    Keep one joined profile and an identity sketch-to-world transform.
    """

    def __init__(self) -> None:
        self.arcs = Arcs()
        self.sketchCurves = SimpleNamespace(sketchArcs=self.arcs)
        self.profiles = SimpleNamespace(count=1)

    def sketchToModelSpace(self, point: Point) -> Point:
        """
        Preserve the input coordinate exactly.
        """
        return point


def test_outer_midpoints_are_contour_splits_not_detached_points() -> None:
    """
    Split both width extrema once, retaining all numbered lobes and circles.
    """
    section = Section()
    lobes = section.arcs.items[:38]
    points = split_outer_edge_midpoints(section, 19)
    assert points[0] == pytest.approx((-10, 0, 0), abs=1e-12)
    assert points[1] == pytest.approx((10, 0, 0), abs=1e-12)
    assert section.arcs.items[:38] == lobes
    assert section.arcs.count == 42 and section.profiles.count == 1
    assert all(len(cap.split_points) == 1 for cap in section.arcs.caps)
    with pytest.raises(ValueError, match="original discrete"):
        split_outer_edge_midpoints(section, 19)
    assert all(len(cap.split_points) == 1 for cap in section.arcs.caps)


@pytest.mark.parametrize("invalid", ("range", "point", "nonfinite", "reversed"))
def test_invalid_cap_evaluation_never_starts_a_split(invalid: str) -> None:
    """
    Validate both midpoints before changing either contour edge.
    """
    section = Section()
    evaluator = section.arcs.caps[1].geometry.evaluator
    if invalid == "range":
        evaluator.range_success = False
    elif invalid == "point":
        evaluator.point_success = False
    elif invalid == "nonfinite":
        evaluator.start = math.nan
    else:
        evaluator.end = evaluator.start
    with pytest.raises(RuntimeError, match="unavailable"):
        split_outer_edge_midpoints(section, 19)
    assert all(not cap.split_points for cap in section.arcs.caps)


def test_split_failure_is_not_retried_or_hidden() -> None:
    """
    Retain the failed split as evidence without touching the second edge.
    """
    section = Section()
    section.arcs.caps[0].result_count = 0
    with pytest.raises(RuntimeError, match="two arcs"):
        split_outer_edge_midpoints(section, 19)
    assert len(section.arcs.caps[0].split_points) == 1
    assert not section.arcs.caps[1].split_points


@pytest.mark.parametrize("profile_count", (0, 2))
def test_invalid_profile_is_rejected_before_geometry_edits(profile_count: int) -> None:
    """
    Preserve the requirement for exactly one original closed contour.
    """
    section = Section()
    section.profiles.count = profile_count
    with pytest.raises(ValueError, match="original discrete"):
        split_outer_edge_midpoints(section, 19)
    assert all(not cap.split_points for cap in section.arcs.caps)
