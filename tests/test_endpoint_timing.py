"""
Check timing attribution and distinguish absent construction from measured zero.
"""

import math

import pytest

from cable_bundler.routing.geometry import dot, magnitude
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_timing import timing_label, timing_values


def test_timing_excludes_audit_and_marks_partial_work() -> None:
    """
    Geometry sums only profile/loft time and keeps unsuccessful work explicit.
    """
    row = {
        "case_id": "sample",
        "numerical_seconds": 0.002,
        "section_seconds": 1.25,
        "loft_seconds": 0.5,
        "audit_seconds": 9,
        "built": True,
    }
    assert timing_values(row) == {
        "solver_seconds": 0.002,
        "geometry_seconds": 1.75,
        "audit_seconds": 9,
    }
    assert timing_label(row) == "sample | solve 2.00 ms | geometry 1.750 s"
    row["built"] = False
    assert timing_label(row).endswith("1.750 s partial")
    del row["loft_seconds"]
    assert timing_values(row)["geometry_seconds"] == 1.25


def test_unattempted_is_distinct_from_zero() -> None:
    """
    An absent solver or build never displays a misleading zero duration.
    """
    assert (
        timing_label({"case_id": "skipped"})
        == "skipped | solve not attempted | geometry not attempted"
    )
    assert "solve 0.00 ms" in timing_label({"case_id": "zero", "numerical_seconds": 0})


@pytest.mark.parametrize("value", [-1, math.inf, math.nan, True, "0.1"])
def test_invalid_measurements_are_rejected(value: object) -> None:
    """
    Malformed external timing values cannot become reassuring counters.
    """
    with pytest.raises(ValueError, match="Invalid timing"):
        timing_values({"numerical_seconds": value})


def test_lateral_inputs_are_fixed_perpendicular_heading_changes() -> None:
    """
    Three independent boundary layouts specify headings without an interior route.
    """
    cases = lateral_cases()
    assert len({c.end for c in cases}) == 3
    for case, angle in zip(cases, (30, 60, 90)):
        assert magnitude(case.end_tangent) == pytest.approx(1)
        assert dot(case.end_tangent, case.end_width) == pytest.approx(0, abs=1e-12)
        assert dot(case.start_tangent, case.end_tangent) == pytest.approx(
            math.cos(math.radians(angle))
        )
