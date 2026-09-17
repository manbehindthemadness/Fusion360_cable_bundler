"""
Tests for group-only transactional harness editing.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Protocol, cast
from uuid import UUID

from wire_bundler.application import (
    HarnessEditGateway,
    WireEditorPairing,
    save_wire_editor,
    set_harness_properties,
    set_wire_group_material_overrides,
    set_wire_group_properties,
)
from wire_bundler.domain import (
    Connection,
    HarnessDefinition,
    PathwayEndpoint,
    StandaloneEndDefinition,
    WireColor,
    WireMaterialOverrides,
    dumps,
    loads,
)


class _RecordingGateway(HarnessEditGateway, Protocol):
    """
    Expose serialized state recorded by the in-memory gateway.
    """

    serialized_definition: str


def _recording_gateway(definition: HarnessDefinition) -> _RecordingGateway:
    """
    Return an in-memory gateway for one definition.
    """
    state = SimpleNamespace(serialized_definition=dumps(definition))

    def read_harness_definition(_harness_id: UUID) -> str:
        return state.serialized_definition

    def replace_harness_definition(_harness_id: UUID, serialized_definition: str) -> None:
        state.serialized_definition = serialized_definition

    state.read_harness_definition = read_harness_definition
    state.replace_harness_definition = replace_harness_definition
    return cast(_RecordingGateway, cast(object, state))


def test_edits_group_construction_and_visual_overrides(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist group-owned construction and appearance settings.
    """
    gateway = _recording_gateway(valid_harness)
    group = valid_harness.wire_groups[0]
    overrides = WireMaterialOverrides(
        insulation_material="ETFE",
        conductor_material="Tinned Copper",
        main_color=WireColor("Red", 255, 0, 0),
        manufacturer="Maker",
        part_number="WG-01",
        notes="Grouped conductor",
    )

    set_wire_group_properties(
        valid_harness.harness_id,
        group.wire_group_id,
        2.4,
        "ETFE",
        "Tinned Copper",
        "Maker",
        "WG-01",
        "Grouped conductor",
        gateway,
    )
    set_wire_group_material_overrides(
        valid_harness.harness_id,
        group.wire_group_id,
        overrides,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.wire_groups[0].diameter_mm == 2.4
    assert stored.wire_groups[0].material_overrides.main_color.name == "Red"
    assert stored.wire_group_materials(stored.wire_groups[0]).part_number == "WG-01"


def test_harness_properties_flow_into_group_inheritance(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Resolve group settings from changed harness defaults when not overridden.
    """
    gateway = _recording_gateway(valid_harness)

    set_harness_properties(
        valid_harness.harness_id,
        "PTFE",
        "Silver Copper",
        "Parent Maker",
        "PARENT-1",
        "Parent notes",
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    materials = stored.wire_group_materials(stored.wire_groups[0])
    assert materials.insulation_material == "PTFE"
    assert materials.part_number == "PARENT-1"


def test_wire_editor_creates_group_from_two_standalone_ends(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create a stable group directly from endpoints on distinct boundaries.
    """
    left_id = UUID("62000000-0000-0000-0000-000000000001")
    right_id = UUID("62000000-0000-0000-0000-000000000002")
    group_id = UUID("63000000-0000-0000-0000-000000000001")
    pathway = valid_harness.pathways[0]
    definition = replace(
        valid_harness,
        connections=(
            Connection(left_id, "Left", "left-token"),
            Connection(right_id, "Right", "right-token"),
        ),
        standalone_ends=(
            StandaloneEndDefinition(left_id, pathway.pathway_id, PathwayEndpoint.START),
            StandaloneEndDefinition(right_id, pathway.pathway_id, PathwayEndpoint.END),
        ),
        wire_groups=(),
    )
    gateway = _recording_gateway(definition)

    save_wire_editor(
        definition.harness_id,
        pathway.pathway_id,
        PathwayEndpoint.START,
        pathway.pathway_id,
        PathwayEndpoint.END,
        (WireEditorPairing(left_id, right_id),),
        (),
        (),
        (),
        gateway,
        id_factory=lambda: group_id,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.wire_groups[0].wire_group_id == group_id
    assert stored.wire_groups[0].connection_ids == (left_id, right_id)
