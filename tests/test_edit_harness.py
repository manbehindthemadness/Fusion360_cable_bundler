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
    add_junction,
    save_wire_editor,
    segment_pathway,
    set_harness_properties,
    set_wire_group_material_overrides,
    set_wire_group_properties,
)
from wire_bundler.application.edit_harness import set_interpolation
from wire_bundler.domain import (
    AutoTransitionPreset,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    PathwayEndpoint,
    StandaloneEndDefinition,
    WireColor,
    WireMaterialOverrides,
    dumps,
    loads,
)
from wire_bundler.domain.model import InterpolationSettings


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


def test_new_junction_control_inherits_gate_interpolation_defaults(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Treat a junction crossing as a default-backed routing control.
    """
    gate_defaults = InterpolationSettings(approach_mm=3.0, departure_mm=4.5)
    definition = replace(valid_harness, gate_defaults=gate_defaults)
    gateway = _recording_gateway(definition)
    generated_ids = iter(
        (
            UUID("64000000-0000-0000-0000-000000000001"),
            UUID("64000000-0000-0000-0000-000000000002"),
        )
    )

    junction = add_junction(
        definition.harness_id,
        "junction-token",
        gateway,
        id_factory=lambda: next(generated_ids),
    )

    stored = loads(gateway.serialized_definition)
    control = next(item for item in stored.controls if item.control_id == junction.control_id)
    assert control.interpolation == gate_defaults
    assert control.interpolation_is_override is False


def test_segmented_junction_retains_source_control_interpolation(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve an interior control's explicit settings when it becomes a junction.
    """
    pathway = valid_harness.pathways[0]
    first_id = UUID("65000000-0000-0000-0000-000000000001")
    junction_control_id = UUID("65000000-0000-0000-0000-000000000002")
    last_id = UUID("65000000-0000-0000-0000-000000000003")
    source_settings = InterpolationSettings(approach_mm=6.0, departure_mm=7.0)
    controls = (
        ControlStructure(first_id, "Gate 1", ControlKind.ROUTING_GATE, "gate-1"),
        ControlStructure(
            junction_control_id,
            "Gate 2",
            ControlKind.ROUTING_GATE,
            "gate-2",
            source_settings,
            True,
        ),
        ControlStructure(last_id, "Gate 3", ControlKind.ROUTING_GATE, "gate-3"),
    )
    definition = replace(
        valid_harness,
        controls=controls,
        pathways=(replace(pathway, ordered_control_ids=(first_id, junction_control_id, last_id)),),
    )
    gateway = _recording_gateway(definition)
    generated_ids = iter(
        (
            UUID("66000000-0000-0000-0000-000000000001"),
            UUID("66000000-0000-0000-0000-000000000002"),
        )
    )

    result = segment_pathway(
        definition.harness_id,
        pathway.pathway_id,
        junction_control_id,
        "Following Pathway",
        gateway,
        id_factory=lambda: next(generated_ids),
    )

    stored = loads(gateway.serialized_definition)
    retained = next(
        item for item in stored.controls if item.control_id == result.junction.control_id
    )
    assert retained.interpolation == source_settings
    assert retained.interpolation_is_override is True


def test_apply_existing_defaults_updates_junctions_and_end_fallbacks(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Apply changed presets without replacing explicit control or end-member overrides.
    """
    inherited_control = valid_harness.controls[0]
    overridden_control = ControlStructure(
        UUID("67000000-0000-0000-0000-000000000001"),
        "Explicit Gate",
        ControlKind.ROUTING_GATE,
        "explicit-gate",
        InterpolationSettings(8.0, 9.0),
        True,
    )
    junction = JunctionDefinition(
        UUID("67000000-0000-0000-0000-000000000002"),
        "Junction 01",
        inherited_control.control_id,
    )
    connection = replace(
        valid_harness.connections[0],
        additional_entity_tokens=("start-guide",),
        member_interpolations=(InterpolationSettings(10.0, 11.0), None),
    )
    definition = replace(
        valid_harness,
        controls=(inherited_control, overridden_control),
        connections=(connection, valid_harness.connections[1]),
        junctions=(junction,),
    )
    gateway = _recording_gateway(definition)
    gate_defaults = InterpolationSettings(2.0, 3.0)
    end_defaults = InterpolationSettings(4.0, 5.0)

    set_interpolation(
        definition.harness_id,
        "defaults",
        gate_defaults,
        gateway,
        end_defaults=end_defaults,
        apply_existing=True,
        auto_transition_preset=AutoTransitionPreset.RELAXED,
    )

    stored = loads(gateway.serialized_definition)
    controls_by_id = {item.control_id: item for item in stored.controls}
    updated_connection = next(
        item for item in stored.connections if item.connection_id == connection.connection_id
    )
    assert controls_by_id[inherited_control.control_id].interpolation == gate_defaults
    assert controls_by_id[overridden_control.control_id] == overridden_control
    assert updated_connection.interpolation == end_defaults
    assert updated_connection.member_settings == (
        InterpolationSettings(10.0, 11.0),
        end_defaults,
    )
    assert stored.auto_transition_preset is AutoTransitionPreset.RELAXED


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
