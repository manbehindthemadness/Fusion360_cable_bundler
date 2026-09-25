"""
Tests for group-only transactional harness editing.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application import (
    CableEditorPairing,
    add_end_refine,
    add_junction,
    append_end_guides,
    remove_end_control,
    remove_end_guide,
    rename_cable_group,
    rename_harness,
    save_cable_editor,
    segment_pathway,
    set_cable_end_properties,
    set_cable_group_material_overrides,
    set_cable_group_properties,
    set_harness_properties,
    set_junction_properties,
    set_pathway_end_properties,
    set_pathway_properties,
    suggest_junction_name,
    switch_standalone_end,
)
from cable_bundler.application.harness_edits import set_interpolation
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
    loads,
)
from cable_bundler.domain.model import InterpolationSettings
from tests.harness_edit_support import recording_gateway as _recording_gateway


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


def test_removes_end_guides_and_controls_by_stable_identity(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve remaining guide settings and prune an end-owned refine definition.
    """
    connection = valid_harness.connections[0]
    end = valid_harness.standalone_ends[0]
    first_member_id = UUID("21000000-0000-0000-0000-000000000001")
    second_member_id = UUID("21000000-0000-0000-0000-000000000002")
    refine_id = UUID("31000000-0000-0000-0000-000000000001")
    first_settings = InterpolationSettings(1.0, 2.0)
    second_settings = InterpolationSettings(3.0, 4.0)
    refine = ControlStructure(
        refine_id,
        "Refine Point 01",
        ControlKind.REFINE,
        "",
        refine_geometry=RefineGeometry(
            origin_mm=(1.0, 2.0, 3.0),
            u_direction=(1.0, 0.0, 0.0),
            v_direction=(0.0, 1.0, 0.0),
            display_radius_mm=2.0,
        ),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(
                connection,
                entity_token="first-guide",
                additional_entity_tokens=("second-guide",),
                member_ids=(first_member_id, second_member_id),
                member_interpolations=(first_settings, second_settings),
            ),
            *valid_harness.connections[1:],
        ),
        controls=(*valid_harness.controls, refine),
        standalone_ends=(
            replace(end, ordered_control_ids=(refine_id,)),
            *valid_harness.standalone_ends[1:],
        ),
    )
    gateway = _recording_gateway(definition)

    remove_end_guide(
        definition.harness_id,
        connection.connection_id,
        first_member_id,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    updated_connection = next(
        item for item in stored.connections if item.connection_id == connection.connection_id
    )
    assert updated_connection.member_tokens == ("second-guide",)
    assert updated_connection.member_identities == (second_member_id,)
    assert updated_connection.member_interpolations == (second_settings,)

    remove_end_control(
        definition.harness_id,
        connection.connection_id,
        refine_id,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    updated_end = next(
        item for item in stored.standalone_ends if item.connection_id == connection.connection_id
    )
    assert updated_end.ordered_control_ids == ()
    assert all(control.control_id != refine_id for control in stored.controls)


def test_rejects_removing_the_only_end_guide(valid_harness: HarnessDefinition) -> None:
    """
    Preserve the minimum terminal guide required by a standalone cable end.
    """
    connection = valid_harness.connections[0]
    gateway = _recording_gateway(valid_harness)

    with pytest.raises(ValueError, match="retain at least one guide"):
        remove_end_guide(
            valid_harness.harness_id,
            connection.connection_id,
            connection.member_identities[0],
            gateway,
        )

    assert loads(gateway.serialized_definition) == valid_harness


def test_renames_harness_without_changing_identity(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Normalize and persist the editable harness display name.
    """
    gateway = _recording_gateway(valid_harness)

    rename_harness(valid_harness.harness_id, "  Engine Harness  ", gateway)

    stored = loads(gateway.serialized_definition)
    assert stored.name == "Engine Harness"
    assert stored.harness_id == valid_harness.harness_id


def test_rejects_empty_harness_name(valid_harness: HarnessDefinition) -> None:
    """
    Keep the persisted definition valid when an empty rename is submitted.
    """
    gateway = _recording_gateway(valid_harness)

    with pytest.raises(ValueError, match="must not be empty"):
        rename_harness(valid_harness.harness_id, "   ", gateway)

    assert loads(gateway.serialized_definition) == valid_harness


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


def test_switches_unassigned_end_between_pathway_boundaries(
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


def test_rejects_switching_assigned_end(valid_harness: HarnessDefinition) -> None:
    """
    Require detachment before an endpoint change can alter a routed group.
    """
    gateway = _recording_gateway(valid_harness)
    end = valid_harness.standalone_ends[0]

    with pytest.raises(
        ValueError,
        match="Only unassigned standalone ends can switch pathway boundaries",
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
        "Braided copper",
        "FEP",
        "Maker",
        "WG-01",
        (("drawing-zone", "B4"),),
        gateway,
        conductor_diameter_mm=1.8,
    )
    set_cable_group_material_overrides(
        valid_harness.harness_id,
        group.cable_group_id,
        overrides,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].diameter_mm == 2.4
    assert stored.cable_groups[0].conductor_diameter_mm == 1.8
    assert stored.cable_groups[0].resolved_conductor_diameter_mm == 1.8
    main_color = stored.cable_groups[0].material_overrides.main_color
    assert main_color is not None
    assert main_color.name == "Red"
    assert stored.cable_group_materials(stored.cable_groups[0]).part_number == "WG-01"
    assert stored.cable_groups[0].metadata_overrides == (("drawing-zone", "B4"),)


def test_renames_cable_group_without_changing_its_route_members(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist a trimmed group name independently of connectivity and construction.
    """
    gateway = _recording_gateway(valid_harness)
    group = valid_harness.cable_groups[0]

    rename_cable_group(
        valid_harness.harness_id,
        group.cable_group_id,
        "  Engine loom  ",
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0] == replace(group, name="Engine loom")


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
        "Foil",
        "FEP",
        "Parent Maker",
        "PARENT-1",
        (("project", "Orion"),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    materials = stored.cable_group_materials(stored.cable_groups[0])
    assert materials.insulation_material == "PTFE"
    assert materials.shielding == "Foil"
    assert materials.dielectric_material == "FEP"
    assert materials.part_number == "PARENT-1"
    assert stored.cable_group_metadata(stored.cable_groups[0]) == (("project", "Orion"),)


def test_pathway_properties_store_searchable_metadata_without_routing_changes(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace pathway-owned metadata while retaining its complete routing definition.
    """
    gateway = _recording_gateway(valid_harness)
    pathway = valid_harness.pathways[0]

    set_pathway_properties(
        valid_harness.harness_id,
        pathway.pathway_id,
        (("zone", "forward"),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.pathways[0] == replace(pathway, metadata=(("zone", "forward"),))


def test_pathway_end_properties_store_metadata_on_only_the_selected_boundary(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace one pathway end's metadata while retaining routing and the opposite end.
    """
    pathway = replace(valid_harness.pathways[0], end_metadata=(("station", "right"),))
    definition = replace(valid_harness, pathways=(pathway,))
    gateway = _recording_gateway(definition)

    set_pathway_end_properties(
        definition.harness_id,
        pathway.pathway_id,
        PathwayEndpoint.START,
        (("station", "left"),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.pathways[0] == replace(
        pathway,
        start_metadata=(("station", "left"),),
    )


def test_cable_end_properties_store_metadata_without_changing_connection(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace one physical end's metadata while retaining its geometry and identity.
    """
    gateway = _recording_gateway(valid_harness)
    connection = valid_harness.connections[0]

    set_cable_end_properties(
        valid_harness.harness_id,
        connection.connection_id,
        (("connector", "J1"),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.connections[0] == replace(connection, metadata=(("connector", "J1"),))


def test_junction_properties_store_metadata_without_changing_topology(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace one junction's metadata while retaining its control and relationships.
    """
    junction = JunctionDefinition(
        UUID(int=901), "Junction 01", valid_harness.controls[0].control_id
    )
    definition = replace(valid_harness, junctions=(junction,))
    gateway = _recording_gateway(definition)

    set_junction_properties(
        definition.harness_id,
        junction.junction_id,
        (("panel", "P2"),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.junctions[0] == replace(junction, metadata=(("panel", "P2"),))


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
        " Power Branch ",
        "junction-token",
        gateway,
        id_factory=lambda: next(generated_ids),
    )

    stored = loads(gateway.serialized_definition)
    control = next(item for item in stored.controls if item.control_id == junction.control_id)
    assert junction.name == "Power Branch"
    assert control.interpolation == gate_defaults
    assert control.interpolation_is_override is False


def test_suggests_next_junction_name(valid_harness: HarnessDefinition) -> None:
    """
    Increment junction names case-insensitively within the owning harness.
    """
    existing = JunctionDefinition(UUID(int=101), "Junction 01", UUID(int=102))
    definition = replace(valid_harness, junctions=(existing,))
    gateway = _recording_gateway(definition)

    suggested = suggest_junction_name(definition.harness_id, "Junction 01", gateway)

    assert suggested == "Junction 02"


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
        pathways=(
            replace(
                pathway,
                ordered_control_ids=(first_id, junction_control_id, last_id),
                metadata=(("zone", "forward"),),
                start_metadata=(("station", "left"),),
                end_metadata=(("station", "right"),),
            ),
        ),
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
    preceding = next(item for item in stored.pathways if item.pathway_id == pathway.pathway_id)
    following = next(
        item for item in stored.pathways if item.pathway_id == result.following_pathway.pathway_id
    )
    assert preceding.metadata == (("zone", "forward"),)
    assert following.metadata == ()
    assert preceding.start_metadata == (("station", "left"),)
    assert preceding.end_metadata == ()
    assert following.start_metadata == ()
    assert following.end_metadata == (("station", "right"),)


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


def test_cable_editor_preserves_existing_group_name(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Retain the group's display identity while committing unchanged membership.
    """
    pathway = valid_harness.pathways[0]
    group = replace(valid_harness.cable_groups[0], name="Engine loom")
    definition = replace(valid_harness, cable_groups=(group,))
    gateway = _recording_gateway(definition)

    save_cable_editor(
        definition.harness_id,
        pathway.pathway_id,
        PathwayEndpoint.START,
        pathway.pathway_id,
        PathwayEndpoint.END,
        (CableEditorPairing(*group.connection_ids),),
        (),
        (),
        (),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].name == "Engine loom"
