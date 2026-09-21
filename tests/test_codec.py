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
    AutoTransitionPreset,
    DefinitionParseError,
    HarnessDefinition,
    JunctionDefinition,
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


def test_serialization_is_deterministic(valid_harness: HarnessDefinition) -> None:
    """
    Produce stable persisted text for the same immutable definition.
    """
    assert dumps(valid_harness) == dumps(valid_harness)


def test_metadata_round_trip_is_optional_and_does_not_change_schema(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve new searchable rows while keeping schema-15 definitions without them readable.
    """
    group = replace(valid_harness.cable_groups[0], metadata_overrides=(("drawing-zone", "B4"),))
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
        pathways=(replace(valid_harness.pathways[0], metadata=(("zone", "forward"),)),),
    )

    payload = json.loads(dumps(definition))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert loads(json.dumps(payload)) == definition
    del payload["metadata"]
    del payload["cable_groups"][0]["metadata_overrides"]
    del payload["connections"][0]["metadata"]
    del payload["junctions"][0]["metadata"]
    del payload["pathways"][0]["metadata"]
    compatible = loads(json.dumps(payload))
    assert compatible.metadata == ()
    assert compatible.cable_groups[0].metadata_overrides == ()
    assert compatible.connections[0].metadata == ()
    assert compatible.junctions[0].metadata == ()
    assert compatible.pathways[0].metadata == ()


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


@pytest.mark.parametrize("version", [1, 2, 3, 11, 16])
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
