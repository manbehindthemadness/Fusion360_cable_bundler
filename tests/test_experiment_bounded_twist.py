"""
Verify orientation-preserving winding reduction independently of native lofting.
"""

import math

import pytest

from experiments.experiment_ribbon_cap_transition.bounded_twist import shortest_twist
from experiments.experiment_ribbon_cap_transition.faith_fixtures import faith_fixtures
from experiments.experiment_ribbon_cap_transition.prescribed_twist import PrescribedTwistDiagnostic


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (0, 0),
        (90, 90),
        (-90, -90),
        (180, 180),
        (-180, -180),
        (270, -90),
        (-270, 90),
        (360, 0),
        (-360, 0),
        (540, 180),
        (-540, -180),
    ],
)
def test_shortest_equivalent_roll(requested: float, expected: float) -> None:
    """
    Reduce winding while preserving signed half-turn ties and endpoint orientation.
    """
    actual = shortest_twist(requested)
    assert actual == expected
    assert abs(actual) <= 180
    assert math.sin(math.radians(actual)) == pytest.approx(math.sin(math.radians(requested)))
    assert math.cos(math.radians(actual)) == pytest.approx(math.cos(math.radians(requested)))
    angles = PrescribedTwistDiagnostic(actual).angles((0.0, 1.0, 2.0), math.radians(requested))
    assert angles[0] == 0
    assert angles[-1] == math.radians(expected)
    assert all(abs(angle) <= math.pi for angle in angles)


@pytest.mark.parametrize("degrees", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_roll_rejected(degrees: float) -> None:
    """
    Reject malformed inputs before any native geometry authoring.
    """
    with pytest.raises(ValueError, match="finite"):
        shortest_twist(degrees)


def test_original_six_twist_branches() -> None:
    """
    Only the original skew-return winding changes in this development replay.
    """
    fixtures = faith_fixtures()
    assert tuple(shortest_twist(item.twist_degrees) for item in fixtures) == (
        0,
        90,
        -90,
        180,
        -180,
        0,
    )
