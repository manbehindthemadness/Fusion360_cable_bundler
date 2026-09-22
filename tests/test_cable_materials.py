"""
Tests for cable-material inheritance and the bundled suggestion catalog.
"""

from dataclasses import replace
from uuid import UUID

from cable_bundler.application import load_cable_material_catalog
from cable_bundler.domain import (
    CableAppearanceReference,
    CableColor,
    CableEndAttachment,
    CableMaterialOverrides,
    CableMaterialSettings,
    CableStripe,
    CableVisualOverrides,
    HarnessDefinition,
)


def test_cable_group_resolves_each_override_independently(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Inherit parent fields unless that field has an explicit group value.
    """
    defaults = CableMaterialSettings(
        insulation_material="PTFE",
        main_color=CableColor("Blue", 0, 0, 255),
        manufacturer="Parent maker",
        notes="Parent note",
    )
    overrides = CableMaterialOverrides(
        main_color=CableColor("Red", 255, 0, 0),
        manufacturer="",
    )
    definition = replace(valid_harness, material_defaults=defaults)
    cable_group = replace(valid_harness.cable_groups[0], material_overrides=overrides)

    resolved = definition.cable_group_materials(cable_group)

    assert resolved.insulation_material == "PTFE"
    assert resolved.main_color.name == "Red"
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
    ) == single.cable_group_materials(group)

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
