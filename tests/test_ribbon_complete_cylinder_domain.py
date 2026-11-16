"""
Check physical intrinsic-window conditioning and complete positive-basis line bounds.
"""

from dataclasses import replace
from fractions import Fraction
from math import sqrt

import pytest

from experiments.experiment_ribbon_complete.cylinder_coordinates import build
from experiments.experiment_ribbon_complete.cylinder_domain import (
    certify_window,
    inspect_line,
    ratio_hull,
)
from tests.test_ribbon_complete_cylinder_coordinates import reference
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_bounded_window_has_global_separation_and_independent_conditioning() -> None:
    """
    Independently reconstructed world chords dominate the certified physical coordinate separation.
    """
    chart = build(reference(), checkpoint)
    proof = certify_window(chart, Fraction(2), checkpoint)
    assert proof.status == "certified_intrinsic_cylinder_window"
    assert proof.separation_lower is not None and proof.separation_lower > 0
    assert proof.condition_upper is not None and proof.condition_upper <= 1024
    with pytest.raises(ValueError, match="SAME owned cylinder window"):
        replace(proof, maximum_abs_ratio=Fraction(100))
    for first, second in (((-2, -2), (2, 2)), ((0, -2), (0, 2)), ((0, 1), (2, 1))):
        a = chart.project(Fraction(first[0]), Fraction(first[1]), checkpoint)
        b = chart.project(Fraction(second[0]), Fraction(second[1]), checkpoint)
        world = sqrt(sum(float(x - y) ** 2 for x, y in zip(a.point, b.point)))
        coordinate = sqrt((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2)
        assert (
            world + float(a.error_upper_mm + b.error_upper_mm)
            >= float(proof.separation_lower) * coordinate
        )
    large = certify_window(chart, Fraction(100), checkpoint)
    assert large.separation_lower is not None and large.separation_lower > 0
    assert large.status == "unresolved_intrinsic_cylinder_window_conditioning"
    assert large.condition_upper is not None and large.condition_upper > 1024


def test_complete_line_branch_and_axial_deviation_are_measured_without_native_uv() -> None:
    """
    Small nonzero radial drift is retained, while large drift and stationary height remain unresolved.
    """
    chart = build(reference(), checkpoint)
    points = (Fraction(0), Fraction(1), Fraction(0)), (Fraction(2), Fraction(1), Fraction(0))
    line = inspect_line(chart, points, checkpoint)
    assert line.status == "qualified_axial_cylinder_line_branch"
    with pytest.raises(ValueError, match="SAME owned cylinder line"):
        replace(line, chart=build(reference(), checkpoint))
    assert line.axial_error_upper_mm.numerator == 0
    assert line.height_difference_mm.numerator == 2 and line.height_difference_mm.denominator == 1
    for error, expected in (
        (Fraction(1, 1000), "qualified_axial_cylinder_line_branch"),
        (Fraction(1, 10), "unresolved_axial_cylinder_line_branch"),
    ):
        endpoints = points[0], (Fraction(2), Fraction(1) + error, Fraction(0))
        result = inspect_line(chart, endpoints, checkpoint)
        assert result.status == expected and result.axial_error_upper_mm == error
    stationary = inspect_line(
        chart, (points[0], (Fraction(0), Fraction(1001, 1000), Fraction(0))), checkpoint
    )
    assert stationary.status == "unresolved_axial_cylinder_line_branch"
    with pytest.raises(ValueError, match="positive whole-curve"):
        ratio_hull(chart, (points[0], (Fraction(2), Fraction(-1), Fraction(0))))


def test_window_validation_and_resource_stop_preserve_unresolved_work() -> None:
    """
    Negative angular domains and source-invalid charts cannot receive default conditioning evidence.
    """
    chart = build(reference(), checkpoint)
    with pytest.raises(ValueError, match="nonnegative angular"):
        certify_window(chart, Fraction(-1), checkpoint)
    invalid = build(
        replace(reference(), native=replace(reference().native, radius_mm=Fraction(2))), checkpoint
    )
    with pytest.raises(ValueError, match="qualified same-source"):
        certify_window(invalid, Fraction(1), checkpoint)

    def stop() -> None:
        """
        Refuse new derivative work after the caller's allocation has stopped.
        """
        raise RuntimeError("window allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        certify_window(chart, Fraction(1), stop)
