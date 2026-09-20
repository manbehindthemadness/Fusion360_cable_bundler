"""
Regression tests for decoration continuity across generated solid segments.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from types import ModuleType
from typing import Any, Iterator, Optional, Protocol, cast
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import CableColor, CableStripe, HarnessDefinition, StripePattern
from cable_bundler.routing import CubicBezier, RoutePreview, StripeMeshResult, Vector3
from cable_bundler.routing.geometry import difference, dot, unit


class _SweepSegment(Protocol):
    """
    Describe one private junction-bounded solid construction segment.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


class _VisibilityState(Protocol):
    """
    Describe captured generated body and stripe visibility.
    """

    occurrences: tuple[tuple[object, bool], ...]
    stripe_groups: tuple[tuple[object, bool], ...]


class _CableSolidsModule(Protocol):
    """
    Describe the host adapter functions exercised without a live Fusion process.
    """

    GENERATED_STRIPE_GROUP_ID: str
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
            CableStripe,
            float,
        ],
        tuple[tuple[_SweepSegment, StripeMeshResult], ...],
    ]
    restore_cable_group_stripe_graphics: Callable[[object, object], int]
    generated_cable_group_occurrences: Callable[[object], tuple[object, ...]]
    hide_generated_cable_group_solids: Callable[[object], _VisibilityState]
    restore_generated_cable_group_visibility: Callable[[_VisibilityState], None]
    _replace_group_stripe_graphics: Callable[..., int]


@pytest.fixture
def cable_solids(monkeypatch: pytest.MonkeyPatch) -> Iterator[_CableSolidsModule]:
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
        "cable_bundler.fusion.cable_solids",
        "cable_bundler.fusion.route_preview",
        "cable_bundler.fusion.harness_gateway",
    )
    fusion_package = importlib.import_module("cable_bundler.fusion")
    missing = object()
    previous_attributes = {
        module_name.rsplit(".", 1)[-1]: getattr(
            fusion_package, module_name.rsplit(".", 1)[-1], missing
        )
        for module_name in module_names
    }
    for module_name in module_names:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = importlib.import_module("cable_bundler.fusion.cable_solids")
    yield cast(_CableSolidsModule, cast(object, module))
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


