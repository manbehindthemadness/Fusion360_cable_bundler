"""
Regression tests for decoration continuity across generated solid segments.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Iterator, Optional, Protocol, cast
from uuid import UUID

import pytest

from wire_bundler.domain import StripePattern, WireColor, WireStripe
from wire_bundler.routing import CubicBezier, RoutePreview, StripeMeshResult, Vector3
from wire_bundler.routing.geometry import difference, dot, unit


class _SweepSegment(Protocol):
    """
    Describe one private junction-bounded solid construction segment.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


class _WireSolidsModule(Protocol):
    """
    Describe the host adapter functions exercised without a live Fusion process.
    """

    _prepare_group_sweep_segments: Callable[
        [tuple[RoutePreview, ...]],
        tuple[
            tuple[_SweepSegment, ...],
            tuple[Optional[int], ...],
            tuple[Optional[int], ...],
        ],
    ]
    _build_continuous_segment_stripes: Callable[
        [
            tuple[_SweepSegment, ...],
            tuple[Optional[int], ...],
            tuple[Optional[int], ...],
            WireStripe,
            float,
        ],
        tuple[tuple[_SweepSegment, StripeMeshResult], ...],
    ]


@pytest.fixture
def wire_solids(monkeypatch: pytest.MonkeyPatch) -> Iterator[_WireSolidsModule]:
    """
    Import the solid adapter against minimal Fusion module stubs.
    """
    adsk_module = ModuleType("adsk")
    core_module = ModuleType("adsk.core")
    fusion_module = ModuleType("adsk.fusion")
    adsk_module.core = core_module  # type: ignore[attr-defined]
    adsk_module.fusion = fusion_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adsk", adsk_module)
    monkeypatch.setitem(sys.modules, "adsk.core", core_module)
    monkeypatch.setitem(sys.modules, "adsk.fusion", fusion_module)
    module_names = (
        "wire_bundler.fusion.wire_solids",
        "wire_bundler.fusion.route_preview",
        "wire_bundler.fusion.harness_gateway",
    )
    fusion_package = importlib.import_module("wire_bundler.fusion")
    missing = object()
    previous_attributes = {
        module_name.rsplit(".", 1)[-1]: getattr(
            fusion_package, module_name.rsplit(".", 1)[-1], missing
        )
        for module_name in module_names
    }
    for module_name in module_names:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = importlib.import_module("wire_bundler.fusion.wire_solids")
    yield cast(_WireSolidsModule, cast(object, module))
    for name, previous in previous_attributes.items():
        if previous is missing:
            if hasattr(fusion_package, name):
                delattr(fusion_package, name)
        else:
            setattr(fusion_package, name, previous)


def _straight_route(identity: int, start: Vector3, end: Vector3) -> RoutePreview:
    """
    Build one exact straight route with stable identity.
    """
    delta = Vector3(
        (end.x - start.x) / 3.0,
        (end.y - start.y) / 3.0,
        (end.z - start.z) / 3.0,
    )
    curve = CubicBezier(
        start,
        start.translated(delta, 1.0),
        end.translated(delta, -1.0),
        end,
    )
    return RoutePreview(UUID(int=identity), f"Leg {identity}", (start, end), (curve,))


def _radial(result: StripeMeshResult, boundary: str) -> tuple[float, float, float]:
    """
    Return one required continuation radial for approximate comparisons.
    """
    continuation = result.start if boundary == "start" else result.end
    assert continuation is not None
    return continuation.radial.x, continuation.radial.y, continuation.radial.z


