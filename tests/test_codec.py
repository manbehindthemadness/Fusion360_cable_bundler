"""
Tests for the current group-only harness codec.
"""

from __future__ import annotations

import json

import pytest

from wire_bundler.domain import (
    SCHEMA_VERSION,
    DefinitionParseError,
    HarnessDefinition,
    dumps,
    loads,
)


def test_round_trip_preserves_group_only_definition(valid_harness: HarnessDefinition) -> None:
    """
    Preserve every current-schema field without emitting legacy wire collections.
    """
    serialized = dumps(valid_harness)

    assert loads(serialized) == valid_harness
    payload = json.loads(serialized)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "profiles" not in payload
    assert "wires" not in payload


def test_serialization_is_deterministic(valid_harness: HarnessDefinition) -> None:
    """
    Produce stable persisted text for the same immutable definition.
    """
    assert dumps(valid_harness) == dumps(valid_harness)


@pytest.mark.parametrize("version", [1, 2, 3, 11, 14])
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

    migrated = loads(json.dumps(payload))

    assert migrated.schema_version == SCHEMA_VERSION
    assert migrated.minimum_clearance_mm == 0.0


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
    del payload["wire_groups"]

    with pytest.raises(DefinitionParseError) as captured:
        loads(json.dumps(payload))

    assert captured.value.path == "$.wire_groups"
