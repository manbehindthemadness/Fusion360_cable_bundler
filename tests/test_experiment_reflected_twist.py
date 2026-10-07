"""
Verify bounded roll motion is not erased and fixed endpoint orientation survives.
"""

import math

import pytest

from cable_bundler.routing.geometry import difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.master_frames import master_scaffold
from experiments.experiment_ribbon_cap_transition.prescribed_twist import PrescribedTwistDiagnostic
from experiments.experiment_ribbon_cap_transition.reflected_twist import ReflectedTwistDiagnostic
from experiments.experiment_ribbon_cap_transition.turn_pair import turn_fixtures


@pytest.mark.parametrize("degrees", (360.0, -360.0))
def test_smooth_reflection_retains_intermediate_motion(degrees: float) -> None:
    """
    Reach the signed half-turn then reverse continuously to the unchanged cap.
    """
    policy = ReflectedTwistDiagnostic(degrees)
    distances = tuple(index / 1000 for index in range(1001))
    angles = policy.angles(distances, 0)
    assert angles[0] == angles[-1] == 0
    assert angles[500] == math.copysign(math.pi, degrees)
    assert max(abs(a) for a in angles) <= math.pi
    assert angles == pytest.approx(tuple(reversed(angles)), abs=1e-12)
    assert angles[250] == pytest.approx(math.copysign(math.pi / 2, degrees))
    assert abs(angles[1]) < 1e-6
    assert abs(angles[500] - angles[499]) < 1e-6
    assert "Two C2" in policy.field_description


@pytest.mark.parametrize("degrees", (0.0, 180.0, 270.0, float("nan")))
def test_other_requests_rejected(degrees: float) -> None:
    """
    This fixed-scope policy does not silently generalize to other requested rolls.
    """
    with pytest.raises(ValueError, match="360"):
        ReflectedTwistDiagnostic(degrees).angles((0, 1, 2), 0)


def test_fixed_cap_and_distance_validation_retained() -> None:
    """
    Reject inconsistent end orientation and malformed station tables before Fusion.
    """
    policy = ReflectedTwistDiagnostic(360)
    with pytest.raises(ValueError, match="end-guide"):
        policy.angles((0, 1, 2), math.pi / 2)
    with pytest.raises(ValueError, match="increasing"):
        policy.angles((0, 1, 1), 0)


@pytest.mark.parametrize("index", (0, 1))
def test_only_interior_roll_changes(index: int) -> None:
    """
    Preserve centerline, section dimensions/perpendicularity and both cap frames.
    """
    case = turn_fixtures()[index].case
    args = (case.route, case.start_width, case.end_width, 28.5)
    control = master_scaffold(*args, twist=PrescribedTwistDiagnostic(0))
    reflected = master_scaffold(*args, twist=ReflectedTwistDiagnostic(360))
    assert reflected.distances_mm == control.distances_mm
    assert reflected.frames[0] == control.frames[0]
    assert reflected.frames[-1] == control.frames[-1]
    assert max(reflected.bank_angles_radians) > math.radians(179)
    assert max(reflected.bank_angles_radians) <= math.pi
    for original, frame in zip(control.frames, reflected.frames):
        assert frame.origin == original.origin
        assert frame.tangent == original.tangent
        assert magnitude(frame.width) == pytest.approx(1)
        assert dot(frame.width, frame.tangent) == pytest.approx(0, abs=1e-8)
        assert dot(frame.thickness, frame.tangent) == pytest.approx(0, abs=1e-8)
        assert dot(frame.width, frame.thickness) == pytest.approx(0, abs=1e-8)
    assert magnitude(difference(control.frames[15].width, reflected.frames[15].width)) > 1.99