def test_copies_root_decoration_position_to_every_branch(
    wire_solids: _WireSolidsModule,
) -> None:
    """
    Give every segment leaving one junction the same physical stripe start.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _straight_route(1, Vector3(-10.0, 0.0, 0.0), junction),
        _straight_route(2, junction, Vector3(10.0, 0.0, 0.0)),
        _straight_route(3, junction, Vector3(15.0, 0.0, 0.0)),
    )
    stripe = WireStripe(WireColor("Red", 255, 0, 0), 0.25, angle_deg=31.0)

    segments, starts, ends = wire_solids._prepare_group_sweep_segments(routes)
    decorated = wire_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

    start_radials = [_radial(result, "start") for _segment, result in decorated]
    assert len(start_radials) == 3
    assert start_radials[1] == pytest.approx(start_radials[0])
    assert start_radials[2] == pytest.approx(start_radials[0])


def test_projects_continuous_decoration_onto_an_angled_branch(
    wire_solids: _WireSolidsModule,
) -> None:
    """
    Accept non-collinear junction tangents and retain a valid stripe radial.
    """
    junction = Vector3(0.0, 0.0, 0.0)
    routes = (
        _straight_route(4, Vector3(-10.0, 0.0, 0.0), junction),
        _straight_route(5, junction, Vector3(10.0, 0.0, 0.0)),
        _straight_route(6, junction, Vector3(0.0, 10.0, 0.0)),
    )
    stripe = WireStripe(WireColor("Green", 0, 180, 80), 0.25, angle_deg=27.0)

    segments, starts, ends = wire_solids._prepare_group_sweep_segments(routes)
    decorated = wire_solids._build_continuous_segment_stripes(
        segments,
        starts,
        ends,
        stripe,
        0.5,
    )

    assert len(segments) == len(decorated) == 3
    for segment, result in decorated:
        assert result.start is not None
        tangent = unit(difference(segment.route.points[1], segment.route.points[0]))
        assert dot(result.start.radial, tangent) == pytest.approx(0.0, abs=1e-9)
        assert result.start.repeat_phase_mm == pytest.approx(0.0)


def test_propagates_decoration_through_a_downstream_junction(
    wire_solids: _WireSolidsModule,
) -> None:
    """
    Continue an upstream helical endpoint onto every downstream child segment.
    """
    root = Vector3(0.0, 0.0, 0.0)
    downstream = Vector3(10.0, 0.0, 0.0)
    routes = (
        _straight_route(10, root, downstream),
        _straight_route(11, root, Vector3(-10.0, 0.0, 0.0)),
        _straight_route(12, root, Vector3(-15.0, 0.0, 0.0)),
        _straight_route(13, downstream, Vector3(20.0, 0.0, 0.0)),
        _straight_route(14, downstream, Vector3(25.0, 0.0, 0.0)),
    )
    stripe = WireStripe(
        WireColor("White", 255, 255, 255),
        0.2,
        StripePattern.HELICAL,
        angle_deg=18.0,
        repeat_mm=7.0,
    )

    segments, starts, ends = wire_solids._prepare_group_sweep_segments(routes)
    decorated = wire_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)
    by_identity = {segment.route.wire_id.int: result for segment, result in decorated}

    upstream_end = _radial(by_identity[10], "end")
    assert _radial(by_identity[13], "start") == pytest.approx(upstream_end)
    assert _radial(by_identity[14], "start") == pytest.approx(upstream_end)
    assert by_identity[13].start is not None
    assert by_identity[14].start is not None
    assert by_identity[13].start.repeat_phase_mm == pytest.approx(3.0)
    assert by_identity[14].start.repeat_phase_mm == pytest.approx(3.0)


def test_continues_across_an_internally_split_pass_through_route(
    wire_solids: _WireSolidsModule,
) -> None:
    """
    Decorate every solid segment created where a lead meets a logical route interior.
    """
    start = Vector3(-10.0, 0.0, 0.0)
    junction = Vector3(0.0, 0.0, 0.0)
    end = Vector3(10.0, 0.0, 0.0)
    left = _straight_route(20, start, junction).curves[0]
    right = _straight_route(20, junction, end).curves[0]
    pass_through = RoutePreview(UUID(int=20), "Pass Through", (start, junction, end), (left, right))
    lead = _straight_route(21, Vector3(-5.0, 0.0, 0.0), junction)
    stripe = WireStripe(WireColor("Blue", 0, 80, 255), 0.2)

    segments, starts, ends = wire_solids._prepare_group_sweep_segments((pass_through, lead))
    decorated = wire_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

    assert len(segments) == 3
    junction_boundaries = tuple(
        boundary
        for segment in segments
        for boundary in (segment.route.curves[0].start, segment.route.curves[-1].end)
        if boundary == junction
    )
    assert junction_boundaries == (junction,) * 3
    assert len(decorated) == 3
    start_radials = [_radial(result, "start") for _segment, result in decorated]
    assert start_radials[1] == pytest.approx(start_radials[0])
    assert start_radials[2] == pytest.approx(start_radials[0])