def test_restores_transient_stripes_from_generated_routes(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Recreate decorations after reload without regenerating persistent bodies.
    """
    definition = replace(
        valid_harness,
        material_defaults=replace(
            valid_harness.material_defaults,
            stripes=(CableStripe(CableColor("Red", 255, 0, 0), 0.25),),
        ),
    )
    group = definition.cable_groups[0]
    route = _straight_route(900, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    metadata = {
        "cable_group_id": str(group.cable_group_id),
        "route_legs": [
            {
                "route_id": str(route.cable_id),
                "label": route.cable_number,
                "route_curves_mm": [
                    [
                        [point.x, point.y, point.z]
                        for point in (
                            route.curves[0].start,
                            route.curves[0].control_a,
                            route.curves[0].control_b,
                            route.curves[0].end,
                        )
                    ]
                ],
            }
        ],
    }
    attribute = type("Attribute", (), {"value": json.dumps(metadata)})()
    attributes = type("Attributes", (), {"itemByName": lambda *_args: attribute})()
    empty_graphics = type("GraphicsGroups", (), {"count": 0})()
    component = type(
        "Component",
        (),
        {"attributes": attributes, "customGraphicsGroups": empty_graphics},
    )()
    occurrence = type(
        "Occurrence",
        (),
        {"component": component, "isLightBulbOn": False},
    )()
    replace_graphics = Mock(return_value=4)
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (occurrence,),
    )
    monkeypatch.setattr(
        cable_solids,
        "_replace_group_stripe_graphics",
        replace_graphics,
    )

    harness = object()

    assert cable_solids.restore_cable_group_stripe_graphics(harness, definition) == 4

    assert replace_graphics.call_args.args[0] is harness
    restored_routes = replace_graphics.call_args.args[1]
    assert restored_routes == (route,)
    assert replace_graphics.call_args.args[3] == group.diameter_mm / 2.0
    assert replace_graphics.call_args.args[4] == group.cable_group_id
    assert replace_graphics.call_args.kwargs == {"is_visible": False}


def test_replacing_harness_owned_stripes_preserves_other_cable_groups(
    cable_solids: _CableSolidsModule,
) -> None:
    """
    Replace one stable harness overlay without deleting a neighboring group.
    """
    target_id = UUID(int=701)
    other_id = UUID(int=702)

    def graphics_group(identity: UUID) -> Any:
        """
        Build one empty deletable stripe-group test double.
        """
        return type(
            "StripeGroup",
            (),
            {
                "id": f"{cable_solids.GENERATED_STRIPE_GROUP_ID}:{identity}",
                "name": "Cable Group Solid Stripes",
                "count": 0,
                "deleteMe": Mock(return_value=True),
            },
        )()

    target = graphics_group(target_id)
    other = graphics_group(other_id)
    stored = (target, other)
    groups = type(
        "GraphicsGroups",
        (),
        {"count": len(stored), "item": lambda _self, index: stored[index]},
    )()
    harness = type("Harness", (), {"customGraphicsGroups": groups})()

    assert cable_solids._replace_group_stripe_graphics(harness, (), (), 0.5, target_id) == 0

    target.deleteMe.assert_called_once_with()
    other.deleteMe.assert_not_called()


def test_generated_solids_visibility_round_trip_preserves_prior_state(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Hide visible managed occurrences temporarily without revealing prior-hidden output.
    """
    visible = type("Occurrence", (), {"isLightBulbOn": True, "isValid": True})()
    hidden = type("Occurrence", (), {"isLightBulbOn": False, "isValid": True})()
    stripe_group = type(
        "StripeGroup",
        (),
        {
            "id": f"{cable_solids.GENERATED_STRIPE_GROUP_ID}:{UUID(int=1)}",
            "name": "Cable Group Solid Stripes",
            "isVisible": True,
            "isValid": True,
        },
    )()
    groups = type(
        "GraphicsGroups",
        (),
        {"count": 1, "item": lambda _self, _index: stripe_group},
    )()
    harness = type("Harness", (), {"customGraphicsGroups": groups})()
    monkeypatch.setattr(
        cable_solids,
        "generated_cable_group_occurrences",
        lambda _harness: (visible, hidden),
    )

    state = cable_solids.hide_generated_cable_group_solids(harness)

    assert state.occurrences == ((visible, True), (hidden, False))
    assert state.stripe_groups == ((stripe_group, True),)
    assert not visible.isLightBulbOn
    assert not hidden.isLightBulbOn
    assert not stripe_group.isVisible

    cable_solids.restore_generated_cable_group_visibility(state)

    assert visible.isLightBulbOn
    assert not hidden.isLightBulbOn
    assert stripe_group.isVisible


def test_copies_root_decoration_position_to_every_branch(
    cable_solids: _CableSolidsModule,
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
    stripe = CableStripe(CableColor("Red", 255, 0, 0), 0.25, angle_deg=31.0)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

    start_radials = [_radial(result, "start") for _segment, result in decorated]
    assert len(start_radials) == 3
    assert start_radials[1] == pytest.approx(start_radials[0])
    assert start_radials[2] == pytest.approx(start_radials[0])


def test_projects_continuous_decoration_onto_an_angled_branch(
    cable_solids: _CableSolidsModule,
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
    stripe = CableStripe(CableColor("Green", 0, 180, 80), 0.25, angle_deg=27.0)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(
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
    cable_solids: _CableSolidsModule,
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
    stripe = CableStripe(
        CableColor("White", 255, 255, 255),
        0.2,
        StripePattern.HELICAL,
        angle_deg=18.0,
        repeat_mm=7.0,
    )

    segments, starts, ends = cable_solids._prepare_group_sweep_segments(routes)
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)
    by_identity = {segment.route.cable_id.int: result for segment, result in decorated}

    upstream_end = _radial(by_identity[10], "end")
    assert _radial(by_identity[13], "start") == pytest.approx(upstream_end)
    assert _radial(by_identity[14], "start") == pytest.approx(upstream_end)
    assert by_identity[13].start is not None
    assert by_identity[14].start is not None
    assert by_identity[13].start.repeat_phase_mm == pytest.approx(3.0)
    assert by_identity[14].start.repeat_phase_mm == pytest.approx(3.0)


def test_continues_across_an_internally_split_pass_through_route(
    cable_solids: _CableSolidsModule,
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
    stripe = CableStripe(CableColor("Blue", 0, 80, 255), 0.2)

    segments, starts, ends = cable_solids._prepare_group_sweep_segments((pass_through, lead))
    decorated = cable_solids._build_continuous_segment_stripes(segments, starts, ends, stripe, 0.5)

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
