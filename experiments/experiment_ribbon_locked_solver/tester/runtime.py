"""
Bind range testing to the selected workspace's owned preview, controller and native output.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

# noinspection PyUnresolvedReferences
import adsk.core

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.budget import NativeBudget
from devtools.ribbon_analysis.gym.boundary import BoundaryReport, assess
from devtools.ribbon_analysis.gym.handoff import freeze
from devtools.ribbon_analysis.gym.scene import Scene

from .. import lock
from ..controller import Controller
from ..native import NativeOwner
from .awake import KeepAwake
from .engine import Tester
from .ranges import FIELDS
from .screenshots import frame
from .sequence import Specification, defaults

if TYPE_CHECKING:
    from ..gym import SelectedWorkspace


class Runtime:
    """
    Use the ordinary runner without accumulating successful replay sessions or native bodies.
    """

    def __init__(self, workspace: SelectedWorkspace) -> None:
        """
        Attach only to an explicitly owned selected-solver workspace with an idle controller.
        """
        self.workspace = workspace
        runner = workspace.diagnostics.runner
        if not isinstance(runner, Controller):
            raise ValueError("Range testing needs the selected solver controller.")
        self.runner = runner
        self.document_id = workspace.native.document_id
        self.native: NativeOwner | None = None
        self.awake = KeepAwake()
        self.engine = Tester(
            workspace.directory / "range-tests",
            runner,
            lock.verify,
            self._guard,
            self._prepare,
            self._cleanup,
            self._present,
            self._setup,
            self._capture,
            self._measure_boundary,
        )

    @property
    def active(self) -> bool:
        """
        Keep manual controls locked until the current operation has been safely collected.
        """
        return self.engine.active

    def _guard(self) -> None:
        """
        Refuse changed documents, user commands, preview edits or insufficient launch headroom.
        """
        app = adsk.core.Application.get()
        if (
            app.activeDocument is None
            or app.activeDocument.creationId != self.document_id
            or app.userInterface.activeCommand != "SelectCommand"
        ):
            raise RuntimeError("Range tester requires its owned idle Fusion design.")
        if (
            self.active
            and self.engine.phase == "running"
            and self.engine.scene != self.workspace.gym.scene
        ):
            raise RuntimeError("Gym inputs changed during the active test case.")
        budget = NativeBudget(maximum_seconds=10, maximum_rss_kib=4194304)
        budget.check("range tester boundary")
        if budget.memory() >= 3984588:
            raise RuntimeError("Range tester reached its 3.8GiB launch-headroom limit.")

    def _setup(self) -> None:
        """
        Preserve prior user output and give automatic cleanup a fresh, exclusively owned body handle.
        """
        workspace = self.workspace
        workspace.gym.archive_interrupted_profiles()
        previous = workspace.native
        previous.hide()
        native = NativeOwner(
            self.document_id, previous.display_x_cm, flat_surfaces=previous.flat_surfaces
        )
        self.native = native
        native.on_progress = workspace.diagnostics.report_progress
        workspace.native = native
        self.runner.build = native.build
        workspace.diagnostics.enable_geometry_clear(native.clear, native.has_geometry)

    def _cleanup(self) -> None:
        """
        Delete only the previous successful body produced by this tester instance.
        """
        if self.native is not None:
            self.native.clear()

    def _prepare(self, scene: Scene) -> None:
        """
        Show one current endpoint preview while keeping the diagnostics controls available.
        """
        workspace = self.workspace
        workspace.ensure_views()
        workspace.gym.set_scene(scene)
        workspace.gym_occurrence.isLightBulbOn = True
        workspace.diagnostic_occurrence.isLightBulbOn = False
        workspace.gym.palette.isVisible = False

    def _present(self, scene: Scene, result: Path | None) -> None:
        """
        Select the stopped case and its latest recorded route without resetting its build log.
        """
        self._guard()
        workspace = self.workspace
        workspace.ensure_views()
        workspace.gym.set_scene(scene)
        assert self.engine.journal is not None
        layout = freeze(scene, self.engine.journal.directory / "inspection")
        workspace.diagnostics.open_results(
            layout, f"Range test · case {self.engine.attempted} · seed {scene.config.seed}", result
        )
        workspace.gym_occurrence.isLightBulbOn = False
        workspace.diagnostic_occurrence.isLightBulbOn = not (
            result is not None
            and workspace.native.rejected_job == result.parent.resolve()
            and workspace.native.has_geometry()
        )
        workspace.diagnostics.palette.isVisible = True
        adsk.core.Application.get().activeViewport.fit()

    def _capture(self, path: Path) -> None:
        """
        Frame only current gym/ribbon bounds and export a PNG without palette chrome or old layouts.
        """
        self._guard()
        workspace = self.workspace
        points: list[Vector3] = []
        if workspace.native.has_geometry():
            box = workspace.native.displayed.component.bRepBodies.item(0).boundingBox
            points.extend(
                Vector3(p.x * 10, p.y * 10, p.z * 10) for p in (box.minPoint, box.maxPoint)
            )
        elif workspace.diagnostic_occurrence.isLightBulbOn:
            snapshot = workspace.diagnostics.session.snapshot
            if snapshot is not None:
                points.extend(p for guide in snapshot.guides for p in guide.controls)
                points.extend(p for section in snapshot.sections for p in section.outline)
        center, span_mm = frame(workspace.gym.scene.config.extent_mm, points)
        shift = workspace.native.display_x_cm
        span = span_mm / 10
        viewport = adsk.core.Application.get().activeViewport
        camera = viewport.camera
        camera.target = adsk.core.Point3D.create(
            center.x / 10 + shift, center.y / 10, center.z / 10
        )
        target = camera.target
        camera.eye = adsk.core.Point3D.create(target.x + span, target.y - span, target.z + span)
        camera.upVector = adsk.core.Vector3D.create(0, 0, 1)
        camera.isFitView = False
        camera.isSmoothTransition = False
        camera.viewExtents = span * 1.5
        viewport.camera = camera
        viewport.refresh()
        if not viewport.saveAsImageFile(str(path), 1600, 1000):
            raise RuntimeError(f"Fusion could not save the requested screenshot: {path}")

    def _measure_boundary(self, scene: Scene) -> BoundaryReport:
        """
        Measure complete built material in local coordinates after fidelity, retaining failures for inspection.

        The occurrence's display translation is excluded by using its native
        component body. No sampled guide, approximate drawing or new graphics.
        """
        self._guard()
        native = self.workspace.native
        if not native.has_geometry() or native.displayed.component.bRepBodies.count != 1:
            raise RuntimeError("Gym boundary requires the current complete native body")
        box = native.displayed.component.bRepBodies.item(0).preciseBoundingBox
        if box is None:
            raise RuntimeError("Fusion did not return precise native body bounds")
        low, high = box.minPoint, box.maxPoint
        return assess(
            scene.config,
            Vector3(low.x * 10, low.y * 10, low.z * 10),
            Vector3(high.x * 10, high.y * 10, high.z * 10),
        )

    def dispatch(self, action: str, data: dict[str, Any]) -> None:
        """
        Accept only explicit start/poll/stop/inspect actions from the diagnostic panel.
        """
        try:
            self._dispatch(action, data)
        finally:
            if not self.engine.active:
                self.awake.release()

    def _dispatch(self, action: str, data: dict[str, Any]) -> None:
        """
        Bind optional wake protection to explicit scheduling and verify it before each poll.
        """
        if action == "start":
            if set(data) != {"specification", "selection"}:
                raise ValueError("Supply tester specification and one solver selection.")
            spec = Specification.parse(data["specification"])
            self.engine.start(data["specification"], data["selection"])
            if spec.keep_awake:
                try:
                    self.awake.acquire()
                except (OSError, RuntimeError) as error:
                    self.engine.stop(f"Keep-awake could not start: {error}")
                    raise
        elif data:
            raise ValueError("Tester poll, stop and inspect actions do not accept input edits.")
        elif action == "poll":
            if (
                self.engine.active
                and self.engine.phase != "stopping"
                and self.engine.specification is not None
                and self.engine.specification.keep_awake
            ):
                try:
                    self.awake.check()
                except RuntimeError as error:
                    self.engine.stop(f"Keep-awake stopped unexpectedly: {error}")
            self.engine.poll()
        elif action == "stop":
            try:
                self.engine.stop()
            finally:
                self.awake.release()
        elif action == "inspect":
            self.engine.inspect()
        else:
            raise ValueError("Unknown range tester action.")

    def state(self) -> dict[str, Any]:
        """
        Expose available ranges and current progress without regenerating a drawing.
        """
        if not self.engine.active:
            self.awake.release()
        return {
            **self.engine.state(),
            "available": True,
            "keep_awake": self.awake.state(),
            "defaults": defaults(self.workspace.gym.scene),
            "fields": [asdict(field) for field in FIELDS],
        }
