"""
Verify physical rational profile height bounds used by full-thickness volume audits.
"""

from fractions import Fraction

from artifacts.verification.resume3255.run import profile_reach


def test_symmetric_off_curve_control_does_not_become_physical_thickness() -> None:
    """
    The rational arch b=10*t*(1-t)/(1-t+t²) attains10/3, while its control reaches10.
    """
    profile = {"controls": ((-1.0, 0.0), (0.0, 10.0), (1.0, 0.0)), "weights": (1.0, 0.5, 1.0)}
    assert profile_reach(profile) == Fraction(10, 3)


def test_asymmetric_arc_retains_conservative_positive_weight_control_extent() -> None:
    """
    An unsupported extremum formula falls back to the unchanged full control range.
    """
    profile = {"controls": ((-1.0, -2.0), (0.0, 10.0), (1.0, 1.0)), "weights": (1.0, 0.5, 1.0)}
    assert profile_reach(profile) == Fraction(10)
