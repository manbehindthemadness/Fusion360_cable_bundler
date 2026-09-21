"""
Tests for transactional unassigned-end creation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional
from uuid import UUID

import pytest

from cable_bundler.application import (
    StandaloneEndGateway,
    StandaloneEndUpdateError,
    add_standalone_end,
)
from cable_bundler.domain import HarnessDefinition, PathwayEndpoint, dumps, loads
from cable_bundler.domain.model import InterpolationSettings

END_ID = UUID("86000000-0000-0000-0000-000000000001")


# noinspection DuplicatedCode
class _RecordingGateway(StandaloneEndGateway):
    """
    Store serialized definitions and inject sequential write failures.
    """

    def __init__(
        self,
        definition: HarnessDefinition,
        failures: tuple[Optional[Exception], ...] = (),
    ) -> None:
        """
        Retain the initial definition and configured failures.
        """
        self.serialized_definition = dumps(definition)
        self.failures = list(failures)
        self.writes: list[str] = []

    def read_harness_definition(self, harness_id: UUID) -> str:
        """
        Return the current serialized definition.
        """
        del harness_id
        return self.serialized_definition

    def replace_harness_definition(
        self,
        harness_id: UUID,
        serialized_definition: str,
    ) -> None:
        """
        Record or reject a replacement.
        """
        del harness_id
        self.writes.append(serialized_definition)
        failure = self.failures.pop(0) if self.failures else None
        if failure is not None:
            raise failure
        self.serialized_definition = serialized_definition


def test_adds_one_ordered_unassigned_end(valid_harness: HarnessDefinition) -> None:
    """
    Persist guide order and placement without adding cable-owned data.
    """
    gateway = _RecordingGateway(valid_harness)

    result = add_standalone_end(
        valid_harness.harness_id,
        ("terminal", "guide-1", "guide-2"),
        valid_harness.pathways[0].pathway_id,
        PathwayEndpoint.END,
        gateway,
        id_factory=lambda: END_ID,
    )

    stored = loads(gateway.serialized_definition)
    assert result.connection.name == "End B 001"
    assert result.connection.member_tokens == ("terminal", "guide-1", "guide-2")
    assert stored.connections[-1] == result.connection
    assert stored.standalone_ends == (*valid_harness.standalone_ends, result.standalone_end)
    assert stored.cable_groups == valid_harness.cable_groups


def test_new_end_guides_inherit_end_interpolation_defaults(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Apply the harness end preset to every member of a newly created guide stack.
    """
    end_defaults = InterpolationSettings(approach_mm=2.5, departure_mm=4.0)
    definition = replace(valid_harness, end_defaults=end_defaults)
    gateway = _RecordingGateway(definition)

    result = add_standalone_end(
        definition.harness_id,
        ("terminal", "guide-1", "guide-2"),
        definition.pathways[0].pathway_id,
        PathwayEndpoint.START,
        gateway,
        id_factory=lambda: END_ID,
    )

    assert result.connection.interpolation == end_defaults
    assert result.connection.member_settings == (end_defaults, end_defaults, end_defaults)


@pytest.mark.parametrize("tokens", [(), ("",), ("valid", " ")])
def test_rejects_invalid_guide_profiles(
    valid_harness: HarnessDefinition,
    tokens: tuple[str, ...],
) -> None:
    """
    Require at least one nonempty selected guide profile.
    """
    gateway = _RecordingGateway(valid_harness)

    with pytest.raises(ValueError, match="guide"):
        add_standalone_end(
            valid_harness.harness_id,
            tokens,
            valid_harness.pathways[0].pathway_id,
            PathwayEndpoint.START,
            gateway,
        )

    assert gateway.writes == []


def test_rolls_back_failed_persistence(valid_harness: HarnessDefinition) -> None:
    """
    Restore the original definition when the first write fails.
    """
    gateway = _RecordingGateway(valid_harness, (RuntimeError("write failed"), None))

    with pytest.raises(RuntimeError, match="write failed"):
        add_standalone_end(
            valid_harness.harness_id,
            ("guide",),
            valid_harness.pathways[0].pathway_id,
            PathwayEndpoint.START,
            gateway,
            id_factory=lambda: END_ID,
        )

    assert loads(gateway.serialized_definition) == valid_harness


def test_reports_failed_rollback(valid_harness: HarnessDefinition) -> None:
    """
    Distinguish an unrecoverable two-write failure.
    """
    gateway = _RecordingGateway(
        valid_harness,
        (RuntimeError("write failed"), RuntimeError("rollback failed")),
    )

    with pytest.raises(StandaloneEndUpdateError, match="rollback failed"):
        add_standalone_end(
            valid_harness.harness_id,
            ("guide",),
            valid_harness.pathways[0].pathway_id,
            PathwayEndpoint.START,
            gateway,
            id_factory=lambda: END_ID,
        )
