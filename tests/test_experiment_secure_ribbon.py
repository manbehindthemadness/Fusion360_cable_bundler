"""
Exercise continuous experiment certificates independently of Fusion.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3
from cable_bundler.routing.parallel import GateFrame, RoutePreview
from experiments.experiment_secure_discrete_ribbon.bank import RibbonBankGate, bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
    split_curve,
)
from experiments.experiment_secure_discrete_ribbon.frames import ribbon_frames


def _route(curve: CubicBezier) -> RoutePreview:
    """
    Retain the exact cubic rather than a sampled polyline.
    """
    return RoutePreview(UUID(int=1), "certificate", (curve.start, curve.end), (curve,))


@pytest.mark.parametrize("scale", (0.001, 1.0, 1000.0))
def test_certificates_are_scale_invariant(scale: float) -> None:
    """
    Certify a gentle curve and reject a tight curve at every physical scale.
    """
    curve = CubicBezier(
        *(Vector3(x * scale, y * scale, 0.0) for x, y in ((0, 0), (30, 0), (30, 30), (60, 30)))
    )
    certificate = certify_curvature(_route(curve), scale)
    assert 0.0 < certificate.maximum_ratio <= 0.8
    with pytest.raises(UnsafeRibbon, match="cannot be certified"):
        certify_curvature(_route(curve), 100 * scale, maximum_depth=8)


def test_subdivision_preserves_exact_cubic() -> None:
    """
    Cover both halves and their common point, not just endpoint positions.
    """
    curve = CubicBezier(Vector3(0, 0, 0), Vector3(10, 8, 4), Vector3(20, -7, 9), Vector3(30, 1, 2))
    left, right = split_curve(curve)
    for index in range(11):
        t = index / 10.0
        assert left.point(t).x == pytest.approx(curve.point(t / 2.0).x)
        assert right.point(t).z == pytest.approx(curve.point((1.0 + t) / 2.0).z)
    assert left.end == right.start == curve.point(0.5)


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), 0.0, -1.0))
def test_invalid_profile_never_reaches_builder(bad: float) -> None:
    """
    Reject malformed physical envelopes even for a straight centerline.
    """
    curve = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 10, 20, 30)))
    with pytest.raises(UnsafeRibbon):
        certify_curvature(_route(curve), bad)


def test_singular_and_corner_routes_are_rejected() -> None:
    """
    A straight-looking cubic cusp and a joined corner remain unsafe.
    """
    cusp = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 1, -1, 0)))
    with pytest.raises(UnsafeRibbon):
        certify_curvature(_route(cusp), 0.1, maximum_depth=8)
    a = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 1, 2, 3)))
    b = CubicBezier(*(Vector3(3, y, 0) for y in (0, 1, 2, 3)))
    route = RoutePreview(UUID(int=1), "corner", (a.start, b.end), (a, b))
    with pytest.raises(UnsafeRibbon, match="join"):
        certify_curvature(route, 0.1)


def test_envelope_includes_side_caps_and_thickness() -> None:
    """
    Use the whole ribbon envelope rather than one lane's radius.
    """
    assert discrete_profile_reach(19, 1.0) > 9.6


def test_infeasible_bank_is_a_failure_not_an_original_frame_fallback() -> None:
    """
    An undersized gate must stop every candidate, including the original bank.
    """
    curve = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 10, 20, 30)))
    frames = ribbon_frames(_route(curve), Vector3(0, 1, 0), Vector3(0, 1, 0))
    gate = GateFrame(
        UUID(int=2), "undersized", frames[16].origin, Vector3(0, 1, 0), Vector3(0, 0, 1), 0.1
    )
    with pytest.raises(UnsafeRibbon, match="bank"):
        bank_ribbon_frames(frames, 3, 1.0, (RibbonBankGate(16, gate),))


def test_nonfinite_curve_and_disconnected_route_are_rejected() -> None:
    """
    Invalid exact geometry is rejected without creating any Fusion entities.
    """
    curve = CubicBezier(*(Vector3(x, 0, 0) for x in (0, 10, 20, 30)))
    malformed = CubicBezier(curve.start, Vector3(float("nan"), 0, 0), curve.control_b, curve.end)
    with pytest.raises(UnsafeRibbon, match="Nonfinite"):
        certify_curvature(_route(malformed), 1.0)
    route = RoutePreview(UUID(int=1), "gap", (curve.start, curve.end), (curve, curve))
    with pytest.raises(UnsafeRibbon, match="Disconnected"):
        certify_curvature(route, 1.0)
