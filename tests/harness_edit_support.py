"""
Provide a recording gateway for host-independent harness edit tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol, cast
from uuid import UUID

from cable_bundler.application import HarnessEditGateway
from cable_bundler.domain import HarnessDefinition, dumps


class RecordingGateway(HarnessEditGateway, Protocol):
    """
    Expose serialized state recorded by the in-memory gateway.
    """

    serialized_definition: str


def recording_gateway(definition: HarnessDefinition) -> RecordingGateway:
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
    return cast(RecordingGateway, cast(object, state))
