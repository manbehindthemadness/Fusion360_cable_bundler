"""State contracts shared by add-refine command handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .....routing import Vector3
from ....cable_solids import (
    CableSolidVisibilityState,
)
from ....refine_graphics import (
    PathwaySpine,
    RefinePlacement,
)


@dataclass
class RefineCommandState:
    """
    Share the temporary spine and current placement across command handlers.
    """

    harness_id: UUID
    target_id: UUID
    spine: PathwaySpine
    target_kind: str = "pathway"
    attachment_id: Optional[UUID] = None
    group: Optional[adsk.fusion.CustomGraphicsGroup] = None
    placement: Optional[RefinePlacement] = None
    candidate: Optional[adsk.fusion.CustomGraphicsLines] = None
    preselected_point_mm: Optional[Vector3] = None
    solid_visibility: CableSolidVisibilityState = field(
        default_factory=lambda: CableSolidVisibilityState((), ())
    )


class SelectionInput(Protocol):
    """
    Expose selection operations needed around preview-backed graphics.
    """

    # noinspection PyPep8Naming
    def setSelectionLimits(self, minimum: int, maximum: int = 0) -> bool:
        """
        Require a bounded number of selections.
        """
        ...

    # noinspection PyPep8Naming
    def clearSelection(self) -> bool:
        """
        Release the transient graphics selection before preview rollback.
        """
        ...
