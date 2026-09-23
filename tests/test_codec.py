"""
Tests for the current group-only harness codec.
"""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.domain import (
    SCHEMA_VERSION,
    AttachmentTargetKind,
    AutoTransitionPreset,
    CableEndAttachment,
    CableEndTarget,
    CablePullbackSettings,
    CableVisualOverrides,
    DefinitionParseError,
    HarnessDefinition,
    JunctionDefinition,
    PullbackMode,
    dumps,
    loads,
)


def test_round_trip_preserves_group_only_definition(valid_harness: HarnessDefinition) -> None:
    """
    Preserve every current-schema field without emitting legacy cable collections.
    """
    serialized = dumps(valid_harness)

    assert loads(serialized) == valid_harness
    payload = json.loads(serialized)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["auto_transition_preset"] == "tight"
    assert "profiles" not in payload
    assert "cables" not in payload


def test_round_trip_and_schema_24_migration_preserve_pullback_settings(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist configured pullback data and default it for the previous schema.
    """
    pullback = CablePullbackSettings(mode=PullbackMode.DISTANCE, value=8.5)
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, pullback=pullback),
        connections=(
            replace(
                valid_harness.connections[0],
                attachment=CableEndAttachment(
                    None,
                    attachment_id=UUID(int=811),
                    visual_overrides=CableVisualOverrides(pullback=pullback),
                ),
            ),
            *valid_harness.connections[1:],
        ),
        cable_groups=(
            replace(
                valid_harness.cable_groups[0],
                material_overrides=replace(
                    valid_harness.cable_groups[0].material_overrides,
                    pullback=pullback,
                ),
            ),
        ),
    )
    restored = loads(dumps(definition))
    assert restored.material_defaults.pullback == pullback
    assert restored.cable_groups[0].material_overrides.pullback == pullback
    restored_attachment = restored.connections[0].attachment
    assert restored_attachment is not None
    assert restored_attachment.visual_overrides.pullback == pullback

    payload = json.loads(dumps(definition))
    payload["schema_version"] = 24
    del payload["material_defaults"]["pullback"]
    del payload["cable_groups"][0]["material_overrides"]["pullback"]
    del payload["connections"][0]["attachment"]["visual_overrides"]["pullback"]
    migrated = loads(json.dumps(payload))
    assert migrated.material_defaults.pullback == CablePullbackSettings()
    assert migrated.cable_groups[0].material_overrides.pullback is None
    migrated_attachment = migrated.connections[0].attachment
    assert migrated_attachment is not None
    assert migrated_attachment.visual_overrides.pullback is None


def test_round_trip_and_schema_25_migration_preserve_conductor_diameters(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist explicit conductor diameters and default earlier files to Auto.
    """
    attachment = CableEndAttachment(
        None,
        attachment_id=UUID(int=812),
        visual_overrides=CableVisualOverrides(
            diameter_mm=0.6,
            conductor_diameter_mm=0.4,
        ),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], attachment=attachment),
            *valid_harness.connections[1:],
        ),
        cable_groups=(replace(valid_harness.cable_groups[0], conductor_diameter_mm=1.1),),
    )

    restored = loads(dumps(definition))
    assert restored.cable_groups[0].conductor_diameter_mm == 1.1
    restored_attachment = restored.connections[0].attachment
    assert restored_attachment is not None
    assert restored_attachment.visual_overrides.conductor_diameter_mm == 0.4

    payload = json.loads(dumps(definition))
    payload["schema_version"] = 25
    del payload["cable_groups"][0]["conductor_diameter_mm"]
    del payload["connections"][0]["attachment"]["visual_overrides"]["conductor_diameter_mm"]
    migrated = loads(json.dumps(payload))
    assert migrated.cable_groups[0].conductor_diameter_mm is None
    assert migrated.cable_groups[0].resolved_conductor_diameter_mm == (
        migrated.cable_groups[0].diameter_mm * 0.75
    )
    migrated_attachment = migrated.connections[0].attachment
    assert migrated_attachment is not None
    assert migrated_attachment.visual_overrides.conductor_diameter_mm is None


