"""
Verify finalized solid pullbacks retain logical route length.
"""

from __future__ import annotations

import importlib
import json
import sys
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.domain import HarnessDefinition
from cable_bundler.routing import RoutePreview, Vector3
from tests.test_cable_solid_decorations import _CableSolidsModule, _straight_route
from tests.test_cable_solid_decorations import cable_solids as cable_solids


def test_finalize_replaces_main_route_endpoint_with_pullback_body(
    cable_solids: _CableSolidsModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create a separate material body while retaining the complete connection length.
    """
    solid_builder = cast(
        Any,
        sys.modules["cable_bundler.fusion.cable_solid_parts.solid_builder"],
    )
    route = _straight_route(696, Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0))
    group = valid_harness.cable_groups[0]
    materials = valid_harness.material_defaults
    stored_bodies: list[Any] = []
    welds_module = importlib.import_module("cable_bundler.fusion.cable_solid_parts.welds")
    weld_endpoint = welds_module.WeldEndpoint(
        UUID(int=697),
        object(),
        group.diameter_mm * 0.75,
        materials.weld,
    )

    class _Bodies:
        @property
        def count(self) -> int:
            return len(stored_bodies)

    def build_sweep(
        _component: object,
        sweep_route: RoutePreview,
        diameter_mm: float,
        _transform: object,
        _centerline_name: str,
        _section_name: str,
        _sweep_name: str,
    ) -> tuple[object, float]:
        """
        Record exact split routes without invoking the live Fusion API.
        """
        body = SimpleNamespace(
            name="",
            appearance=None,
            route=sweep_route,
            diameter_mm=diameter_mm,
        )
        stored_bodies.append(body)
        length_mm = abs(sweep_route.curves[-1].end.x - sweep_route.curves[0].start.x)
        return body, length_mm

    add_attribute = Mock(return_value=object())
    component = SimpleNamespace(
        bRepBodies=_Bodies(),
        attributes=SimpleNamespace(add=add_attribute),
        name="",
    )
    stripes = Mock(return_value=0)
    preview_stripes = Mock(return_value=0)
    monkeypatch.setitem(solid_builder.__dict__, "_build_route_sweep", build_sweep)

    def build_weld(
        _component: object,
        _route: RoutePreview,
        _transform: object,
        _endpoint: object,
        _name: str,
    ) -> object:
        """
        Record a distinct finalized weld body without invoking Fusion.
        """
        body = SimpleNamespace(name="", appearance=None)
        stored_bodies.append(body)
        return SimpleNamespace(body=body, length_mm=weld_endpoint.radius_mm)

    monkeypatch.setitem(solid_builder.__dict__, "build_weld_body", build_weld)
    monkeypatch.setitem(
        solid_builder.__dict__,
        "route_in_component_space",
        lambda item, _matrix: item,
    )
    monkeypatch.setitem(
        solid_builder.__dict__,
        "cable_appearance",
        lambda _design, color, _reference=None: color.name,
    )
    monkeypatch.setitem(solid_builder.__dict__, "clear_group_stripe_graphics", Mock())
    monkeypatch.setitem(solid_builder.__dict__, "replace_group_stripe_bodies", stripes)
    monkeypatch.setitem(solid_builder.__dict__, "replace_group_stripe_graphics", preview_stripes)

    solid_builder.build_cable_group_solid(
        component,
        object(),
        group,
        0,
        (route,),
        object(),
        valid_harness.harness_id,
        materials,
        object(),
        "finalized",
        route_pullbacks_mm=(2.4,),
        route_end_pullbacks_mm=(0.0,),
        route_pullback_materials=(materials,),
        route_pullback_attachment_ids=(UUID(int=697),),
        route_pullback_diameters_mm=(group.diameter_mm * 0.75,),
        route_end_pullback_diameters_mm=(0.0,),
        route_welds=(weld_endpoint,),
    )

    assert len(stored_bodies) == 3
    assert stored_bodies[0].appearance == "Black"
    assert stored_bodies[0].diameter_mm == pytest.approx(group.diameter_mm)
    assert stored_bodies[0].route.curves[0].start.x == pytest.approx(2.4)
    assert stored_bodies[1].appearance == "Copper"
    assert stored_bodies[1].diameter_mm == pytest.approx(group.diameter_mm * 0.75)
    assert stored_bodies[1].route.curves[0].start.x == pytest.approx(0.0)
    assert stored_bodies[1].route.curves[-1].end.x == pytest.approx(2.4)
    assert stored_bodies[2].appearance == "Silver"
    assert component.name.endswith("_10.00mm")
    metadata = json.loads(add_attribute.call_args.args[2])
    assert metadata["length_mm"] == pytest.approx(10.0)
    assert metadata["main_pullbacks"][0]["requested_mm"] == pytest.approx(2.4)
    assert metadata["main_pullbacks"][0]["diameter_mm"] == pytest.approx(group.diameter_mm * 0.75)
    assert metadata["main_welds"][0]["diameter_mm"] == pytest.approx(group.diameter_mm * 0.75 * 1.5)
    assert metadata["main_welds"][0]["length_mm"] == pytest.approx(group.diameter_mm * 0.75 * 0.75)
    assert metadata["weld"] == {
        "appearance": None,
        "color": "#C0C0C0",
        "color_name": "Silver",
        "value": 150.0,
    }
    stripe_routes = stripes.call_args.args[1]
    assert stripe_routes[0].curves[0].start.x == pytest.approx(2.4)

    stored_bodies.clear()
    preview_component = SimpleNamespace(
        bRepBodies=_Bodies(),
        attributes=SimpleNamespace(add=Mock(return_value=object())),
        name="",
    )
    solid_builder.build_cable_group_solid(
        preview_component,
        object(),
        group,
        0,
        (route,),
        object(),
        valid_harness.harness_id,
        materials,
        object(),
        "solids",
        route_pullbacks_mm=(2.4,),
        route_pullback_materials=(materials,),
        route_pullback_attachment_ids=(UUID(int=697),),
        route_welds=(weld_endpoint,),
    )

    assert len(stored_bodies) == 1
    assert stored_bodies[0].route == route
    assert stored_bodies[0].appearance == "Black"
    preview_routes = preview_stripes.call_args.args[1]
    assert preview_routes == (route,)
