"""
Tests for cable-material inheritance and the bundled suggestion catalog.
"""

from dataclasses import replace
from uuid import UUID

from cable_bundler.application import load_cable_material_catalog
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableAppearanceReference,
    CableColor,
    CableEndAttachment,
    CableMaterialOverrides,
    CableMaterialSettings,
    CablePullbackSettings,
    CableStripe,
    CableVisualOverrides,
    HarnessDefinition,
    PullbackMode,
)


def test_cable_group_resolves_each_override_independently(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Inherit parent fields unless that field has an explicit group value.
    """
    defaults = CableMaterialSettings(
        insulation_material="PTFE",
        shielding="Foil",
        dielectric_material="PE",
        main_color=CableColor("Blue", 0, 0, 255),
        manufacturer="Parent maker",
        notes="Parent note",
    )
    overrides = CableMaterialOverrides(
        main_color=CableColor("Red", 255, 0, 0),
        shielding="Braided copper",
        dielectric_material="FEP",
        manufacturer="",
    )
    definition = replace(valid_harness, material_defaults=defaults)
    cable_group = replace(valid_harness.cable_groups[0], material_overrides=overrides)

    resolved = definition.cable_group_materials(cable_group)

    assert resolved.insulation_material == "PTFE"
    assert resolved.main_color.name == "Red"
    assert resolved.shielding == "Braided copper"
    assert resolved.dielectric_material == "FEP"
    assert resolved.manufacturer == ""
    assert resolved.notes == "Parent note"


def test_base_visual_override_replaces_or_inherits_library_appearance(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Pair the optional Fusion appearance with the existing main-color override.
    """
    parent_appearance = CableAppearanceReference("lib", "Library", "blue", "Blue Rubber")
    defaults = CableMaterialSettings(
        main_color=CableColor("Blue", 0, 0, 255), appearance=parent_appearance
    )

    inherited = CableMaterialOverrides().resolve(defaults)
    plain_red = CableMaterialOverrides(main_color=CableColor("Red", 255, 0, 0)).resolve(defaults)

    assert inherited.appearance == parent_appearance
    assert plain_red.appearance is None


def test_pullback_defaults_and_overrides_inherit_as_one_setting(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep amount, unit mode, color, and appearance together across inheritance.
    """
    default_pullback = valid_harness.material_defaults.pullback
    assert default_pullback.mode is PullbackMode.PERCENT
    assert default_pullback.value == 200.0
    assert default_pullback.color.hex_rgb == "#B87333"

    override = CablePullbackSettings(
        mode=PullbackMode.DISTANCE,
        value=12.5,
        color=CableColor("Blue", 0, 0, 255),
    )
    assert (
        CableMaterialOverrides().resolve(valid_harness.material_defaults).pullback
        == default_pullback
    )
    assert (
        CableMaterialOverrides(pullback=override).resolve(valid_harness.material_defaults).pullback
        == override
    )
    assert (
        CableVisualOverrides(pullback=override).resolve(valid_harness.material_defaults).pullback
        == override
    )


def test_connection_visuals_inherit_singly_and_override_each_branch(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Apply per-node visuals only when one cable end owns multiple connections.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    inherited = replace(
        connection,
        attachment=CableEndAttachment(None, attachment_id=UUID(int=701)),
    )
    red = CableColor("Red", 255, 0, 0)
    assert inherited.attachment is not None
    overridden = replace(
        inherited.attachment,
        visual_overrides=CableVisualOverrides(
            diameter_mm=0.6,
            conductor_diameter_mm=0.45,
            insulation_material="ETFE",
            conductor_material="Aluminum",
            shielding="Foil",
            manufacturer="Branch maker",
            part_number="BR-01",
            main_color=red,
            stripes=(CableStripe(CableColor("White", 255, 255, 255), 0.2),),
        ),
    )
    single = replace(
        valid_harness,
        connections=(replace(inherited, attachment=overridden), *valid_harness.connections[1:]),
    )

    assert single.cable_end_attachment_materials(
        group, connection.connection_id, overridden.attachment_id
    ) == replace(single.cable_group_materials(group), shielding="Foil")

    second = CableEndAttachment(None, attachment_id=UUID(int=702))
    multiple_connection = replace(
        inherited,
        attachment=overridden,
        additional_attachments=(second,),
    )
    multiple = replace(
        valid_harness,
        connections=(multiple_connection, *valid_harness.connections[1:]),
    )

    resolved = multiple.cable_end_attachment_materials(
        group, connection.connection_id, overridden.attachment_id
    )
    assert resolved.main_color == red
    assert resolved.stripes == overridden.visual_overrides.stripes
    assert resolved.insulation_material == "ETFE"
    assert resolved.conductor_material == "Aluminum"
    assert resolved.shielding == "Foil"
    assert resolved.manufacturer == "Branch maker"
    assert resolved.part_number == "BR-01"
    assert (
        multiple.cable_end_attachment_diameter(
            group, connection.connection_id, overridden.attachment_id
        )
        == 0.6
    )
    assert (
        multiple.cable_end_attachment_diameter(
            group, connection.connection_id, second.attachment_id
        )
        == group.diameter_mm / 2.0
    )
    assert (
        multiple.cable_end_attachment_conductor_diameter(
            group, connection.connection_id, overridden.attachment_id
        )
        == 0.45
    )
    assert (
        multiple.cable_end_attachment_conductor_diameter(
            group, connection.connection_id, second.attachment_id
        )
        == group.diameter_mm / 2.0 * 0.75
    )


def test_nested_connections_inherit_from_their_immediate_parent(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Resolve descendant construction values through each parent branch level.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    root = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "root-profile",
        "Root",
        attachment_id=UUID(int=711),
        visual_overrides=CableVisualOverrides(
            diameter_mm=0.7,
            insulation_material="ETFE",
        ),
    )
    root_peer = CableEndAttachment(None, attachment_id=UUID(int=712))
    child = CableEndAttachment(
        None,
        attachment_id=UUID(int=713),
        parent_attachment_id=root.attachment_id,
        visual_overrides=CableVisualOverrides(
            diameter_mm=0.3,
            conductor_material="Aluminum",
            shielding="Braided copper",
        ),
    )
    child_peer = CableEndAttachment(
        None,
        attachment_id=UUID(int=714),
        parent_attachment_id=root.attachment_id,
    )
    nested_connection = replace(
        connection,
        attachment=root,
        additional_attachments=(root_peer, child, child_peer),
    )
    definition = replace(
        valid_harness,
        connections=(nested_connection, *valid_harness.connections[1:]),
    )

    resolved = definition.cable_end_attachment_materials(
        group, connection.connection_id, child.attachment_id
    )

    assert resolved.insulation_material == "ETFE"
    assert resolved.conductor_material == "Aluminum"
    assert resolved.shielding == "Braided copper"
    assert (
        definition.cable_end_attachment_diameter(
            group, connection.connection_id, child.attachment_id
        )
        == 0.3
    )
    assert (
        definition.cable_end_attachment_diameter(
            group, connection.connection_id, child_peer.attachment_id
        )
        == 0.35
    )


def test_connection_shielding_override_applies_without_a_divided_branch(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Start and interrupt shielding inheritance at ordinary connector nodes.
    """
    group = valid_harness.cable_groups[0]
    connection = valid_harness.connections[0]
    root = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "root-profile",
        "Root",
        attachment_id=UUID(int=721),
        visual_overrides=CableVisualOverrides(shielding="Foil", dielectric_material="FEP"),
    )
    child = CableEndAttachment(
        None,
        attachment_id=UUID(int=722),
        parent_attachment_id=root.attachment_id,
        visual_overrides=CableVisualOverrides(shielding=""),
    )
    nested = replace(connection, attachment=root, additional_attachments=(child,))
    definition = replace(
        valid_harness,
        connections=(nested, *valid_harness.connections[1:]),
    )

    assert (
        definition.cable_end_attachment_materials(
            group, connection.connection_id, root.attachment_id
        ).shielding
        == "Foil"
    )
    assert (
        definition.cable_end_attachment_materials(
            group, connection.connection_id, root.attachment_id
        ).dielectric_material
        == "FEP"
    )
    assert (
        definition.cable_end_attachment_materials(
            group, connection.connection_id, child.attachment_id
        ).shielding
        == ""
    )
    assert (
        definition.cable_end_attachment_materials(
            group, connection.connection_id, child.attachment_id
        ).dielectric_material
        == ""
    )


def test_cable_metadata_inherits_parent_rows_and_applies_keyed_overrides(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve parent ordering while replacing and extending child-searchable values.
    """
    definition = replace(
        valid_harness,
        metadata=(("project", "Orion"), ("drawing-zone", "A1")),
    )
    cable_group = replace(
        valid_harness.cable_groups[0],
        metadata_overrides=(("Drawing-Zone", "B4"), ("inspection", "required")),
    )

    assert definition.cable_group_metadata(cable_group) == (
        ("project", "Orion"),
        ("Drawing-Zone", "B4"),
        ("inspection", "required"),
    )


def test_catalog_provides_search_suggestions_without_owning_values() -> None:
    """
    Load bundled materials, conductors, colors, and supported stripe patterns.
    """
    catalog = load_cable_material_catalog()

    assert "ETFE" in catalog.insulation_materials
    assert "Tinned Copper" in catalog.conductor_materials
    assert any(color.name == "Blue" for color in catalog.colors)
    assert {pattern.value for pattern in catalog.stripe_patterns} == {
        "longitudinal",
        "dashed",
        "helical",
    }
