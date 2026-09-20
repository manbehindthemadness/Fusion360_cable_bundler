"""
Tests for group-only transactional harness editing.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Protocol, cast
from uuid import UUID

import pytest

from cable_bundler.application import (
    CableEditorPairing,
    HarnessEditGateway,
    add_end_refine,
    add_junction,
    append_end_guides,
    save_cable_editor,
    segment_pathway,
    set_cable_group_material_overrides,
    set_cable_group_properties,
    set_harness_properties,
    switch_standalone_end,
)
from cable_bundler.application.edit_harness import set_interpolation
from cable_bundler.domain import (
    AutoTransitionPreset,
    CableColor,
    CableMaterialOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    PathwayEndpoint,
    RefineGeometry,
    StandaloneEndDefinition,
    dumps,
    loads,
)
from cable_bundler.domain.model import InterpolationSettings


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


def test_appends_guides_to_end_without_mutating_parent_pathway(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Extend the selected connection's guide stack independently of its pathway.
    """
    gateway = _recording_gateway(valid_harness)
    connection = valid_harness.connections[0]
    new_member_id = UUID("21000000-0000-0000-0000-000000000001")

    append_end_guides(
        valid_harness.harness_id,
        connection.connection_id,
        ("new-end-guide",),
        gateway,
        id_factory=lambda: new_member_id,
    )

    stored = loads(gateway.serialized_definition)
    updated_connection = next(
        item for item in stored.connections if item.connection_id == connection.connection_id
    )
    assert updated_connection.member_tokens == (connection.entity_token, "new-end-guide")
    assert updated_connection.member_identities[-1] == new_member_id
    assert stored.pathways == valid_harness.pathways


def test_adds_end_owned_refine_without_mutating_parent_pathway(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist an end refine only in the selected standalone end's ordered stack.
    """
    gateway = _recording_gateway(valid_harness)
    end = valid_harness.standalone_ends[0]
    refine_id = UUID("31000000-0000-0000-0000-000000000001")
    geometry = RefineGeometry(
        origin_mm=(1.0, 2.0, 3.0),
        u_direction=(1.0, 0.0, 0.0),
        v_direction=(0.0, 1.0, 0.0),
        display_radius_mm=2.0,
    )

    add_end_refine(
        valid_harness.harness_id,
        end.connection_id,
        0,
        geometry,
        gateway,
        id_factory=lambda: refine_id,
    )

    stored = loads(gateway.serialized_definition)
    updated_end = next(
        item for item in stored.standalone_ends if item.connection_id == end.connection_id
    )
    assert updated_end.ordered_control_ids == (refine_id,)
    assert (
        next(item for item in stored.controls if item.control_id == refine_id).refine_geometry
        == geometry
    )
    assert stored.pathways == valid_harness.pathways


def test_switches_disconnected_end_between_pathway_boundaries(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Swap only the selected end's A/B relationship while preserving its identity.
    """
    definition = replace(valid_harness, cable_groups=())
    gateway = _recording_gateway(definition)
    end = definition.standalone_ends[0]

    switch_standalone_end(
        definition.harness_id,
        end.connection_id,
        gateway,
    )

    switched = loads(gateway.serialized_definition)
    switched_end = next(
        item for item in switched.standalone_ends if item.connection_id == end.connection_id
    )
    assert switched_end == replace(end, endpoint=PathwayEndpoint.END)
    assert switched.connections == definition.connections
    assert switched.pathways == definition.pathways

    switch_standalone_end(
        definition.harness_id,
        end.connection_id,
        gateway,
    )

    restored = loads(gateway.serialized_definition)
    assert (
        next(item for item in restored.standalone_ends if item.connection_id == end.connection_id)
        == end
    )


def test_rejects_switching_connected_end(valid_harness: HarnessDefinition) -> None:
    """
    Require detachment before an endpoint change can alter a routed group.
    """
    gateway = _recording_gateway(valid_harness)
    end = valid_harness.standalone_ends[0]

    with pytest.raises(
        ValueError,
        match="Only disconnected standalone ends can switch pathway boundaries",
    ):
        switch_standalone_end(
            valid_harness.harness_id,
            end.connection_id,
            gateway,
        )

    assert loads(gateway.serialized_definition) == valid_harness


def test_edits_group_construction_and_visual_overrides(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist group-owned construction and appearance settings.
    """
    gateway = _recording_gateway(valid_harness)
    group = valid_harness.cable_groups[0]
    overrides = CableMaterialOverrides(
        insulation_material="ETFE",
        conductor_material="Tinned Copper",
        main_color=CableColor("Red", 255, 0, 0),
        manufacturer="Maker",
        part_number="WG-01",
        notes="Grouped conductor",
    )

    set_cable_group_properties(
        valid_harness.harness_id,
        group.cable_group_id,
        2.4,
        "ETFE",
        "Tinned Copper",
        "Maker",
        "WG-01",
        "Grouped conductor",
        gateway,
    )
    set_cable_group_material_overrides(
        valid_harness.harness_id,
        group.cable_group_id,
        overrides,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].diameter_mm == 2.4
    assert stored.cable_groups[0].material_overrides.main_color.name == "Red"
    assert stored.cable_group_materials(stored.cable_groups[0]).part_number == "WG-01"


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
    materials = stored.cable_group_materials(stored.cable_groups[0])
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


def test_cable_editor_creates_group_from_two_standalone_ends(
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
        cable_groups=(),
    )
    gateway = _recording_gateway(definition)

    save_cable_editor(
        definition.harness_id,
        pathway.pathway_id,
        PathwayEndpoint.START,
        pathway.pathway_id,
        PathwayEndpoint.END,
        (CableEditorPairing(left_id, right_id),),
        (),
        (),
        (),
        gateway,
        id_factory=lambda: group_id,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].cable_group_id == group_id
    assert stored.cable_groups[0].connection_ids == (left_id, right_id)
