"""
Open an independent endpoint gym linked to complete-case diagnostics, with no native builder.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.gym.scene import Scene
from devtools.ribbon_analysis.gym.view import GymView

from .panel import Panel
from .panel import install as install_panel

_owners: list[Workspace] = []


class Workspace:
    """
    Retain one mutable endpoint draft and separate complete diagnostic histories.
    """

    def __init__(self, scene: Scene, directory: Path, occurrence: Any, document_id: str) -> None:
        """
        Bind the original endpoint-gym controls to an explicit complete-case handoff.
        """
        self.occurrence, self.document_id = occurrence, document_id
        self.panel: Panel | None = None
        self.gym = GymView(occurrence.component, directory / "draft", scene, self.open_complete)
        self.panel = install_panel(self, directory / "jobs", document_id)

    def open_complete(self, scene: Scene) -> None:
        """
        Reveal complete evaluation controls without solving or changing the supplied draft.
        """
        if scene != self.gym.scene or self.panel is None:
            raise ValueError("Complete handoff requires the current retained gym draft")
        self.panel.palette.isVisible = True


def install(
    scene: Scene,
    directory: Path,
    document_id: str,
    checkpoint: Callable[[], None],
) -> Workspace:
    """
    Create one caller-owned gym component and two palettes under the caller's setup guard.

    Replaying an existing scene starts no solver and earns no independent-layout
    coverage. Original native demonstration bodies and their view are untouched.
    An interrupted setup is retained for review; no automatic replacement follows.
    """
    checkpoint()
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != document_id
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise ValueError("Create complete gym in its explicitly owned idle document")
    if any(owner.document_id == document_id for owner in _owners):
        raise ValueError("Complete gym workspace already retained for this document")
    directory.mkdir(parents=True, exist_ok=False)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise ValueError("Complete gym requires an active Fusion design")
    occurrence = design.rootComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occurrence.component.name = "Complete ribbon gym - experimental diagnostic inputs"
    checkpoint()
    owner = Workspace(scene, directory, occurrence, document_id)
    _owners.append(owner)
    checkpoint()
    owner.gym.show()
    checkpoint()
    return owner
