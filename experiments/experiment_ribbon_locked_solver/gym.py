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
from devtools.ribbon_analysis.inspection.run_contract import TesterControls
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_test_gym.workspace import Workspace

from .controller import Controller
from .lock import verify
from .native import NativeOwner
from .tester.runtime import Runtime as RangeTester
from .views import restore as restore_views

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
        *,
        container: Any = None,
    ) -> None:
        """
        Retain the native owner before the base workspace binds its navigation callback.
        """
        self.native = native
        self.container: Any = container
        super().__init__(diagnostics, diagnostic_occurrence, gym_occurrence, directory, scene)
        diagnostics.enable_geometry_clear(native.clear, native.has_geometry)
        native.on_progress = diagnostics.report_progress
        self.range_tester = RangeTester(self)
        diagnostics.tester = self.range_tester
        diagnostics.ensure_owned_views = self.ensure_views

    def ensure_views(self) -> None:
        """
        Recreate deleted display containers without resetting model inputs, logs or active work.
        """
        restore_views(self)

    def open_gym(self) -> None:
        """
        Hide this workspace's last native output while editing its next endpoint draft.
        """
        self.native.hide()
        self.ensure_views()
        super().open_gym()

    def open_diagnostics(self, scene: Scene) -> None:
        """
        Recover a deleted diagnostic container before handing off the current draft.
        """
        self.ensure_views()
        super().open_diagnostics(scene)


def install(
    directory: Path,
    python: Path,
    document_id: str,
    scene: Scene | None = None,
    *,
    contact_policy: ContactPolicy = ContactPolicy.STRICT,
) -> SelectedWorkspace:
    """
    Create one retained gym/diagnostic workspace without solving or changing unrelated designs.

    Manual Solve and build or an explicitly started range tester launches work. Inputs and
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
    for owner in previous:
        tester: TesterControls | None = getattr(owner.diagnostics, "tester", None)
        if (
            owner.diagnostics.runner is not None
            and owner.diagnostics.runner.state()["status"] in ("running", "cancelling")
        ) or (tester is not None and tester.active):
            raise ValueError(
                "Stop and collect the prior gym job/tester before replacing its workspace"
            )
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
        contact_policy=contact_policy,
    )
    diagnostics = DiagnosticViewer(
        diagnostics_occurrence.component, app.activeDocument, manifest, runner=controller
    )
    diagnostics.show()
    workspace = SelectedWorkspace(
        native,
        diagnostics,
        diagnostics_occurrence,
        gym_occurrence,
        directory / "workspace",
        scene,
        container=owner,
    )
    for owner in previous:
        Workspace.deactivate(owner)
        owner.native.hide()
    _owners.append(workspace)
    workspace.open_gym()
    return workspace
