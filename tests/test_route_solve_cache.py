"""
Regressions for geometry-validated route-solve reuse.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from tests.fusion_ui_support import _PaletteLifecycleModule
from wire_bundler.domain import AutoTransitionPreset, ControlStructure, HarnessDefinition
from wire_bundler.routing import RefineFrame, Vector3


def test_reuses_solve_until_resolved_geometry_or_definition_changes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse Preview geometry for Generate while rejecting stale Fusion inputs.
    """
    from wire_bundler.fusion import route_preview

    del addin_module
    design = object()
    gate_z = [10.0]

    def routing_frame(_design: object, control: ControlStructure, control_id: UUID) -> RefineFrame:
        """
        Return the current synthetic control geometry.
        """
        return RefineFrame(
            control_id,
            control.name,
            Vector3(0.0, 0.0, gate_z[0]),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    def profile_frame(_design: object, token: str) -> Any:
        """
        Return distinct synthetic start and end profile frames.
        """
        z = 0.0 if token == "fusion-start-token" else 20.0
        return route_preview._ProfileFrame(
            Vector3(0.0, 0.0, z),
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, 0.0, 0.0),
            Vector3(0.0, 1.0, 0.0),
        )

    monkeypatch.setattr(route_preview, "_routing_frame", routing_frame)
    monkeypatch.setattr(route_preview, "_profile_frame", profile_frame)
    monkeypatch.setattr(route_preview, "_route_solve_cache", None)

    first = route_preview.solve_wire_group_centerlines(design, valid_harness)
    second = route_preview.solve_wire_group_centerlines(design, valid_harness)

    assert second == first
    assert second[0] is first[0]
    assert second[1] is first[1]

    gate_z[0] = 11.0
    moved = route_preview.solve_wire_group_centerlines(design, valid_harness)
    renamed = route_preview.solve_wire_group_centerlines(
        design,
        replace(valid_harness, name="Renamed Harness"),
    )
    relaxed = route_preview.solve_wire_group_centerlines(
        design,
        replace(
            valid_harness,
            auto_transition_preset=AutoTransitionPreset.LOOSE,
        ),
    )

    assert moved != first
    assert renamed == moved
    assert moved[0] is not first[0]
    assert renamed[0] is not moved[0]
    assert relaxed != renamed
    assert relaxed[0] is not renamed[0]
