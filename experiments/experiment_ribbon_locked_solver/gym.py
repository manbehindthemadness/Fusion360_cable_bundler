"""
Install the selected solver into an explicitly owned endpoint-gym workspace in Fusion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from devtools.ribbon_analysis.gym import Scene, generate
from devtools.ribbon_analysis.gym.handoff import freeze
from devtools.ribbon_analysis.inspection.fusion_view import DiagnosticViewer
from experiments.experiment_ribbon_test_gym.workspace import Workspace

from .controller import Controller
from .lock import verify
from .native import NativeOwner

_owners: list[SelectedWorkspace] = []


class SelectedWorkspace(Workspace):
    """
    Keep mutable gym previews separate from the selected solver's retained native output.
    """

    def __init__(
        self,
        native: NativeOwner,
        diagnostics: DiagnosticViewer,
        diagnostic_occurrence: Any,
        gym_occurrence: Any,
        directory: Path,
        scene: Scene,
    ) -> None:
        """
        Retain the native owner before the base workspace binds its navigation callback.
        """
        self.native = native
        super().__init__(diagnostics, diagnostic_occurrence, gym_occurrence, directory, scene)
        diagnostics.enable_geometry_clear(native.clear, native.has_geometry)
        native.on_progress = diagnostics.report_progress

    def open_gym(self) -> None:
        """
        Hide this workspace's last native output while editing its next endpoint draft.
        """
        self.native.hide()
        super().open_gym()


def install(
    directory: Path, python: Path, document_id: str, scene: Scene | None = None
) -> SelectedWorkspace:
    """
    Create one retained gym/diagnostic workspace without solving or changing unrelated designs.

    The explicit Solve and build action is the only solver launch. Inputs and
    results stay under the caller-owned repository artifact directory. V2 is the
    default and original v1 remains selectable; retired discovery stays unavailable.
    Native profiles and per-conductor face order preserve the existing builder contract.
    """
    verify()
    app = adsk.core.Application.get()
    if (
        app.activeDocument.creationId != document_id
        or app.userInterface.activeCommand != "SelectCommand"
    ):
        raise RuntimeError("Install the selected gym in its owned idle development design")
    previous = tuple(
        owner
        for owner in _owners
        if owner.diagnostics.root.isValid and owner.diagnostics.document.creationId == document_id
    )
    if any(
        owner.diagnostics.runner is not None
        and owner.diagnostics.runner.state()["status"] in ("running", "cancelling")
        for owner in previous
    ):
        raise ValueError("Stop and collect the prior gym job before replacing its workspace")
    directory.mkdir(parents=True, exist_ok=False)
    root = adsk.fusion.Design.cast(app.activeProduct).rootComponent
    native = NativeOwner(document_id)
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(native.display_x_cm, 0, 0)
    owner = root.occurrences.addNewComponent(transform)
    owner.component.name = "Material solvers v1 and v2 - endpoint gym"
    diagnostics_occurrence = owner.component.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    )
    diagnostics_occurrence.component.name = "Selected solver diagnostics"
    gym_occurrence = owner.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    gym_occurrence.component.name = "Endpoint gym draft"
    scene = scene or generate()
    manifest = freeze(scene, directory / "initial")
    controller = Controller(
        python,
        directory / "jobs",
        document_id,
        native.build,
        native_point_tolerance_mm=app.pointTolerance * 10,
    )
    diagnostics = DiagnosticViewer(
        diagnostics_occurrence.component, app.activeDocument, manifest, runner=controller
    )
    diagnostics.show()
    workspace = SelectedWorkspace(
        native, diagnostics, diagnostics_occurrence, gym_occurrence, directory / "workspace", scene
    )
    for owner in previous:
        Workspace.deactivate(owner)
        owner.native.hide()
    _owners.append(workspace)
    workspace.open_gym()
    return workspace
