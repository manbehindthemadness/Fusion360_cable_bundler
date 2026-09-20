"""
Edit ordered pathway gates and wire endpoint pairings transactionally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain import (
    JunctionDefinition,
    PathwayDefinition,
)


class HarnessEditGateway(Protocol):
    """
    Describe persisted harness operations required by ordered edits.
    """

    def read_harness_definition(self, harness_id: UUID) -> str:
        """
        Return the serialized definition owned by one harness.
        """

    def replace_harness_definition(self, harness_id: UUID, serialized_definition: str) -> None:
        """
        Replace the serialized definition owned by one harness.
        """


class HarnessEditError(RuntimeError):
    """
    Report an edit that failed and could not be rolled back cleanly.
    """


@dataclass(frozen=True)
class PathwaySegmentResult:
    """
    Return the two pathway halves and their intervening junction.
    """

    preceding_pathway: PathwayDefinition
    following_pathway: PathwayDefinition
    junction: JunctionDefinition
