"""
Check native witness correspondence without substituting planned points for actual evaluations.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.experiment_ribbon_complete.native_membership import witness_distance_mm
from tests.test_ribbon_complete_native_distance import Face, Point


class MeasuredPoint(Point):
    """
    Provide the SDK distance operation for a synthetic actual witness.
    """

    def distance_to(self, other: Point) -> float:
        """
        Measure geometric separation in centimeters rather than returning assumed zero.
        """
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    distanceTo = distance_to


class EvaluatedFace(Face):
    """
    Add an explicit native evaluator boundary to the shared assembly-proxy fixture.
    """

    def __init__(self) -> None:
        """
        Retain the proxy fixture and declare its independently configured evaluator.
        """
        super().__init__()
        self.evaluator: Any = None


@pytest.mark.parametrize("offset", (0.0, 0.0007))
def test_positive_trim_witness_avoids_minimum_search_and_keeps_actual_error(offset: float) -> None:
    """
    An actual0.0007cm witness discrepancy stays0.007mm, with no expensive minimum search.
    """
    point = MeasuredPoint(0, 0, 0)

    def parameter(_point: Any) -> tuple[bool, int]:
        """
        Return one native chart parameter.
        """
        return True, 3

    def member(value: int) -> bool:
        """
        Accept only that same unmodified native parameter.
        """
        return value == 3

    def evaluated(value: int) -> tuple[bool, Point]:
        """
        Supply an independently evaluated on-trim witness rather than the input point.
        """
        assert value == 3
        return True, Point(offset, 0, 0)

    def forbidden(_point: Any, _face: Any) -> None:
        """
        Reject unnecessary minimum-distance work.
        """
        raise AssertionError("Minimum search must not run for an accepted on-trim witness")

    evaluator = SimpleNamespace(
        getParameterAtPoint=parameter, isParameterOnFace=member, getPointAtParameter=evaluated
    )
    distance = witness_distance_mm(
        point,
        SimpleNamespace(evaluator=evaluator),
        object(),
        SimpleNamespace(measureMinimumDistance=forbidden),
    )
    assert distance == offset * 10


def test_missing_native_inverse_uses_real_trimmed_distance_in_assembly_context() -> None:
    """
    A rejected inverse retains an actual minimum-distance measurement rather than assuming contact.
    """
    face = EvaluatedFace()

    def missing(_point: Any) -> tuple[bool, None]:
        """
        Report the native chart inverse miss.
        """
        return False, None

    def measured(world: Point, proxy: object) -> SimpleNamespace:
        """
        Accept the transformed point and the same face's occurrence proxy.
        """
        assert world == Point(610, 0, 0) and proxy is face.proxy
        return SimpleNamespace(value=0.0001)

    face.evaluator = SimpleNamespace(getParameterAtPoint=missing)
    value = witness_distance_mm(
        MeasuredPoint(0, 0, 0),
        face,
        SimpleNamespace(transform2=(610, 0, 0)),
        SimpleNamespace(measureMinimumDistance=measured),
    )
    assert value == 0.001
