"""
Protect bounded certificate-only fixture selection without real ribbon solves.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import magnitude
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_cap_transition import curve_limit
from experiments.experiment_ribbon_cap_transition.fixtures import (
    certificate_limit_case,
    close_full_turn_case,
)
from experiments.experiment_secure_discrete_ribbon.contract import (
    CurvatureCertificate,
    UnsafeRibbon,
)


def test_radius_search_freezes_passing_side_and_retains_all_24_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise search control with a synthetic monotonic certificate, not geometry.
    """
    calls: list[float] = []

    def certificate(route: RoutePreview, reach: float) -> CurvatureCertificate:
        """
        Reject below a known threshold and record the unchanged material envelope.
        """
        radius = magnitude(route.curves[0].start)
        calls.append(radius)
        assert reach > 14
        if radius < 18.1234567:
            raise UnsafeRibbon("synthetic bound")
        return CurvatureCertificate(0.8 * 18.1234567 / radius, 1)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.curve_limit.certify_curvature", certificate
    )
    result = curve_limit.select_radius()
    assert len(calls) == len(result.checks) == 24
    assert result.rejected_radius_mm < 18.1234567 <= result.radius_mm
    assert result.radius_mm - result.rejected_radius_mm == pytest.approx(20 / 2**23)
    assert any(not check.passed for check in result.checks)
    assert result.maximum_ratio <= 0.8
    assert result.radius_mm in calls


def test_search_stops_if_parent_certificate_regresses(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reject an invalid parent without searching or masking unrelated exceptions.
    """

    def reject(_route: RoutePreview, _reach: float) -> CurvatureCertificate:
        """
        Simulate a contract rejection at the registered parent radius.
        """
        raise UnsafeRibbon("parent rejection")

    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.curve_limit.certify_curvature", reject
    )
    with pytest.raises(RuntimeError, match="Parent R20"):
        curve_limit.select_radius()


def test_search_stops_before_evaluation_when_time_cap_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refuse further authoring work when the measured scheduling cap is reached.
    """
    times = iter((0.0, 10.0))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_cap_transition.curve_limit.perf_counter", lambda: next(times)
    )
    with pytest.raises(RuntimeError, match="time cap"):
        curve_limit.select_radius()


@pytest.mark.parametrize("radius", (0, -1, 20.1, math.inf, math.nan))
def test_limit_fixture_rejects_invalid_radius(radius: float) -> None:
    """
    Reject nonpositive, nonfinite or enlarged authoring inputs.
    """
    with pytest.raises(ValueError, match="radius"):
        certificate_limit_case(radius)


def test_limit_fixture_preserves_parent_material_sphere_and_endpoint_roll() -> None:
    """
    A new fixture scale must not change material, sphere or cap directions.
    """
    parent, case = close_full_turn_case(), certificate_limit_case(18.2)
    assert case.lines == parent.lines and case.diameter_mm == parent.diameter_mm
    assert case.end_boundary == parent.end_boundary
    assert case.start_width == parent.start_width and case.end_width == parent.end_width
    assert magnitude(case.route.curves[0].start) == pytest.approx(18.2)
    assert magnitude(case.route.curves[-1].end) == pytest.approx(18.2)
    assert case.name != parent.name