def test_serialization_is_deterministic(valid_harness: HarnessDefinition) -> None:
    """
    Produce stable persisted text for the same immutable definition.
    """
    assert dumps(valid_harness) == dumps(valid_harness)


def test_round_trip_preserves_optional_cable_end_attachment(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve attachment metadata while keeping older attachments without it readable.
    """
    attachment = CableEndAttachment(
        AttachmentTargetKind.FACE,
        "face-token",
        "Connector body",
        "Pin 4",
        (0.25, 0.75),
        (("drawing-reference", "J1"),),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], attachment=attachment),
            valid_harness.connections[1],
        ),
    )

    serialized = dumps(definition)
    assert loads(serialized) == definition

    legacy_payload = json.loads(serialized)
    legacy_payload["connections"][0]["attachment"].pop("metadata")
    legacy_definition = loads(json.dumps(legacy_payload))
    legacy_attachment = legacy_definition.connections[0].attachment
    assert legacy_attachment is not None
    assert legacy_attachment.metadata == ()


def test_round_trip_preserves_unattached_cable_end_connection(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve a connection node before a Fusion target has been selected.
    """
    first = CableEndAttachment(None, attachment_id=UUID(int=801))
    second = CableEndAttachment(None, attachment_id=UUID(int=802))
    definition = replace(
        valid_harness,
        connections=(
            replace(
                valid_harness.connections[0],
                attachment=first,
                additional_attachments=(second,),
            ),
            valid_harness.connections[1],
        ),
    )

    restored = loads(dumps(definition))
    assert restored == definition
    assert restored.connections[0].attachments == (first, second)


def test_metadata_round_trip_is_optional_and_does_not_change_schema(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve new searchable rows while keeping schema-15 definitions without them readable.
    """
    group = replace(valid_harness.cable_groups[0], metadata_overrides=(("drawing-zone", "B4"),))
    group = replace(group, name="Engine loom")
    junction = JunctionDefinition(
        UUID(int=900),
        "Junction 01",
        valid_harness.controls[0].control_id,
        metadata=(("panel", "P2"),),
    )
    definition = replace(
        valid_harness,
        metadata=(("project", "Orion"),),
        cable_groups=(group,),
        connections=(
            replace(valid_harness.connections[0], metadata=(("connector", "J1"),)),
            valid_harness.connections[1],
        ),
        junctions=(junction,),
        pathways=(
            replace(
                valid_harness.pathways[0],
                metadata=(("zone", "forward"),),
                start_metadata=(("station", "left"),),
                end_metadata=(("station", "right"),),
            ),
        ),
    )

    payload = json.loads(dumps(definition))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert loads(json.dumps(payload)) == definition
    del payload["metadata"]
    del payload["cable_groups"][0]["metadata_overrides"]
    del payload["cable_groups"][0]["name"]
    del payload["connections"][0]["metadata"]
    del payload["junctions"][0]["metadata"]
    del payload["pathways"][0]["metadata"]
    del payload["pathways"][0]["start_metadata"]
    del payload["pathways"][0]["end_metadata"]
    compatible = loads(json.dumps(payload))
    assert compatible.metadata == ()
    assert compatible.cable_groups[0].metadata_overrides == ()
    assert compatible.cable_groups[0].name == ""
    assert compatible.connections[0].metadata == ()
    assert compatible.junctions[0].metadata == ()
    assert compatible.pathways[0].metadata == ()
    assert compatible.pathways[0].start_metadata == ()
    assert compatible.pathways[0].end_metadata == ()


def test_auto_transition_presets_expose_approved_span_fractions() -> None:
    """
    Keep persisted semantic choices aligned with routing policy values.
    """
    assert {preset.value: preset.span_fraction for preset in AutoTransitionPreset} == {
        "tight": 0.25,
        "compact": 0.3125,
        "balanced": 0.375,
        "relaxed": 0.4375,
        "loose": 0.5,
    }


@pytest.mark.parametrize("version", [1, 2, 3, 11, 27])
def test_rejects_unsupported_schema_versions(
    valid_harness: HarnessDefinition,
    version: int,
) -> None:
    """
    Refuse legacy and future files instead of retaining migration behavior.
    """
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = version

    with pytest.raises(DefinitionParseError, match=f"expected {SCHEMA_VERSION}"):
        loads(json.dumps(payload))


def test_migrates_schema_12_with_zero_minimum_clearance(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep current saved harnesses readable when collision-aware routing is introduced.
    """
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = 12
    del payload["minimum_clearance_mm"]
    del payload["auto_transition_preset"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert migrated.minimum_clearance_mm == 0.0
    assert migrated.auto_transition_preset is AutoTransitionPreset.TIGHT


def test_migrates_schema_13_with_tight_auto_transitions(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve current generated geometry when adding harness relaxation presets.
    """
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = 13
    del payload["auto_transition_preset"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert migrated.auto_transition_preset is AutoTransitionPreset.TIGHT


def test_migrates_schema_14_with_empty_end_controls(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve existing end guide stacks when end-owned refines are introduced.
    """
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = 14
    for end in payload["standalone_ends"]:
        del end["ordered_control_ids"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert all(not end.ordered_control_ids for end in migrated.standalone_ends)


def test_migrates_schema_15_with_detached_cable_ends(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Treat cable ends saved before connection attachments as detached.
    """
    payload = json.loads(dumps(valid_harness))
    payload["schema_version"] = 15
    for connection in payload["connections"]:
        del connection["attachment"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert all(connection.attachment is None for connection in migrated.connections)


def test_migrates_schema_17_with_empty_connection_controls(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve external targets when connection-owned refines are introduced.
    """
    attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "target-token",
        "Target",
        attachment_id=UUID(int=81),
    )
    definition = replace(
        valid_harness,
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 17
    del payload["connections"][0]["attachment"]["ordered_control_ids"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    migrated_attachment = migrated.connections[0].attachment
    assert migrated_attachment is not None
    assert migrated_attachment.ordered_control_ids == ()


def test_migrates_schema_18_with_inherited_connection_visuals(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve existing connection nodes when branch material overrides are introduced.
    """
    attachment = CableEndAttachment(None, attachment_id=UUID(int=82))
    definition = replace(
        valid_harness,
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 18
    del payload["connections"][0]["attachment"]["visual_overrides"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    migrated_attachment = migrated.connections[0].attachment
    assert migrated_attachment is not None
    assert migrated_attachment.visual_overrides == CableVisualOverrides()


def test_round_trip_preserves_connection_construction_overrides(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist divided-branch diameter and material overrides with visual settings.
    """
    overrides = CableVisualOverrides(
        diameter_mm=0.55,
        insulation_material="ETFE",
        conductor_material="Aluminum",
        shielding="Foil",
        manufacturer="Branch maker",
        part_number="BR-01",
    )
    shielding_target = CableEndTarget(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "shield-token",
        "Shield stud",
    )
    attachment = CableEndAttachment(
        None,
        attachment_id=UUID(int=83),
        visual_overrides=overrides,
        shielding_target=shielding_target,
    )
    definition = replace(
        valid_harness,
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )

    restored = loads(dumps(definition))

    restored_attachment = restored.connections[0].attachment
    assert restored_attachment is not None
    assert restored_attachment.visual_overrides == overrides
    assert restored_attachment.shielding_target == shielding_target


def test_migrates_schema_19_with_inherited_connection_construction(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Default newly introduced branch construction fields for schema 19 data.
    """
    attachment = CableEndAttachment(None, attachment_id=UUID(int=84))
    definition = replace(
        valid_harness,
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 19
    visual_overrides = payload["connections"][0]["attachment"]["visual_overrides"]
    del visual_overrides["diameter_mm"]
    del visual_overrides["insulation_material"]
    del visual_overrides["conductor_material"]
    del visual_overrides["manufacturer"]
    del visual_overrides["part_number"]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert migrated.connections[0].attachment is not None
    assert migrated.connections[0].attachment.visual_overrides == CableVisualOverrides()


def test_migrates_schema_20_connections_as_root_nodes(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve the former flat connection list as root-level sibling branches.
    """
    first = CableEndAttachment(None, attachment_id=UUID(int=85))
    second = CableEndAttachment(None, attachment_id=UUID(int=86))
    definition = replace(
        valid_harness,
        connections=(
            replace(
                valid_harness.connections[0],
                attachment=first,
                additional_attachments=(second,),
            ),
        ),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 20
    payload["connections"][0]["attachment"].pop("parent_attachment_id")
    payload["connections"][0]["additional_attachments"][0].pop("parent_attachment_id")

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert all(item.parent_attachment_id is None for item in migrated.connections[0].attachments)


@pytest.mark.parametrize(
    ("schema_version", "removed_fields"),
    ((21, ("shielding", "dielectric_material")), (23, ("dielectric_material",))),
)
def test_migrates_legacy_construction_fields_with_empty_values(
    valid_harness: HarnessDefinition,
    schema_version: int,
    removed_fields: tuple[str, ...],
) -> None:
    """
    Default later construction fields without guessing materials for legacy harnesses.
    """
    attachment = CableEndAttachment(
        None,
        attachment_id=UUID(int=87),
        visual_overrides=CableVisualOverrides(conductor_material="Aluminum", shielding="Foil"),
    )
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, shielding="Foil"),
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = schema_version
    for field in removed_fields:
        del payload["material_defaults"][field]
        del payload["cable_groups"][0]["material_overrides"][field]
        del payload["connections"][0]["attachment"]["visual_overrides"][field]

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    migrated_attachment = migrated.connections[0].attachment
    assert migrated_attachment is not None
    for field in removed_fields:
        assert getattr(migrated.material_defaults, field) == ""
        assert getattr(migrated.cable_groups[0].material_overrides, field) is None
        assert getattr(migrated_attachment.visual_overrides, field) is None


def test_migrates_schema_22_without_shielding_targets(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve current connection nodes when shielding relationships are introduced.
    """
    attachment = CableEndAttachment(None, attachment_id=UUID(int=88))
    definition = replace(
        valid_harness,
        connections=(replace(valid_harness.connections[0], attachment=attachment),),
    )
    payload = json.loads(dumps(definition))
    payload["schema_version"] = 22
    del payload["connections"][0]["attachment"]["shielding_target"]

    migrated = loads(json.dumps(payload))

    migrated_attachment = migrated.connections[0].attachment
    assert migrated.schema_version == SCHEMA_VERSION
    assert migrated_attachment is not None
    assert migrated_attachment.shielding_target is None


@pytest.mark.parametrize("preset", ["", "very_loose", 4, None])
def test_rejects_invalid_current_auto_transition_preset(
    valid_harness: HarnessDefinition,
    preset: object,
) -> None:
    """
    Reject malformed preset values at the persisted-data boundary.
    """
    payload = json.loads(dumps(valid_harness))
    payload["auto_transition_preset"] = preset

    with pytest.raises(DefinitionParseError) as captured:
        loads(json.dumps(payload))

    assert captured.value.path == "$.auto_transition_preset"


@pytest.mark.parametrize(
    ("serialized", "path"),
    [
        ("not-json", "$"),
        ("[]", "$"),
        ('{"schema_version": true}', "$.schema_version"),
        (f'{{"schema_version": {SCHEMA_VERSION}}}', "$.harness_id"),
    ],
)
def test_rejects_malformed_external_data(serialized: str, path: str) -> None:
    """
    Report malformed JSON and shapes at the failing field path.
    """
    with pytest.raises(DefinitionParseError) as captured:
        loads(serialized)

    assert captured.value.path == path


def test_requires_current_group_collections(valid_harness: HarnessDefinition) -> None:
    """
    Treat the group-only collections as explicit parts of the current schema.
    """
    payload = json.loads(dumps(valid_harness))
    del payload["cable_groups"]

    with pytest.raises(DefinitionParseError) as captured:
        loads(json.dumps(payload))

    assert captured.value.path == "$.cable_groups"
