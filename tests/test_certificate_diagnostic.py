"""
Distinguish real curvature and containment certificate failures without rule changes.
"""

import sys

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.certificate_diagnostic import probe_certificate


@pytest.mark.parametrize("curved", (False, True))
def test_probe_identifies_the_actual_failed_condition_and_restores_tracing(curved: bool) -> None:
    """
    Separate excessive curvature from an undersized sphere on simple exact curves.
    """
    scale = 10000 if curved else 1
    points = (
        Vector3(0, 0, 0),
        Vector3(0.5 * scale, 0, 0),
        Vector3(scale, scale if curved else 0, 0),
    )
    radius = 100 * scale if curved else 0.1
    result = probe_certificate(points, scale, Vector3(0, 0, 0), radius)
    rejected = result["first_rejected_interval"]
    assert result["rejection"]
    assert rejected["depth"] == 16
    assert rejected["curvature_bound_ok"] is (not curved)
    assert rejected["containment_ok"] is curved
    assert rejected["frame_regular"] is True
    assert sys.gettrace() is None
    if curved:
        assert result["sampled_worst_curvature"]["curvature_times_reach"] == pytest.approx(2)


def test_normalization_error_is_distinct_from_geometry_rejection() -> None:
    """
    Preserve the existing small-vector normalization error as a separate outcome.
    """
    points = (Vector3(0, 0, 0), Vector3(0.5, 0, 0), Vector3(1, 1, 0))
    result = probe_certificate(points, 1, Vector3(0, 0, 0), 100)
    assert "rejection" not in result
    assert result["certificate_error"] == "Routing normals must be finite nonzero vectors."
    interval = result["first_rejected_interval"]
    assert interval["exception_type"] == "ValueError"
    assert interval["frame_regular"] is None
    assert 1e-18 < interval["local_binormal_magnitude"] <= 1e-12
    assert sys.gettrace() is None


def test_successful_straight_certificate_retains_its_original_result() -> None:
    """
    Observing an accepted curve does not introduce a diagnostic rejection.
    """
    points = (Vector3(0, 0, 0), Vector3(0.5, 0, 0), Vector3(1, 0, 0))
    result = probe_certificate(points, 1, Vector3(0, 0, 0), 100)
    assert result["certificate"]["maximum_ratio"] == 0
    assert result["first_rejected_interval"] is None
    assert result["visited_intervals"] == 1
    assert sys.gettrace() is None
