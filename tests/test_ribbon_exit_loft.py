"""
Deterministic route sampling for in-place ribbon exit lofts.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from tests.fusion_ui_support import _PaletteLifecycleModule


def test_reverse_samples_keep_target_and_cap_once(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reverse joined cubics without duplicating their common section.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts.ribbon_exit_loft import _reverse_samples
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    first = CubicBezier(
        Vector3(0.0, 0.0, 0.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(2.0, 0.0, 0.0),
        Vector3(3.0, 0.0, 0.0),
    )
    second = CubicBezier(
        first.end,
        Vector3(4.0, 0.0, 0.0),
        Vector3(5.0, 0.0, 0.0),
        Vector3(6.0, 0.0, 0.0),
    )
    route = RoutePreview(
        UUID(int=101), "Exit", (first.start, first.end, second.end), (first, second)
    )

    samples = _reverse_samples(route)

    assert len(samples) == 9
    assert samples[0][0] == second.end
    assert samples[-1][0] == first.start
    assert all(tangent == Vector3(1.0, 0.0, 0.0) for _point, tangent in samples)


def test_reverse_samples_recover_zero_endpoint_handles(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Section normals remain defined for a straight cubic with collapsed handles.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts.ribbon_exit_loft import _reverse_samples
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start = Vector3(0.0, 0.0, 0.0)
    end = Vector3(10.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=102), "Exit", (start, end), (CubicBezier(start, start, end, end),)
    )

    samples = _reverse_samples(route)

    assert samples[0][1] == Vector3(1.0, 0.0, 0.0)
    assert samples[-1][1] == Vector3(1.0, 0.0, 0.0)


def test_reverse_samples_reject_zero_length_route(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Never submit a loft containing only one geometric section.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts.ribbon_exit_loft import _reverse_samples
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    point = Vector3(0.0, 0.0, 0.0)
    route = RoutePreview(
        UUID(int=103), "Exit", (point, point), (CubicBezier(point, point, point, point),)
    )

    with pytest.raises(ValueError, match="route samples"):
        _reverse_samples(route)


def test_route_length_matches_straight_exit_span(addin_module: _PaletteLifecycleModule) -> None:
    """
    Metadata retains the route's logical length without a sweep measurement.
    """
    del addin_module
    from cable_bundler.fusion.cable_solid_parts.sweep_geometry import route_length_mm
    from cable_bundler.routing import CubicBezier, RoutePreview, Vector3

    start = Vector3(0.0, 0.0, 0.0)
    end = Vector3(10.0, 0.0, 0.0)
    curve = CubicBezier(start, Vector3(3.0, 0.0, 0.0), Vector3(7.0, 0.0, 0.0), end)
    route = RoutePreview(UUID(int=104), "Exit", (start, end), (curve,))

    assert route_length_mm(route) == pytest.approx(10.0)
