"""
Verify measured interval provenance and controlled diagnostic classifications.
"""

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.failure_fixtures import author, specifications
from experiments.experiment_ribbon_cap_transition.failure_regions import (
    Sample,
    Series,
    measure,
    regions,
)


@pytest.mark.parametrize(
    "direction,limit,values",
    [("upper", 1.0, (0.5, 1.0, 1.2, 1.3, 0.5)), ("lower", 0.0, (0.5, 0.1, 0.0, -0.2, 0.5))],
)
def test_regions_preserve_boundary_brackets_and_worst_witness(
    direction: str, limit: float, values: tuple[float, ...]
) -> None:
    """
    Locate the same contiguous red interval for upper and inclusive-lower policies.
    """
    samples = tuple(Sample(i / 4, Vector3(i, 0, 0), value) for i, value in enumerate(values))
    series = Series("test", 9, 2.0, limit, direction, 0.1, samples)
    found = [r for r in regions(series) if r.severity == "red"]
    assert len(found) == 1
    region = found[0]
    assert (region.first_index, region.last_index) == (2, 3)
    assert region.entry_bracket == (0.25, 0.5)
    assert region.exit_bracket == (0.75, 1.0)
    assert region.worst_u == 0.75
    assert region.worst_point == samples[3].point
    assert region.worst_value == values[3]
    assert region.trace == 9


def test_unavailable_measurement_splits_findings_instead_of_becoming_safe() -> None:
    """
    Do not interpolate a continuous violation or a pass across missing evidence.
    """
    row = Series(
        "test",
        1,
        0,
        1,
        "upper",
        0.1,
        tuple(Sample(i / 4, Vector3(i, 0, 0), value) for i, value in enumerate((2, 2, None, 2, 2))),
    )
    found = regions(row)
    assert [(r.first_index, r.last_index) for r in found] == [(0, 1), (3, 4)]
    assert found[0].entry_bracket is None
    assert found[1].exit_bracket is None
    assert row.severity(2) == "unmeasured"


@pytest.mark.parametrize("index", range(6))
def test_controlled_family_exposes_expected_boundary_and_failure(index: int) -> None:
    """
    Check declared fixture expectations without interpreting them as route success.
    """
    spec = specifications()[index]
    path, case = author(spec)
    series, found = measure(path, lambda: None, intervals=128)
    assert {r.kind for r in found if r.severity == "red"} == set(spec.expected_red)
    if spec.expected_amber:
        assert spec.expected_amber in {r.kind for r in found if r.severity == "amber"}
    if spec.number.startswith("F"):
        boundary = next(s for s in series if s.kind == "material J" and s.trace == -2)
        expected_minimum = {"F1": 0.3, "F2": 0.01, "F3": -0.2}[spec.number]
        assert min(s.value for s in boundary.samples if s.value is not None) == pytest.approx(
            expected_minimum
        )
    assert case.lines == 7
    assert case.start == path.lane(0, 0)[0]
    assert case.end == path.lane(1, 0)[0]
