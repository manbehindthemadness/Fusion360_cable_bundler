"""
Recreate externally deleted gym display containers without changing solver state or native output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.inspection.archive import write_document

from .lock import verify

if TYPE_CHECKING:
    from .gym import SelectedWorkspace


def restore(workspace: SelectedWorkspace) -> None:
    """
    Rebind only missing owned display branches, preserving valid siblings, palettes and history.

    Require the same idle document and frozen executable policy. Deleted native
    output remains deleted. A failed display rebuild is retained and propagates;
    this function does not retry, solve routes or construct native ribbon bodies.
    """
    gym_missing = not workspace.gym_occurrence.isValid
    diagnostics_missing = not workspace.diagnostic_occurrence.isValid
    if not gym_missing and not diagnostics_missing:
        return
    app = adsk.core.Application.get()
    if (
        app.activeDocument is None
        or app.activeDocument.creationId != workspace.native.document_id
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Display recovery requires its owned idle Fusion design.")
    budget = NativeBudget(maximum_seconds=30, maximum_rss_kib=4194304)
    budget.check("display recovery launch")
    if budget.memory() >= 3984588:
        raise RuntimeError("Display recovery lacks 3.8GiB launch headroom.")
    plan = workspace.directory / ("display-recovery-" + uuid4().hex + ".json")
    write_document(
        plan,
        {
            "sources": verify(),
            "gym_missing": gym_missing,
            "diagnostics_missing": diagnostics_missing,
            "scope": "Recreate deleted owned display containers from retained inputs/sessions. Preserve palettes, layouts, logs, runner and native output. No route solve or native ribbon construction.",
            "seconds": 30,
            "rss_kib": 4194304,
            "solves": 0,
            "native_attempts": 0,
        },
    )
    parent: Any = workspace.container
    if parent is None or not parent.isValid:
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(workspace.native.display_x_cm, 0, 0)
        parent = adsk.fusion.Design.cast(
            app.activeProduct
        ).rootComponent.occurrences.addNewComponent(matrix)
        parent.component.name = "Material solvers v1 and v2 - endpoint gym"
        workspace.container = parent
    if gym_missing:
        occurrence = parent.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = "Endpoint gym draft"
        workspace.gym_occurrence = occurrence
        workspace.gym.rebind_component(occurrence.component)
        occurrence.isLightBulbOn = False
    budget.check("gym display recovered")
    if diagnostics_missing:
        occurrence = parent.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occurrence.component.name = "Selected solver diagnostics"
        workspace.diagnostic_occurrence = occurrence
        workspace.diagnostics.rebind_root(occurrence.component)
        occurrence.isLightBulbOn = True
    budget.check("diagnostic display recovered")
